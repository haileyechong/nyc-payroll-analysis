"""
Compare MongoDB vs MySQL query performance on the NYC Payroll dataset.

Runs two benchmarks:
  1. Head-to-head: 9 equivalent queries timed on both databases
  2. Index impact: same queries across 3 phases
       Phase 1 — no indexes (MySQL: PK only, MongoDB: _id only)
       Phase 2 — MySQL indexes only
       Phase 3 — both databases fully indexed

Usage:
    python scripts/compare_db_performance.py

Requirements:
    - MongoDB running on localhost:27017 with database 'NYC_Payroll'
    - MySQL running on /tmp/mysql.sock with database 'nyc_payroll'
    - pip install pymongo mysql-connector-python
"""

import time
import statistics
import mysql.connector
from pymongo import MongoClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MONGO_HOST = "localhost"
MONGO_PORT = 27017
MONGO_DB = "NYC_Payroll"
MONGO_COLLECTION = "payroll_records"

MYSQL_CFG = dict(
    host="localhost",
    user="root",
    password="Tiffany-0826",
    database="nyc_payroll",
    unix_socket="/tmp/mysql.sock",
)

WARMUP_RUNS = 2
TIMED_RUNS = 5

# ---------------------------------------------------------------------------
# Queries — MongoDB aggregation pipelines
# ---------------------------------------------------------------------------

MONGO_QUERIES = {
    "Q1: Underpaid OT (compute+filter)": [
        {"$match": {
            "compensation.overtime_hours": {"$gt": 0},
            "compensation.base_salary": {"$gt": 0},
        }},
        {"$addFields": {
            "hourly_rate": {"$divide": ["$compensation.base_salary", 2080]},
        }},
        {"$addFields": {
            "expected_ot_rate": {"$multiply": ["$hourly_rate", 1.5]},
            "actual_ot_rate": {"$divide": [
                "$compensation.total_overtime_paid",
                "$compensation.overtime_hours",
            ]},
        }},
        {"$match": {"$expr": {"$lt": ["$actual_ot_rate", "$expected_ot_rate"]}}},
        {"$count": "count"},
    ],

    "Q2: Top OT earners (sort+limit)": [
        {"$match": {"compensation.total_overtime_paid": {"$gt": 0}}},
        {"$sort": {"compensation.total_overtime_paid": -1}},
        {"$limit": 25},
        {"$project": {
            "_id": 0,
            "employee_id": 1,
            "agency": "$agency_snapshot.agency_name",
            "total_overtime_paid": "$compensation.total_overtime_paid",
        }},
    ],

    "Q3: Agency OT per employee (group+distinct)": [
        {"$group": {
            "_id": "$agency_snapshot.agency_name",
            "total_ot_hours": {"$sum": "$compensation.overtime_hours"},
            "headcount": {"$addToSet": "$employee_id"},
        }},
        {"$addFields": {
            "headcount": {"$size": "$headcount"},
            "ot_per_employee": {"$divide": [
                "$total_ot_hours", {"$size": "$headcount"},
            ]},
        }},
        {"$sort": {"ot_per_employee": -1}},
        {"$project": {
            "_id": 0,
            "agency": "$_id",
            "total_ot_hours": 1,
            "headcount": 1,
            "ot_per_employee": 1,
        }},
    ],

    "Q4: Title avg OT pay (group+avg)": [
        {"$match": {"compensation.total_overtime_paid": {"$gt": 0}}},
        {"$group": {
            "_id": "$title_snapshot.title_description",
            "avg_ot_pay": {"$avg": "$compensation.total_overtime_paid"},
            "headcount": {"$sum": 1},
        }},
        {"$sort": {"avg_ot_pay": -1}},
        {"$limit": 15},
        {"$project": {"_id": 0, "title": "$_id", "avg_ot_pay": 1, "headcount": 1}},
    ],

    "Q5: Agency total OT spend (group+sum)": [
        {"$group": {
            "_id": "$agency_snapshot.agency_name",
            "total_ot_paid": {"$sum": "$compensation.total_overtime_paid"},
            "headcount": {"$addToSet": "$employee_id"},
        }},
        {"$addFields": {"headcount": {"$size": "$headcount"}}},
        {"$sort": {"total_ot_paid": -1}},
        {"$limit": 15},
        {"$project": {"_id": 0, "agency": "$_id", "total_ot_paid": 1, "headcount": 1}},
    ],

    "Q6: Agency OT reliance (ratio of sums)": [
        {"$group": {
            "_id": "$agency_snapshot.agency_name",
            "total_ot_paid": {"$sum": "$compensation.total_overtime_paid"},
            "total_regular_gross": {"$sum": "$compensation.regular_gross_paid"},
        }},
        {"$match": {"total_regular_gross": {"$gt": 0}}},
        {"$addFields": {
            "ot_ratio": {"$divide": ["$total_ot_paid", "$total_regular_gross"]},
        }},
        {"$sort": {"ot_ratio": -1}},
        {"$limit": 15},
        {"$project": {
            "_id": 0,
            "agency": "$_id",
            "total_ot_paid": 1,
            "total_regular_gross": 1,
            "ot_ratio": 1,
        }},
    ],

    "Q7: Spending by fiscal year (group+sum)": [
        {"$group": {
            "_id": "$fiscal_year",
            "total_regular_gross": {"$sum": "$compensation.regular_gross_paid"},
            "total_ot_paid": {"$sum": "$compensation.total_overtime_paid"},
            "total_compensation": {"$sum": "$compensation.total_compensation"},
            "headcount": {"$addToSet": "$employee_id"},
        }},
        {"$addFields": {"headcount": {"$size": "$headcount"}}},
        {"$sort": {"_id": 1}},
        {"$project": {
            "_id": 0,
            "fiscal_year": "$_id",
            "total_regular_gross": 1,
            "total_ot_paid": 1,
            "total_compensation": 1,
            "headcount": 1,
        }},
    ],

    "Q8: Title avg total compensation (group+filter)": [
        {"$match": {"compensation.total_compensation": {"$gt": 0}}},
        {"$group": {
            "_id": "$title_snapshot.title_description",
            "avg_total_compensation": {"$avg": "$compensation.total_compensation"},
            "avg_base_salary": {"$avg": "$compensation.base_salary"},
            "headcount": {"$sum": 1},
        }},
        {"$match": {"headcount": {"$gte": 10}}},
        {"$sort": {"avg_total_compensation": -1}},
        {"$limit": 15},
        {"$project": {
            "_id": 0,
            "title": "$_id",
            "avg_total_compensation": 1,
            "avg_base_salary": 1,
            "headcount": 1,
        }},
    ],

    "Q9: Agency total compensation (group+distinct)": [
        {"$group": {
            "_id": "$agency_snapshot.agency_name",
            "total_compensation": {"$sum": "$compensation.total_compensation"},
            "total_ot_paid": {"$sum": "$compensation.total_overtime_paid"},
            "headcount": {"$addToSet": "$employee_id"},
        }},
        {"$addFields": {
            "headcount": {"$size": "$headcount"},
            "avg_comp_per_employee": {"$divide": [
                "$total_compensation", {"$size": "$headcount"},
            ]},
        }},
        {"$sort": {"total_compensation": -1}},
        {"$project": {
            "_id": 0,
            "agency": "$_id",
            "total_compensation": 1,
            "total_ot_paid": 1,
            "headcount": 1,
            "avg_comp_per_employee": 1,
        }},
    ],
}

