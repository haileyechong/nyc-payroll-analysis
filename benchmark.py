"""
Benchmark: MongoDB vs MySQL — NYC Payroll Queries
Runs 9 equivalent analytical queries on both databases (3 warm-up, 5 timed runs each).
"""

import time
import statistics
import mysql.connector
from pymongo import MongoClient

MYSQL_CFG = dict(
    host="localhost",
    user="root",
    password="Tiffany-0826",
    database="nyc_payroll",
    unix_socket="/tmp/mysql.sock",
)

RUNS = 5
WARMUP = 2

# ---------------------------------------------------------------------------
# MongoDB pipelines
# ---------------------------------------------------------------------------

mongo_queries = {
    "Q1: Underpaid overtime": [
        {"$match": {"compensation.overtime_hours": {"$gt": 0}, "compensation.base_salary": {"$gt": 0}}},
        {"$addFields": {"hourly_rate": {"$divide": ["$compensation.base_salary", 2080]}}},
        {"$addFields": {
            "expected_ot_rate": {"$multiply": ["$hourly_rate", 1.5]},
            "actual_ot_rate": {"$divide": ["$compensation.total_overtime_paid", "$compensation.overtime_hours"]}
        }},
        {"$match": {"$expr": {"$lt": ["$actual_ot_rate", "$expected_ot_rate"]}}},
        {"$count": "count"},
    ],
    "Q2: Top OT earners": [
        {"$match": {"compensation.total_overtime_paid": {"$gt": 0}}},
        {"$sort": {"compensation.total_overtime_paid": -1}},
        {"$limit": 25},
        {"$project": {"_id": 0, "employee_id": 1, "agency": "$agency_snapshot.agency_name",
                       "total_overtime_paid": "$compensation.total_overtime_paid"}},
    ],
    "Q3: Agency OT per employee": [
        {"$group": {
            "_id": "$agency_snapshot.agency_name",
            "total_ot_hours": {"$sum": "$compensation.overtime_hours"},
            "headcount": {"$addToSet": "$employee_id"},
        }},
        {"$addFields": {"headcount": {"$size": "$headcount"},
                         "ot_hours_per_employee": {"$divide": ["$total_ot_hours", {"$size": "$headcount"}]}}},
        {"$sort": {"ot_hours_per_employee": -1}},
        {"$project": {"_id": 0, "agency": "$_id", "total_ot_hours": 1,
                       "headcount": 1, "ot_hours_per_employee": 1}},
    ],
    "Q4: Title avg OT pay": [
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
    "Q5: Agency total OT spend": [
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
    "Q6: Agency OT reliance": [
        {"$group": {
            "_id": "$agency_snapshot.agency_name",
            "total_ot_paid": {"$sum": "$compensation.total_overtime_paid"},
            "total_regular_gross": {"$sum": "$compensation.regular_gross_paid"},
        }},
        {"$match": {"total_regular_gross": {"$gt": 0}}},
        {"$addFields": {"ot_ratio": {"$divide": ["$total_ot_paid", "$total_regular_gross"]}}},
        {"$sort": {"ot_ratio": -1}},
        {"$limit": 15},
        {"$project": {"_id": 0, "agency": "$_id", "total_ot_paid": 1,
                       "total_regular_gross": 1, "ot_ratio": 1}},
    ],
    "Q7: Spending by fiscal year": [
        {"$group": {
            "_id": "$fiscal_year",
            "total_regular_gross": {"$sum": "$compensation.regular_gross_paid"},
            "total_ot_paid": {"$sum": "$compensation.total_overtime_paid"},
            "total_compensation": {"$sum": "$compensation.total_compensation"},
            "headcount": {"$addToSet": "$employee_id"},
        }},
        {"$addFields": {"headcount": {"$size": "$headcount"}}},
        {"$sort": {"_id": 1}},
        {"$project": {"_id": 0, "fiscal_year": "$_id", "total_regular_gross": 1,
                       "total_ot_paid": 1, "total_compensation": 1, "headcount": 1}},
    ],
    "Q8: Title avg total compensation": [
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
        {"$project": {"_id": 0, "title": "$_id", "avg_total_compensation": 1,
                       "avg_base_salary": 1, "headcount": 1}},
    ],
    "Q9: Agency total compensation": [
        {"$group": {
            "_id": "$agency_snapshot.agency_name",
            "total_compensation": {"$sum": "$compensation.total_compensation"},
            "total_ot_paid": {"$sum": "$compensation.total_overtime_paid"},
            "headcount": {"$addToSet": "$employee_id"},
        }},
        {"$addFields": {"headcount": {"$size": "$headcount"},
                         "avg_comp_per_employee": {"$divide": ["$total_compensation", {"$size": "$headcount"}]}}},
        {"$sort": {"total_compensation": -1}},
        {"$project": {"_id": 0, "agency": "$_id", "total_compensation": 1,
                       "total_ot_paid": 1, "headcount": 1, "avg_comp_per_employee": 1}},
    ],
}

# ---------------------------------------------------------------------------
# MySQL queries (equivalent analytics)
# ---------------------------------------------------------------------------

mysql_queries = {
    "Q1: Underpaid overtime": """
        SELECT COUNT(*) AS count
        FROM payroll_records pr
        WHERE pr.overtime_hours > 0
          AND pr.base_salary > 0
          AND (pr.total_overtime_paid / pr.overtime_hours)
              < ((pr.base_salary / 2080) * 1.5)
    """,
    "Q2: Top OT earners": """
        SELECT pr.employee_id, a.agency_name, pr.total_overtime_paid
        FROM payroll_records pr
        JOIN agencies a ON pr.agency_id = a.agency_id
        WHERE pr.total_overtime_paid > 0
        ORDER BY pr.total_overtime_paid DESC
        LIMIT 25
    """,
    "Q3: Agency OT per employee": """
        SELECT a.agency_name,
               SUM(pr.overtime_hours) AS total_ot_hours,
               COUNT(DISTINCT pr.employee_id) AS headcount,
               SUM(pr.overtime_hours) / COUNT(DISTINCT pr.employee_id) AS ot_hours_per_employee
        FROM payroll_records pr
        JOIN agencies a ON pr.agency_id = a.agency_id
        GROUP BY a.agency_name
        ORDER BY ot_hours_per_employee DESC
    """,
    "Q4: Title avg OT pay": """
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
    "Q5: Agency total OT spend": """
        SELECT a.agency_name,
               SUM(pr.total_overtime_paid) AS total_ot_paid,
               COUNT(DISTINCT pr.employee_id) AS headcount
        FROM payroll_records pr
        JOIN agencies a ON pr.agency_id = a.agency_id
        GROUP BY a.agency_name
        ORDER BY total_ot_paid DESC
        LIMIT 15
    """,
    "Q6: Agency OT reliance": """
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
    "Q7: Spending by fiscal year": """
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
    "Q8: Title avg total compensation": """
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
    "Q9: Agency total compensation": """
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
# Timing helpers
# ---------------------------------------------------------------------------

def time_mongo(collection, pipeline, runs, warmup):
    for _ in range(warmup):
        list(collection.aggregate(pipeline))
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        list(collection.aggregate(pipeline))
        times.append(time.perf_counter() - t0)
    return times

def time_mysql(cursor, sql, runs, warmup):
    for _ in range(warmup):
        cursor.execute(sql)
        cursor.fetchall()
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        cursor.execute(sql)
        cursor.fetchall()
        times.append(time.perf_counter() - t0)
    return times

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Connecting to databases...")
    mongo_col = MongoClient("localhost", 27017)["NYC_Payroll"]["payroll_records"]
    mysql_conn = mysql.connector.connect(**MYSQL_CFG)
    cursor = mysql_conn.cursor()

    print(f"\nBenchmark: {WARMUP} warm-up + {RUNS} timed runs per query")
    print(f"Dataset: 1,113,103 payroll records\n")
    print(f"{'Query':<35} {'MongoDB (ms)':>14} {'MySQL (ms)':>12} {'Winner':>10}")
    print("-" * 75)

    mongo_total, mysql_total = 0.0, 0.0
    results = []

    for key in mongo_queries:
        pipeline = mongo_queries[key]
        sql = mysql_queries[key]

        m_times = time_mongo(mongo_col, pipeline, RUNS, WARMUP)
        s_times = time_mysql(cursor, sql, RUNS, WARMUP)

        m_med = statistics.median(m_times) * 1000
        s_med = statistics.median(s_times) * 1000
        winner = "MongoDB" if m_med < s_med else "MySQL"
        speedup = max(m_med, s_med) / min(m_med, s_med)

        mongo_total += m_med
        mysql_total += s_med
        results.append((key, m_med, s_med, winner, speedup))

        print(f"{key:<35} {m_med:>12.1f}ms {s_med:>10.1f}ms {winner + f' ({speedup:.1f}x)':>14}")

    print("-" * 75)
    overall_winner = "MongoDB" if mongo_total < mysql_total else "MySQL"
    speedup = max(mongo_total, mysql_total) / min(mongo_total, mysql_total)
    print(f"{'TOTAL (sum of medians)':<35} {mongo_total:>12.1f}ms {mysql_total:>10.1f}ms {overall_winner + f' ({speedup:.1f}x)':>14}")

    print("\n--- Per-query breakdown (min / median / max) ---")
    for key, m_med, s_med, winner, speedup in results:
        print(f"\n  {key}")
        print(f"    MongoDB : {m_med:.1f}ms median")
        print(f"    MySQL   : {s_med:.1f}ms median")
        print(f"    Winner  : {winner} by {speedup:.1f}x")

    cursor.close()
    mysql_conn.close()

if __name__ == "__main__":
    main()
