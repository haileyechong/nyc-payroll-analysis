"""
Index impact benchmark: MongoDB vs MySQL — NYC Payroll
Three phases:
  Phase 1 — No indexes  (MySQL: PK only, MongoDB: _id only)
  Phase 2 — MySQL only  (MySQL: all 7 non-PK indexes restored)
  Phase 3 — Both        (MongoDB also gets field indexes)
"""

import time
import statistics
import mysql.connector
from pymongo import MongoClient

MYSQL_CFG = dict(
    host="localhost", user="root", password="Tiffany-0826",
    database="nyc_payroll", unix_socket="/tmp/mysql.sock",
)
RUNS = 5
WARMUP = 2

# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

mongo_queries = {
    "Q1: Underpaid OT (compute+filter)": [
        {"$match": {"compensation.overtime_hours": {"$gt": 0}, "compensation.base_salary": {"$gt": 0}}},
        {"$addFields": {"hourly_rate": {"$divide": ["$compensation.base_salary", 2080]}}},
        {"$addFields": {
            "expected_ot_rate": {"$multiply": ["$hourly_rate", 1.5]},
            "actual_ot_rate": {"$divide": ["$compensation.total_overtime_paid", "$compensation.overtime_hours"]}
        }},
        {"$match": {"$expr": {"$lt": ["$actual_ot_rate", "$expected_ot_rate"]}}},
        {"$count": "count"},
    ],
    "Q2: Top OT earners (sort+limit)": [
        {"$match": {"compensation.total_overtime_paid": {"$gt": 0}}},
        {"$sort": {"compensation.total_overtime_paid": -1}},
        {"$limit": 25},
        {"$project": {"_id": 0, "employee_id": 1, "total_overtime_paid": "$compensation.total_overtime_paid"}},
    ],
    "Q3: Agency OT per employee (group+distinct)": [
        {"$group": {
            "_id": "$agency_snapshot.agency_name",
            "total_ot_hours": {"$sum": "$compensation.overtime_hours"},
            "headcount": {"$addToSet": "$employee_id"},
        }},
        {"$addFields": {"headcount": {"$size": "$headcount"},
                         "ot_per_emp": {"$divide": ["$total_ot_hours", {"$size": "$headcount"}]}}},
        {"$sort": {"ot_per_emp": -1}},
        {"$project": {"_id": 0, "agency": "$_id", "total_ot_hours": 1, "headcount": 1, "ot_per_emp": 1}},
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
        {"$addFields": {"ot_ratio": {"$divide": ["$total_ot_paid", "$total_regular_gross"]}}},
        {"$sort": {"ot_ratio": -1}},
        {"$limit": 15},
        {"$project": {"_id": 0, "agency": "$_id", "total_ot_paid": 1, "total_regular_gross": 1, "ot_ratio": 1}},
    ],
    "Q8: Title avg compensation (group+filter)": [
        {"$match": {"compensation.total_compensation": {"$gt": 0}}},
        {"$group": {
            "_id": "$title_snapshot.title_description",
            "avg_total_compensation": {"$avg": "$compensation.total_compensation"},
            "headcount": {"$sum": 1},
        }},
        {"$match": {"headcount": {"$gte": 10}}},
        {"$sort": {"avg_total_compensation": -1}},
        {"$limit": 15},
        {"$project": {"_id": 0, "title": "$_id", "avg_total_compensation": 1, "headcount": 1}},
    ],
    "Q9: Agency total compensation (group+distinct)": [
        {"$group": {
            "_id": "$agency_snapshot.agency_name",
            "total_compensation": {"$sum": "$compensation.total_compensation"},
            "headcount": {"$addToSet": "$employee_id"},
        }},
        {"$addFields": {"headcount": {"$size": "$headcount"},
                         "avg_comp": {"$divide": ["$total_compensation", {"$size": "$headcount"}]}}},
        {"$sort": {"total_compensation": -1}},
        {"$project": {"_id": 0, "agency": "$_id", "total_compensation": 1, "headcount": 1, "avg_comp": 1}},
    ],
}

