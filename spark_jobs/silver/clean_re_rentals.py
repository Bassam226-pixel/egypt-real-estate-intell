from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session
from spark_jobs.silver.clean_fx import latest_egp_rate

LEADING_NUMBER = r"([\d,]+\.?\d*)"


def clean_re_rentals(spark: SparkSession) -> DataFrame:
    egp_rate = latest_egp_rate(spark)

    df = (
        io.read_csv(spark, "rental_listings.csv")
        .withColumnRenamed("url", "link")
        .withColumn("bedrooms", F.col("bedrooms").cast("int"))
        .withColumn("bathrooms", F.col("bathrooms").cast("int"))
        .withColumn("latitude", F.col("latitude").cast("double"))
        .withColumn("longitude", F.col("longitude").cast("double"))
        .withColumn("posted_date", F.to_date(F.col("posted_date")))
        .withColumn("scraped_at", F.to_timestamp(F.col("scraped_at")))
        .withColumn(
            "area_sqm",
            F.regexp_extract(F.regexp_extract(F.col("area"), LEADING_NUMBER, 1), ",", 1).cast("double"),
        )
    )

    rent_raw = F.regexp_replace(F.col("price"), ",", "").cast("double")
    rent_egp = F.when(F.col("currency") == "USD", rent_raw / F.lit(egp_rate)).otherwise(rent_raw)
    df = df.withColumn(
        "monthly_rent_egp",
        F.when(F.col("period") == "monthly", rent_egp)
        .when(F.col("period") == "yearly", rent_egp / F.lit(12.0)),
    )

    df = df.filter(
        F.col("district").isNotNull()
        & F.col("latitude").isNotNull()
        & F.col("longitude").isNotNull()
        & F.col("monthly_rent_egp").isNotNull()
        & F.col("area_sqm").isNotNull()
        & (F.col("area_sqm") > 0)
    )

    df = df.dropDuplicates(["link"]).withColumn("for_recommendation_use", F.lit(False))

    return df.select(
        "link", "source", "title", "property_type", "governorate", "district",
        "latitude", "longitude", "area_sqm", "monthly_rent_egp",
        "bedrooms", "bathrooms", "posted_date", "scraped_at", "for_recommendation_use",
    )


def run() -> None:
    spark = get_spark_session("clean_re_rentals")
    ensure_namespaces(spark)
    df = io.add_metadata(clean_re_rentals(spark), "rental_listings.csv")
    io.write_table(df, "silver", "re_rentals")


if __name__ == "__main__":
    run()