# ---------------------------------------------------------------------------
# Queries — MySQL equivalents
# ---------------------------------------------------------------------------

MYSQL_QUERIES = {
    "Q1: Underpaid OT (compute+filter)": """
        SELECT COUNT(*) AS count
        FROM payroll_records pr
        WHERE pr.overtime_hours > 0
          AND pr.base_salary > 0
          AND (pr.total_overtime_paid / pr.overtime_hours)
              < ((pr.base_salary / 2080) * 1.5)
    """,

    "Q2: Top OT earners (sort+limit)": """
        SELECT pr.employee_id, a.agency_name, pr.total_overtime_paid
        FROM payroll_records pr
        JOIN agencies a ON pr.agency_id = a.agency_id
        WHERE pr.total_overtime_paid > 0
        ORDER BY pr.total_overtime_paid DESC
        LIMIT 25
    """,

    "Q3: Agency OT per employee (group+distinct)": """
        SELECT a.agency_name,
               SUM(pr.overtime_hours) AS total_ot_hours,
               COUNT(DISTINCT pr.employee_id) AS headcount,
               SUM(pr.overtime_hours) / COUNT(DISTINCT pr.employee_id) AS ot_per_employee
        FROM payroll_records pr
        JOIN agencies a ON pr.agency_id = a.agency_id
        GROUP BY a.agency_name
        ORDER BY ot_per_employee DESC
    """,

    "Q4: Title avg OT pay (group+avg)": """
        SELECT jt.title_description,
               AVG(pr.total_overtime_paid) AS avg_ot_pay,
               COUNT(*) AS headcount
        FROM payroll_records pr
        JOIN job_titles jt ON pr.title_id = jt.title_id
        WHERE pr.total_overtime_paid > 0
        GROUP BY jt.title_description
        ORDER BY avg_ot_pay DESC
        LIMIT 15
    """,

    "Q5: Agency total OT spend (group+sum)": """
        SELECT a.agency_name,
               SUM(pr.total_overtime_paid) AS total_ot_paid,
               COUNT(DISTINCT pr.employee_id) AS headcount
        FROM payroll_records pr
        JOIN agencies a ON pr.agency_id = a.agency_id
        GROUP BY a.agency_name
        ORDER BY total_ot_paid DESC
        LIMIT 15
    """,

    "Q6: Agency OT reliance (ratio of sums)": """
        SELECT a.agency_name,
               SUM(pr.total_overtime_paid) AS total_ot_paid,
               SUM(pr.regular_gross_paid) AS total_regular_gross,
               SUM(pr.total_overtime_paid) / NULLIF(SUM(pr.regular_gross_paid), 0) AS ot_ratio
        FROM payroll_records pr
        JOIN agencies a ON pr.agency_id = a.agency_id
        GROUP BY a.agency_name
        HAVING SUM(pr.regular_gross_paid) > 0
        ORDER BY ot_ratio DESC
        LIMIT 15
    """,

    "Q7: Spending by fiscal year (group+sum)": """
        SELECT fy.fiscal_year,
               SUM(pr.regular_gross_paid) AS total_regular_gross,
               SUM(pr.total_overtime_paid) AS total_ot_paid,
               SUM(pr.total_compensation) AS total_compensation,
               COUNT(DISTINCT pr.employee_id) AS headcount
        FROM payroll_records pr
        JOIN fiscal_years fy ON pr.fiscal_year_id = fy.fiscal_year_id
        GROUP BY fy.fiscal_year
        ORDER BY fy.fiscal_year
    """,

    "Q8: Title avg total compensation (group+filter)": """
        SELECT jt.title_description,
               AVG(pr.total_compensation) AS avg_total_compensation,
               AVG(pr.base_salary) AS avg_base_salary,
               COUNT(*) AS headcount
        FROM payroll_records pr
        JOIN job_titles jt ON pr.title_id = jt.title_id
        WHERE pr.total_compensation > 0
        GROUP BY jt.title_description
        HAVING COUNT(*) >= 10
        ORDER BY avg_total_compensation DESC
        LIMIT 15
    """,

    "Q9: Agency total compensation (group+distinct)": """
        SELECT a.agency_name,
               SUM(pr.total_compensation) AS total_compensation,
               SUM(pr.total_overtime_paid) AS total_ot_paid,
               COUNT(DISTINCT pr.employee_id) AS headcount,
               SUM(pr.total_compensation) / COUNT(DISTINCT pr.employee_id) AS avg_comp_per_employee
        FROM payroll_records pr
        JOIN agencies a ON pr.agency_id = a.agency_id
        GROUP BY a.agency_name
        ORDER BY total_compensation DESC
    """,
}

