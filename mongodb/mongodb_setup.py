import pandas as pd
from pymongo import MongoClient
import pprint
from bson import ObjectId

# load data
payroll_data = pd.read_csv('Citywide_Payroll_Data_2025.csv')
payroll_data.head()

# Connect
client = MongoClient('localhost', 27017)
db = client['NYC_Payroll']

# Load
payroll_data.columns = payroll_data.columns.str.strip().str.lower().str.replace(' ', '_')

# 1. Agencies
agencies_records = payroll_data[['payroll_number', 'agency_name']].drop_duplicates().to_dict('records')
db['agencies'].insert_many(agencies_records)

# 2. Job titles
job_titles_records = payroll_data[['title_description']].drop_duplicates().to_dict('records')
db['job_titles'].insert_many(job_titles_records)

# 3. Work locations
work_locations_records = payroll_data[['work_location_borough']].drop_duplicates().to_dict('records')
db['work_locations'].insert_many(work_locations_records)

# 4. Employees
employees_records = payroll_data[['first_name', 'last_name', 'mid_init', 'agency_start_date']].drop_duplicates().rename(columns={
    'mid_init': 'middle_initial'
}).to_dict('records')
db['employees'].insert_many(employees_records)

# 5. Build lookup maps
agency_map = {a['agency_name']: a['_id'] for a in db['agencies'].find()}
title_map = {t['title_description']: t['_id'] for t in db['job_titles'].find()}
location_map = {l['work_location_borough']: l['_id'] for l in db['work_locations'].find()}
employee_map = {(e['first_name'], e['last_name']): e['_id'] for e in db['employees'].find()}

# 6. Payroll records
payroll_records = []
for _, row in payroll_data.iterrows():
    record = {
        'employee_id': employee_map.get((row['first_name'], row['last_name'])),
        'agency_id': agency_map.get(row['agency_name']),
        'title_id': title_map.get(row['title_description']),
        'location_id': location_map.get(row['work_location_borough']),
        'fiscal_year': row['fiscal_year'],
        'leave_status': row['leave_status_as_of_june_30'],
        'compensation': {
            'base_salary': row['base_salary'],
            'pay_basis': row['pay_basis'],
            'regular_hours': row['regular_hours'],
            'regular_gross_paid': row['regular_gross_paid'],
            'overtime_hours': row['ot_hours'],
            'total_overtime_paid': row['total_ot_paid'],
            'total_other_pay': row['total_other_pay']
        },
        'agency_snapshot': {'payroll_number': row['payroll_number'], 'agency_name': row['agency_name']},
        'title_snapshot': {'title_description': row['title_description']},
        'location_snapshot': {'work_location_borough': row['work_location_borough']}
    }
    payroll_records.append(record)

db['payroll_records'].insert_many(payroll_records);
