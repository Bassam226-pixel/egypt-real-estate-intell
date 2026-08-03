"""
gold_transform_dag
--------------------
Builds the 7 Gold analytics marts under nessie.gold.*. Triggered
automatically once every Silver dataset has been updated.

Unlike bronze/silver, Gold has REAL runtime dependencies -- several jobs
call spark_jobs.common.io.read_table() to read another Gold job's
already-published output, not just a raw/silver file. Those are encoded
below as explicit task dependencies (>>), confirmed by reading each
module's source:

  Level 1 (read Silver only, independent of each other):
    stock_returns_vol, gold_metal_roi, re_sale_metrics, market_snapshot

  Level 2:
    stock_scores        -- reads gold.stock_returns_vol
    re_district_metrics -- reads silver.re_rentals + recomputes
                            re_sale_metrics's logic in-process (no Iceberg
                            read of gold.re_sale_metrics, but kept after it
                            here for logical grouping/observability)

  Level 3:
    asset_scores -- reads gold.stock_returns_vol, gold.gold_metal_roi,
                     gold.re_district_metrics, and silver.re_sales

Get this order wrong and a job will either read a stale/missing upstream
table or fail outright with a "table not found" error.

max_active_tasks=2 note: the sibling silver_transform_dag ran all 6 of
its tasks in full parallel and every task except one failed with
"PySparkRuntimeError: [JAVA_GATEWAY_EXITED] Java gateway process exited
before sending its port number." -- too many simultaneous Spark/JVM
sessions exhausted the Airflow worker container's memory. Capping
concurrency here too, even though Gold already has some task-level
ordering, since up to 4 Level-1 tasks would otherwise still race in
parallel. Raise this once the container has more RAM available.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator

from spark_jobs.gold import (
    stock_returns_vol,
    gold_metal_roi,
    re_sale_metrics,
    market_snapshot,
    stock_scores,
    re_district_metrics,
    asset_scores,
)

# Same URIs as in silver_transform_dag.py.
DS_SILVER_STOCK_EOD = Dataset("silver://stock_eod")
DS_SILVER_FX_RATES = Dataset("silver://fx_rates")
DS_SILVER_METALS = Dataset("silver://metals")
DS_SILVER_FUNDAMENTALS = Dataset("silver://fundamentals")
DS_SILVER_STOCK_QUOTES = Dataset("silver://stock_quotes")
DS_SILVER_EGX30_INDEX = Dataset("silver://egx30_index")
DS_SILVER_RE_SALES = Dataset("silver://re_sales")
DS_SILVER_RE_RENTALS = Dataset("silver://re_rentals")

# Datasets this DAG produces -- a future quality_gate_dag can schedule on these.
DS_GOLD_STOCK_RETURNS_VOL = Dataset("gold://stock_returns_vol")
DS_GOLD_METAL_ROI = Dataset("gold://gold_metal_roi")
DS_GOLD_RE_SALE_METRICS = Dataset("gold://re_sale_metrics")
DS_GOLD_MARKET_SNAPSHOT = Dataset("gold://market_snapshot")
DS_GOLD_STOCK_SCORES = Dataset("gold://stock_scores")
DS_GOLD_RE_DISTRICT_METRICS = Dataset("gold://re_district_metrics")
DS_GOLD_ASSET_SCORES = Dataset("gold://asset_scores")

default_args = {
    "owner": "bassam",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="gold_transform_dag",
    description="Build Gold analytics marts under nessie.gold.* in dependency order",
    default_args=default_args,
    # Waits until ALL silver datasets have been updated since this DAG's
    # last run -- i.e. until a full silver_transform_dag run has completed.
    schedule=[
        DS_SILVER_STOCK_EOD,
        DS_SILVER_FX_RATES,
        DS_SILVER_METALS,
        DS_SILVER_FUNDAMENTALS,
        DS_SILVER_STOCK_QUOTES,
        DS_SILVER_EGX30_INDEX,
        DS_SILVER_RE_SALES,
        DS_SILVER_RE_RENTALS,
    ],
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_tasks=2,  # cap concurrent Spark/JVM sessions -- see docstring above
    tags=["gold", "lakehouse"],
) as dag:

    # ---- Level 1: independent, read Silver only ----
    t_stock_returns_vol = PythonOperator(
        task_id="stock_returns_vol",
        python_callable=stock_returns_vol.run,
        outlets=[DS_GOLD_STOCK_RETURNS_VOL],
    )

    t_gold_metal_roi = PythonOperator(
        task_id="gold_metal_roi",
        python_callable=gold_metal_roi.run,
        outlets=[DS_GOLD_METAL_ROI],
    )

    t_re_sale_metrics = PythonOperator(
        task_id="re_sale_metrics",
        python_callable=re_sale_metrics.run,
        outlets=[DS_GOLD_RE_SALE_METRICS],
    )

    t_market_snapshot = PythonOperator(
        task_id="market_snapshot",
        python_callable=market_snapshot.run,
        outlets=[DS_GOLD_MARKET_SNAPSHOT],
    )

    # ---- Level 2 ----
    t_stock_scores = PythonOperator(
        task_id="stock_scores",
        python_callable=stock_scores.run,
        outlets=[DS_GOLD_STOCK_SCORES],
    )

    t_re_district_metrics = PythonOperator(
        task_id="re_district_metrics",
        python_callable=re_district_metrics.run,
        outlets=[DS_GOLD_RE_DISTRICT_METRICS],
    )

    # ---- Level 3 ----
    t_asset_scores = PythonOperator(
        task_id="asset_scores",
        python_callable=asset_scores.run,
        outlets=[DS_GOLD_ASSET_SCORES],
    )

    # Real dependency edges, per the module docstring above.
    t_stock_returns_vol >> t_stock_scores
    t_re_sale_metrics >> t_re_district_metrics
    [t_stock_returns_vol, t_gold_metal_roi, t_re_district_metrics] >> t_asset_scores

    # t_market_snapshot has no downstream Gold dependents -- it stays
    # parallel to everything else, subject to max_active_tasks=2 above.
