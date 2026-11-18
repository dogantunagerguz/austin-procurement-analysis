# Junior data-stack extension

This extension turns the original pandas analysis into a small, inspectable
data pipeline without claiming production deployment.

| Skill | Evidence | Boundary |
|---|---|---|
| REST API | Paginated Socrata downloader with retries and schema validation | Public endpoint; no authentication flow |
| DuckDB | Typed staging view, supplier/month KPI views and four checks | Local analytical database |

## Run

```bash
python -m pip install -r requirements.txt
python duckdb/run_analysis.py
```

To refresh the committed source from the public API:

```bash
python scripts/download_data.py --fiscal-year 2023
```

GitHub Actions runs the DuckDB checks and unit tests on each push and pull request.
