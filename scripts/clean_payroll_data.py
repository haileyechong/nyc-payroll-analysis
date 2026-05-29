import pandas as pd
import numpy as np
from pathlib import Path

# =========================================================
# CONFIG
# =========================================================

RAW_PATH = Path("data/raw/nyc_payroll_raw.csv")
OUTPUT_PATH = Path("data/processed/nyc_payroll_cleaned.csv")

YEARS_TO_KEEP = [2024, 2025]

CHUNKSIZE = 100_000

# Keep negative values because payroll datasets can include corrections/reversals.
# Set to True only if your team decides to remove negative payroll adjustment rows.
REMOVE_NEGATIVE_ROWS = False


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def standardize_column_names(df):
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("/", "_", regex=False)
    )

    df = df.rename(columns={
        "mid_init": "middle_initial",
        "leave_status_as_of_june_30": "leave_status",
        "ot_hours": "overtime_hours",
        "total_ot_paid": "total_overtime_paid"
    })

    return df


def clean_money_column(series):
    cleaned = (
        series.astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
        .replace(["", "nan", "NaN", "None", "NONE"], "0")
    )

    return pd.to_numeric(cleaned, errors="coerce").fillna(0)


def clean_text_column(series, fill_value="UNKNOWN"):
    return (
        series
        .fillna(fill_value)
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r"\s+", " ", regex=True)   # collapse repeated spaces
        .replace({
            "NAN": fill_value,
            "NONE": fill_value,
            "NULL": fill_value,
            "": fill_value
        })
    )


def clean_date_column(series):
    dates = pd.to_datetime(series, errors="coerce")

    # Treat unrealistic placeholder dates as missing
    dates = dates.mask(dates >= pd.Timestamp("2100-01-01"))

    return dates


def clean_chunk(df):
    # Standardize column names first
    df = standardize_column_names(df)

    # Filter to chosen fiscal years
    df = df[df["fiscal_year"].isin(YEARS_TO_KEEP)].copy()

    if df.empty:
        return df

    # Clean text columns
    text_cols = [
        "agency_name",
        "last_name",
        "first_name",
        "middle_initial",
        "work_location_borough",
        "title_description",
        "leave_status",
        "pay_basis"
    ]

    for col in text_cols:
        if col in df.columns:
            df[col] = clean_text_column(df[col])

    # Middle initial can be blank instead of UNKNOWN
    df["middle_initial"] = df["middle_initial"].replace("UNKNOWN", "")

    # Clean money columns
    money_cols = [
        "base_salary",
        "regular_gross_paid",
        "total_overtime_paid",
        "total_other_pay"
    ]

    for col in money_cols:
        df[col] = clean_money_column(df[col])

    # Make hour columns numeric
    hour_cols = [
        "regular_hours",
        "overtime_hours"
    ]

    for col in hour_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Clean date column
    df["agency_start_date"] = clean_date_column(df["agency_start_date"])

    # Optional: remove negative adjustment rows
    if REMOVE_NEGATIVE_ROWS:
        numeric_check_cols = [
            "base_salary",
            "regular_hours",
            "regular_gross_paid",
            "overtime_hours",
            "total_overtime_paid",
            "total_other_pay"
        ]

        for col in numeric_check_cols:
            df = df[df[col] >= 0].copy()

    # Derived fields
    df["total_compensation"] = (
        df["regular_gross_paid"]
        + df["total_overtime_paid"]
        + df["total_other_pay"]
    )

    df["total_hours"] = df["regular_hours"] + df["overtime_hours"]

    df["overtime_pay_share"] = np.where(
        df["total_compensation"] != 0,
        df["total_overtime_paid"] / df["total_compensation"],
        0
    )

    df["overtime_hours_share"] = np.where(
        df["total_hours"] != 0,
        df["overtime_hours"] / df["total_hours"],
        0
    )

    # Replace inf / NaN from weird division cases
    df["overtime_pay_share"] = (
        df["overtime_pay_share"]
        .replace([np.inf, -np.inf], 0)
        .fillna(0)
    )

    df["overtime_hours_share"] = (
        df["overtime_hours_share"]
        .replace([np.inf, -np.inf], 0)
        .fillna(0)
    )

    # Keep only the columns we want
    final_cols = [
        "fiscal_year",
        "agency_name",
        "last_name",
        "first_name",
        "middle_initial",
        "agency_start_date",
        "work_location_borough",
        "title_description",
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
    ]

    df = df[final_cols]

    # Drop exact duplicate rows inside this chunk
    df = df.drop_duplicates()

    return df


# =========================================================
# MAIN CLEANING PROCESS
# =========================================================

def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    first_chunk = True
    total_rows = 0
    year_counts = {}

    negative_counts = {
        "base_salary": 0,
        "regular_hours": 0,
        "regular_gross_paid": 0,
        "overtime_hours": 0,
        "total_overtime_paid": 0,
        "total_other_pay": 0,
        "total_compensation": 0
    }

    print("Cleaning NYC payroll data...")
    print("Raw file:", RAW_PATH)
    print("Years kept:", YEARS_TO_KEEP)

    for chunk in pd.read_csv(RAW_PATH, chunksize=CHUNKSIZE, low_memory=False):
        cleaned = clean_chunk(chunk)

        if cleaned.empty:
            continue

        # Count negatives for reporting
        for col in negative_counts:
            if col in cleaned.columns:
                negative_counts[col] += int((cleaned[col] < 0).sum())

        total_rows += len(cleaned)

        for year, count in cleaned["fiscal_year"].value_counts().items():
            year_counts[year] = year_counts.get(year, 0) + count

        cleaned.to_csv(
            OUTPUT_PATH,
            mode="w" if first_chunk else "a",
            index=False,
            header=first_chunk
        )

        first_chunk = False
        print(f"Processed rows so far: {total_rows:,}")

    # Final pass to remove exact duplicates across chunks
    print("\nRemoving exact duplicates across full cleaned file...")
    final_df = pd.read_csv(OUTPUT_PATH, low_memory=False)
    before_dedup = len(final_df)
    final_df = final_df.drop_duplicates()
    after_dedup = len(final_df)
    final_df.to_csv(OUTPUT_PATH, index=False)

    print("\nCleaned data saved to:", OUTPUT_PATH)
    print("Rows before final duplicate removal:", before_dedup)
    print("Rows after final duplicate removal:", after_dedup)
    print("Exact duplicate rows removed:", before_dedup - after_dedup)

    print("\nRows by fiscal year:")
    print(final_df["fiscal_year"].value_counts().sort_index())

    print("\nMissing agency_start_date count:")
    print(final_df["agency_start_date"].isna().sum())

    print("\nNegative value counts, not automatically wrong:")
    for col, count in negative_counts.items():
        print(f"{col}: {count}")

    print("\nColumn names:")
    for col in final_df.columns:
        print(col)

    print("\nDone.")


if __name__ == "__main__":
    main()