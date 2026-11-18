"""Run reproducible procurement checks and KPI queries with DuckDB."""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb


def sql_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def build_model(connection: duckdb.DuckDBPyConnection, source: Path) -> None:
    connection.execute(
        f"""
        create or replace view stg_purchase_orders as
        select
            trim(purchase_order) as purchase_order,
            cast(award_date as date) as award_date,
            trim(vendor_code) as vendor_code,
            trim(lgl_nm) as vendor_name,
            try_cast(itm_tot_am as decimal(18, 2)) as line_amount,
            nullif(trim(master_agreement), '') as master_agreement
        from read_csv_auto('{sql_path(source)}', header = true, all_varchar = true)
        """
    )
    connection.execute(
        """
        create or replace view supplier_spend as
        select
            vendor_code,
            any_value(vendor_name) as vendor_name,
            count(distinct purchase_order) as purchase_orders,
            round(sum(line_amount), 2) as spend
        from stg_purchase_orders
        group by vendor_code
        """
    )
    connection.execute(
        """
        create or replace view monthly_spend as
        select
            date_trunc('month', award_date)::date as award_month,
            count(distinct purchase_order) as purchase_orders,
            round(sum(line_amount), 2) as spend
        from stg_purchase_orders
        group by 1
        order by 1
        """
    )


def quality_checks(connection: duckdb.DuckDBPyConnection) -> dict[str, int]:
    checks = {
        "missing_purchase_order": "purchase_order is null or purchase_order = ''",
        "missing_vendor_code": "vendor_code is null or vendor_code = ''",
        "invalid_award_date": "award_date is null",
        "invalid_line_amount": "line_amount is null",
    }
    return {
        name: connection.execute(
            f"select count(*) from stg_purchase_orders where {condition}"
        ).fetchone()[0]
        for name, condition in checks.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/austin_purchase_orders_fy2023.csv"),
    )
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(args.input)
    connection = duckdb.connect()
    build_model(connection, args.input)
    checks = quality_checks(connection)
    print("Data-quality checks:", checks)
    if any(checks.values()):
        raise SystemExit("FAIL: one or more quality checks returned rows")

    if not args.check_only:
        print("Top suppliers:")
        for row in connection.execute(
            "select vendor_code, vendor_name, spend from supplier_spend order by spend desc limit 10"
        ).fetchall():
            print(row)
        print("PASS: DuckDB staging, KPI views and quality checks completed.")


if __name__ == "__main__":
    main()
