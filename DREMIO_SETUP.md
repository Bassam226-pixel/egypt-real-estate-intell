# Dremio setup (one-time)

Dremio needs its Nessie source added once through the UI. After that it queries every table Spark writes.

## 1. Start it
```bash
docker compose up -d dremio
```
First boot takes ~1–2 minutes. Open **http://localhost:9047**.

## 2. Create the admin user
On first visit Dremio asks you to create an admin account. Use the same values you put in `.env`:
- username: `admin`
- password: `admin123`

## 3. Add the Nessie source
In the Dremio UI: **Add Source → Nessie** (under "Metastores" / "Catalogs"), then:

**General**
- Name: `nessie`   ← must match the catalog name used in your SQL (`nessie.gold.*`)
- Nessie endpoint URL: `http://nessie:19120/api/v2`
- Authentication: `None`

**Storage** (this project uses real AWS S3, not MinIO — there is no `minio` service in `docker-compose.yml`)
- AWS access key / secret: your `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` from `.env`
- Root path: the bucket + prefix from `WAREHOUSE` in `.env` (e.g. `your-bucket-name/warehouse`)
- Region: your `AWS_REGION` from `.env`
- Leave compatibility mode **off** — that's only for MinIO / non-AWS S3-compatible stores

Save. You should now see `nessie` in the source list, and can browse `nessie → gold → stock_scores`, etc.

## 4. Query it
- In the UI SQL editor: `SELECT * FROM nessie.gold.stock_scores`
- From the API: `api/services/dremio_reader.py` (Arrow Flight SQL on port 32010)
- From a BI tool: JDBC/ODBC on port 31010, or Arrow Flight on 32010

## Notes
- **Branches:** because Dremio queries Nessie, it sees `main` by default. You can query a branch explicitly: `SELECT * FROM nessie.gold.stock_scores AT BRANCH "etl_20260702"`.
- **No quality gate yet:** `spark_jobs/quality/` is scaffolded but its check files are currently empty — Gold jobs write straight to `main` with no validation before Dremio/Grafana/Streamlit read it. There is no run-branch-then-merge-on-pass behavior today.
- **Reflections (optional):** Dremio can materialize/accelerate frequent queries ("reflections") — useful later for the dashboard, not needed for the MVP.
- **Memory:** Dremio wants ~4 GB. With Spark + Airflow + Postgres also running, aim for 16 GB RAM on the machine, or lower `DREMIO_MAX_MEMORY_SIZE_MB` and stop services you're not using.