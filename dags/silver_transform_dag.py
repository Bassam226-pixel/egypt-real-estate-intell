
"""
silver_transform_dag
----------------------
Cleans each raw source into a typed, deduped Iceberg table under
nessie.silver.*. Triggered automatically once every raw dataset from
bronze_ingestion_dag has been updated (Dataset-based scheduling -- see
the `schedule` argument below).

Dependency note: clean_metals and clean_re_rentals both recompute the
latest EGP/USD rate directly from currency_rates.csv (via
clean_fx.latest_egp_rate) rather than reading the already-published
silver.fx_rates table -- so there's no Iceberg-level dependency on the
clean_fx *task*, only on load_fx's raw file already being in S3, which
the DAG-level schedule already guarantees. All 6 tasks below are
therefore independent and safe to run in parallel from a data standpoint.

max_active_tasks=2 note: running all 6 in full parallel was tested and
failed every task except clean_re_sales with
"PySparkRuntimeError: [JAVA_GATEWAY_EXITED] Java gateway process exited
before sending its port number." -- 6 simultaneous Spark/JVM sessions
exhausted the Airflow worker container's memory. Capping concurrency to
2 avoids that; raise this once the container has more RAM available.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator

from spark_jobs.silver import (
    clean_stocks_eod,
    clean_fx,
    clean_metals,
    clean_fundamentals,
    clean_re_sales,
    clean_re_rentals,
)

# Same URIs as in bronze_ingestion_dag.py -- Airflow matches datasets by URI,
# not by Python object identity, so redefining them here is safe and keeps
# the two DAG files decoupled.
DS_RAW_STOCKS = Dataset("raw://stocks")
DS_RAW_EGX_INDEX = Dataset("raw://egx_index")
DS_RAW_METALS = Dataset("raw://metals")
DS_RAW_FX = Dataset("raw://fx")
DS_RAW_RE_SALES = Dataset("raw://re_sales")
DS_RAW_RE_RENTALS = Dataset("raw://re_rentals")

# Datasets this DAG produces -- gold_transform_dag schedules on these.
DS_SILVER_STOCK_EOD = Dataset("silver://stock_eod")
DS_SILVER_FX_RATES = Dataset("silver://fx_rates")
DS_SILVER_METALS = Dataset("silver://metals")
# clean_fundamentals.run() writes 3 tables (fundamentals, stock_quotes,
# egx30_index) in one job -- one outlet per table it actually produces.
DS_SILVER_FUNDAMENTALS = Dataset("silver://fundamentals")
DS_SILVER_STOCK_QUOTES = Dataset("silver://stock_quotes")
DS_SILVER_EGX30_INDEX = Dataset("silver://egx30_index")
DS_SILVER_RE_SALES = Dataset("silver://re_sales")
DS_SILVER_RE_RENTALS = Dataset("silver://re_rentals")

default_args = {
    "owner": "bassam",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),  # Spark/Iceberg jobs take longer than a plain upload
}

with DAG(
    dag_id="silver_transform_dag",
    description="Clean raw S3 files into typed Iceberg tables under nessie.silver.*",
    default_args=default_args,
    # Waits until ALL 6 raw datasets have been updated at least once since
    # the last run of this DAG -- i.e. until a full bronze_ingestion_dag
    # run has completed. Airflow triggers this DAG automatically then.
    schedule=[
        DS_RAW_STOCKS,
        DS_RAW_EGX_INDEX,
        DS_RAW_METALS,
        DS_RAW_FX,
        DS_RAW_RE_SALES,
        DS_RAW_RE_RENTALS,
    ],
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_tasks=2,  # cap concurrent Spark/JVM sessions -- see docstring above
    tags=["silver", "lakehouse"],
) as dag:

    PythonOperator(
        task_id="clean_stocks_eod",
        python_callable=clean_stocks_eod.run,
        outlets=[DS_SILVER_STOCK_EOD],
    )

    PythonOperator(
        task_id="clean_fx",
        python_callable=clean_fx.run,
        outlets=[DS_SILVER_FX_RATES],
    )

    PythonOperator(
        task_id="clean_metals",
        python_callable=clean_metals.run,
        outlets=[DS_SILVER_METALS],
    )

    PythonOperator(
        task_id="clean_fundamentals",
        python_callable=clean_fundamentals.run,
        outlets=[DS_SILVER_FUNDAMENTALS, DS_SILVER_STOCK_QUOTES, DS_SILVER_EGX30_INDEX],
    )

    PythonOperator(
        task_id="clean_re_sales",
        python_callable=clean_re_sales.run,
        outlets=[DS_SILVER_RE_SALES],
    )

    PythonOperator(
        task_id="clean_re_rentals",
        python_callable=clean_re_rentals.run,
        outlets=[DS_SILVER_RE_RENTALS],
    )

    # No >> chains -- all 6 are data-independent (see module docstring above).
    # max_active_tasks=2 controls concurrency instead of task dependencies.