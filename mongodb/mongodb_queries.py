# 1. Which individuals are not paid sufficiently for the overtime hours they have worked (Are employees paid 1.5 times their regular hourly pay for every overtime hour)?
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
        "employee_id": 1,
        "agency_snapshot.agency_name": 1,
        "title_snapshot.title_description": 1,
        "compensation.base_salary": 1,
        "compensation.overtime_hours": 1,
        "compensation.total_overtime_paid": 1,
        "hourly_rate": 1,
        "expected_ot_rate": 1,
        "actual_ot_rate": 1
    }}
]

results = list(db['payroll_records'].aggregate(pipeline))



# 2. Which employees earned the most in overtime pay?
pipeline = [
    {"$match": {"compensation.total_overtime_paid": {"$gt": 0}}},
    {"$sort": {"compensation.total_overtime_paid": -1}},
    {"$limit": 10},
    {"$project": {
        "employee_id": 1,
        "agency": "$agency_snapshot.agency_name",
        "title": "$title_snapshot.title_description",
        "fiscal_year": 1,
        "total_overtime_paid": "$compensation.total_overtime_paid",
        "overtime_hours": "$compensation.overtime_hours",
        "_id": 0
    }}
]

results = list(db['payroll_records'].aggregate(pipeline))


#3. Which agencies have a high OT-to-headcount ratio?
pipeline = [
    {"$group": {
        "_id": "$agency_snapshot.agency_name",
        "total_ot_hours": {"$sum": "$compensation.overtime_hours"},
        "total_ot_paid": {"$sum": "$compensation.total_overtime_paid"},
        "headcount": {"$addToSet": "$employee_id"}  # distinct employees
    }},
    {"$addFields": {
        "headcount": {"$size": "$headcount"},  # convert set to count
    }},
    {"$addFields": {
        "ot_hours_per_employee": {
            "$divide": ["$total_ot_hours", "$headcount"]
        }
    }},
    {"$sort": {"ot_hours_per_employee": -1}},
    {"$project": {
        "agency": "$_id",
        "total_ot_hours": 1,
        "total_ot_paid": 1,
        "headcount": 1,
        "ot_hours_per_employee": 1,
        "_id": 0
    }}
]

results = list(db['payroll_records'].aggregate(pipeline))
for r in results:
    print(r)

