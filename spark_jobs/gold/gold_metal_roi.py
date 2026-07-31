from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session

HORIZON_YEARS = [1, 3, 5, 10]
METALS = ["gold", "silver"]


def daily_metal_prices(spark: SparkSession) -> DataFrame:
    """One representative (metal, price_date) row per day, collapsed from the
    multi-session authority_prices history. Reused by asset_scores.py for volatility."""
    history = io.read_table(spark, "silver", "metals").filter(F.col("kind") == "history")
    session_priority = F.when(F.col("session") == "pm", 1).when(F.col("session") == "am", 2).otherwise(3)
    by_session = Window.partitionBy("metal", "price_date").orderBy(session_priority)
    return (
        history.withColumn("_rn", F.row_number().over(by_session))
        .filter(F.col("_rn") == 1)
        .select("metal", "price_date", "price_usd", "price_egp")
    )


def _asof_horizon(daily: DataFrame, latest: DataFrame, years: int) -> DataFrame:
    target = latest.select("metal", "latest_date").withColumn(
        "target_date", F.expr(f"add_months(latest_date, {-12 * years})")
    )
    candidates = target.join(daily, "metal").where(F.col("price_date") <= F.col("target_date"))
    nearest = Window.partitionBy("metal").orderBy(F.col("price_date").desc())
    return (
        candidates.withColumn("_rn", F.row_number().over(nearest))
        .filter(F.col("_rn") == 1)
        .select(
            "metal",
            F.col("price_usd").alias(f"_base_usd_{years}"),
            F.col("price_egp").alias(f"_base_egp_{years}"),
        )
    )


def gold_metal_roi(spark: SparkSession) -> DataFrame:
    daily = daily_metal_prices(spark).filter(F.col("metal").isin(*METALS))

    latest_window = Window.partitionBy("metal").orderBy(F.col("price_date").desc())
    latest = (
        daily.withColumn("_rn", F.row_number().over(latest_window))
        .filter(F.col("_rn") == 1)
        .select(
            "metal",
            F.col("price_date").alias("latest_date"),
            F.col("price_usd").alias("latest_price_usd"),
            F.col("price_egp").alias("latest_price_egp"),
        )
    )

    result = latest
    for years in HORIZON_YEARS:
        base = _asof_horizon(daily, latest, years)
        result = result.join(base, "metal", "left")
        result = (
            result.withColumn(f"roi_{years}yr_usd", F.col("latest_price_usd") / F.col(f"_base_usd_{years}") - 1)
            .withColumn(f"roi_{years}yr_egp", F.col("latest_price_egp") / F.col(f"_base_egp_{years}") - 1)
            .drop(f"_base_usd_{years}", f"_base_egp_{years}")
        )

    roi_columns = [c for years in HORIZON_YEARS for c in (f"roi_{years}yr_usd", f"roi_{years}yr_egp")]
    return result.select("metal", "latest_date", "latest_price_usd", "latest_price_egp", *roi_columns)


def run() -> None:
    spark = get_spark_session("gold_metal_roi")
    ensure_namespaces(spark)
    df = io.add_metadata(gold_metal_roi(spark), "silver.metals")
    io.write_table(df, "gold", "gold_metal_roi")


if __name__ == "__main__":
    run()