mysql_queries = {
    "Q1: Underpaid OT (compute+filter)": """
        SELECT COUNT(*) FROM payroll_records pr
        WHERE pr.overtime_hours > 0 AND pr.base_salary > 0
          AND (pr.total_overtime_paid / pr.overtime_hours) < ((pr.base_salary / 2080) * 1.5)
    """,
    "Q2: Top OT earners (sort+limit)": """
        SELECT pr.employee_id, a.agency_name, pr.total_overtime_paid
        FROM payroll_records pr JOIN agencies a ON pr.agency_id = a.agency_id
        WHERE pr.total_overtime_paid > 0
        ORDER BY pr.total_overtime_paid DESC LIMIT 25
    """,
    "Q3: Agency OT per employee (group+distinct)": """
        SELECT a.agency_name,
               SUM(pr.overtime_hours) AS total_ot_hours,
               COUNT(DISTINCT pr.employee_id) AS headcount,
               SUM(pr.overtime_hours) / COUNT(DISTINCT pr.employee_id) AS ot_per_emp
        FROM payroll_records pr JOIN agencies a ON pr.agency_id = a.agency_id
        GROUP BY a.agency_name ORDER BY ot_per_emp DESC
    """,
    "Q5: Agency total OT spend (group+sum)": """
        SELECT a.agency_name, SUM(pr.total_overtime_paid) AS total_ot_paid,
               COUNT(DISTINCT pr.employee_id) AS headcount
        FROM payroll_records pr JOIN agencies a ON pr.agency_id = a.agency_id
        GROUP BY a.agency_name ORDER BY total_ot_paid DESC LIMIT 15
    """,
    "Q6: Agency OT reliance (ratio of sums)": """
        SELECT a.agency_name,
               SUM(pr.total_overtime_paid) AS total_ot_paid,
               SUM(pr.regular_gross_paid) AS total_regular_gross,
               SUM(pr.total_overtime_paid) / NULLIF(SUM(pr.regular_gross_paid), 0) AS ot_ratio
        FROM payroll_records pr JOIN agencies a ON pr.agency_id = a.agency_id
        GROUP BY a.agency_name HAVING SUM(pr.regular_gross_paid) > 0
        ORDER BY ot_ratio DESC LIMIT 15
    """,
    "Q8: Title avg compensation (group+filter)": """
        SELECT jt.title_description, AVG(pr.total_compensation) AS avg_total_compensation,
               COUNT(*) AS headcount
        FROM payroll_records pr JOIN job_titles jt ON pr.title_id = jt.title_id
        WHERE pr.total_compensation > 0
        GROUP BY jt.title_description HAVING COUNT(*) >= 10
        ORDER BY avg_total_compensation DESC LIMIT 15
    """,
    "Q9: Agency total compensation (group+distinct)": """
        SELECT a.agency_name, SUM(pr.total_compensation) AS total_compensation,
               COUNT(DISTINCT pr.employee_id) AS headcount,
               SUM(pr.total_compensation) / COUNT(DISTINCT pr.employee_id) AS avg_comp
        FROM payroll_records pr JOIN agencies a ON pr.agency_id = a.agency_id
        GROUP BY a.agency_name ORDER BY total_compensation DESC
    """,
}

# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------

MYSQL_DROP_FKS = """
    ALTER TABLE payroll_records
        DROP FOREIGN KEY payroll_records_ibfk_1,
        DROP FOREIGN KEY payroll_records_ibfk_2,
        DROP FOREIGN KEY payroll_records_ibfk_3,
        DROP FOREIGN KEY payroll_records_ibfk_4,
        DROP FOREIGN KEY payroll_records_ibfk_5;
"""

MYSQL_DROP_INDEXES = """
    ALTER TABLE payroll_records
        DROP INDEX idx_payroll_employee,
        DROP INDEX idx_payroll_agency,
        DROP INDEX idx_payroll_title,
        DROP INDEX idx_payroll_fiscal_year,
        DROP INDEX idx_payroll_location,
        DROP INDEX idx_payroll_overtime_paid,
        DROP INDEX idx_payroll_total_compensation;
"""

MYSQL_ADD_INDEXES = """
    ALTER TABLE payroll_records
        ADD INDEX idx_payroll_employee (employee_id),
        ADD INDEX idx_payroll_agency (agency_id),
        ADD INDEX idx_payroll_title (title_id),
        ADD INDEX idx_payroll_fiscal_year (fiscal_year_id),
        ADD INDEX idx_payroll_location (location_id),
        ADD INDEX idx_payroll_overtime_paid (total_overtime_paid),
        ADD INDEX idx_payroll_total_compensation (total_compensation);
"""

MYSQL_ADD_FKS = """
    ALTER TABLE payroll_records
        ADD FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
        ADD FOREIGN KEY (agency_id)   REFERENCES agencies(agency_id),
        ADD FOREIGN KEY (title_id)    REFERENCES job_titles(title_id),
        ADD FOREIGN KEY (location_id) REFERENCES work_locations(location_id),
        ADD FOREIGN KEY (fiscal_year_id) REFERENCES fiscal_years(fiscal_year_id);
"""

MONGO_INDEXES = [
    [("compensation.total_overtime_paid", -1)],
    [("compensation.total_compensation", 1)],
    [("compensation.overtime_hours", 1)],
    [("compensation.base_salary", 1)],
    [("agency_snapshot.agency_name", 1)],
    [("title_snapshot.title_description", 1)],
    [("fiscal_year", 1)],
]

def drop_mongo_indexes(col):
    for idx in list(col.list_indexes()):
        if idx["name"] != "_id_":
            col.drop_index(idx["name"])

def add_mongo_indexes(col):
    for spec in MONGO_INDEXES:
        col.create_index(spec)

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

def time_mongo(col, pipeline):
    for _ in range(WARMUP):
        list(col.aggregate(pipeline))
    times = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        list(col.aggregate(pipeline))
        times.append((time.perf_counter() - t0) * 1000)
    return statistics.median(times)

