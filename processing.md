# Processing Pipeline Guide

## Overview

The processing layer turns cleaned news articles into machine-learning ready features. This guide explains how the `SparkProcessor` works, the storage layout it writes to, and the different ways you can run it—locally or inside the provided Spark container.

**Key goals**
- Transform curated article text into token and TF-IDF features.
- Persist derived vectors to the `processed_articles` table for downstream NLP.
- Support both ad-hoc batch runs and continuous micro-batch streaming.

## Data Requirements

Before running any Spark jobs, make sure the ingestion/enrichment pipeline has populated the SQLite database:

1. Run RSS collection or Kafka enrichment so `news_articles.db` contains articles with `content` or `full_content`.
2. Verify the database location (default: project root). Use `python -m newsbot.db_stats` to confirm content is present.
3. Optional: warm up enrichment to maximize full articles. The processor prefers `full_content` but will fall back to RSS summaries when needed.

## Processed Data Schema

The processor writes to the `processed_articles` table, created automatically by `newsbot.storage.NewsStorage`:

| Column           | Type    | Description                                                   |
|------------------|---------|---------------------------------------------------------------|
| `article_id`     | INTEGER | Foreign key pointing to the source row in `articles`.         |
| `token_count`    | INTEGER | Number of tokens that survived cleaning/stop-word removal.    |
| `tokens`         | TEXT    | JSON array of normalized tokens (lowercase).                  |
| `feature_vector` | TEXT    | JSON array representing the TF-IDF sparse vector.            |
| `pipeline_version` | TEXT  | Logical version identifier (default `spark_v1`).              |
| `processed_at`   | TEXT    | UTC timestamp for auditing and incremental catches.           |

The table enforces a primary key on `article_id`, so re-processing an article replaces the existing record without creating duplicates.

## SparkProcessor Capabilities

The component lives in `newsbot/spark_processor.py` and implements:

- **Reusable Spark ML pipeline** – regex tokenizer → stop-word removal → HashingTF → IDF.
- **Minimum content guards** – skip documents shorter than configurable thresholds.
- **Incremental runs** – `since_article_id` argument skips already processed items.
- **Micro-batch streaming** – Spark Structured Streaming using the rate source to poll SQLite on a schedule.
- **Storage helper** – persists results via `NewsStorage.save_processed_article` with upserts.

## Running Locally

### 1. Install Dependencies

```bash
conda activate news-env
pip install pyspark numpy
```

Spark also needs Java 17+. On Ubuntu/Debian:

```bash
sudo apt-get install openjdk-17-jdk
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
```

### 2. Launch a Batch Job

```bash
spark-submit \
  --master local[*] \
  --name NewsbotSparkProcessor \
  scripts/run_spark_processor.py --mode batch
```

Useful flags:

- `--limit 500` – cap the number of rows processed.
- `--since-id 1200` – resume from the last processed article id.
- `--prefer-summaries` – flip to RSS summary text when full content is scarce.
- `--db-path /path/to/news_articles.db` – point to an alternative database.

The script prints how many feature rows were written and exits cleanly.

### 3. Stream New Articles

```bash
spark-submit \
  --master local[*] \
  --name NewsbotSparkProcessorStream \
  scripts/run_spark_processor.py --mode stream --interval 300
```

This configuration:
- Polls for new articles every 5 minutes.
- Utilizes Spark Structured Streaming with a synthetic rate source.
- Continues until interrupted (CTRL+C) or `--max-batches` is reached.

## Running Inside the Spark Container

A ready-to-use Spark image is declared in `docker-compose.yml`. The service mounts the repository under `/workspace` so you can run jobs without installing local Java or Spark.

### 1. Start the Container

```bash
docker compose up -d spark
```

### 2. Prime Python Dependencies

The image provides Python but lacks extra libraries. Install once by targeting the shared `.sparkdeps` directory:

```bash
docker compose exec spark pip install --target /workspace/.sparkdeps numpy
```

> **Tip:** `pyspark` is already included in the container image. Additional wheels added under `.sparkdeps` become available to both host and container and do not need reinstallation.

