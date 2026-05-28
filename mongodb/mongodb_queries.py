from pymongo import MongoClient
import pandas as pd
import os

client = MongoClient('localhost', 27017)
db = client['NYC_Payroll']

output_dir = os.path.join(os.path.dirname(__file__), 'results')
os.makedirs(output_dir, exist_ok=True)


# 1. Which individuals are not paid sufficiently for the overtime hours they have worked
#    (Are employees paid 1.5x their regular hourly rate for every overtime hour?)
print("Running Query 1: Employees underpaid on overtime...")

pipeline = [
    {"$match": {
        "compensation.overtime_hours": {"$gt": 0},
        "compensation.base_salary": {"$gt": 0}
    }},
    {"$addFields": {
        "hourly_rate": {"$divide": ["$compensation.base_salary", 2080]},
    }},
    {"$addFields": {
        "expected_ot_rate": {"$multiply": ["$hourly_rate", 1.5]},
        "actual_ot_rate": {
            "$divide": [
                "$compensation.total_overtime_paid",
                "$compensation.overtime_hours"
            ]
        }
    }},
    {"$match": {
        "$expr": {"$lt": ["$actual_ot_rate", "$expected_ot_rate"]}
    }},
    {"$project": {
        "_id": 0,
        "employee_id": {"$toString": "$employee_id"},
        "agency_name": "$agency_snapshot.agency_name",
        "title": "$title_snapshot.title_description",
        "base_salary": "$compensation.base_salary",
        "overtime_hours": "$compensation.overtime_hours",
        "total_overtime_paid": "$compensation.total_overtime_paid",
        "hourly_rate": 1,
        "expected_ot_rate": 1,
        "actual_ot_rate": 1
    }}
]

results = list(db['payroll_records'].aggregate(pipeline))
df = pd.DataFrame(results)
path = os.path.join(output_dir, 'q1_underpaid_overtime.csv')
df.to_csv(path, index=False)
print(f"  -> {len(df)} rows saved to {path}")


# 2. Which employees earned the most in overtime pay?
print("Running Query 2: Top employees by total overtime pay...")

pipeline = [
    {"$match": {"compensation.total_overtime_paid": {"$gt": 0}}},
    {"$sort": {"compensation.total_overtime_paid": -1}},
    {"$project": {
        "_id": 0,
        "employee_id": {"$toString": "$employee_id"},
        "agency": "$agency_snapshot.agency_name",
        "title": "$title_snapshot.title_description",
        "fiscal_year": 1,
        "total_overtime_paid": "$compensation.total_overtime_paid",
        "overtime_hours": "$compensation.overtime_hours",
    }}
]

results = list(db['payroll_records'].aggregate(pipeline))
df = pd.DataFrame(results)
path = os.path.join(output_dir, 'q2_top_ot_earners.csv')
df.to_csv(path, index=False)
print(f"  -> {len(df)} rows saved to {path}")


# 3. Which agencies have a high OT-to-headcount ratio?
print("Running Query 3: Agencies by OT hours per employee...")

pipeline = [
    {"$group": {
        "_id": "$agency_snapshot.agency_name",
        "total_ot_hours": {"$sum": "$compensation.overtime_hours"},
        "total_ot_paid": {"$sum": "$compensation.total_overtime_paid"},
        "headcount": {"$addToSet": "$employee_id"}
    }},
    {"$addFields": {
        "headcount": {"$size": "$headcount"},
    }},
    {"$addFields": {
        "ot_hours_per_employee": {
            "$divide": ["$total_ot_hours", "$headcount"]
        }
    }},
    {"$sort": {"ot_hours_per_employee": -1}},
    {"$project": {
        "_id": 0,
        "agency": "$_id",
        "total_ot_hours": 1,
        "total_ot_paid": 1,
        "headcount": 1,
        "ot_hours_per_employee": 1,
    }}
]

results = list(db['payroll_records'].aggregate(pipeline))
df = pd.DataFrame(results)
path = os.path.join(output_dir, 'q3_agency_ot_ratio.csv')
df.to_csv(path, index=False)
print(f"  -> {len(df)} rows saved to {path}")


# 4. Which job titles have the highest average overtime pay?
print("Running Query 4: Job titles by average overtime pay...")

pipeline = [
    {"$match": {"compensation.total_overtime_paid": {"$gt": 0}}},
    {"$group": {
        "_id": "$title_snapshot.title_description",
        "avg_ot_pay": {"$avg": "$compensation.total_overtime_paid"},
        "total_ot_pay": {"$sum": "$compensation.total_overtime_paid"},
        "headcount": {"$sum": 1}
    }},
    {"$sort": {"avg_ot_pay": -1}},
    {"$project": {
        "_id": 0,
        "title": "$_id",
        "avg_ot_pay": 1,
        "total_ot_pay": 1,
        "headcount": 1,
    }}
]

results = list(db['payroll_records'].aggregate(pipeline))
df = pd.DataFrame(results)
path = os.path.join(output_dir, 'q4_title_avg_ot_pay.csv')
df.to_csv(path, index=False)
print(f"  -> {len(df)} rows saved to {path}")

print("\nDone! All results saved to mongodb/results/")
