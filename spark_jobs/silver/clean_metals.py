from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session
from spark_jobs.silver.clean_fx import latest_egp_rate

RAW_FILE = "authority_prices.csv"
SPOT_FILE = "spot_prices.csv"


def _to_egp(price_usd: F.Column, egp_rate: float) -> F.Column:
    """currency_rates.csv stores "USD value of 1 unit of currency", so EGP = USD / rate."""
    return price_usd / F.lit(egp_rate)


def clean_metals_history(spark: SparkSession, egp_rate: float) -> DataFrame:
    df = (
        io.read_csv(spark, RAW_FILE)
        .withColumn("metal", F.trim(F.lower(F.col("metal"))))
        .withColumn("authority", F.trim(F.lower(F.col("authority"))))
        .withColumn("session", F.trim(F.lower(F.col("session"))))
        .withColumn("price_ts", F.to_timestamp(F.col("time")))
        .withColumn("price_date", F.to_date(F.col("price_ts")))
        .withColumn("price_usd", F.col("price").cast("double"))
        .dropDuplicates(["metal", "price_date", "session"])
    )

    df = (
        df.withColumn("price_egp", _to_egp(F.col("price_usd"), egp_rate))
        .withColumn("kind", F.lit("history"))
        .select("metal", "kind", "session", "price_date", "price_ts", "price_usd", "price_egp", "authority")
    )
    return df


def clean_metals_spot(spark: SparkSession, egp_rate: float) -> DataFrame:
    df = (
        io.read_csv(spark, SPOT_FILE)
        .withColumn("metal", F.trim(F.lower(F.col("metal"))))
        .withColumn("price_ts", F.to_timestamp(F.col("time")))
        .withColumn("price_date", F.to_date(F.col("price_ts")))
        .withColumn("price_usd", F.col("price").cast("double"))
        .withColumn("bid_usd", F.col("bid").cast("double"))
        .withColumn("ask_usd", F.col("ask").cast("double"))
        .withColumn("day_high_usd", F.col("high").cast("double"))
        .withColumn("day_low_usd", F.col("low").cast("double"))
        .withColumn("change_usd", F.col("change").cast("double"))
        .withColumn("change_pct", F.col("change_pct").cast("double"))
    )

    latest_per_metal = Window.partitionBy("metal").orderBy(F.col("price_ts").desc())
    df = df.withColumn("_rn", F.row_number().over(latest_per_metal)).filter(F.col("_rn") == 1).drop("_rn")

    return df.withColumn("kind", F.lit("spot")).select(
        "metal", "kind", "price_date", "price_ts",
        "price_usd", "bid_usd", "ask_usd", "day_high_usd", "day_low_usd",
        "change_usd", "change_pct",
    )


def clean_metals(spark: SparkSession) -> DataFrame:
    egp_rate = latest_egp_rate(spark)
    history = clean_metals_history(spark, egp_rate)
    spot = clean_metals_spot(spark, egp_rate)
    return history.unionByName(spot, allowMissingColumns=True)


def run() -> None:
    spark = get_spark_session("clean_metals")
    ensure_namespaces(spark)
    df = io.add_metadata(clean_metals(spark), f"{RAW_FILE}+{SPOT_FILE}")
    io.write_table(df, "silver", "metals")


if __name__ == "__main__":
    run()
