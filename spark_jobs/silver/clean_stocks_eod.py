from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session

RAW_FILE = "batch_eod_all_stocks.csv"
TICKER_SUFFIX = r"\.CA$"


def clean_stocks_eod(spark: SparkSession) -> DataFrame:
    df = (
        io.read_csv(spark, RAW_FILE)
        .withColumn("ticker", F.regexp_replace(F.col("Symbol"), TICKER_SUFFIX, ""))
        .withColumn("trade_date", F.to_date(F.col("Date")))
        .withColumn("open", F.col("Open").cast("double"))
        .withColumn("high", F.col("High").cast("double"))
        .withColumn("low", F.col("Low").cast("double"))
        .withColumn("close", F.col("Close").cast("double"))
        .withColumn("volume", F.col("Volume").cast("long"))
        .withColumn("dividends", F.col("Dividends").cast("double"))
        .withColumn("stock_splits", F.col("Stock_Splits").cast("double"))
    )

    # dropDuplicates has no defined tie-break, so a re-run on unchanged input could pick a
    # different arbitrary row for the same (ticker, trade_date). Break ties deterministically.
    dedup_order = Window.partitionBy("ticker", "trade_date").orderBy(
        F.col("close").desc(), F.col("volume").desc()
    )
    df = (
        df.withColumn("_rn", F.row_number().over(dedup_order))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )

    by_ticker_asc = Window.partitionBy("ticker").orderBy("trade_date")
    forward = by_ticker_asc.rowsBetween(1, Window.unboundedFollowing)
    prev_close = F.lag("close").over(by_ticker_asc)

    # Back-adjust historical closes for any split/dividend that happens *after* them, so a
    # chart of adj_close has no artificial jump on the split/dividend date. Spark has no
    # windowed running-product aggregate, so the cumulative forward factor is done via
    # log-sum-exp (all ratios are positive: 1.0 when nothing happened that day).
    # A stock_splits value of e.g. 2.0 means a 2-for-1 split: pre-split prices must be
    # *divided* by the ratio (not multiplied) so historical adj_close shrinks to match.
    split_ratio = F.when(F.col("stock_splits") != 0, F.lit(1.0) / F.col("stock_splits")).otherwise(F.lit(1.0))
    dividend_ratio = F.when(
        (F.col("dividends") != 0) & prev_close.isNotNull() & (prev_close != 0),
        F.lit(1.0) - F.col("dividends") / prev_close,
    ).otherwise(F.lit(1.0))

    df = (
        df.withColumn("_log_factor", F.log(split_ratio) + F.log(dividend_ratio))
        .withColumn("_forward_factor", F.coalesce(F.exp(F.sum("_log_factor").over(forward)), F.lit(1.0)))
        .withColumn("adj_close", F.col("close") * F.col("_forward_factor"))
        .withColumn("daily_return", F.col("close") / prev_close - F.lit(1.0))
        .drop("_log_factor", "_forward_factor")
    )

    return df.select(
        "ticker", "trade_date", "open", "high", "low", "close", "adj_close",
        "volume", "dividends", "stock_splits", "daily_return",
    )


def run() -> None:
    spark = get_spark_session("clean_stocks_eod")
    ensure_namespaces(spark)
    df = io.add_metadata(clean_stocks_eod(spark), RAW_FILE)
    io.write_table(df, "silver", "stock_eod")


if __name__ == "__main__":
    run()
