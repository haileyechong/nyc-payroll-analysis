# NYC Payroll Analysis

## Project Overview

This project looks at NYC payroll data, with a focus on overtime spending. We used payroll records from fiscal years 2024 and 2025 and compared how the data worked in both MySQL and MongoDB.

The main goal was to answer questions like:

* Which agencies spend the most on overtime?
* Which agencies rely on overtime the most?
* Which job titles have high overtime pay?
* How do MySQL and MongoDB compare for these types of queries?

The final cleaned dataset has **1,113,103 payroll records**.

## Dataset

The dataset comes from NYC Open Data:

https://data.cityofnewyork.us/d/k397-673e

The original dataset includes information such as agency name, employee name, job title, work location, base salary, regular gross pay, overtime hours, overtime pay, and other pay.

The cleaned CSV is not included in this GitHub repo because it is too large. To run the project, place the cleaned file here:

```text
data/processed/nyc_payroll_cleaned.csv
```

## Data Cleaning

The cleaning script is:

```text
scripts/clean_payroll_data.py
```

The main cleaning steps were:

* Filtered the data to fiscal years 2024 and 2025
* Standardized column names
* Cleaned text fields
* Converted money and hour columns to numeric values
* Created calculated fields like `total_compensation`, `total_hours`, `overtime_pay_share`, and `overtime_hours_share`
* Removed exact duplicate rows

To run cleaning:

```bash
python3 scripts/clean_payroll_data.py
```

## MySQL Setup

The MySQL schema is in:

```text
sql/mysql_schema.sql
```

The main table is `payroll_records`. It connects to smaller lookup tables:

* `agencies`
* `job_titles`
* `work_locations`
* `fiscal_years`
* `employees`

This makes the database more organized and avoids repeating the same agency or job title text over and over.

To create the MySQL database:

```bash
mysql -u root -p < sql/mysql_schema.sql
```

To split the cleaned data into MySQL tables:

```bash
python3 scripts/split_tables.py
```

To load the MySQL database:

```bash
python3 scripts/load_mysql.py
```

To run the SQL queries:

```bash
mysql -u root -p --table < sql/mysql_queries.sql > query_results.txt
```

## MongoDB Setup

The MongoDB files are in:

```text
mongodb/
```

MongoDB stores each payroll record as a document with nested sections for employee information, agency, job title, location, and compensation.

To load MongoDB:

```bash
python3 mongodb/load_mongodb.py
```

To run MongoDB queries:

```bash
python3 mongodb/mongodb_queries.py
```

## Main Questions

Some of the main questions we answered were:

1. Which NYC agencies spend the most total money on overtime pay?
2. Which agencies rely most heavily on overtime compared to regular gross pay?
3. How much does each agency spend on total compensation?
4. How did payroll and overtime spending change from 2024 to 2025?
5. Which job titles have the highest average overtime pay?
6. Which job titles have the highest average total compensation?
7. Which records look unusual based on overtime pay compared to estimated hourly rate?

## Main Findings

Some of the main findings were:

* The Police Department spent the most total money on overtime.
* The Department of Correction and Fire Department were the most overtime-reliant compared to regular gross pay.
* The Department of Education Pedagogical group had the highest total compensation spending.
* Total payroll and overtime spending were slightly lower in 2025 than in 2024.
* High overtime pay showed up in public safety, correction, transportation, sanitation, and skilled trade roles.

## Performance Comparison

We compared MySQL and MongoDB on three similar aggregation queries:

1. Total overtime spending by agency
2. Overtime reliance by agency
3. Payroll and overtime spending by fiscal year

The performance results are saved in:

```text
reports/performance/
```

Files included:

```text
runtime_comparison.csv
mysql_explain_q1.csv
mongo_explain_q1.json
index_before_after.csv
```

In our tests, MongoDB was faster for the three aggregation queries. This makes sense because the MongoDB documents stored agency and compensation information together, so it did not need joins.

MySQL was still useful because the data has a clear relational structure. Agencies, job titles, employees, fiscal years, and payroll records all fit naturally into separate connected tables.

## Dashboard

The Streamlit dashboard is in:

```text
dashboard/streamlit_app.py
```

To run it:

```bash
streamlit run dashboard/streamlit_app.py
```

The dashboard shows overtime spending, overtime reliance, compensation trends, and job title-level results.

## Repository Structure

```text
nyc-payroll-analysis/
├── README.md
├── docs/
├── sql/
├── mongodb/
├── scripts/
├── dashboard/
├── reports/
└── data/
```

The `data/` folder is ignored by Git because the dataset files are too large.

## Final Takeaway

MySQL is better for organizing this dataset because the data has clear relationships between payroll records, agencies, job titles, employees, and years. MongoDB was faster for some aggregation queries, but MySQL made the structure easier to understand and explain.

If we had more time, we would add more years, improve employee matching, test more indexes, and build out the dashboard more.
