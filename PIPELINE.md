# Pipeline: EGX Equities Data Pipeline

## Architecture

```
Raw CSV/JSON (data/) → S3 (ingestion/loaders/) → Silver Iceberg (Nessie) → Gold Iceberg (Nessie)
                                                                      ↓
                                                         PostgreSQL (via Spark JDBC)
                                                                      ↓
                                                         Grafana Dashboard (localhost:3000)
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| `nessie` | 19120 | Iceberg catalog (Nessie) |
| `spark_notebook` | 8888 | PySpark + Jupyter (runs pipeline jobs) |
| `postgres` | 5432 | PostgreSQL (Grafana backend) |
| `grafana` | 3000 | Dashboard UI |
| `dremio2` | 9047 | SQL query layer over Iceberg/S3 |
| `grafana-image-renderer` | - | Dashboard screenshot rendering |

## Running the Pipeline

### 1. Start all services

```bash
docker compose up -d
```

### 2. Upload raw data to S3

```bash
docker compose exec spark_notebook python -m ingestion.loaders.load_stocks
docker compose exec spark_notebook python -m ingestion.loaders.load_egx_index
docker compose exec spark_notebook python -m ingestion.loaders.load_metals
docker compose exec spark_notebook python -m ingestion.loaders.load_fx
docker compose exec spark_notebook python -m ingestion.loaders.load_re_sales
```

### 3. Run Silver jobs (6 jobs)

```bash
docker compose exec spark_notebook python -m spark_jobs.silver.clean_stocks_eod
docker compose exec spark_notebook python -m spark_jobs.silver.clean_fx
docker compose exec spark_notebook python -m spark_jobs.silver.clean_metals
docker compose exec spark_notebook python -m spark_jobs.silver.clean_fundamentals
docker compose exec spark_notebook python -m spark_jobs.silver.clean_re_sales
docker compose exec spark_notebook python -m spark_jobs.silver.clean_re_rentals
```

### 4. Run Gold jobs (7 jobs)

```bash
docker compose exec spark_notebook python -m spark_jobs.gold.stock_returns_vol
docker compose exec spark_notebook python -m spark_jobs.gold.stock_scores
docker compose exec spark_notebook python -m spark_jobs.gold.gold_metal_roi
docker compose exec spark_notebook python -m spark_jobs.gold.re_sale_metrics
docker compose exec spark_notebook python -m spark_jobs.gold.re_district_metrics
docker compose exec spark_notebook python -m spark_jobs.gold.asset_scores
docker compose exec spark_notebook python -m spark_jobs.gold.market_snapshot
```

### 5. Export to PostgreSQL

```bash
docker compose exec spark_notebook python /opt/project/scripts/export_to_postgres.py
```

Or via the exporter profile:

```bash
docker compose --profile export run --rm exporter
```

### 6. Open Grafana

- URL: http://localhost:3000
- Login: `admin` / `admin`

## Dremio Setup (Optional)

Dremio provides a SQL query layer over Iceberg tables in S3.

1. Open http://localhost:9047
2. Create admin user (if first time)
3. Add Nessie source:
   - **General tab:**
     - Name: `Dev`
     - Endpoint URL: `http://nessie:19120/api/v2`
     - Authentication: `None`
   - **Storage tab:**
     - Select `AWS` storage provider
     - Access key: (from `.env`)
     - Secret key: (from `.env`)
     - Region: `us-east-1`
     - Root path: `/investing-gradutation-project/warehouse`
     - Connection properties:
       - `fs.s3a.path.style.access` = `true`
       - `dremio.s3.compat` = `true`
     - Uncheck "Encrypt connection"
4. Click Save

## Environment Variables (.env)

```
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
WAREHOUSE=s3://investing-gradutation-project/warehouse/
NESSIE_URI=http://nessie:19120/api/v2
```

## Table Schema

### Silver Layer (Iceberg in Nessie)

| Table | Rows | Description |
|-------|------|-------------|
| `silver.stock_eod` | 1,230 | Daily OHLCV for EGX stocks |
| `silver.fundamentals` | 10 | Company fundamentals |
| `silver.stock_quotes` | 10 | Live stock quotes |
| `silver.egx30_index` | 123 | EGX30 index history |
| `silver.metals` | 80,628 | Gold/silver prices (history + spot) |
| `silver.fx_rates` | 9 | Currency exchange rates |
| `silver.re_sales` | 2,350 | Real estate sale listings |
| `silver.re_rentals` | 0 | Real estate rental listings (no data) |

### Gold Layer (Iceberg in Nessie)

| Table | Rows | Description |
|-------|------|-------------|
| `gold.stock_returns_vol` | 1,230 | Returns, momentum, volatility |
| `gold.stock_scores` | 10 | Composite stock scores |
| `gold.gold_metal_roi` | 2 | Metal ROI at 1/3/5/10yr horizons |
| `gold.re_sale_metrics` | 103 | District-level sale metrics |
| `gold.re_district_metrics` | 0 | District yield metrics |
| `gold.asset_scores` | 4 | Cross-asset comparison |
| `gold.market_snapshot` | 32 | Market snapshot |

### PostgreSQL (Grafana backend)

| Table | Rows | Description |
|-------|------|-------------|
| `gold.stock_performance` | 1,230 | OHLCV + change_pct (mapped from silver.stock_eod) |
| `gold.stock_fundamentals` | 10 | Company fundamentals (mapped from silver.fundamentals) |
| `gold.stock_technical` | 1,230 | SMA20/50 + RSI14 (computed from silver.stock_eod) |
