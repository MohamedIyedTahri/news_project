"""Utility script to display the most recent article stored in the Delta table."""
from __future__ import annotations

import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

DELTA_TABLE_PATH = os.environ.get("DELTA_ARTICLES_PATH", "/data/delta/articles")
DISPLAY_LIMIT = int(os.environ.get("DELTA_DISPLAY_LIMIT", "1"))


def build_spark_session() -> SparkSession:
    builder = (
        SparkSession.builder.appName("ShowLatestArticle")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    )
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def main() -> None:
    spark = build_spark_session()
    df = spark.read.format("delta").load(DELTA_TABLE_PATH)
    enriched_order = F.coalesce(
        F.to_timestamp("enriched_at"),
        F.to_timestamp("fetched_at"),
        F.col("ingested_at"),
    )
    latest = df.orderBy(enriched_order.desc())
    latest.show(DISPLAY_LIMIT, truncate=False)
    spark.stop()


if __name__ == "__main__":
    main()
