from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session
from spark_jobs.gold.re_sale_metrics import re_sale_metrics

MIN_RENTAL_LISTINGS = 2


def _district_rental_metrics(spark: SparkSession) -> DataFrame:
    rentals = io.read_table(spark, "silver", "re_rentals")
    rentals = rentals.withColumn(
        "rent_per_sqm_egp", F.col("monthly_rent_egp") / F.col("area_sqm")
    )
    return rentals.groupBy("district").agg(
        F.count("*").alias("rental_listing_count"),
        F.avg("rent_per_sqm_egp").alias("avg_rent_per_sqm_egp"),
    ).filter(F.col("rental_listing_count") >= MIN_RENTAL_LISTINGS)


def re_district_metrics(spark: SparkSession) -> DataFrame:
    sale = (
        re_sale_metrics(spark)
        .select("district", "avg_price_per_sqm_egp", "listing_count", "as_of_date")
        .withColumnRenamed("listing_count", "sale_listing_count")
    )
    rental = _district_rental_metrics(spark)

    df = sale.join(rental, "district", "inner").withColumn(
        "gross_yield_pct", (F.col("avg_rent_per_sqm_egp") * 12 / F.col("avg_price_per_sqm_egp")) * 100
    )
    df = df.withColumn("for_recommendation_use", F.lit(False))

    return df.select(
        "district", "avg_price_per_sqm_egp", "sale_listing_count",
        "avg_rent_per_sqm_egp", "rental_listing_count", "gross_yield_pct",
        "as_of_date", "for_recommendation_use",
    )


def run() -> None:
    spark = get_spark_session("re_district_metrics")
    ensure_namespaces(spark)
    df = io.add_metadata(re_district_metrics(spark), "gold.re_sale_metrics+silver.re_rentals")
    io.write_table(df, "gold", "re_district_metrics")


if __name__ == "__main__":
    run()
