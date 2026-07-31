from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session


def _index_snapshot(spark: SparkSession) -> DataFrame:
    latest = io.read_table(spark, "silver", "egx30_index").orderBy(F.col("trade_date").desc()).limit(1)
    return latest.select(
        F.lit("index").alias("category"),
        F.lit("EGX30").alias("symbol"),
        F.col("trade_date").alias("as_of_date"),
        F.expr(
            "stack(2, "
            "'close', cast(close as double), 'points', "
            "'daily_return_pct', daily_return * 100, 'pct'"
            ") as (metric, value, unit)"
        ),
    )


def _metals_spot_snapshot(spark: SparkSession) -> DataFrame:
    spot = io.read_table(spark, "silver", "metals").filter(F.col("kind") == "spot")
    return spot.select(
        F.lit("metal_spot").alias("category"),
        F.col("metal").alias("symbol"),
        F.col("price_date").alias("as_of_date"),
        F.expr(
            "stack(3, "
            "'price_usd', price_usd, 'USD/g', "
            "'price_egp', price_egp, 'EGP/g', "
            "'change_pct', change_pct, 'pct'"
            ") as (metric, value, unit)"
        ),
    )


def _fx_snapshot(spark: SparkSession) -> DataFrame:
    fx = io.read_table(spark, "silver", "fx_rates")
    latest = Window.partitionBy("currency").orderBy(F.col("rate_date").desc())
    fx = fx.withColumn("_rn", F.row_number().over(latest)).filter(F.col("_rn") == 1).drop("_rn")
    return fx.select(
        F.lit("fx").alias("category"),
        F.col("currency").alias("symbol"),
        F.col("rate_date").alias("as_of_date"),
        F.expr(
            "stack(2, "
            "'usd_per_unit', rate, 'USD', "
            "'units_per_usd', units_per_usd, 'ratio'"
            ") as (metric, value, unit)"
        ),
    )


def market_snapshot(spark: SparkSession) -> DataFrame:
    return (
        _index_snapshot(spark)
        .unionByName(_metals_spot_snapshot(spark))
        .unionByName(_fx_snapshot(spark))
        .select("category", "symbol", "metric", "value", "unit", "as_of_date")
    )


def run() -> None:
    spark = get_spark_session("market_snapshot")
    ensure_namespaces(spark)
    df = io.add_metadata(market_snapshot(spark), "silver.egx30_index+silver.metals+silver.fx_rates")
    io.write_table(df, "gold", "market_snapshot")


if __name__ == "__main__":
    run()
