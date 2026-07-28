from functools import reduce

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session
from spark_jobs.gold.gold_metal_roi import daily_metal_prices

VOL_WINDOW_DAYS = 90
ANNUALIZED_VOL_FACTOR = 252 ** 0.5

ASSET_SCORE_SCHEMA = (
    "asset_class string, roi_proxy double, roi_proxy_label string, "
    "vol_proxy double, vol_proxy_label string, as_of_date date"
)


def _stocks_row(spark: SparkSession) -> DataFrame:
    returns_vol = io.read_table(spark, "gold", "stock_returns_vol")
    latest_date = returns_vol.select(F.max("trade_date").alias("d")).first()["d"]
    agg = (
        returns_vol.filter(F.col("trade_date") == latest_date)
        .agg(F.avg("momentum_3m").alias("roi"), F.avg("vol_90d").alias("vol"))
        .first()
    )
    return spark.createDataFrame(
        [("stocks", agg["roi"], "equal_weight_trailing_3m_return",
          agg["vol"], "equal_weight_annualized_90d_price_vol", latest_date)],
        ASSET_SCORE_SCHEMA,
    )


def _metal_row(spark: SparkSession, metal: str, daily: DataFrame, roi: DataFrame) -> DataFrame:
    by_date = Window.orderBy("price_date")
    trailing = by_date.rowsBetween(-(VOL_WINDOW_DAYS - 1), 0)
    latest_vol = (
        daily.filter(F.col("metal") == metal)
        .withColumn("_ret", F.col("price_egp") / F.lag("price_egp").over(by_date) - 1)
        .withColumn("_vol", F.stddev("_ret").over(trailing) * F.lit(ANNUALIZED_VOL_FACTOR))
        .orderBy(F.col("price_date").desc())
        .select("_vol")
        .first()
    )
    roi_row = roi.filter(F.col("metal") == metal).select("roi_1yr_egp", "latest_date").first()
    return spark.createDataFrame(
        [(
            metal,
            roi_row["roi_1yr_egp"] if roi_row else None,
            "trailing_1yr_return",
            latest_vol["_vol"] if latest_vol else None,
            "annualized_90d_price_vol",
            roi_row["latest_date"] if roi_row else None,
        )],
        ASSET_SCORE_SCHEMA,
    )


def _real_estate_row(spark: SparkSession) -> DataFrame:
    sales = io.read_table(spark, "silver", "re_sales")
    dispersion = sales.agg(
        (F.stddev("price_per_sqm_egp") / F.avg("price_per_sqm_egp")).alias("cv"),
        F.max(F.to_date("scraped_at")).alias("as_of_date"),
    ).first()
    yield_avg = io.read_table(spark, "gold", "re_district_metrics").agg(
        F.avg("gross_yield_pct").alias("y")
    ).first()["y"]
    return spark.createDataFrame(
        [(
            "real_estate", yield_avg, "avg_district_gross_rental_yield_pct",
            dispersion["cv"], "cross_sectional_price_per_sqm_dispersion", dispersion["as_of_date"],
        )],
        ASSET_SCORE_SCHEMA,
    )


def asset_scores(spark: SparkSession) -> DataFrame:
    # Stocks and metals have genuine daily price history, so their roi/vol are a real
    # trailing return and time-series volatility. RE listings are a single snapshot with
    # no price history, so it borrows district rental yield as its "return" and the
    # cross-sectional dispersion of price/m2 as its "risk" -- the closest available
    # proxies, not the same statistic as the other rows. Hence the *_label columns
    # spelling out what each row's numbers actually mean.
    #
    # ROI and district-yield are read from the already-published gold tables rather
    # than recomputed via function import: this job runs after both in the DAG anyway,
    # and re-deriving them here doubled the S3 traffic (silver.metals scanned twice,
    # re_district_metrics re-aggregated from scratch) for no benefit.
    daily = daily_metal_prices(spark).filter(F.col("metal").isin("gold", "silver"))
    roi = io.read_table(spark, "gold", "gold_metal_roi")

    rows = [
        _stocks_row(spark),
        _metal_row(spark, "gold", daily, roi),
        _metal_row(spark, "silver", daily, roi),
        _real_estate_row(spark),
    ]
    # Each row above is its own single-row DataFrame at Spark's default parallelism,
    # so the union lands in defaultParallelism-times-4 mostly-empty partitions (e.g.
    # 32 for 4 rows at parallelism 8). Writing that many partitions for a 4-row table
    # fires off a burst of near-simultaneous S3 connections during the Iceberg commit,
    # which was intermittently overwhelming the container's DNS resolver.
    return reduce(DataFrame.unionByName, rows).coalesce(1)


def run() -> None:
    spark = get_spark_session("asset_scores")
    ensure_namespaces(spark)
    df = io.add_metadata(
        asset_scores(spark),
        "gold.stock_returns_vol+gold.gold_metal_roi+silver.re_sales+gold.re_district_metrics",
    )
    io.write_table(df, "gold", "asset_scores")


if __name__ == "__main__":
    run()
