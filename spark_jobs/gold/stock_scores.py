from pyspark.sql import Column, DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session


def _min_max_normalize(column: str) -> Column:
    # Cross-sectional min-max over every ticker (no partition -> whole frame) -> 0..1 score.
    whole_frame = Window.partitionBy().rowsBetween(Window.unboundedPreceding, Window.unboundedFollowing)
    lo, hi = F.min(column).over(whole_frame), F.max(column).over(whole_frame)
    return F.when(hi > lo, (F.col(column) - lo) / (hi - lo))


def _liquidity(spark: SparkSession) -> DataFrame:
    # silver.stock_eod's volume is 0 for every historical row (a gap in that source
    # scrape), so a rolling average from it would always be zero. stock_quotes (the
    # live snapshot) has real volume, just for a single day rather than a trailing window.
    quotes = io.read_table(spark, "silver", "stock_quotes")
    return quotes.select("ticker", (F.col("volume") * F.col("close")).alias("dollar_volume_latest"))


def stock_scores(spark: SparkSession) -> DataFrame:
    fundamentals = io.read_table(spark, "silver", "fundamentals").select(
        "ticker", "roe_proxy", "dividend_yield"
    )
    returns_vol = io.read_table(spark, "gold", "stock_returns_vol")
    latest_date = returns_vol.select(F.max("trade_date").alias("d")).first()["d"]
    latest_returns = returns_vol.filter(F.col("trade_date") == latest_date).select(
        "ticker", "momentum_3m", "vol_90d"
    )
    liquidity = _liquidity(spark)

    df = fundamentals.join(latest_returns, "ticker", "left").join(liquidity, "ticker", "left")

    df = (
        df.withColumn("norm_roe", _min_max_normalize("roe_proxy"))
        .withColumn("div_yield_score", _min_max_normalize("dividend_yield"))
        .withColumn("_vol_norm", _min_max_normalize("vol_90d"))
        .withColumn("vol_score", F.lit(1.0) - F.col("_vol_norm"))  # lower vol -> higher score
        .withColumn("liquidity_score", _min_max_normalize("dollar_volume_latest"))
        .withColumn("as_of_date", F.lit(latest_date))
        .drop("_vol_norm")
    )

    return df.select(
        "ticker", "as_of_date", "roe_proxy", "norm_roe", "dividend_yield", "div_yield_score",
        "momentum_3m", "vol_90d", "vol_score", "dollar_volume_latest", "liquidity_score",
    )


def run() -> None:
    spark = get_spark_session("stock_scores")
    ensure_namespaces(spark)
    df = io.add_metadata(stock_scores(spark), "silver.fundamentals+silver.stock_quotes+gold.stock_returns_vol")
    io.write_table(df, "gold", "stock_scores")


if __name__ == "__main__":
    run()
