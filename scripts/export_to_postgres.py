#!/usr/bin/env python3
"""
Export Gold/Silver layer tables from Nessie/Iceberg to PostgreSQL via Spark.
Creates tables the Grafana dashboards expect:
  - gold.stock_performance, gold.stock_fundamentals, gold.stock_technical
  - silver.metals_history, silver.fx_rates, silver.re_sales
  - gold.gold_metal_roi, gold.re_sale_metrics, gold.asset_scores, gold.market_snapshot
"""

import os
import sys
import psycopg2
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F


def ensure_pg_schemas():
    """Create gold and silver schemas in PostgreSQL if they don't exist."""
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "investment_analytics")
    user = os.environ.get("POSTGRES_USER", "admin")
    password = os.environ.get("POSTGRES_PASSWORD", "admin123")

    conn = psycopg2.connect(host=host, port=port, dbname=db, user=user, password=password)
    conn.autocommit = True
    cur = conn.cursor()
    for schema in ("gold", "silver"):
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        print(f"  Schema '{schema}' ensured")
    cur.close()
    conn.close()


def get_spark():
    """Create a local Spark session with Nessie catalog (same config as upstream jobs)."""
    nessie_uri = os.environ.get("NESSIE_URI", "http://nessie:19120/api/v2")
    warehouse = os.environ.get("WAREHOUSE", "s3://investing-gradutation-project/warehouse/")
    aws_region = os.environ.get("AWS_REGION", "us-east-1")
    access_key = os.environ["AWS_ACCESS_KEY_ID"]
    secret_key = os.environ["AWS_SECRET_ACCESS_KEY"]

    spark = (
        SparkSession.builder
        .appName("export_to_postgres")
        .master("local[*]")
        .config("spark.jars.packages", ",".join([
            "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.11.0",
            "org.apache.iceberg:iceberg-aws-bundle:1.11.0",
            "org.projectnessie.nessie-integrations:nessie-spark-extensions-3.5_2.12:0.108.3",
            "org.apache.hadoop:hadoop-aws:3.3.4",
            "com.amazonaws:aws-java-sdk-bundle:1.12.262",
            "org.postgresql:postgresql:42.7.3",
        ]))
        .config("spark.sql.extensions", ",".join([
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
            "org.projectnessie.spark.extensions.NessieSparkSessionExtensions",
        ]))
        .config("spark.sql.catalog.nessie", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.nessie.catalog-impl", "org.apache.iceberg.nessie.NessieCatalog")
        .config("spark.sql.catalog.nessie.uri", nessie_uri)
        .config("spark.sql.catalog.nessie.ref", "main")
        .config("spark.sql.catalog.nessie.warehouse", warehouse)
        .config("spark.sql.catalog.nessie.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", "com.amazonaws.auth.EnvironmentVariableCredentialsProvider")
        .config("spark.hadoop.fs.s3a.access.key", access_key)
        .config("spark.hadoop.fs.s3a.secret.key", secret_key)
        .config("spark.hadoop.fs.s3a.endpoint.region", aws_region)
        .config("spark.driver.host", "localhost")
        .config("spark.driver.bindAddress", "0.0.0.0")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def get_pg_jdbc_url():
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "investment_analytics")
    return f"jdbc:postgresql://{host}:{port}/{db}"


def get_pg_props():
    return {
        "user": os.environ.get("POSTGRES_USER", "admin"),
        "password": os.environ.get("POSTGRES_PASSWORD", "admin123"),
        "driver": "org.postgresql.Driver",
    }


def write_to_pg(df, table_name, schema="gold"):
    """Write a Spark DataFrame to PostgreSQL."""
    jdbc_url = get_pg_jdbc_url()
    props = get_pg_props()
    full_table = f"{schema}.{table_name}"

    df.write.jdbc(
        jdbc_url,
        full_table,
        mode="overwrite",
        properties=props,
    )
    print(f"  [OK] Wrote {full_table}")


def build_stock_performance(spark):
    """gold.stock_performance: daily OHLCV + change_pct for each ticker."""
    print("Building gold.stock_performance...")
    df = spark.table("nessie.silver.stock_eod").select(
        F.concat(F.col("ticker"), F.lit(".CA")).alias("symbol"),
        F.col("trade_date").alias("date"),
        "open", "high", "low", "close", "adj_close", "volume",
        F.round(F.col("daily_return") * 100, 4).alias("change_pct"),
        "dividends", "stock_splits",
    )
    write_to_pg(df, "stock_performance")
    print(f"  {df.count()} rows written")


def build_stock_fundamentals(spark):
    """gold.stock_fundamentals: company fundamentals for each ticker."""
    print("Building gold.stock_fundamentals...")
    df = spark.table("nessie.silver.fundamentals").select(
        F.concat(F.col("ticker"), F.lit(".CA")).alias("symbol"),
        "name", "sector", "industry",
        F.col("market_cap").alias("market_cap_egp"),
        "trailing_pe", "forward_pe", "price_to_book",
        "eps", "dividend_yield", "beta",
        F.col("fifty_two_week_high").alias("week52_high"),
        F.col("fifty_two_week_low").alias("week52_low"),
        "employees",
    )
    write_to_pg(df, "stock_fundamentals")
    print(f"  {df.count()} rows written")


def build_stock_technical(spark):
    """gold.stock_technical: daily close + computed SMA20, SMA50, RSI14."""
    print("Building gold.stock_technical...")

    eod = spark.table("nessie.silver.stock_eod").select(
        F.concat(F.col("ticker"), F.lit(".CA")).alias("symbol"),
        F.col("trade_date").alias("date"),
        "close",
    ).orderBy("symbol", "date")

    by_symbol = Window.partitionBy("symbol").orderBy("date")

    # SMA 20 / 50
    df = eod \
        .withColumn("sma_20", F.round(F.avg("close").over(by_symbol.rowsBetween(-19, 0)), 2)) \
        .withColumn("sma_50", F.round(F.avg("close").over(by_symbol.rowsBetween(-49, 0)), 2))

    # RSI 14
    df = df.withColumn("prev_close", F.lag("close").over(by_symbol))
    df = df.withColumn("daily_change", F.col("close") - F.col("prev_close"))
    df = df.withColumn("gain", F.when(F.col("daily_change") > 0, F.col("daily_change")).otherwise(0.0))
    df = df.withColumn("loss", F.when(F.col("daily_change") < 0, -F.col("daily_change")).otherwise(0.0))

    avg_gain = F.avg("gain").over(by_symbol.rowsBetween(-13, 0))
    avg_loss = F.avg("loss").over(by_symbol.rowsBetween(-13, 0))

    df = df.withColumn(
        "rsi",
        F.when(avg_loss == 0, 100.0)
        .otherwise(F.round(100.0 - 100.0 / (1.0 + avg_gain / avg_loss), 2))
    )

    df = df.select("symbol", "date", "close", "sma_20", "sma_50", "rsi")
    write_to_pg(df, "stock_technical")
    print(f"  {df.count()} rows written")


def build_metals_history(spark):
    """silver.metals_history: daily gold/silver prices in USD and EGP."""
    print("Building silver.metals_history...")
    df = spark.table("nessie.silver.metals").filter(F.col("kind") == "history").select(
        "metal", "session",
        F.col("price_date").alias("date"),
        "price_usd", "price_egp", "authority",
    )
    write_to_pg(df, "metals_history", schema="silver")
    print(f"  {df.count()} rows written")


def build_fx_rates(spark):
    """silver.fx_rates: daily exchange rates for major currencies vs EGP."""
    print("Building silver.fx_rates...")
    df = spark.table("nessie.silver.fx_rates").select(
        "currency",
        F.col("rate_date").alias("date"),
        "rate", "units_per_usd",
    )
    write_to_pg(df, "fx_rates", schema="silver")
    print(f"  {df.count()} rows written")


def build_re_sales(spark):
    """silver.re_sales: individual real estate sale listings."""
    print("Building silver.re_sales...")
    df = spark.table("nessie.silver.re_sales").select(
        "source", "title", "property_type", "governorate", "district",
        "area_sqm", "price_egp", "bedrooms", "bathrooms",
        "price_per_sqm_egp", "scraped_at",
    )
    write_to_pg(df, "re_sales", schema="silver")
    print(f"  {df.count()} rows written")


def build_gold_metal_roi(spark):
    """gold.gold_metal_roi: return on investment for gold/silver at various horizons."""
    print("Building gold.gold_metal_roi...")
    df = spark.table("nessie.silver.metals").filter(F.col("kind") == "spot").select(
        "metal", "price_usd", "change_pct",
        F.current_date().alias("as_of_date"),
    )
    write_to_pg(df, "gold_metal_spot", schema="gold")
    print(f"  {df.count()} rows written")

    roi_df = spark.table("nessie.gold.gold_metal_roi").select("*")
    write_to_pg(roi_df, "gold_metal_roi", schema="gold")
    print(f"  {roi_df.count()} rows written")


def build_re_sale_metrics(spark):
    """gold.re_sale_metrics: district-level aggregated sale metrics."""
    print("Building gold.re_sale_metrics...")
    df = spark.table("nessie.gold.re_sale_metrics").select(
        "district", "listing_count",
        "avg_price_per_sqm_egp", "median_price_per_sqm_egp",
        "min_price_per_sqm_egp", "max_price_per_sqm_egp",
        "avg_area_sqm", "as_of_date",
    )
    write_to_pg(df, "re_sale_metrics", schema="gold")
    print(f"  {df.count()} rows written")


def build_asset_scores(spark):
    """gold.asset_scores: cross-asset class comparison scores."""
    print("Building gold.asset_scores...")
    df = spark.table("nessie.gold.asset_scores").select(
        "asset_class", "roi_proxy", "roi_proxy_label",
        "vol_proxy", "vol_proxy_label", "as_of_date",
    )
    write_to_pg(df, "asset_scores", schema="gold")
    print(f"  {df.count()} rows written")


def build_market_snapshot(spark):
    """gold.market_snapshot: latest values for indices, metals, and FX."""
    print("Building gold.market_snapshot...")
    df = spark.table("nessie.gold.market_snapshot").select(
        "category", "symbol", "metric", "value", "unit", "as_of_date",
    )
    write_to_pg(df, "market_snapshot", schema="gold")
    print(f"  {df.count()} rows written")


def build_stock_returns_vol(spark):
    """gold.stock_returns_vol: daily returns + momentum + volatility for stocks."""
    print("Building gold.stock_returns_vol...")
    df = spark.table("nessie.gold.stock_returns_vol").select(
        F.concat(F.col("ticker"), F.lit(".CA")).alias("symbol"),
        "trade_date", "close", "adj_close", "volume",
        "daily_return", "momentum_3m", "vol_90d",
    )
    write_to_pg(df, "stock_returns_vol", schema="gold")
    print(f"  {df.count()} rows written")


if __name__ == "__main__":
    print("=" * 60)
    print("Nessie/Iceberg -> PostgreSQL Export (via Spark)")
    print("=" * 60)

    ensure_pg_schemas()

    spark = get_spark()

    # --- Equities ---
    build_stock_performance(spark)
    build_stock_fundamentals(spark)
    build_stock_technical(spark)
    build_stock_returns_vol(spark)

    # --- Commodities ---
    build_metals_history(spark)
    build_gold_metal_roi(spark)

    # --- Currencies ---
    build_fx_rates(spark)

    # --- Real Estate ---
    build_re_sales(spark)
    build_re_sale_metrics(spark)

    # --- Portfolio / Cross-asset ---
    build_asset_scores(spark)
    build_market_snapshot(spark)

    print("\n" + "=" * 60)
    print("Export complete!")
    print("=" * 60)

    spark.stop()
