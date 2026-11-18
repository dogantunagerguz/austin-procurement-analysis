"""Download one fiscal year of City of Austin purchase-order lines.

This is a small, explicit REST API ingestion example. It uses the public
Socrata endpoint, paginates with $limit/$offset, and validates the fields
needed by the analytical models before replacing the output file.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


API_URL = "https://data.austintexas.gov/resource/3ebq-e9iz.json"
REQUIRED_FIELDS = {
    "purchase_order",
    "award_date",
    "vendor_code",
    "lgl_nm",
    "itm_tot_am",
    "master_agreement",
}


def build_session() -> requests.Session:
    retry = Retry(
        total=4,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "junior-bi-portfolio/1.0"})
    return session


def fetch_fiscal_year(fiscal_year: int, page_size: int = 5000) -> list[dict[str, str]]:
    start_year = fiscal_year - 1
    where = (
        f"award_date between '{start_year}-10-01T00:00:00' "
        f"and '{fiscal_year}-09-30T23:59:59'"
    )
    rows: list[dict[str, str]] = []
    session = build_session()

    for offset in range(0, 1_000_000, page_size):
        response = session.get(
            API_URL,
            params={"$where": where, "$limit": page_size, "$offset": offset},
            timeout=60,
        )
        response.raise_for_status()
        page = response.json()
        if not page:
            break
        rows.extend(page)
        if len(page) < page_size:
            break
    return rows


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        raise ValueError("The API returned no rows for the requested fiscal year.")
    available = set().union(*(row.keys() for row in rows))
    missing = REQUIRED_FIELDS - available
    if missing:
        raise ValueError(f"API schema is missing required fields: {sorted(missing)}")
    return sorted(available)


def write_csv(rows: list[dict[str, str]], destination: Path) -> None:
    fields = validate_rows(rows)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fiscal-year", type=int, default=2023)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/austin_purchase_orders_fy2023.csv"),
    )
    args = parser.parse_args()
    rows = fetch_fiscal_year(args.fiscal_year)
    write_csv(rows, args.output)
    print(f"Downloaded {len(rows):,} rows to {args.output}")


if __name__ == "__main__":
    main()