# ---------------------------------------------------------------------------
# Index management DDL
# ---------------------------------------------------------------------------

_MYSQL_DROP_FKS = """
    ALTER TABLE payroll_records
        DROP FOREIGN KEY payroll_records_ibfk_1,
        DROP FOREIGN KEY payroll_records_ibfk_2,
        DROP FOREIGN KEY payroll_records_ibfk_3,
        DROP FOREIGN KEY payroll_records_ibfk_4,
        DROP FOREIGN KEY payroll_records_ibfk_5
"""

_MYSQL_DROP_INDEXES = """
    ALTER TABLE payroll_records
        DROP INDEX idx_payroll_employee,
        DROP INDEX idx_payroll_agency,
        DROP INDEX idx_payroll_title,
        DROP INDEX idx_payroll_fiscal_year,
        DROP INDEX idx_payroll_location,
        DROP INDEX idx_payroll_overtime_paid,
        DROP INDEX idx_payroll_total_compensation
"""

_MYSQL_ADD_INDEXES = """
    ALTER TABLE payroll_records
        ADD INDEX idx_payroll_employee          (employee_id),
        ADD INDEX idx_payroll_agency            (agency_id),
        ADD INDEX idx_payroll_title             (title_id),
        ADD INDEX idx_payroll_fiscal_year       (fiscal_year_id),
        ADD INDEX idx_payroll_location          (location_id),
        ADD INDEX idx_payroll_overtime_paid     (total_overtime_paid),
        ADD INDEX idx_payroll_total_compensation(total_compensation)
"""

