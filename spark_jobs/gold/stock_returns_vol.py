from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session

# ~3 trading months. History is only ~118 trading days, so the original skeleton's
# 126-day (6mo) lag would return all-null -- see Layer_Tasks delta note.
MOMENTUM_LAG_DAYS = 63
VOL_WINDOW_DAYS = 90
TRADING_DAYS_PER_YEAR = 252


def stock_returns_vol(spark: SparkSession) -> DataFrame:
    df = io.read_table(spark, "silver", "stock_eod")

    by_ticker = Window.partitionBy("ticker").orderBy("trade_date")
    momentum_3m = F.col("adj_close") / F.lag("adj_close", MOMENTUM_LAG_DAYS).over(by_ticker) - F.lit(1.0)

    trailing_90 = by_ticker.rowsBetween(-(VOL_WINDOW_DAYS - 1), 0)
    vol_90d = F.stddev("daily_return").over(trailing_90) * F.lit(TRADING_DAYS_PER_YEAR ** 0.5)

    return df.select(
        "ticker", "trade_date", "close", "adj_close", "volume", "daily_return",
        momentum_3m.alias("momentum_3m"),
        vol_90d.alias("vol_90d"),
    )


def run() -> None:
    spark = get_spark_session("stock_returns_vol")
    ensure_namespaces(spark)
    df = io.add_metadata(stock_returns_vol(spark), "silver.stock_eod")
    io.write_table(df, "gold", "stock_returns_vol")


if __name__ == "__main__":
    run()
