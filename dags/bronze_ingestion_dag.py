
from datetime import datetime, timedelta

from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator

from ingestion.loaders import (
    load_stocks,
    load_egx_index,
    load_metals,
    load_fx,
    load_re_sales,
    load_re_rentals,
)

# One dataset per loader. silver_transform_dag's schedule waits on all of these.
DS_RAW_STOCKS = Dataset("raw://stocks")          # batch_eod, fundamentals, live_quotes
DS_RAW_EGX_INDEX = Dataset("raw://egx_index")    # EGX30_index.csv
DS_RAW_METALS = Dataset("raw://metals")          # authority_prices, spot_prices
DS_RAW_FX = Dataset("raw://fx")                  # currency_rates.csv
DS_RAW_RE_SALES = Dataset("raw://re_sales")      # aqarmap/propertyfinder/bayut json
DS_RAW_RE_RENTALS = Dataset("raw://re_rentals")  # rental_listings.csv

default_args = {
    "owner": "bassam",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="bronze_ingestion_dag",
    description="Upload local source files to S3 raw/ (no Iceberg tables -- plain passthrough)",
    default_args=default_args,
    schedule="0 3 * * *",  # daily 03:00 -- adjust to match how often source files actually refresh
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["bronze", "ingestion", "lakehouse"],
) as dag:

    PythonOperator(
        task_id="load_stocks",
        python_callable=load_stocks.run,
        outlets=[DS_RAW_STOCKS],
    )

    PythonOperator(
        task_id="load_egx_index",
        python_callable=load_egx_index.run,
        outlets=[DS_RAW_EGX_INDEX],
    )

    PythonOperator(
        task_id="load_metals",
        python_callable=load_metals.run,
        outlets=[DS_RAW_METALS],
    )

    PythonOperator(
        task_id="load_fx",
        python_callable=load_fx.run,
        outlets=[DS_RAW_FX],
    )

    PythonOperator(
        task_id="load_re_sales",
        python_callable=load_re_sales.run,
        outlets=[DS_RAW_RE_SALES],
    )

    PythonOperator(
        task_id="load_re_rentals",
        python_callable=load_re_rentals.run,
        outlets=[DS_RAW_RE_RENTALS],
    )

    # No >> chains here on purpose -- all 6 loaders are independent and safe
    # to run in parallel (Airflow will do so automatically).
