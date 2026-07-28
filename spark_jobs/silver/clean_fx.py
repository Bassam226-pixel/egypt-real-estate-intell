from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session

RAW_FILE = "currency_rates.csv"
MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CNY", "SAR", "AED"]


def clean_fx_rates(spark: SparkSession) -> DataFrame:
    df = (
        io.read_csv(spark, RAW_FILE)
        .withColumn("currency", F.trim(F.col("currency")))
        .withColumn("rate", F.col("rate").cast("double"))
        .withColumn("rate_ts", F.to_timestamp(F.col("time")))
        .withColumn("rate_date", F.to_date(F.col("rate_ts")))
        .filter(F.col("currency").isin(*MAJOR_CURRENCIES, "EGP"))
    )

    # The source is scraped multiple times a day (near-duplicate snapshots seconds apart);
    # collapse to the grain the rest of Silver expects: one rate per currency per day.
    latest_per_day = Window.partitionBy("currency", "rate_date").orderBy(F.col("rate_ts").desc())
    df = (
        df.withColumn("_rn", F.row_number().over(latest_per_day))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )

    return df.withColumn("units_per_usd", F.lit(1.0) / F.col("rate")).select(
        "currency", "rate_date", "rate", "units_per_usd"
    )


def latest_egp_rate(spark: SparkSession) -> float:
    """USD value of 1 EGP, as of the most recent day in the source. Shared with
    clean_metals.py and clean_re_rentals.py so every USD->EGP conversion in Silver
    uses one consistent rate."""
    row = (
        clean_fx_rates(spark)
        .filter(F.col("currency") == "EGP")
        .orderBy(F.col("rate_date").desc())
        .select("rate")
        .first()
    )
    if row is None:
        raise ValueError("No EGP rate found in currency_rates.csv")
    return row["rate"]


def run() -> None:
    spark = get_spark_session("clean_fx")
    ensure_namespaces(spark)
    df = io.add_metadata(clean_fx_rates(spark), RAW_FILE)
    io.write_table(df, "silver", "fx_rates")


if __name__ == "__main__":
    run()