### 3. Run a Batch Job

```bash
docker compose exec -e PYTHONPATH=/workspace:/workspace/.sparkdeps \
  spark spark-submit \
  --master local[*] \
  --name ContainerSparkBatch \
  scripts/run_spark_processor.py --mode batch
```

### 4. Run Continuous Streaming

```bash
docker compose exec -e PYTHONPATH=/workspace:/workspace/.sparkdeps \
  spark spark-submit \
  --master local[*] \
  --name ContainerSparkStream \
  scripts/run_spark_processor.py \
  --mode stream \
  --interval 180 \
  --rows-per-second 2
```

### 5. Managing Output Paths

- SQLite lives at `/workspace/news_articles.db` by default; the container sees the same file as your host.
- Use `--db-path /workspace/newsbot/news_articles.db` if you created project-scoped copies under the package folder.
- Processed results are written in-place; you can inspect them with any SQLite client on the host.

## Integrating with the Pipeline

1. **Kafka Consumers** finish enriching full content and commit it to SQLite.
2. **SparkProcessor** converts the text into vectors and tokens, storing them under `processed_articles`.
3. Downstream NLP jobs (embeddings, clustering, retrieval) can pull from this table.

Suggested workflows:

- Schedule a nightly batch run after the enrichment automation completes.
- Trigger the streaming mode alongside Kafka consumers for near-real-time vector availability.
- Chain with notebook experiments by reading `processed_articles` via pandas or Spark.

## Configuration Reference

| Parameter | Location | Default | Notes |
|-----------|----------|---------|-------|
| `min_content_length` | `SparkProcessor` init | 80 | Drop short/low-signal texts. |
| `num_features` | `SparkProcessor` init | 4096 | HashingTF vector size – adjust for vocabulary richness. |
| `pipeline_version` | `SparkProcessor` init | `spark_v1` | Stored in DB for reproducibility. |
| `--limit` | CLI | `None` | Safety cap for large backfills. |
| `--since-id` | CLI | `None` | Incremental processing boundary. |
| `--interval` | CLI | 300 | Streaming polling cadence (seconds). |
| `--rows-per-second` | CLI | 1 | Structured Streaming trigger frequency. |
| `--max-batches` | CLI | `None` | Stop streaming after N triggers. |

## Monitoring Results

Use the SQLite shell or Python to inspect processed rows:

```bash
sqlite3 news_articles.db "SELECT COUNT(*) FROM processed_articles;"
```

```python
from newsbot.storage import NewsStorage
storage = NewsStorage()
print(storage.conn.execute('SELECT COUNT(*) FROM processed_articles').fetchone()[0])
print(storage.conn.execute('SELECT * FROM processed_articles ORDER BY processed_at DESC LIMIT 5').fetchall())
storage.close()
```

### Verifying Vector Shapes

```python
import json, sqlite3
db = sqlite3.connect('news_articles.db')
row = db.execute('SELECT token_count, LENGTH(tokens), LENGTH(feature_vector) FROM processed_articles LIMIT 1').fetchone()
print(row)
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ImportError: pyspark` | Library missing locally | `pip install pyspark` inside `news-env` or use container. |
| `java.lang.UnsupportedClassVersionError` | Java 8 or older | Install Java 17 and set `JAVA_HOME`. |
| Permissions error on `news_articles.db` inside container | Host file owned by non-root | Run container as root (default) or `chmod 664 news_articles.db`. |
| `TypeError: Unsupported vector type` | Spark returned dense vector array | Upgrade PySpark (4.0.1+) and rerun; fallback handles sparse and dense arrays. |
| Streaming seems idle | No new articles being ingested | Verify Kafka consumers are running and `articles` table is growing. |

## Related Documentation

- [`README.md`](README.md) – project overview and quickstart.
- [`architecture.md`](architecture.md) – high-level system design.
- [`Reports.md`](Reports.md) – detailed metrics and performance results.
- [`AUTOMATION_GUIDE.md`](AUTOMATION_GUIDE.md) – running ingestion automation.

For questions or improvements, open an issue or update this document alongside code changes.
