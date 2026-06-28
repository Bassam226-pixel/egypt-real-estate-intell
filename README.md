# Egyptian Investment Lakehouse

A personal data lakehouse built on **Apache Iceberg**, **Project Nessie**, **Apache Spark**, and **AWS S3** — designed to ingest, clean, and serve Egyptian investment data across equities, commodities, currencies, and real estate.

This repository covers my personal contribution to the [Egyptian Investment Intelligence Platform](https://github.com/): the full lakehouse foundation — storage, catalog, compute, and query engine — built on a production-grade open lakehouse stack.

---

## What This Project Does

Raw investment data from multiple Egyptian market sources is ingested into a **Medallion Architecture** (Bronze → Silver → Gold) stored as **Apache Iceberg tables** on **AWS S3**, cataloged by **Project Nessie**, and queryable through **Dremio** for BI tools like Power BI and Grafana.

### Data Sources

| File | Format | Description |
|---|---|---|
| `batch_eod_all_stocks.csv` | CSV | Daily OHLCV data for 10 EGX-listed stocks |
| `EGX30_index.csv` | CSV | EGX30 benchmark index daily prices |
| `fundamentals_all.csv` | CSV | Company financials: P/E, MarketCap, Beta, EPS |
| `live_quotes_all.csv` | CSV | Real-time stock quotes with change % |
| `authority_prices.csv` | CSV | Historical LBMA gold & silver prices since 1968 |
| `currency_rates.csv` | CSV | Exchange rates for world currencies |
| `spot_prices.csv` | CSV | Current gold & silver spot prices with bid/ask |
| `data_enriched.json` | JSON | Enriched real estate listings (PropertyFinder.eg) |

---

## Architecture

```
Raw Source Files (CSV, JSON)
         │
         ▼
  AWS S3 (raw/)
         │
         ▼  Apache Spark + Apache Iceberg
  Bronze Layer  ── s3://my-icebergdatalake/bronze/
         │
         ▼  Apache Spark + Apache Iceberg
  Silver Layer  ── s3://my-icebergdatalake/silver/
         │
         ▼  Apache Spark + Apache Iceberg
  Gold Layer    ── s3://my-icebergdatalake/gold/
         │
    ┌────┴────┐
    ▼         ▼
  Dremio    RAG Pipeline
  Power BI  (FAISS + LLM)
  Grafana
```

**Catalog:** Project Nessie — Git-like branching for the Iceberg catalog  
**Storage:** AWS S3 (`my-icebergdatalake`, eu-north-1 / Stockholm)  
**Query Engine:** Dremio — SQL interface for Power BI and Grafana  

---

## Tech Stack

| Tool | Version | Role |
|---|---|---|
| Apache Spark | 3.3 | Data processing engine |
| Apache Iceberg | 1.3.0 | Open table format |
| Project Nessie | 0.67.0 | Iceberg catalog with Git-like branching |
| AWS S3 | — | Data lake object storage (eu-north-1) |
| Dremio OSS | latest | SQL query engine + BI connectivity |
| Docker | — | Container orchestration |

---

## Medallion Architecture

### Bronze Layer — 9 Tables

Raw ingestion with zero transformations. Every source record lands exactly as-is, with two metadata columns appended: `_ingested_at` and `_source_file`.

| Table | Rows |
|---|---|
| `bronze.stocks_eod` | 1,230 |
| `bronze.egx30_index` | 123 |
| `bronze.fundamentals` | 10 |
| `bronze.live_quotes` | 10 |
| `bronze.gold_silver_prices` | 80,638 |
| `bronze.currency_rates` | 348 |
| `bronze.spot_prices` | 8 |
| `bronze.real_estate` | 107 |
| `bronze.real_estate_enriched` | 300 |

### Silver Layer — 9 Tables

Cleaned, typed, and standardized data ready for the Gold layer. Key transformations per table:

| Table | Transformations |
|---|---|
| `silver.stocks_eod` | Snake_case columns, date cast, `Dividends`/`Stock_Splits` dropped, dedup on `(symbol, date)` |
| `silver.egx30_index` | Snake_case, date cast, dedup on `date` |
| `silver.fundamentals` | `Website`, `Country`, `Exchange`, `Currency` dropped (constant values across all rows) |
| `silver.live_quotes` | `Currency`, `Exchange` dropped; floats rounded to 4 decimal places |
| `silver.gold_silver_prices` | Metal name uppercased, date cast, dedup on `(date, metal, session)` |
| `silver.currency_rates` | Filtered from 348 currencies → 10 investment-relevant: USD, EUR, GBP, JPY, CNY, SAR, AED, EGP, CHF, CAD |
| `silver.spot_prices` | Metal name uppercased, all price fields rounded to 6 decimal places |
| `silver.real_estate_propertyfinder` | Area parsed from `'165 sqm'` → `165.0`; price parsed from `'5,900,000'` → `5900000.0`; image/link/redundant columns dropped; amenities array → string; dedup on `listing_id` |
| `silver.real_estate_unified` | Final unified real estate table using PropertyFinder data only (Bayut dropped due to null values across key columns) |

### Gold Layer

Business-level aggregations and enriched tables consumed by Power BI, Grafana, and the RAG pipeline. Gold layer development uses Nessie branching (`gold-dev` → merge to `main`) to protect the main catalog during active development.

---

## Infrastructure Setup

### Prerequisites

- Docker Desktop installed
- AWS account with S3 bucket `my-icebergdatalake` in region `eu-north-1`
- AWS IAM user with S3 read/write permissions

### Required JARs

Before running any notebook, the following JARs must be placed in PySpark's `jars/` directory inside the notebook container:

```
bundle-2.20.18.jar              # AWS SDK v2 — for Iceberg S3FileIO
hadoop-aws-3.3.2.jar            # Hadoop S3A filesystem
aws-java-sdk-bundle-1.12.262.jar  # AWS SDK v1 — required by hadoop-aws
```

> **Why direct placement?** The `bundle-2.20.18.jar` is too large to broadcast over Spark's internal network. It must be placed directly in the `jars/` directory — passing it via `spark.jars` will fail.

Download script (run inside the notebook container):

```python
import urllib.request, os, pyspark

spark_jars_dir = os.path.join(os.path.dirname(pyspark.__file__), 'jars')

jars = {
    'bundle-2.20.18.jar': 'https://repo1.maven.org/maven2/software/amazon/awssdk/bundle/2.20.18/bundle-2.20.18.jar',
    'hadoop-aws-3.3.2.jar': 'https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.2/hadoop-aws-3.3.2.jar',
    'aws-java-sdk-bundle-1.12.262.jar': 'https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar',
}

for name, url in jars.items():
    dst = os.path.join(spark_jars_dir, name)
    if not os.path.exists(dst):
        print(f'Downloading {name}...')
        urllib.request.urlretrieve(url, dst)
        print(f'Done: {os.path.getsize(dst)/1024/1024:.1f} MB')
    else:
        print(f'Already exists: {name}')
```

### Environment Variables

Create a `.env` file in the project root:

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

> ⚠️ Never commit `.env` to Git. It is listed in `.gitignore`.

### Starting the Stack

```bash
docker compose up -d
```

| Service | URL |
|---|---|
| Jupyter Notebook | http://localhost:8888 |
| Nessie API | http://localhost:19120/api/v1 |
| Dremio UI | http://localhost:9047 |

---

## Running the Pipeline

Run notebooks in order:

```
notebooks/01_bronze_layer.ipynb   →  Raw ingestion from S3 raw/
notebooks/02_silver_layer.ipynb   →  Cleaning, typing, standardization
notebooks/03_gold_layer.ipynb     →  Business aggregations
```

---

## S3 Bucket Structure

```
s3://my-icebergdatalake/
├── raw/                    # Source files uploaded before bronze run
├── bronze/                 # Iceberg tables — raw data
├── silver/                 # Iceberg tables — cleaned data
├── gold/                   # Iceberg tables — aggregated data
└── iceberg-warehouse/      # Nessie internal metadata
```

---

## Connecting Dremio to Nessie

1. Open Dremio at `http://localhost:9047`
2. **Sources → Add Source → Nessie**
3. Set:
   - **Endpoint URL:** `http://nessie:19120/api/v1`
   - **Authentication:** None
   - **Default Branch:** `main`
4. Under **Storage**, add your AWS credentials and set region to `eu-north-1`

---

## Nessie Branching Workflow

Nessie branches isolate Gold layer development from the main catalog:

```python
import requests

NESSIE = 'http://nessie:19120/api/v1'
hash_ = requests.get(f'{NESSIE}/trees/tree/main').json()['hash']

# Create dev branch
requests.post(f'{NESSIE}/trees/branch', json={
    'name': 'gold-dev',
    'hash': hash_,
    'sourceRefName': 'main'
})

# Point Spark to the dev branch
# .config('spark.sql.catalog.nessie.ref', 'gold-dev')
```

Merge `gold-dev` → `main` only when Gold layer tables are verified.

---

## Important Notes

- **S3A vs S3 paths:** Use `s3a://` for reading raw CSV/JSON files (Spark Hadoop filesystem); use `s3://` for Iceberg table locations (Iceberg S3FileIO)
- **JAR placement:** `bundle-2.20.18.jar` must go directly in PySpark's `jars/` directory — not via `spark.jars`
- **No AWS Glue:** Glue uses the Glue Data Catalog and is incompatible with the Nessie catalog used here
- **Dremio as intermediary:** Grafana cannot read Parquet/Iceberg directly from S3 — Dremio is required as the query layer for both Power BI and Grafana
- **`createOrReplace()` over SQL DDL:** Iceberg tables are created via the DataFrame API (`createOrReplace()`) rather than SQL `CREATE TABLE` statements, to avoid Nessie stale reference conflicts

---

## Project Context

This repository is my individual contribution to the **Egyptian Investment Intelligence Platform** — a team project combining a data lakehouse with a RAG-based investment recommendation engine. My scope covers the lakehouse foundation: Iceberg table design, Nessie catalog management, Spark ingestion jobs (Bronze & Silver), S3 storage architecture, and Dremio query layer setup.
