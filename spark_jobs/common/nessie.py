import json
import os
import urllib.request

from pyspark.sql import SparkSession

NAMESPACES = ("bronze", "silver", "gold")


def check_connection(timeout: float = 5.0) -> dict:
    """Hit Nessie's REST config endpoint directly (no Spark/JVM required) so connectivity
    can be confirmed before paying the cost of a Spark session + jar downloads."""
    uri = os.environ.get("NESSIE_URI", "http://nessie:19120/api/v2").rstrip("/")
    with urllib.request.urlopen(f"{uri}/config", timeout=timeout) as response:
        config = json.loads(response.read())
    print(f"Connected to Nessie at {uri} (default branch: {config['defaultBranch']})")
    return config


def ensure_namespaces(spark: SparkSession, namespaces=NAMESPACES) -> None:
    for namespace in namespaces:
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS nessie.{namespace}")
    print(f"Namespaces ready: {', '.join(namespaces)}")
