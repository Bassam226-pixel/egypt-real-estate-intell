from pyspark.sql import Column, DataFrame, SparkSession
from pyspark.sql import functions as F

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session

LEADING_NUMBER = r"([\d,]+\.?\d*)"

COMMON_COLUMNS = [
    "source", "listing_id", "title", "property_type", "district", "location_raw",
    "area_sqm", "price_egp", "bedrooms", "bathrooms", "link", "scraped_at",
]


def _price_egp(price: Column) -> Column:
    return F.regexp_replace(price, r"[^0-9]", "").cast("double")


def _area_sqm(area: Column) -> Column:
    number = F.regexp_extract(area, LEADING_NUMBER, 1)
    return F.regexp_replace(number, ",", "").cast("double")


def _listing_id_from_link(link: Column, pattern: str) -> Column:
    return F.regexp_extract(link, pattern, 1)


def _district_from_slash_location(location: Column) -> Column:
    # aqarmap: "New Cairo - Fifth Settlement / Katameya Heights Compound" -> first segment.
    return F.trim(F.element_at(F.split(location, r"\s*/\s*"), 1))


def _district_from_comma_location(location: Column) -> Column:
    # propertyfinder/bayut: "Project, Sub-area, District, City, Governorate" (depth
    # varies); the governorate/region is always last, so the segment before it is the
    # best available district proxy.
    parts = F.filter(F.split(location, r"\s*,\s*"), lambda x: x != "")
    n = F.size(parts)
    return F.when(n >= 2, F.element_at(parts, -2)).when(n == 1, F.element_at(parts, -1))


def _read_aqarmap(spark: SparkSession) -> DataFrame:
    df = io.read_json(spark, "aqarmap_data.json")
    return df.select(
        F.lit("aqarmap").alias("source"),
        _listing_id_from_link(F.col("link"), r"/listing/(\d+)-").alias("listing_id"),
        F.col("title").alias("title"),
        F.col("property_type").alias("property_type"),
        _district_from_slash_location(F.col("location")).alias("district"),
        F.col("location").alias("location_raw"),
        _area_sqm(F.col("area")).alias("area_sqm"),
        _price_egp(F.col("price")).alias("price_egp"),
        F.col("bedrooms").cast("int").alias("bedrooms"),
        F.col("bathrooms").cast("int").alias("bathrooms"),
        F.col("link").alias("link"),
        F.to_timestamp(F.col("scraped_at")).alias("scraped_at"),
    )


def _read_propertyfinder(spark: SparkSession) -> DataFrame:
    df = io.read_json(spark, "propertyfinder_data.json")
    return df.select(
        F.lit("propertyfinder").alias("source"),
        _listing_id_from_link(F.col("link"), r"-(\d+)\.html$").alias("listing_id"),
        F.col("title").alias("title"),
        F.col("property_type").alias("property_type"),
        _district_from_comma_location(F.col("location")).alias("district"),
        F.col("location").alias("location_raw"),
        _area_sqm(F.col("area")).alias("area_sqm"),
        _price_egp(F.col("price")).alias("price_egp"),
        F.col("bedrooms").cast("int").alias("bedrooms"),
        F.col("bathrooms").cast("int").alias("bathrooms"),
        F.col("link").alias("link"),
        F.to_timestamp(F.col("scraped_at")).alias("scraped_at"),
    )


def _read_bayut(spark: SparkSession) -> DataFrame:
    df = io.read_json(spark, "bayut_data.json")
    return df.select(
        F.lit("bayut").alias("source"),
        _listing_id_from_link(F.col("link"), r"details-(\d+)\.html$").alias("listing_id"),
        F.col("title").alias("title"),
        F.col("property_type").alias("property_type"),
        _district_from_comma_location(F.col("location")).alias("district"),
        F.col("location").alias("location_raw"),
        _area_sqm(F.col("area")).alias("area_sqm"),
        _price_egp(F.col("price")).alias("price_egp"),
        F.col("bedrooms").cast("int").alias("bedrooms"),
        F.col("bathrooms").cast("int").alias("bathrooms"),
        F.col("link").alias("link"),
        F.lit(None).cast("timestamp").alias("scraped_at"),
    )


def clean_re_sales(spark: SparkSession) -> DataFrame:
    combined = (
        _read_aqarmap(spark)
        .unionByName(_read_propertyfinder(spark))
        .unionByName(_read_bayut(spark))
    )

    combined = combined.filter(
        F.col("district").isNotNull()
        & (F.col("district") != "")
        & (F.col("price_egp") > 0)
        & (F.col("area_sqm") > 0)
    ).withColumn("price_per_sqm_egp", F.col("price_egp") / F.col("area_sqm"))

    # No shared external ID across the 3 platforms (listing_id is only unique *within*
    # a source), so de-dupe on a business key instead.
    return combined.dropDuplicates(["district", "bedrooms", "price_egp", "area_sqm"]).select(
        *COMMON_COLUMNS, "price_per_sqm_egp"
    )


def run() -> None:
    spark = get_spark_session("clean_re_sales")
    ensure_namespaces(spark)
    df = io.add_metadata(clean_re_sales(spark), "aqarmap_data.json+propertyfinder_data.json+bayut_data.json")
    io.write_table(df, "silver", "re_sales")


if __name__ == "__main__":
    run()
