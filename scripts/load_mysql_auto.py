import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine

TABLE_DIR = Path("data/processed/tables")
MYSQL_USER = "root"
MYSQL_PASSWORD = "Tiffany-0826"
MYSQL_SOCKET = "/tmp/mysql.sock"
DATABASE = "nyc_payroll"

TABLE_LOAD_ORDER = [
    "agencies",
    "job_titles",
    "work_locations",
    "fiscal_years",
    "employees",
    "payroll_records",
]

engine = create_engine(
    f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@localhost/{DATABASE}"
    f"?unix_socket={MYSQL_SOCKET}"
)

for table in TABLE_LOAD_ORDER:
    csv_path = TABLE_DIR / f"{table}.csv"
    print(f"Loading {table}...", flush=True)
    df = pd.read_csv(csv_path, low_memory=False)
    df.to_sql(table, con=engine, if_exists="append", index=False, chunksize=5000)
    print(f"  -> {len(df):,} rows", flush=True)

print("Done.")
