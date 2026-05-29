from pymongo import MongoClient
import pandas as pd
import os

client = MongoClient('localhost', 27017)
db = client['NYC_Payroll']

output_dir = os.path.join(os.path.dirname(__file__), 'results')
os.makedirs(output_dir, exist_ok=True)


# 1. Which individuals are not paid sufficiently for the overtime hours they have worked
#    (Are employees paid 1.5x their regular hourly rate for every overtime hour?)

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


# 2. Which employees earned the most in overtime pay?

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


# 3. Which agencies have a high OT-to-headcount ratio?

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


# 4. Which job titles have the highest average overtime pay?

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



# 5. Which NYC agencies spend the most total money on overtime pay?

pipeline = [
    {"$group": {
        "_id": "$agency_snapshot.agency_name",
        "total_ot_paid": {"$sum": "$compensation.total_overtime_paid"},
        "headcount": {"$addToSet": "$employee_id"}
    }},
    {"$addFields": {"headcount": {"$size": "$headcount"}}},
    {"$sort": {"total_ot_paid": -1}},
    {"$project": {
        "_id": 0,
        "agency": "$_id",
        "total_ot_paid": 1,
        "headcount": 1
    }}
]

results = list(db['payroll_records'].aggregate(pipeline))
df = pd.DataFrame(results)
path = os.path.join(output_dir, 'q5_agency_total_ot_spend.csv')
df.to_csv(path, index=False)



# 6. Which agencies rely most heavily on overtime compared to regular gross pay?

pipeline = [
    {"$group": {
        "_id": "$agency_snapshot.agency_name",
        "total_ot_paid": {"$sum": "$compensation.total_overtime_paid"},
        "total_regular_gross": {"$sum": "$compensation.regular_gross_paid"}
    }},
    {"$match": {"total_regular_gross": {"$gt": 0}}},
    {"$addFields": {
        "ot_to_regular_ratio": {"$divide": ["$total_ot_paid", "$total_regular_gross"]}
    }},
    {"$sort": {"ot_to_regular_ratio": -1}},
    {"$project": {
        "_id": 0,
        "agency": "$_id",
        "total_ot_paid": 1,
        "total_regular_gross": 1,
        "ot_to_regular_ratio": 1
    }}
]

results = list(db['payroll_records'].aggregate(pipeline))
df = pd.DataFrame(results)
path = os.path.join(output_dir, 'q6_agency_ot_reliance.csv')
df.to_csv(path, index=False)



# 7. How have payroll spending and overtime spending changed across fiscal years?

pipeline = [
    {"$group": {
        "_id": "$fiscal_year",
        "total_regular_gross": {"$sum": "$compensation.regular_gross_paid"},
        "total_ot_paid": {"$sum": "$compensation.total_overtime_paid"},
        "total_other_pay": {"$sum": "$compensation.total_other_pay"},
        "total_compensation": {"$sum": "$compensation.total_compensation"},
        "headcount": {"$addToSet": "$employee_id"}
    }},
    {"$addFields": {"headcount": {"$size": "$headcount"}}},
    {"$sort": {"_id": 1}},
    {"$project": {
        "_id": 0,
        "fiscal_year": "$_id",
        "total_regular_gross": 1,
        "total_ot_paid": 1,
        "total_other_pay": 1,
        "total_compensation": 1,
        "headcount": 1
    }}
]

results = list(db['payroll_records'].aggregate(pipeline))
df = pd.DataFrame(results)
path = os.path.join(output_dir, 'q7_spending_by_fiscal_year.csv')
df.to_csv(path, index=False)


# 8. Which job titles have the highest average total compensation (base + OT + other)?

pipeline = [
    {"$match": {"compensation.total_compensation": {"$gt": 0}}},
    {"$group": {
        "_id": "$title_snapshot.title_description",
        "avg_total_compensation": {"$avg": "$compensation.total_compensation"},
        "avg_base_salary": {"$avg": "$compensation.base_salary"},
        "avg_ot_paid": {"$avg": "$compensation.total_overtime_paid"},
        "headcount": {"$sum": 1}
    }},
    {"$match": {"headcount": {"$gte": 10}}},
    {"$sort": {"avg_total_compensation": -1}},
    {"$project": {
        "_id": 0,
        "title": "$_id",
        "avg_total_compensation": 1,
        "avg_base_salary": 1,
        "avg_ot_paid": 1,
        "headcount": 1
    }}
]

results = list(db['payroll_records'].aggregate(pipeline))
df = pd.DataFrame(results)
path = os.path.join(output_dir, 'q8_title_avg_total_compensation.csv')
df.to_csv(path, index=False)
print(f"  -> {len(df)} rows saved to {path}")


# 9. How much does each agency spend on total compensation?

pipeline = [
    {"$group": {
        "_id": "$agency_snapshot.agency_name",
        "total_compensation": {"$sum": "$compensation.total_compensation"},
        "total_regular_gross": {"$sum": "$compensation.regular_gross_paid"},
        "total_ot_paid": {"$sum": "$compensation.total_overtime_paid"},
        "total_other_pay": {"$sum": "$compensation.total_other_pay"},
        "headcount": {"$addToSet": "$employee_id"}
    }},
    {"$addFields": {"headcount": {"$size": "$headcount"}}},
    {"$addFields": {
        "avg_compensation_per_employee": {"$divide": ["$total_compensation", "$headcount"]}
    }},
    {"$sort": {"total_compensation": -1}},
    {"$project": {
        "_id": 0,
        "agency": "$_id",
        "total_compensation": 1,
        "total_regular_gross": 1,
        "total_ot_paid": 1,
        "total_other_pay": 1,
        "headcount": 1,
        "avg_compensation_per_employee": 1
    }}
]

results = list(db['payroll_records'].aggregate(pipeline))
df = pd.DataFrame(results)
path = os.path.join(output_dir, 'q9_agency_total_compensation.csv')
df.to_csv(path, index=False)
print(f"  -> {len(df)} rows saved to {path}")
