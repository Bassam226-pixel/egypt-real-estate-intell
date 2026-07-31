from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session

RAW_FILE = "fundamentals_all.csv"
TICKER_SUFFIX = r"\.CA"


def clean_fundamentals(spark: SparkSession) -> DataFrame:
    df = (
        io.read_csv(spark, RAW_FILE)
        .withColumn("ticker", F.regexp_replace(F.col("Symbol"), TICKER_SUFFIX, ""))
        .withColumn("name", F.trim(F.col("Name")))
        .withColumn("sector", F.trim(F.col("Sector")))
        .withColumn("industry", F.trim(F.col("Industry")))
        .withColumn("country", F.trim(F.col("Country")))
        .withColumn("currency", F.trim(F.col("Currency")))
        .withColumn("exchange", F.trim(F.col("Exchange")))
        .withColumn("market_cap", F.col("MarketCap").cast("long"))
        .withColumn("trailing_pe", F.col("TrailingPE").cast("double"))
        .withColumn("forward_pe", F.col("ForwardPE").cast("double"))
        .withColumn("price_to_book", F.col("PriceToBook").cast("double"))
        .withColumn("eps", F.col("EPS").cast("double"))
        .withColumn("dividend_yield", F.col("DividendYield").cast("double"))
        .withColumn("beta", F.col("Beta").cast("double"))
        .withColumn("fifty_two_week_high", F.col("FiftyTwoWeekHigh").cast("double"))
        .withColumn("fifty_two_week_low", F.col("FiftyTwoWeekLow").cast("double"))
        .withColumn("employees", F.col("Employees").cast("int"))
        .dropDuplicates(["ticker"])
    )

    # ROE proxy from the P/B / P/E identity: (Price/BVPS)/(Price/EPS) = EPS/BVPS = ROE.
    # Sidelining needing book value or shares outstanding, neither of which is in this feed.
    df = df.withColumn(
        "roe_proxy",
        F.when(
            F.col("trailing_pe").isNotNull() & (F.col("trailing_pe") != 0),
            F.col("price_to_book") / F.col("trailing_pe"),
        ),
    )

    return df.select(
        "ticker", "name", "sector", "industry", "country", "currency", "exchange",
        "market_cap", "trailing_pe", "forward_pe", "price_to_book", "eps",
        "dividend_yield", "beta", "fifty_two_week_high", "fifty_two_week_low",
        "employees", "roe_proxy",
    )


def clean_stock_quotes(spark: SparkSession) -> DataFrame:
    return (
        io.read_csv(spark, "live_quotes_all.csv")
        .withColumn("ticker", F.regexp_replace(F.col("Symbol"), TICKER_SUFFIX, ""))
        .withColumn("previous_close", F.col("previousClose").cast("double"))
        .withColumn("open", F.col("Open").cast("double"))
        .withColumn("day_high", F.col("dayHigh").cast("double"))
        .withColumn("day_low", F.col("dayLow").cast("double"))
        .withColumn("close", F.col("Close").cast("double"))
        .withColumn("volume", F.col("Volume").cast("long"))
        .withColumn("change", F.col("Change").cast("double"))
        .withColumn("change_pct", F.col("Change_pct").cast("double"))
        .withColumn("market_cap", F.col("MarketCap").cast("long"))
        .withColumn("currency", F.trim(F.col("Currency")))
        .withColumn("exchange", F.trim(F.col("Exchange")))
        .withColumn("quote_ts", F.to_timestamp(F.col("Timestamp")))
        .select(
            "ticker", "previous_close", "open", "day_high", "day_low", "close",
            "volume", "change", "change_pct", "market_cap", "currency", "exchange", "quote_ts",
        )
    )


def clean_egx30_index(spark: SparkSession) -> DataFrame:
    df = (
        io.read_csv(spark, "EGX30_index.csv")
        .withColumn("trade_date", F.to_date(F.col("Date")))
        .withColumn("open", F.col("Open").cast("double"))
        .withColumn("high", F.col("High").cast("double"))
        .withColumn("low", F.col("Low").cast("double"))
        .withColumn("close", F.col("Close").cast("double"))
        .withColumn("volume", F.col("Volume").cast("long"))
        .dropDuplicates(["trade_date"])
    )

    by_date = Window.orderBy("trade_date")
    prev_close = F.lag("close").over(by_date)
    return df.withColumn("daily_return", F.col("close") / prev_close - F.lit(1.0)).select(
        "trade_date", "open", "high", "low", "close", "volume", "daily_return",
    )


def run() -> None:
    spark = get_spark_session("clean_fundamentals")
    ensure_namespaces(spark)
    io.write_table(io.add_metadata(clean_fundamentals(spark), RAW_FILE), "silver", "fundamentals")
    io.write_table(io.add_metadata(clean_stock_quotes(spark), "live_quotes_all.csv"), "silver", "stock_quotes")
    io.write_table(io.add_metadata(clean_egx30_index(spark), "EGX30_index.csv"), "silver", "egx30_index")


if __name__ == "__main__":
    run()
