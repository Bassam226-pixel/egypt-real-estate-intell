import os

from pyspark.sql import SparkSession

# Version-matched trio for the pinned quay.io/jupyter/pyspark-notebook:spark-3.5.3 image
# (Spark 3.5.3 / Hadoop 3.3.4). Nessie has no released Spark-extensions build past 3.5,
# so these must move together if the base image is ever upgraded.
ICEBERG_VERSION = "1.11.0"
NESSIE_VERSION = "0.108.3"
HADOOP_AWS_VERSION = "3.3.4"     # matches the Hadoop client bundled in Spark 3.5.3
AWS_SDK_V1_VERSION = "1.12.262"  # aws-java-sdk-bundle version hadoop-aws 3.3.4 was built against

_PACKAGES = ",".join([
    f"org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:{ICEBERG_VERSION}",
    f"org.apache.iceberg:iceberg-aws-bundle:{ICEBERG_VERSION}",
    f"org.projectnessie.nessie-integrations:nessie-spark-extensions-3.5_2.12:{NESSIE_VERSION}",
    f"org.apache.hadoop:hadoop-aws:{HADOOP_AWS_VERSION}",
    f"com.amazonaws:aws-java-sdk-bundle:{AWS_SDK_V1_VERSION}",
])

_EXTENSIONS = ",".join([
    "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
    "org.projectnessie.spark.extensions.NessieSparkSessionExtensions",
])


def get_spark_session(app_name: str) -> SparkSession:
    """Local-mode SparkSession wired to the Nessie catalog (Iceberg tables on S3).

    Reads NESSIE_URI, WAREHOUSE, AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    from the environment (already set on the jupyter/airflow containers via .env).
    """
    nessie_uri = os.environ.get("NESSIE_URI", "http://nessie:19120/api/v2")
    warehouse = os.environ["WAREHOUSE"]
    aws_region = os.environ.get("AWS_REGION", "us-east-1")

    spark = (
        SparkSession.builder.appName(app_name)
        .master(os.environ.get("SPARK_MASTER", "local[*]"))
        .config("spark.jars.packages", _PACKAGES)
        .config("spark.sql.extensions", _EXTENSIONS)
        .config("spark.sql.catalog.nessie", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.nessie.catalog-impl", "org.apache.iceberg.nessie.NessieCatalog")
        .config("spark.sql.catalog.nessie.uri", nessie_uri)
        .config("spark.sql.catalog.nessie.ref", "main")
        .config("spark.sql.catalog.nessie.warehouse", warehouse)
        .config("spark.sql.catalog.nessie.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .config("spark.sql.defaultCatalog", "nessie")
        # s3a:// (Hadoop/Spark reads of raw files) - separate from S3FileIO above, which
        # only handles s3:// Iceberg table data. See spark_jobs/common/io.py.
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "com.amazonaws.auth.EnvironmentVariableCredentialsProvider",
        )
        .config("spark.hadoop.fs.s3a.endpoint.region", aws_region)
        .config("spark.driver.host", "localhost")
        .config("spark.driver.bindAddress", "0.0.0.0")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark
