from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from spark_jobs.common import io
from spark_jobs.common.nessie import ensure_namespaces
from spark_jobs.common.spark_session import get_spark_session

LEADING_NUMBER = r"([\d,]+\.?\d*)"

COMMON_COLUMNS = [
    "source", "listing_id", "title", "property_type",
    "governorate", "district",
    "area_sqm", "price_egp", "bedrooms", "bathrooms",
    "link", "scraped_at",
]


def _price_egp(price: F.Column) -> F.Column:
    return F.regexp_replace(price, r"[^0-9.]", "").cast("double")


def _area_sqm(area: F.Column) -> F.Column:
    number = F.regexp_extract(area, LEADING_NUMBER, 1)
    return F.regexp_replace(number, ",", "").cast("double")


def _listing_id_from_link(link: F.Column, pattern: str) -> F.Column:
    return F.regexp_extract(link, pattern, 1)


def _district_from_splash_location(location: F.Column) -> F.Column:
    # Aqarmap: "New Cairo - Fifth Settlement / Katamy Heights Compound" -> first segment.
    return F.trim(F.element_at(F.split(location, r"\s*/\s*"), 1))


def _district_from_comma_location(location: F.Column) -> F.Column:
    # PropertyFinder/Bayut: "Project, Sub-area, District, City, Governorate" (most-specific-first),
    # so the *second* segment is the best available district proxy.
    parts = F.split(location, r"\s*,\s*")
    n = F.size(parts)
    return F.when(n >= 2, F.trim(parts[1])).otherwise(F.trim(parts[0]))


def _read_aqarmap(spark: SparkSession) -> DataFrame:
    df = io.read_json(spark, "aqarmap_data.json")
    return df.select(
        F.lit("aqarmap").alias("source"),
        _listing_id_from_link(df["link"], r"/listing/(\d+)-").alias("listing_id"),
        df["title"],
        df["property_type"],
        df["location"].alias("governorate"),
        _district_from_splash_location(df["location"]).alias("district"),
        _area_sqm(df["area"]).alias("area_sqm"),
        _price_egp(df["price"]).alias("price_egp"),
        df["bedrooms"].cast("int"),
        df["bathrooms"].cast("int"),
        df["link"],
        F.to_timestamp(df["scraped_at"]).alias("scraped_at"),
    )


def _read_propertyfinder(spark: SparkSession) -> DataFrame:
    df = io.read_json(spark, "propertyfinder_data.json")
    return df.select(
        F.lit("propertyfinder").alias("source"),
        _listing_id_from_link(df["link"], r"-(\d+)$").alias("listing_id"),
        df["title"],
        df["property_type"],
        df["location"].alias("governorate"),
        _district_from_comma_location(df["location"]).alias("district"),
        _area_sqm(df["area"]).alias("area_sqm"),
        _price_egp(df["price"]).alias("price_egp"),
        df["bedrooms"].cast("int"),
        df["bathrooms"].cast("int"),
        df["link"],
        F.to_timestamp(df["scraped_at"]).alias("scraped_at"),
    )


def _read_bayut(spark: SparkSession) -> DataFrame:
    df = io.read_json(spark, "bayut_data.json")
    return df.select(
        F.lit("bayut").alias("source"),
        _listing_id_from_link(df["link"], r"details-(\d+)/").alias("listing_id"),
        df["title"],
        df["property_type"],
        df["location"].alias("governorate"),
        _district_from_comma_location(df["location"]).alias("district"),
        _area_sqm(df["area"]).alias("area_sqm"),
        _price_egp(df["price"]).alias("price_egp"),
        df["bedrooms"].cast("int"),
        df["bathrooms"].cast("int"),
        df["link"],
        F.current_timestamp().alias("scraped_at"),
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
        & F.col("price_egp").isNotNull()
        & (F.col("price_egp") > 0)
        & F.col("area_sqm").isNotNull()
        & (F.col("area_sqm") > 0)
    ).withColumn("price_per_sqm_egp", F.col("price_egp") / F.col("area_sqm"))

    # De-dupe on a business key instead of listing_id -- that's only unique *within* a
    # source, not across the 3 sale platforms (same listing_id on Bayut and PropertyFinder).
    return combined.dropDuplicates(["district", "bedrooms", "price_egp", "area_sqm"]).select(
        *COMMON_COLUMNS, "price_per_sqm_egp",
    )


def run() -> None:
    spark = get_spark_session("clean_re_sales")
    ensure_namespaces(spark)
    df = io.add_metadata(
        clean_re_sales(spark),
        "aqarmap_data.json+propertyfinder_data.json+bayut_data.json",
    )
    io.write_table(df, "silver", "re_sales")


if __name__ == "__main__":
    run()
