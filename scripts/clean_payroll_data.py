import pandas as pd
from pathlib import Path

RAW_PATH = Path("data/raw/nyc_payroll.csv")
PROCESSED_PATH = Path("data/processed/nyc_payroll_cleaned.csv")

def clean_money_column(series):
    return (
        series.astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
        .replace("", "0")
        .astype(float)
    )

def main():
    df = pd.read_csv(RAW_PATH, low_memory=False)

    # Standardize column names
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("/", "_")
    )

    # Rename awkward columns
    df = df.rename(columns={
        "mid_init": "middle_initial",
        "leave_status_as_of_june_30": "leave_status",
        "ot_hours": "overtime_hours",
        "total_ot_paid": "total_overtime_paid"
    })

    # Clean money columns
    money_cols = [
        "base_salary",
        "regular_gross_paid",
        "total_overtime_paid",
        "total_other_pay"
    ]

    for col in money_cols:
        df[col] = clean_money_column(df[col])

    # Clean date column
    df["agency_start_date"] = pd.to_datetime(
        df["agency_start_date"],
        errors="coerce"
    )

    # Fill missing categorical values
    df["last_name"] = df["last_name"].fillna("Unknown")
    df["first_name"] = df["first_name"].fillna("Unknown")
    df["middle_initial"] = df["middle_initial"].fillna("")
    df["work_location_borough"] = df["work_location_borough"].fillna("Unknown")
    df["title_description"] = df["title_description"].fillna("Unknown")

    # Create useful derived fields
    df["total_compensation"] = (
        df["regular_gross_paid"]
        + df["total_overtime_paid"]
        + df["total_other_pay"]
    )

    df["overtime_pay_share"] = df["total_overtime_paid"] / df["total_compensation"]
    df["overtime_pay_share"] = df["overtime_pay_share"].replace([float("inf"), -float("inf")], 0)
    df["overtime_pay_share"] = df["overtime_pay_share"].fillna(0)

    df["total_hours"] = df["regular_hours"] + df["overtime_hours"]
    df["overtime_hours_share"] = df["overtime_hours"] / df["total_hours"]
    df["overtime_hours_share"] = df["overtime_hours_share"].replace([float("inf"), -float("inf")], 0)
    df["overtime_hours_share"] = df["overtime_hours_share"].fillna(0)

    # Standardize text fields so duplicate categories do not break MySQL UNIQUE constraints
    text_cols = [
        "agency_name",
        "first_name",
        "last_name",
        "middle_initial",
        "work_location_borough",
        "title_description",
        "leave_status",
        "pay_basis"
    ]

    for col in text_cols:
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
            .str.upper()
        )

# Replace placeholder missing values created by astype(str)
    df["middle_initial"] = df["middle_initial"].replace("NAN", "")
    df["work_location_borough"] = df["work_location_borough"].replace("NAN", "UNKNOWN")
    df["title_description"] = df["title_description"].replace("NAN", "UNKNOWN")
    df["first_name"] = df["first_name"].replace("NAN", "UNKNOWN")
    df["last_name"] = df["last_name"].replace("NAN", "UNKNOWN")


    # Save cleaned dataset
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED_PATH, index=False)

    print("Cleaned data saved to:", PROCESSED_PATH)
    print("Shape:", df.shape)
    print(df.head())
    print(df.dtypes)

if __name__ == "__main__":
    main()