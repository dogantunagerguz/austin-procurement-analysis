import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


download = load_module("download_data", ROOT / "scripts" / "download_data.py")
analysis = load_module("run_analysis", ROOT / "duckdb" / "run_analysis.py")


class RestApiValidationTests(unittest.TestCase):
    def test_required_fields_are_accepted(self):
        row = {field: "value" for field in download.REQUIRED_FIELDS}
        self.assertEqual(set(download.validate_rows([row])), set(row))

    def test_missing_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            download.validate_rows([{"purchase_order": "PO1"}])


class DuckDbPipelineTests(unittest.TestCase):
    def test_clean_sample_builds_and_passes_checks(self):
        fields = [
            "purchase_order",
            "award_date",
            "vendor_code",
            "lgl_nm",
            "itm_tot_am",
            "master_agreement",
        ]
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "orders.csv"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "purchase_order": "PO1",
                        "award_date": "2022-10-03",
                        "vendor_code": "V1",
                        "lgl_nm": "Vendor One",
                        "itm_tot_am": "100.00",
                        "master_agreement": "MA1",
                    }
                )
            connection = duckdb.connect()
            analysis.build_model(connection, source)
            self.assertEqual(analysis.quality_checks(connection), {
                "missing_purchase_order": 0,
                "missing_vendor_code": 0,
                "invalid_award_date": 0,
                "invalid_line_amount": 0,
            })
            self.assertEqual(connection.execute("select spend from supplier_spend").fetchone()[0], 100)


if __name__ == "__main__":
    unittest.main()