_MYSQL_ADD_FKS = """
    ALTER TABLE payroll_records
        ADD FOREIGN KEY (employee_id)    REFERENCES employees(employee_id),
        ADD FOREIGN KEY (agency_id)      REFERENCES agencies(agency_id),
        ADD FOREIGN KEY (title_id)       REFERENCES job_titles(title_id),
        ADD FOREIGN KEY (location_id)    REFERENCES work_locations(location_id),
        ADD FOREIGN KEY (fiscal_year_id) REFERENCES fiscal_years(fiscal_year_id)
"""

_MONGO_INDEX_SPECS = [
    [("compensation.total_overtime_paid", -1)],
    [("compensation.total_compensation",   1)],
    [("compensation.overtime_hours",       1)],
    [("compensation.base_salary",          1)],
    [("agency_snapshot.agency_name",       1)],
    [("title_snapshot.title_description",  1)],
    [("fiscal_year",                       1)],
]


def _mysql_indexes_exist(cur):
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.STATISTICS
        WHERE table_schema = 'nyc_payroll'
          AND table_name   = 'payroll_records'
          AND index_name   = 'idx_payroll_overtime_paid'
    """)
    return cur.fetchone()[0] > 0


def _mysql_fks_exist(cur):
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
        WHERE table_schema   = 'nyc_payroll'
          AND table_name     = 'payroll_records'
          AND constraint_type = 'FOREIGN KEY'
    """)
    return cur.fetchone()[0] > 0


def drop_mysql_indexes(cur, conn):
    if _mysql_fks_exist(cur):
        cur.execute(_MYSQL_DROP_FKS); conn.commit()
    if _mysql_indexes_exist(cur):
        cur.execute(_MYSQL_DROP_INDEXES); conn.commit()


def add_mysql_indexes(cur, conn):
    if not _mysql_indexes_exist(cur):
        cur.execute(_MYSQL_ADD_INDEXES); conn.commit()
    if not _mysql_fks_exist(cur):
        cur.execute(_MYSQL_ADD_FKS); conn.commit()


def drop_mongo_indexes(col):
    for idx in list(col.list_indexes()):
        if idx["name"] != "_id_":
            col.drop_index(idx["name"])


def add_mongo_indexes(col):
    for spec in _MONGO_INDEX_SPECS:
        col.create_index(spec)

# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------

def _time_mongo(col, pipeline):
    for _ in range(WARMUP_RUNS):
        list(col.aggregate(pipeline))
    samples = []
    for _ in range(TIMED_RUNS):
        t0 = time.perf_counter()
        list(col.aggregate(pipeline))
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.median(samples)


def _time_mysql(cur, sql):
    for _ in range(WARMUP_RUNS):
        cur.execute(sql); cur.fetchall()
    samples = []
    for _ in range(TIMED_RUNS):
        t0 = time.perf_counter()
        cur.execute(sql); cur.fetchall()
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.median(samples)

# ---------------------------------------------------------------------------
# Benchmark 1: head-to-head
# ---------------------------------------------------------------------------

def run_head_to_head(col, cur):
    print("\n" + "=" * 72)
    print("  BENCHMARK 1 — Head-to-head (current index state)")
    print(f"  {WARMUP_RUNS} warm-up + {TIMED_RUNS} timed runs per query | median reported")
    print("=" * 72)
    print(f"  {'Query':<44} {'MongoDB':>10} {'MySQL':>10}  Winner")
    print(f"  {'-'*70}")

    mongo_total = mysql_total = 0.0
    rows = []

    for key in MONGO_QUERIES:
        m = _time_mongo(col, MONGO_QUERIES[key])
        s = _time_mysql(cur, MYSQL_QUERIES[key])
        winner = "MongoDB" if m < s else "MySQL"
        ratio  = max(m, s) / min(m, s)
        mongo_total += m
        mysql_total += s
        rows.append((key, m, s, winner, ratio))
        tag = f"{winner} ({ratio:.1f}x)"
        print(f"  {key:<44} {m:>8.1f}ms {s:>8.1f}ms  {tag}")

    print(f"  {'-'*70}")
    ow    = "MongoDB" if mongo_total < mysql_total else "MySQL"
    oratio = max(mongo_total, mysql_total) / min(mongo_total, mysql_total)
    print(f"  {'TOTAL (sum of medians)':<44} {mongo_total:>8.1f}ms {mysql_total:>8.1f}ms  {ow} ({oratio:.1f}x)")
    return rows

# ---------------------------------------------------------------------------
# Benchmark 2: index impact (3 phases)
# ---------------------------------------------------------------------------

