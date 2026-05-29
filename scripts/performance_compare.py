import json
import time
from pathlib import Path
from getpass import getpass
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text
from pymongo import MongoClient


# =========================================================
# CONFIG
# =========================================================

MYSQL_DB = "nyc_payroll"
MYSQL_USER = "root"

MONGO_DB = "NYC_Payroll"
MONGO_COLLECTION = "payroll_records"

OUTPUT_DIR = Path("reports/performance")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REPEATS = 3


# =========================================================
# CONNECTIONS
# =========================================================

def get_mysql_engine():
    password = getpass("Enter MySQL password: ")
    password_encoded = quote_plus(password)

    return create_engine(
        f"mysql+pymysql://{MYSQL_USER}:{password_encoded}@localhost:3306/{MYSQL_DB}"
    )


def get_mongo_collection():
    client = MongoClient("localhost", 27017)
    db = client[MONGO_DB]
    return db[MONGO_COLLECTION]


# =========================================================
# TIMING HELPERS
# =========================================================

def time_mysql_query(engine, query, repeats=REPEATS):
    times = []

    for _ in range(repeats):
        start = time.perf_counter()
        df = pd.read_sql(query, engine)
        end = time.perf_counter()
        times.append(end - start)

    return {
        "rows_returned": len(df),
        "avg_seconds": sum(times) / len(times),
        "min_seconds": min(times),
        "max_seconds": max(times),
    }


def time_mongo_pipeline(collection, pipeline, repeats=REPEATS):
    times = []

    for _ in range(repeats):
        start = time.perf_counter()
        results = list(collection.aggregate(pipeline, allowDiskUse=True))
        end = time.perf_counter()
        times.append(end - start)

    return {
        "rows_returned": len(results),
        "avg_seconds": sum(times) / len(times),
        "min_seconds": min(times),
        "max_seconds": max(times),
    }


# =========================================================
# COMPARABLE QUERIES
# =========================================================

MYSQL_QUERIES = {
    "Q1_agency_total_overtime": """
        SELECT 
            a.agency_name,
            ROUND(SUM(pr.total_overtime_paid), 2) AS total_overtime_spending
        FROM payroll_records pr
        JOIN agencies a
            ON pr.agency_id = a.agency_id
        GROUP BY a.agency_name
        ORDER BY total_overtime_spending DESC
        LIMIT 15
    """,

    "Q2_agency_overtime_reliance": """
        SELECT 
            a.agency_name,
            ROUND(SUM(pr.total_overtime_paid), 2) AS total_overtime_paid,
            ROUND(SUM(pr.regular_gross_paid), 2) AS total_regular_gross_paid,
            ROUND(
                SUM(pr.total_overtime_paid) / NULLIF(SUM(pr.regular_gross_paid), 0),
                4
            ) AS overtime_to_regular_pay_ratio
        FROM payroll_records pr
        JOIN agencies a
            ON pr.agency_id = a.agency_id
        GROUP BY a.agency_name
        HAVING SUM(pr.regular_gross_paid) > 0
        ORDER BY overtime_to_regular_pay_ratio DESC
        LIMIT 15
    """,

    "Q3_fiscal_year_spending": """
        SELECT 
            fy.fiscal_year,
            ROUND(SUM(pr.total_compensation), 2) AS total_compensation,
            ROUND(SUM(pr.total_overtime_paid), 2) AS total_overtime_paid
        FROM payroll_records pr
        JOIN fiscal_years fy
            ON pr.fiscal_year_id = fy.fiscal_year_id
        GROUP BY fy.fiscal_year
        ORDER BY fy.fiscal_year
    """
}


MONGO_PIPELINES = {
    "Q1_agency_total_overtime": [
        {
            "$group": {
                "_id": "$agency_snapshot.agency_name",
                "total_overtime_spending": {
                    "$sum": "$compensation.total_overtime_paid"
                }
            }
        },
        {"$sort": {"total_overtime_spending": -1}},
        {"$limit": 15},
        {
            "$project": {
                "_id": 0,
                "agency_name": "$_id",
                "total_overtime_spending": 1
            }
        }
    ],

    "Q2_agency_overtime_reliance": [
        {
            "$group": {
                "_id": "$agency_snapshot.agency_name",
                "total_overtime_paid": {
                    "$sum": "$compensation.total_overtime_paid"
                },
                "total_regular_gross_paid": {
                    "$sum": "$compensation.regular_gross_paid"
                }
            }
        },
        {"$match": {"total_regular_gross_paid": {"$gt": 0}}},
        {
            "$addFields": {
                "overtime_to_regular_pay_ratio": {
                    "$divide": [
                        "$total_overtime_paid",
                        "$total_regular_gross_paid"
                    ]
                }
            }
        },
        {"$sort": {"overtime_to_regular_pay_ratio": -1}},
        {"$limit": 15},
        {
            "$project": {
                "_id": 0,
                "agency_name": "$_id",
                "total_overtime_paid": 1,
                "total_regular_gross_paid": 1,
                "overtime_to_regular_pay_ratio": 1
            }
        }
    ],

    "Q3_fiscal_year_spending": [
        {
            "$group": {
                "_id": "$fiscal_year",
                "total_compensation": {
                    "$sum": "$compensation.total_compensation"
                },
                "total_overtime_paid": {
                    "$sum": "$compensation.total_overtime_paid"
                }
            }
        },
        {"$sort": {"_id": 1}},
        {
            "$project": {
                "_id": 0,
                "fiscal_year": "$_id",
                "total_compensation": 1,
                "total_overtime_paid": 1
            }
        }
    ]
}


