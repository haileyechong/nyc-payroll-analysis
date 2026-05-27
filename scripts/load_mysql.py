import pandas as pd
from pathlib import Path
from getpass import getpass
from urllib.parse import quote_plus
from sqlalchemy import create_engine

TABLE_DIR = Path("data/processed/tables")

TABLE_LOAD_ORDER = [
    "agencies",
    "job_titles",
    "work_locations",
    "fiscal_years",
    "employees",
    "payroll_records",
]

def load_table(engine, table_name):
    csv_path = TABLE_DIR / f"{table_name}.csv"

    print(f"Loading {table_name} from {csv_path}...")

    df = pd.read_csv(csv_path, low_memory=False)

    df.to_sql(
        table_name,
        con=engine,
        if_exists="append",
        index=False,
        chunksize=1000
    )

    print(f"Finished loading {table_name}: {len(df)} rows")

def main():
    mysql_user = "root"
    mysql_password = getpass("Enter MySQL password: ")
    mysql_password_encoded = quote_plus(mysql_password)

    database_name = "nyc_payroll"

    engine = create_engine(
        f"mysql+pymysql://{mysql_user}:{mysql_password_encoded}@localhost:3306/{database_name}"
    )

    for table_name in TABLE_LOAD_ORDER:
        load_table(engine, table_name)

    print("All tables loaded into MySQL.")

if __name__ == "__main__":
    main()