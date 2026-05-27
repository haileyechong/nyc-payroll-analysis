import pandas as pd
from pathlib import Path

INPUT_PATH = Path("data/processed/nyc_payroll_cleaned.csv")
OUTPUT_DIR = Path("data/processed/tables")

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_PATH, low_memory=False)

    # Extra cleanup before creating lookup tables
    text_cols = [
        "agency_name",
        "title_description",
        "work_location_borough",
        "first_name",
        "last_name",
        "middle_initial",
        "leave_status",
        "pay_basis"
    ]

    for col in text_cols:
        df[col] = (
            df[col]
            .fillna("UNKNOWN")
            .astype(str)
            .str.strip()
            .str.upper()
        )

    df["middle_initial"] = df["middle_initial"].replace("UNKNOWN", "")

    # Make sure dates are formatted correctly for MySQL
    df["agency_start_date"] = pd.to_datetime(
        df["agency_start_date"],
        errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    # Agencies table
   
    agencies = (
        df[["agency_name"]]
        .dropna()
        .drop_duplicates()
        .sort_values("agency_name")
        .reset_index(drop=True)
    )   
    
    agencies["agency_id"] = agencies.index + 1
    agencies = agencies[["agency_id", "agency_name"]]

    agency_map = dict(zip(agencies["agency_name"], agencies["agency_id"]))
    df["agency_id"] = df["agency_name"].map(agency_map)

  
    # Job titles table
  
    job_titles = (
    df[["title_description"]]
    .dropna()
    .drop_duplicates()
    .sort_values("title_description")
    .reset_index(drop=True)
    )
    job_titles["title_id"] = job_titles.index + 1
    job_titles = job_titles[["title_id", "title_description"]]
    
    title_map = dict(zip(job_titles["title_description"], job_titles["title_id"]))
    df["title_id"] = df["title_description"].map(title_map)

  
    # Work locations table

    work_locations = (
        df[["work_location_borough"]]
        .dropna()
        .drop_duplicates()
        .sort_values("work_location_borough")
        .reset_index(drop=True)
    )
    
    work_locations["location_id"] = work_locations.index + 1
    work_locations = work_locations[["location_id", "work_location_borough"]]

    location_map = dict(zip(work_locations["work_location_borough"], work_locations["location_id"]))
    df["location_id"] = df["work_location_borough"].map(location_map)

  
    # Fiscal years table
 
    fiscal_years = (
        df[["fiscal_year"]]
        .drop_duplicates()
        .sort_values("fiscal_year")
        .reset_index(drop=True)
    )
    fiscal_years["fiscal_year_id"] = fiscal_years.index + 1
    fiscal_years = fiscal_years[["fiscal_year_id", "fiscal_year"]]

    fiscal_year_map = dict(zip(fiscal_years["fiscal_year"], fiscal_years["fiscal_year_id"]))
    df["fiscal_year_id"] = df["fiscal_year"].map(fiscal_year_map)

  
    # Employees table
  
    employee_cols = [
        "first_name",
        "last_name",
        "middle_initial",
        "agency_start_date"
    ]

    df["employee_id"] = df.groupby(employee_cols, sort=False).ngroup() + 1

    employees = (
        df[["employee_id"] + employee_cols]
        .drop_duplicates("employee_id")
        .sort_values("employee_id")
    )

   
    # Payroll records fact table
    
    payroll_records = df[[
        "employee_id",
        "agency_id",
        "title_id",
        "location_id",
        "fiscal_year_id",
        "leave_status",
        "base_salary",
        "pay_basis",
        "regular_hours",
        "regular_gross_paid",
        "overtime_hours",
        "total_overtime_paid",
        "total_other_pay",
        "total_compensation",
        "overtime_pay_share",
        "total_hours",
        "overtime_hours_share"
    ]].copy()

    payroll_records.insert(0, "payroll_record_id", range(1, len(payroll_records) + 1))

    # Save tables
    agencies.to_csv(OUTPUT_DIR / "agencies.csv", index=False)
    job_titles.to_csv(OUTPUT_DIR / "job_titles.csv", index=False)
    work_locations.to_csv(OUTPUT_DIR / "work_locations.csv", index=False)
    fiscal_years.to_csv(OUTPUT_DIR / "fiscal_years.csv", index=False)
    employees.to_csv(OUTPUT_DIR / "employees.csv", index=False)
    payroll_records.to_csv(OUTPUT_DIR / "payroll_records.csv", index=False)

    print("Saved normalized tables to:", OUTPUT_DIR)
    print("agencies:", agencies.shape)
    print("job_titles:", job_titles.shape)
    print("work_locations:", work_locations.shape)
    print("fiscal_years:", fiscal_years.shape)
    print("employees:", employees.shape)
    print("payroll_records:", payroll_records.shape)

if __name__ == "__main__":
    main()