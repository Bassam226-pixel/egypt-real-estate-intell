import os
from urllib.parse import urlparse

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import current_timestamp, lit


def _bucket() -> str:
    return urlparse(os.environ["WAREHOUSE"]).netloc


def raw_path(relative_path: str) -> str:
    """s3a:// path under the bucket's raw/ prefix, for reading source files via Spark/Hadoop."""
    return f"s3a://{_bucket()}/raw/{relative_path.lstrip('/')}"


def table_location(layer: str, table_name: str) -> str:
    """s3:// path for an Iceberg table's location (S3FileIO), e.g. layer='bronze'."""
    return f"s3://{_bucket()}/{layer}/{table_name}"


def add_metadata(df: DataFrame, source_file: str) -> DataFrame:
    return df.withColumn("_ingested_at", current_timestamp()).withColumn("_source_file", lit(source_file))


def write_table(df: DataFrame, layer: str, table_name: str) -> None:
    """Create-or-replace an Iceberg table at nessie.<layer>.<table_name>."""
    df.writeTo(f"nessie.{layer}.{table_name}") \
        .tableProperty("location", table_location(layer, table_name)) \
        .createOrReplace()


def read_table(spark: SparkSession, layer: str, table_name: str) -> DataFrame:
    """Read an already-published Iceberg table at nessie.<layer>.<table_name>, e.g. for
    a Gold job reading a Silver table, or one Gold job composing another's output."""
    return spark.table(f"nessie.{layer}.{table_name}")


def read_csv(spark: SparkSession, relative_path: str, **options) -> DataFrame:
    reader = spark.read.option("header", True).option("inferSchema", True)
    for key, value in options.items():
        reader = reader.option(key, value)
    return reader.csv(raw_path(relative_path))


def read_json(spark: SparkSession, relative_path: str, **options) -> DataFrame:
    reader = spark.read.option("multiline", True)
    for key, value in options.items():
        reader = reader.option(key, value)
    return reader.json(raw_path(relative_path))
