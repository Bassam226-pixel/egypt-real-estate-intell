from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session

RAW_FILE = "currency_rates.csv"
MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CNY", "SAR", "AED"]


def latest_egp_rate(spark: SparkSession) -> float:
    """USD value of 1 EGP, shared by clean_metals.py and clean_re_rentals.py for
    USD->EGP conversion (one single EGP rate scales both the full 1968-2026 history
    and the ~56/420 USD-denominated rows to EGP via clean_metals.py)."""
    raw = (
        io.read_csv(spark, RAW_FILE)
        .withColumn("currency", F.trim(F.upper(F.col("currency"))))
        .withColumn("rate", F.col("rate").cast("double"))
    )
    row = raw.filter(F.col("currency") == "EGP").orderBy(F.col("time").desc()).first()
    if row is None:
        raise ValueError("No EGP rate found in currency_rates.csv")
    return row["rate"]


def clean_fx(spark: SparkSession) -> DataFrame:
    df = (
        io.read_csv(spark, RAW_FILE)
        .withColumn("currency", F.trim(F.upper(F.col("currency"))))
        .withColumn("rate", F.col("rate").cast("double"))
        .withColumn("rate_ts", F.to_timestamp(F.col("time")))
        .withColumn("rate_date", F.to_date(F.col("rate_ts")))
        .filter(F.col("currency").isin(*MAJOR_CURRENCIES, "EGP"))
    )

    # The source is scraped multiple times a day (near-duplicate snapshots seconds apart);
    # collapse to the grey the rest of Silver expects: one rate per currency per day.
    latest_per_day = Window.partitionBy("currency", "rate_date").orderBy(F.col("rate_ts").desc())
    df = df.withColumn("_rn", F.row_number().over(latest_per_day)).filter(F.col("_rn") == 1).drop("_rn")

    return df.withColumn("units_per_usd", F.lit(1.0) / F.col("rate")).select(
        "currency", "rate_date", "rate_ts", "rate", "units_per_usd",
    )


def run() -> None:
    spark = get_spark_session("clean_fx")
    ensure_namespaces(spark)
    df = io.add_metadata(clean_fx(spark), RAW_FILE)
    io.write_table(df, "silver", "fx_rates")


if __name__ == "__main__":
    run()
