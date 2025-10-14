"""Structured Streaming job: consume enriched articles from Kafka and persist to Delta Lake.

Run with spark-submit from inside the spark-master container, e.g.:

    docker compose exec spark-master \
        /opt/spark/bin/spark-submit \
        --master spark://spark-master:7077 \
        --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1 \
        /opt/spark/jobs/articles_cleaned_to_delta.py

The job expects the spark-master and spark-worker containers to have a shared
volume mounted at /data/delta so both can read/write the same Delta tables.
Environment variables allow overriding key settings when necessary.
"""
from __future__ import annotations

import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructField, StructType, StringType

# Kafka -> Delta configuration (override via environment variables if needed)
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
SOURCE_TOPIC = os.environ.get("ARTICLES_CLEANED_TOPIC", "articles.cleaned")
STARTING_OFFSETS = os.environ.get("KAFKA_STARTING_OFFSETS", "latest")
MAX_OFFSETS_PER_TRIGGER = os.environ.get("KAFKA_MAX_OFFSETS_PER_TRIGGER")
DELTA_TABLE_PATH = os.environ.get("DELTA_ARTICLES_PATH", "/data/delta/articles")
DELTA_CHECKPOINT_PATH = os.environ.get(
    "DELTA_ARTICLES_CHECKPOINT", "/data/delta/checkpoints/articles_cleaned"
)
TRIGGER_INTERVAL = os.environ.get("DELTA_TRIGGER_INTERVAL", "60 seconds")


ARTICLE_SCHEMA = StructType(
    [
        StructField("id", StringType(), True),
        StructField("title", StringType(), True),
        StructField("link", StringType(), True),
        StructField("publish_date", StringType(), True),
        StructField("source", StringType(), True),
        StructField("category", StringType(), True),
        StructField("summary", StringType(), True),
        StructField("fetched_at", StringType(), True),
        StructField("full_content", StringType(), True),
        StructField("enriched_at", StringType(), True),
    ]
)


def build_spark_session() -> SparkSession:
    """Create or reuse a SparkSession configured for Delta Lake."""

    builder = (
        SparkSession.builder.appName("ArticlesCleanedToDelta")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    )
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("INFO")
    return spark


def main() -> None:
    spark = build_spark_session()

    kafka_reader = spark.readStream.format("kafka").option(
        "kafka.bootstrap.servers", KAFKA_BOOTSTRAP
    ).option("subscribe", SOURCE_TOPIC).option("startingOffsets", STARTING_OFFSETS)

    if MAX_OFFSETS_PER_TRIGGER:
        kafka_reader = kafka_reader.option("maxOffsetsPerTrigger", MAX_OFFSETS_PER_TRIGGER)

    raw_stream = kafka_reader.load().selectExpr("CAST(value AS STRING) AS json_value")

    parsed_stream = (
        raw_stream
        .withColumn("parsed", F.from_json(F.col("json_value"), ARTICLE_SCHEMA))
        .select("parsed.*")
        .withColumn("ingested_at", F.current_timestamp())
    )

    query = (
        parsed_stream.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", DELTA_CHECKPOINT_PATH)
        .trigger(processingTime=TRIGGER_INTERVAL)
        .start(DELTA_TABLE_PATH)
    )

    query.awaitTermination()


if __name__ == "__main__":
    main()
