"""Spark-based processing for enriched news articles.

The SparkProcessor component bridges the enrichment/storage layer with downstream
NLP workloads by transforming cleaned article text into tokenized and vectorized
features suitable for machine learning pipelines. It supports both traditional
batch execution and a micro-batch streaming mode that periodically re-processes
new records as they arrive in the SQLite database.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from newsbot.storage import NewsStorage, DB_PATH

try:  # pragma: no cover - defer heavy imports until needed
    from pyspark.ml import Pipeline
    from pyspark.ml.feature import HashingTF, IDF, RegexTokenizer, StopWordsRemover
    from pyspark.ml.pipeline import PipelineModel
    from pyspark.ml.linalg import SparseVector
    from pyspark.sql import DataFrame, SparkSession
    from pyspark.sql import functions as F
    from pyspark.sql.types import IntegerType, StringType, StructField, StructType
except ImportError as exc:  # pragma: no cover - surfaced during runtime
    raise ImportError(
        "SparkProcessor requires pyspark. Install it via `pip install pyspark` "
        "within the active environment."
    ) from exc

logger = logging.getLogger(__name__)


class SparkProcessor:
    """Process cleaned news articles with Apache Spark.

    The processor reads cleaned article content from the `articles` table,
    applies a reusable Spark ML pipeline (tokenization, normalization, TF-IDF),
    and persists derived features into the `processed_articles` table.
    """

    DEFAULT_PIPELINE_VERSION = "spark_v1"

    def __init__(
        self,
        spark: SparkSession,
        *,
        db_path: str = DB_PATH,
        pipeline_version: str = DEFAULT_PIPELINE_VERSION,
        num_features: int = 4096,
        min_content_length: int = 80,
    ) -> None:
        self.spark = spark
        self.db_path = db_path
        self.storage = NewsStorage(db_path=db_path)
        self.pipeline_version = pipeline_version
        self.num_features = num_features
        self.min_content_length = min_content_length
        self._pipeline_model: Optional[PipelineModel] = None
        self._schema = StructType(
            [
                StructField("article_id", IntegerType(), False),
                StructField("clean_text", StringType(), False),
            ]
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run_batch_processing(
        self,
        *,
        limit: Optional[int] = None,
        since_article_id: Optional[int] = None,
        prefer_full_content: bool = True,
    ) -> int:
        """Execute a one-off Spark job over stored articles.

        Args:
            limit: Max number of articles to process in this batch.
            since_article_id: Optional lower bound (exclusive) for incremental runs.
            prefer_full_content: Choose whether to prioritise enriched text.

        Returns:
            Number of records written to `processed_articles`.
        """

        articles = self.storage.fetch_articles_for_processing(
            since_id=since_article_id,
            limit=limit,
            min_length=self.min_content_length,
            prefer_full_content=prefer_full_content,
        )
        if not articles:
            logger.info("SparkProcessor batch found no candidate articles.")
            return 0

        source_df = self._create_source_dataframe(articles)
        if source_df.rdd.isEmpty():
            logger.info("SparkProcessor batch produced no rows after normalization.")
            return 0
        processed_df = self._transform_dataframe(source_df)
        written = self._persist_processed_rows(processed_df)
        logger.info("SparkProcessor batch stored %s processed articles", written)
        return written

    def run_streaming_processing(
        self,
        *,
        interval_seconds: int = 300,
        max_batches: Optional[int] = None,
        rows_per_second: int = 1,
        prefer_full_content: bool = True,
        checkpoint_dir: Optional[str] = None,
    ) -> None:
        """Start a micro-batch streaming loop that tails the database.

        A rate source is used purely as a scheduling primitive. Each micro-batch
        polls the database for new articles (based on the latest processed id)
        and executes the same Spark pipeline as the batch mode.
        """

        checkpoint_dir = checkpoint_dir or os.path.join(
            "/tmp", f"newsbot_spark_processor_{os.getpid()}"
        )
        os.makedirs(checkpoint_dir, exist_ok=True)

        latest_processed = self.storage.get_latest_processed_article_id()
        batches_completed = 0

        def _process_trigger_batch(_timer_df: DataFrame, batch_id: int) -> None:
            nonlocal latest_processed, batches_completed
            try:
                logger.debug("Streaming trigger %s activated", batch_id)
                written = self.run_batch_processing(
                    since_article_id=latest_processed,
                    prefer_full_content=prefer_full_content,
                )
                if written:
                    latest_processed = self.storage.get_latest_processed_article_id()
                batches_completed += 1
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.exception("SparkProcessor streaming batch failed: %s", exc)

        stream_df = (
            self.spark.readStream.format("rate")
            .option("rowsPerSecond", rows_per_second)
            .load()
        )

        query = (
            stream_df.writeStream.foreachBatch(_process_trigger_batch)
            .trigger(processingTime=f"{interval_seconds} seconds")
            .option("checkpointLocation", checkpoint_dir)
            .start()
        )

        if max_batches is not None:
            while batches_completed < max_batches and query.isActive:
                query.processAllAvailable()
            query.stop()
        else:
            query.awaitTermination()

    def close(self) -> None:
        """Release backing resources."""
        try:
            self.storage.close()
        finally:
            self.spark.stop()

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------
    @classmethod
    def for_local_mode(
        cls,
        *,
        app_name: str = "NewsbotSparkProcessor",
        db_path: str = DB_PATH,
        extra_configs: Optional[Dict[str, Any]] = None,
    ) -> "SparkProcessor":
        """Construct a processor with a locally configured Spark session."""

        builder = SparkSession.builder.appName(app_name).master("local[*]")
        for key, value in (extra_configs or {}).items():
            builder = builder.config(key, value)
        spark = builder.getOrCreate()
        return cls(spark, db_path=db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _create_source_dataframe(self, articles: List[Dict[str, Any]]) -> DataFrame:
        df = self.spark.createDataFrame(articles, schema=self._schema)
        normalized = (
            df.withColumn(
                "normalized_text",
                F.lower(F.col("clean_text")),
            )
            .withColumn(
                "normalized_text",
                F.regexp_replace("normalized_text", "[^\\p{L}\\p{Nd}\\s]", " "),
            )
            .withColumn(
                "normalized_text",
                F.regexp_replace("normalized_text", "\\s+", " "),
            )
            .filter(F.length(F.col("normalized_text")) >= self.min_content_length)
        )
        return normalized

    def _build_pipeline(self) -> Pipeline:
        tokenizer = RegexTokenizer(
            inputCol="normalized_text",
            outputCol="token_candidates",
            pattern="\\W+",
            minTokenLength=2,
        )
        remover = StopWordsRemover(
            inputCol="token_candidates",
            outputCol="tokens",
            caseSensitive=False,
        )
        hashing_tf = HashingTF(
            inputCol="tokens",
            outputCol="token_tf",
            numFeatures=self.num_features,
        )
        idf = IDF(inputCol="token_tf", outputCol="features")
        return Pipeline(stages=[tokenizer, remover, hashing_tf, idf])

    def _transform_dataframe(self, df: DataFrame) -> DataFrame:
        if self._pipeline_model is None:
            self._pipeline_model = self._build_pipeline().fit(df)
        transformed = self._pipeline_model.transform(df)
        enriched = transformed.select(
            "article_id",
            "tokens",
            "features",
            F.size("tokens").alias("token_count"),
        )
        return enriched

    def _persist_processed_rows(self, df: DataFrame) -> int:
        rows_written = 0
        for row in df.toLocalIterator():
            feature_vector = self._vector_to_list(row.features)
            tokens = row.tokens if isinstance(row.tokens, list) else list(row.tokens)
            if not tokens:
                continue
            success = self.storage.save_processed_article(
                article_id=int(row.article_id),
                tokens=tokens,
                feature_vector=feature_vector,
                token_count=int(row.token_count),
                pipeline_version=self.pipeline_version,
                processed_at=datetime.utcnow().isoformat(timespec="seconds"),
            )
            if success:
                rows_written += 1
        return rows_written

    @staticmethod
    def _vector_to_list(vector: Any) -> List[float]:
        if hasattr(vector, "toArray"):
            return vector.toArray().tolist()
        if isinstance(vector, SparseVector):
            return vector.toArray().tolist()
        if isinstance(vector, (list, tuple)):
            return [float(x) for x in vector]
        raise TypeError(f"Unsupported vector type: {type(vector)}")


__all__ = ["SparkProcessor"]
