# Egyptian Investment Intelligence Platform

A data lakehouse project built for Egyptian investment analysis, combining EGX stock market data, gold and silver commodity prices, currency exchange rates, and real estate listings into a unified analytical platform with a RAG-based investment recommendation engine.

---

## Architecture Overview

```
Raw Source Files (CSV, JSON)
        |
        v
AWS S3 (raw/)
        |
        v  Apache Spark + Apache Iceberg
Bronze Layer (s3://my-icebergdatalake/bronze/)
        |
        v  Apache Spark + Apache Iceberg
Silver Layer (s3://my-icebergdatalake/silver/)
        |
        v  Apache Spark + Apache Iceberg
Gold Layer   (s3://my-icebergdatalake/gold/)
        |
   +----+----+
   |         |
   v         v
Dremio    RAG Pipeline
Power BI  (FAISS + LLM)
Grafana
```

**Catalog:** Project Nessie (Iceberg catalog with Git-like branching)  
**Storage:** AWS S3 (eu-north-1, Stockholm region)  
**Query Engine:** Dremio (SQL + Power BI + Grafana connectivity)

---



---

## Data Sources

| Source | Format | Description |
|---|---|---|
| batch_eod_all_stocks.csv | CSV | Daily OHLCV data for 10 EGX stocks |
| EGX30_index.csv | CSV | EGX30 benchmark index daily prices |
| fundamentals_all.csv | CSV | Company financials: P/E, MarketCap, Beta, EPS |
| live_quotes_all.csv | CSV | Real-time stock quotes with change % |
| authority_prices.csv | CSV | Historical LBMA gold and silver prices since 1968 |
| currency_rates.csv | CSV | Exchange rates for world currencies |
| spot_prices.csv | CSV | Current gold and silver spot prices with bid/ask |
| data.json | JSON | Real estate listings from Bayut.eg |
| data_enriched.json | JSON | Enriched real estate listings from PropertyFinder.eg |

---

## Medallion Architecture

### Bronze Layer (9 tables)
Raw ingestion with no transformations. Every record from the source files lands here exactly as-is, with two metadata columns added: _ingested_at and _source_file.

| Table | Rows |
|---|---|
| bronze.stocks_eod | 1,230 |
| bronze.egx30_index | 123 |
| bronze.fundamentals | 10 |
| bronze.live_quotes | 10 |
| bronze.gold_silver_prices | 80,638 |
| bronze.currency_rates | 348 |
| bronze.spot_prices | 8 |
| bronze.real_estate | 107 |
| bronze.real_estate_enriched | 300 |

### Silver Layer (9 tables)
Cleaned, typed, and standardized data ready for the gold layer. Key transformations per table:

- stocks_eod: Snake_case column names, date cast, Dividends and Stock_Splits dropped, deduplication on (symbol, date)
- egx30_index: Snake_case, date cast, deduplication on date
- fundamentals: Website, Country, Exchange, Currency columns dropped (constant values)
- live_quotes: Currency and Exchange dropped, floats rounded to 4 decimal places
- gold_silver_prices: Metal uppercased, date cast, deduplication on (date, metal, session)
- currency_rates: Filtered from 348 currencies to 10 investment-relevant ones (USD, EUR, GBP, JPY, CNY, SAR, AED, EGP, CHF, CAD)
- spot_prices: Metal uppercased, all price fields rounded to 6 decimal places
- real_estate_propertyfinder: Area parsed from '165 sqm' to 165.0, price parsed from '5,900,000' to 5900000.0, image/link/redundant columns dropped, amenities array converted to string, deduplication on listing_id
- real_estate_unified: Final unified real estate table using PropertyFinder only (Bayut data was too sparse for analysis)

### Gold Layer ()
Business-level aggregations and enriched tables for Power BI, Grafana, and the RAG pipeline.

---

## Tech Stack

| Tool | Version | Purpose |
|---|---|---|
| Apache Spark | 3.3 | Data processing engine |
| Apache Iceberg | 1.3.0 | Open table format |
| Project Nessie | 0.67.0 | Iceberg catalog with branching |
| AWS S3 | - | Data lake storage (eu-north-1) |
| Dremio | OSS latest | SQL query engine and BI connectivity |
| Docker | - | Container orchestration |

---

## Infrastructure Setup

### Prerequisites
- Docker Desktop installed
- AWS account with S3 bucket named my-icebergdatalake in eu-north-1
- AWS IAM user with S3 read/write permissions

### Required JARs
Before running any notebook, copy these JARs into PySpark's jars directory inside the notebook container:

```
bundle-2.20.18.jar          (AWS SDK v2 - for Iceberg S3FileIO)
hadoop-aws-3.3.2.jar        (Hadoop S3A filesystem)
aws-java-sdk-bundle-1.12.262.jar  (AWS SDK v1 - required by hadoop-aws)
```

Download command (run inside the notebook container):
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
Create a .env file in the project root:
```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

Note: Never commit the .env file to Git. It is listed in .gitignore.

### Starting the Stack
```bash
docker compose up -d
```

Services:
- Jupyter Notebook: http://localhost:8888
- Nessie API: http://localhost:19120/api/v1
- Dremio UI: http://localhost:9047

### Connecting Dremio to Nessie
1. Open Dremio at http://localhost:9047
2. Sources -> Add Source -> Nessie
3. Endpoint URL: http://nessie:19120/api/v1
4. Authentication: None
5. Default Branch: main
6. Under Storage: add your AWS credentials and region eu-north-1

---

## Running the Pipeline

Run the notebooks in order:

```
notebooks/01_bronze_layer.ipynb   - Raw ingestion
notebooks/02_silver_layer.ipynb   - Cleaning and typing
notebooks/03_gold_layer.ipynb     - Business aggregations (Omar)
```

---

## S3 Bucket Structure

```
s3://my-icebergdatalake/
    raw/                    Source files uploaded before bronze run
    bronze/                 Iceberg tables - raw data
    silver/                 Iceberg tables - cleaned data
    gold/                   Iceberg tables - aggregated data
    iceberg-warehouse/      Nessie internal metadata
```

---

## Nessie Branching Workflow

Use Nessie branches to safely develop gold layer transformations without affecting main:

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

---

## Important Notes

- s3a:// is used for reading raw CSV and JSON files (Spark Hadoop filesystem)
- s3:// is used for Iceberg table locations (Iceberg S3FileIO)
- The bundle-2.20.18.jar must be placed directly in PySpark's jars/ directory, not passed via spark.jars, because it is too large to broadcast over the Spark internal network
- Do not use AWS Glue for gold layer jobs as it uses a different catalog (Glue Data Catalog) and is incompatible with the Nessie catalog used by this project
- Dremio is the recommended query engine for both Power BI and Grafana. Grafana cannot read Parquet/Iceberg from S3 directly and requires Dremio as an intermediary
