from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session

# Engine-eligible mart: don't let one noisy listing set a district's recommended price/m2.
MIN_LISTINGS = 3


def re_sale_metrics(spark: SparkSession) -> DataFrame:
    sales = io.read_table(spark, "silver", "re_sales")
    as_of_date = sales.select(F.max(F.to_date("scraped_at")).alias("d")).first()["d"]

    agg = sales.groupBy("district").agg(
        F.count("*").alias("listing_count"),
        F.avg("price_per_sqm_egp").alias("avg_price_per_sqm_egp"),
        F.expr("percentile_approx(price_per_sqm_egp, 0.5)").alias("median_price_per_sqm_egp"),
        F.min("price_per_sqm_egp").alias("min_price_per_sqm_egp"),
        F.max("price_per_sqm_egp").alias("max_price_per_sqm_egp"),
        F.avg("area_sqm").alias("avg_area_sqm"),
    ).filter(F.col("listing_count") >= MIN_LISTINGS)

    # NEW mart per the skeleton delta: price/m2 only, never rent/yield -- that split
    # is what keeps this table engine-eligible (see re_district_metrics.py, dashboard-only).
    return agg.withColumn("as_of_date", F.lit(as_of_date)).withColumn(
        "for_recommendation_use", F.lit(True)
    )


def run() -> None:
    spark = get_spark_session("re_sale_metrics")
    ensure_namespaces(spark)
    df = io.add_metadata(re_sale_metrics(spark), "silver.re_sales")
    io.write_table(df, "gold", "re_sale_metrics")


if __name__ == "__main__":
    run()