def _run_phase(label, col, cur):
    print(f"\n{'─'*72}")
    print(f"  {label}")
    print(f"{'─'*72}")
    print(f"  {'Query':<44} {'MongoDB':>10} {'MySQL':>10}  Winner")
    print(f"  {'-'*70}")

    mongo_total = mysql_total = 0.0
    rows = []

    for key in MONGO_QUERIES:
        m = _time_mongo(col, MONGO_QUERIES[key])
        s = _time_mysql(cur, MYSQL_QUERIES[key])
        winner = "MongoDB" if m < s else "MySQL"
        ratio  = max(m, s) / min(m, s)
        mongo_total += m
        mysql_total += s
        rows.append((key, m, s, winner, ratio))
        tag = f"{winner} ({ratio:.1f}x)"
        print(f"  {key:<44} {m:>8.1f}ms {s:>8.1f}ms  {tag}")

    print(f"  {'-'*70}")
    ow    = "MongoDB" if mongo_total < mysql_total else "MySQL"
    oratio = max(mongo_total, mysql_total) / min(mongo_total, mysql_total)
    print(f"  {'TOTAL':<44} {mongo_total:>8.1f}ms {mysql_total:>8.1f}ms  {ow} ({oratio:.1f}x)")
    return rows, {"MongoDB": mongo_total, "MySQL": mysql_total}


def run_index_impact(col, cur, conn):
    print("\n" + "=" * 72)
    print("  BENCHMARK 2 — Index impact (3 phases)")
    print("  Phase 1: no indexes | Phase 2: MySQL only | Phase 3: both")
    print("=" * 72)

    print("\n  [Phase 1] Dropping all non-PK indexes on both databases...")
    drop_mysql_indexes(cur, conn)
    drop_mongo_indexes(col)
    p1_rows, p1_totals = _run_phase(
        "Phase 1 — No indexes (MySQL: PK only | MongoDB: _id only)", col, cur)

    print("\n  [Phase 2] Adding MySQL indexes (MongoDB still unindexed)...")
    add_mysql_indexes(cur, conn)
    p2_rows, p2_totals = _run_phase(
        "Phase 2 — MySQL indexed only", col, cur)

    print("\n  [Phase 3] Adding MongoDB field indexes...")
    add_mongo_indexes(col)
    p3_rows, p3_totals = _run_phase(
        "Phase 3 — Both databases fully indexed", col, cur)

    # Summary table
    print(f"\n\n{'='*72}")
    print("  INDEX IMPACT SUMMARY — median ms per query")
    print(f"{'='*72}")
    print(f"  {'Query':<44} {'P1 Mongo':>9} {'P1 MySQL':>9} {'P2 Mongo':>9} {'P2 MySQL':>9} {'P3 Mongo':>9} {'P3 MySQL':>9}")
    print(f"  {'-'*100}")

    for i, key in enumerate(MONGO_QUERIES):
        r1, r2, r3 = p1_rows[i], p2_rows[i], p3_rows[i]
        print(
            f"  {key:<44} "
            f"{r1[1]:>7.1f}ms {r1[2]:>7.1f}ms "
            f"{r2[1]:>7.1f}ms {r2[2]:>7.1f}ms "
            f"{r3[1]:>7.1f}ms {r3[2]:>7.1f}ms"
        )

    print(f"  {'-'*100}")
    print(
        f"  {'TOTAL':<44} "
        f"{p1_totals['MongoDB']:>7.1f}ms {p1_totals['MySQL']:>7.1f}ms "
        f"{p2_totals['MongoDB']:>7.1f}ms {p2_totals['MySQL']:>7.1f}ms "
        f"{p3_totals['MongoDB']:>7.1f}ms {p3_totals['MySQL']:>7.1f}ms"
    )

    mysql_speedup  = p1_totals["MySQL"]  / p2_totals["MySQL"]
    mongo_speedup  = p1_totals["MongoDB"] / p3_totals["MongoDB"]
    print(f"\n  Speedup from indexing:")
    print(f"    MySQL   (Phase 1 → 2): {mysql_speedup:.2f}x")
    print(f"    MongoDB (Phase 1 → 3): {mongo_speedup:.2f}x")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("Connecting to databases...")
    col  = MongoClient(MONGO_HOST, MONGO_PORT)[MONGO_DB][MONGO_COLLECTION]
    conn = mysql.connector.connect(**MYSQL_CFG)
    cur  = conn.cursor()

    record_count = col.estimated_document_count()
    print(f"MongoDB collection: {record_count:,} documents")

    cur.execute("SELECT COUNT(*) FROM payroll_records")
    print(f"MySQL table:        {cur.fetchone()[0]:,} rows")
    print(f"Runs per query:     {WARMUP_RUNS} warm-up + {TIMED_RUNS} timed")

    run_head_to_head(col, cur)
    run_index_impact(col, cur, conn)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