def time_mysql(cur, sql):
    for _ in range(WARMUP):
        cur.execute(sql); cur.fetchall()
    times = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        cur.execute(sql); cur.fetchall()
        times.append((time.perf_counter() - t0) * 1000)
    return statistics.median(times)

def run_phase(label, col, cur, mysql_conn):
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    print(f"  {'Query':<42} {'MongoDB':>10} {'MySQL':>10} {'Winner':>14}")
    print(f"  {'-'*78}")
    totals = {"MongoDB": 0.0, "MySQL": 0.0}
    rows = []
    for key in mongo_queries:
        m = time_mongo(col, mongo_queries[key])
        s = time_mysql(cur, mysql_queries[key])
        winner = "MongoDB" if m < s else "MySQL"
        ratio = max(m, s) / min(m, s)
        totals["MongoDB"] += m
        totals["MySQL"] += s
        rows.append((key, m, s, winner, ratio))
        print(f"  {key:<42} {m:>8.1f}ms {s:>8.1f}ms  {winner} ({ratio:.1f}x)")
    print(f"  {'-'*78}")
    ow = "MongoDB" if totals["MongoDB"] < totals["MySQL"] else "MySQL"
    or_ = max(totals.values()) / min(totals.values())
    print(f"  {'TOTAL':<42} {totals['MongoDB']:>8.1f}ms {totals['MySQL']:>8.1f}ms  {ow} ({or_:.1f}x)")
    return rows, totals

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    mongo_col = MongoClient("localhost", 27017)["NYC_Payroll"]["payroll_records"]
    mysql_conn = mysql.connector.connect(**MYSQL_CFG)
    cur = mysql_conn.cursor()

    print("NYC Payroll — Index Impact Benchmark")
    print(f"1,113,103 records | {WARMUP} warm-up + {RUNS} timed runs per query")

    # ── Phase 1: No indexes ──────────────────────────────────────────────────
    print("\n[Phase 1] Dropping FK constraints, all non-PK MySQL indexes, and all MongoDB indexes...")
    cur.execute(MYSQL_DROP_FKS); mysql_conn.commit()
    cur.execute(MYSQL_DROP_INDEXES); mysql_conn.commit()
    drop_mongo_indexes(mongo_col)
    p1_rows, p1_totals = run_phase("PHASE 1 — No indexes (MySQL: PK only | MongoDB: _id only)",
                                    mongo_col, cur, mysql_conn)

    # ── Phase 2: MySQL indexes only ─────────────────────────────────────────
    print("\n[Phase 2] Restoring MySQL indexes (MongoDB still unindexed)...")
    cur.execute(MYSQL_ADD_INDEXES); mysql_conn.commit()
    cur.execute(MYSQL_ADD_FKS); mysql_conn.commit()
    p2_rows, p2_totals = run_phase("PHASE 2 — MySQL indexed only (MongoDB: _id only)",
                                    mongo_col, cur, mysql_conn)

    # ── Phase 3: Both indexed ────────────────────────────────────────────────
    print("\n[Phase 3] Adding MongoDB field indexes...")
    add_mongo_indexes(mongo_col)
    p3_rows, p3_totals = run_phase("PHASE 3 — Both databases fully indexed",
                                    mongo_col, cur, mysql_conn)

    # ── Summary table ────────────────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print("  INDEX IMPACT SUMMARY — median ms per query")
    print(f"{'='*70}")
    header = f"  {'Query':<42} {'P1 Mongo':>9} {'P1 MySQL':>9} {'P2 Mongo':>9} {'P2 MySQL':>9} {'P3 Mongo':>9} {'P3 MySQL':>9}"
    print(header)
    print(f"  {'-'*96}")
    for i, key in enumerate(mongo_queries):
        r1, r2, r3 = p1_rows[i], p2_rows[i], p3_rows[i]
        print(f"  {key:<42} {r1[1]:>7.1f}ms {r1[2]:>7.1f}ms {r2[1]:>7.1f}ms {r2[2]:>7.1f}ms {r3[1]:>7.1f}ms {r3[2]:>7.1f}ms")
    print(f"  {'-'*96}")
    print(f"  {'TOTAL':<42} {p1_totals['MongoDB']:>7.1f}ms {p1_totals['MySQL']:>7.1f}ms "
          f"{p2_totals['MongoDB']:>7.1f}ms {p2_totals['MySQL']:>7.1f}ms "
          f"{p3_totals['MongoDB']:>7.1f}ms {p3_totals['MySQL']:>7.1f}ms")

    print("\n  Speedup from indexing:")
    print(f"    MySQL  (P1→P2): {p1_totals['MySQL']/p2_totals['MySQL']:.1f}x faster")
    print(f"    MongoDB(P1→P3): {p1_totals['MongoDB']/p3_totals['MongoDB']:.1f}x faster")

    cur.close(); mysql_conn.close()

if __name__ == "__main__":
    main()
