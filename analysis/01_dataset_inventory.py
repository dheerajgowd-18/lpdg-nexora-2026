from pathlib import Path
import pandas as pd


DATA_DIR = Path("data")


def inspect_dataframe(name, df):
    print("\n" + "=" * 80)
    print(f"DATASET: {name}")
    print("=" * 80)

    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")

    print("\nColumns and dtypes:")
    print(df.dtypes.to_string())

    print("\nMissing values:")
    missing = df.isna().sum()
    missing = missing[missing > 0]

    if missing.empty:
        print("None")
    else:
        print(missing.to_string())

    print(f"\nDuplicate rows: {df.duplicated().sum():,}")

    if "gateway_id" in df.columns:
        print(f"\nUnique gateways: {df['gateway_id'].nunique():,}")

    datetime_columns = [
    column
    for column in [
        "ts_utc",
        "DateDt",
        "requested_on",
        "visited_on",
        "week_start",
        "reviewed_on",
        "fw_updated_on",
        "installed_on",
        "decommissioned_on",
    ]
    if column in df.columns
]

    if datetime_columns:
        print("\nDate/time ranges:")

        for column in datetime_columns:
            values = pd.to_datetime(df[column], errors="coerce")

            valid = values.dropna()

            if not valid.empty:
                print(
                    f"{column}: "
                    f"{valid.min()} -> {valid.max()}"
                )


def inspect_csv(path):
    try:
        if path.name == "gateway_master.csv":
            df = pd.read_csv(path, encoding="latin1")
        else:
            df = pd.read_csv(path)

        inspect_dataframe(path.name, df)

    except Exception as exc:
        print(f"\nERROR reading {path}: {exc}")


def inspect_excel(path):
    try:
        df = pd.read_excel(path)
        inspect_dataframe(path.name, df)
    except Exception as exc:
        print(f"\nERROR reading {path}: {exc}")


def inspect_parquet_files():
    telemetry_dir = DATA_DIR / "telemetry"

    if not telemetry_dir.exists():
        print("\nTelemetry directory not found.")
        return

    parquet_files = sorted(telemetry_dir.rglob("*.parquet"))

    print("\n" + "=" * 80)
    print("TELEMETRY PARQUET INVENTORY")
    print("=" * 80)

    print(f"Parquet files found: {len(parquet_files)}")

    if not parquet_files:
        return

    total_rows = 0

    for path in parquet_files:
        try:
            df = pd.read_parquet(path)

            print(
                f"{path.relative_to(DATA_DIR)}: "
                f"{len(df):,} rows x {len(df.columns)} columns"
            )

            total_rows += len(df)

        except Exception as exc:
            print(f"ERROR reading {path}: {exc}")

    print(f"\nTotal telemetry rows: {total_rows:,}")

    # Inspect the first parquet file in detail.
    first_file = parquet_files[0]

    try:
        df = pd.read_parquet(first_file)

        inspect_dataframe(
            f"Telemetry sample: {first_file.relative_to(DATA_DIR)}",
            df,
        )

    except Exception as exc:
        print(f"ERROR inspecting telemetry sample: {exc}")


def main():
    if not DATA_DIR.exists():
        raise FileNotFoundError(
            "data/ directory not found. "
            "Run this script from the project root."
        )

    print("=" * 80)
    print("NEXORA 2026 — DATASET INVENTORY")
    print("=" * 80)

    csv_files = sorted(DATA_DIR.glob("*.csv"))
    excel_files = sorted(DATA_DIR.glob("*.xlsx"))

    print(f"\nCSV files found: {len(csv_files)}")
    print(f"Excel files found: {len(excel_files)}")

    for path in csv_files:
        inspect_csv(path)

    for path in excel_files:
        inspect_excel(path)

    inspect_parquet_files()

    print("\n" + "=" * 80)
    print("INVENTORY COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()