# =========================================================
# EXPLAIN OUTPUTS
# =========================================================

def save_mysql_explain(engine):
    explain_query = "EXPLAIN " + MYSQL_QUERIES["Q1_agency_total_overtime"]
    explain_df = pd.read_sql(explain_query, engine)
    explain_df.to_csv(OUTPUT_DIR / "mysql_explain_q1.csv", index=False)
    print("Saved MySQL EXPLAIN output.")


def save_mongo_explain(collection):
    explain = collection.database.command(
        "explain",
        {
            "aggregate": MONGO_COLLECTION,
            "pipeline": MONGO_PIPELINES["Q1_agency_total_overtime"],
            "cursor": {}
        },
        verbosity="executionStats"
    )

    with open(OUTPUT_DIR / "mongo_explain_q1.json", "w") as f:
        json.dump(explain, f, indent=2, default=str)

    print("Saved MongoDB explain output.")


# =========================================================
# BEFORE / AFTER INDEX TEST
# =========================================================

def mysql_index_test(engine):
    query = """
        SELECT
            COUNT(*) AS high_comp_record_count,
            ROUND(AVG(total_compensation), 2) AS avg_total_compensation,
            ROUND(SUM(total_compensation), 2) AS total_compensation
        FROM payroll_records
        WHERE total_compensation >= 200000
    """

    with engine.connect() as conn:
        try:
            conn.execute(text("DROP INDEX idx_perf_total_compensation ON payroll_records"))
            conn.commit()
            print("Dropped old MySQL performance index.")
        except Exception:
            print("No old MySQL performance index to drop.")

    before = time_mysql_query(engine, query)

    with engine.connect() as conn:
        conn.execute(text(
            "CREATE INDEX idx_perf_total_compensation ON payroll_records(total_compensation)"
        ))
        conn.commit()
        print("Created MySQL performance index on total_compensation.")

    after = time_mysql_query(engine, query)

    return {
        "database": "MySQL",
        "query": "High compensation records filter",
        "index_used": "idx_perf_total_compensation on payroll_records(total_compensation)",
        "before_avg_seconds": before["avg_seconds"],
        "after_avg_seconds": after["avg_seconds"],
        "before_min_seconds": before["min_seconds"],
        "after_min_seconds": after["min_seconds"],
        "rows_returned": after["rows_returned"]
    }


def mongo_index_test(collection):
    pipeline = [
        {
            "$match": {
                "compensation.total_compensation": {"$gte": 200000}
            }
        },
        {
            "$group": {
                "_id": None,
                "high_comp_record_count": {"$sum": 1},
                "avg_total_compensation": {
                    "$avg": "$compensation.total_compensation"
                },
                "total_compensation": {
                    "$sum": "$compensation.total_compensation"
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "high_comp_record_count": 1,
                "avg_total_compensation": 1,
                "total_compensation": 1
            }
        }
    ]

    try:
        collection.drop_index("compensation.total_compensation_1")
        print("Dropped old MongoDB performance index.")
    except Exception:
        print("No old MongoDB performance index to drop.")

    before = time_mongo_pipeline(collection, pipeline)

    collection.create_index("compensation.total_compensation")
    print("Created MongoDB performance index on compensation.total_compensation.")

    after = time_mongo_pipeline(collection, pipeline)

    return {
        "database": "MongoDB",
        "query": "High compensation records filter",
        "index_used": "compensation.total_compensation",
        "before_avg_seconds": before["avg_seconds"],
        "after_avg_seconds": after["avg_seconds"],
        "before_min_seconds": before["min_seconds"],
        "after_min_seconds": after["min_seconds"],
        "rows_returned": after["rows_returned"]
    }


# =========================================================
# MAIN
# =========================================================

def main():
    mysql_engine = get_mysql_engine()
    mongo_collection = get_mongo_collection()

    print("\nRunning comparable query runtime tests...")

    performance_rows = []

    for query_name in MYSQL_QUERIES:
        print(f"Timing MySQL {query_name}...")
        mysql_result = time_mysql_query(mysql_engine, MYSQL_QUERIES[query_name])
        performance_rows.append({
            "query_name": query_name,
            "database": "MySQL",
            **mysql_result
        })

        print(f"Timing MongoDB {query_name}...")
        mongo_result = time_mongo_pipeline(mongo_collection, MONGO_PIPELINES[query_name])
        performance_rows.append({
            "query_name": query_name,
            "database": "MongoDB",
            **mongo_result
        })

    performance_df = pd.DataFrame(performance_rows)
    performance_df.to_csv(OUTPUT_DIR / "runtime_comparison.csv", index=False)

    print("\nSaving EXPLAIN outputs...")
    save_mysql_explain(mysql_engine)
    save_mongo_explain(mongo_collection)

    print("\nRunning before/after index tests...")
    index_results = [
        mysql_index_test(mysql_engine),
        mongo_index_test(mongo_collection)
    ]

    index_df = pd.DataFrame(index_results)
    index_df.to_csv(OUTPUT_DIR / "index_before_after.csv", index=False)

    print("\nDone. Performance evidence saved to:")
    print(OUTPUT_DIR)

    print("\nRuntime comparison:")
    print(performance_df)

    print("\nIndex comparison:")
    print(index_df)


if __name__ == "__main__":
    main()