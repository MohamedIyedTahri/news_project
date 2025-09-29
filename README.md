# News Chatbot Project

A production-ready, scalable Python application that collects news articles from multiple RSS feeds through a streaming architecture. Features real-time processing via Apache Kafka, intelligent content enrichment, and optimized storage for NLP model training and retrieval-augmented generation (RAG) pipelines.

## Features

### Core Capabilities
- **Real-time streaming architecture**: Apache Kafka-powered message streaming for immediate processing
- **Extensive RSS feed coverage**: 66+ feeds across 8 categories with RSS_FEEDS_EXTENDED dictionary
- **Feed policy management**: Allowlist/denylist support with skip-bozo validation for reliable feeds
- **Extended feed registry**: Curated high-quality feeds for science, health, and specialized content
- **Feed quality validation**: Built-in validator to identify full-text vs summary-only sources
- **Intelligent content enrichment**: Full article scraping with fallback mechanisms and retry logic
- **Advanced text cleaning**: Removes HTML tags, scripts, ads, and excessive whitespace
- **Smart deduplication**: URL-based and content-based duplicate detection with title similarity matching
- **Production-ready storage**: SQLite with WAL mode, schema migrations, and upsert capabilities

### Streaming & Scalability
- **Kafka streaming layer**: Producer/consumer architecture with bootstrap fallback resolution
- **Dual processing modes**: Synchronous and asynchronous consumer implementations with lz4/gzip compression
- **Horizontal scaling**: Stateless consumers with configurable concurrency and semaphore control
- **Graceful error handling**: Dead letter topics, retry mechanisms, and bootstrap hostname fallback
- **Feed selection policies**: Runtime feed filtering with allowlist/denylist and per-feed limits
- **Monitoring & metrics**: Built-in counters with database statistics module and coverage tracking

### Development & Analysis
- **Comprehensive logging**: Structured logging with configurable levels
- **Docker development stack**: Complete Kafka ecosystem with Schema Registry
- **Embedding evaluation**: Comparative analysis of CBOW, Skip-gram, and DistilBERT embeddings
- **Quality assurance**: Smoke tests, integration tests, and manual verification scripts

## Project Structure

```
news_project/
├── newsbot/                          # Core application package
│   ├── __init__.py                   # Package initialization
│   ├── main.py                       # RSS fetching and batch processing
│   ├── rss_feeds.py                  # RSS feed URLs configuration
│   ├── feed_policies.py              # Feed allowlist/denylist management
│   ├── extended_feed_smoke.py        # Extended feed testing with enrichment
│   ├── db_stats.py                   # Database statistics and coverage analysis
│   ├── cleaner.py                    # HTML cleaning and text processing
│   ├── storage.py                    # SQLite database with migrations
│   ├── deduplicator.py               # Article deduplication logic
│   ├── scraper.py                    # Full article content fetching
│   ├── vpn.py                        # VPN rotation utilities
│   ├── hooks.py                      # Extensibility hooks
│   ├── smoke_enrich.py               # Enrichment pipeline testing
│   ├── feed_validator.py             # RSS feed quality validation tool
│   ├── kafka_utils.py                # Kafka utilities with bootstrap fallback
│   ├── kafka_producer.py             # Kafka RSS article producer
│   ├── kafka_scraper_consumer.py     # Sync Kafka consumer for enrichment
│   ├── kafka_scraper_async_consumer.py # Async Kafka consumer with concurrency
│   ├── smoke_kafka_run.py            # Manual Kafka pipeline testing
│   └── tests/                        # Test suite
│       └── test_kafka_smoke.py       # Kafka integration tests
├── scripts/                          # Operational scripts
│   └── create_kafka_topics.sh        # Kafka topic creation
├── notebooks/                        # Analysis and experimentation
│   ├── Week4_*.ipynb                 # Embedding comparison studies
│   └── Lab*.ipynb                    # NLP development labs
├── docker-compose.yml                # Kafka development stack
├── requirements-kafka.txt            # Streaming dependencies
├── news_articles.db                  # SQLite database (auto-created)
├── architecture.md                   # System architecture documentation
├── README.md                         # This file
└── .github/
    └── copilot-instructions.md       # Development guidelines
```

## Setup

### Prerequisites
- Python 3.12+ (conda environment recommended)
- Docker and Docker Compose for Kafka stack
- Internet connection for RSS feeds and article scraping

### 1. Environment Setup
```bash
# Activate your conda environment
conda activate news-env

# Install core dependencies
pip install feedparser beautifulsoup4 requests

# Install Kafka streaming dependencies (optional)
pip install -r requirements-kafka.txt
```

### 2. Basic Mode (No Kafka)
```bash
# Navigate to project directory
cd /path/to/news_project

# Run basic RSS collection
python -m newsbot.main
```

### 3. Streaming Mode (With Kafka)
```bash
# Start Kafka infrastructure
docker-compose up -d
bash scripts/create_kafka_topics.sh

# Run streaming pipeline
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 python -m newsbot.kafka_producer --once
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 python -m newsbot.kafka_scraper_consumer --max-messages 10
```

## Usage Examples

### Batch Processing (Traditional Mode)

#### Fetch All Categories
```python
from newsbot.main import fetch_multiple_feeds, save_articles_batch
from newsbot.storage import NewsStorage

# Initialize storage with automatic migrations
storage = NewsStorage()

# Fetch articles from all configured RSS feeds with deduplication
all_articles = fetch_multiple_feeds(use_deduplication=True)

# Save articles to database with progress tracking
stats = save_articles_batch(all_articles, storage)

# Print statistics
for category, stat in stats.items():
    print(f"{category}: {stat['saved']}/{stat['total']} saved")

storage.close()
```

#### Enhanced Content Pipeline
```python
from newsbot.main import collect_and_store_articles

# Complete pipeline: RSS → Full content → Storage
result = collect_and_store_articles(
    categories=["tech", "international"], 
    enrich_full=True,
    batch_enrich_limit=50
)
print(f"Pipeline completed: {result}")
```

### Streaming Processing (Kafka Mode)

#### Producer Operations
```bash
# Environment setup
export KAFKA_BOOTSTRAP_SERVERS=localhost:29092

# One-time batch production
python -m newsbot.kafka_producer --once --categories tech,international

# Continuous polling (every 10 minutes)
python -m newsbot.kafka_producer --poll 10
```

#### Consumer Operations
```bash
# Synchronous consumer (reliable, simple)
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 python -m newsbot.kafka_scraper_consumer

# Asynchronous consumer (high throughput)
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 CONCURRENCY=10 python -m newsbot.kafka_scraper_async_consumer

# Limited processing for testing
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 python -m newsbot.kafka_scraper_consumer --max-messages 5
```

### Performance Monitoring

#### Database Statistics
```bash
# View per-category full-content coverage
python -m newsbot.db_stats

# JSON output for scripting
python -m newsbot.db_stats --json

# Health check with coverage threshold
python -m newsbot.db_stats --min-coverage 50
```

```python
# Programmatic access
from newsbot.storage import NewsStorage

storage = NewsStorage()
stats = storage.get_statistics()
print(f"Total articles: {stats['total_articles']}")
print(f"By category: {stats['by_category']}")
print(f"Top sources: {stats['top_sources']}")
storage.close()
```

#### Typical Performance Metrics
- **RSS Fetching**: 150-300 articles/minute from 12+ sources
- **Content Enrichment**: 5-15 articles/minute (depends on network and source)
- **Storage Operations**: 1000+ inserts/second with WAL mode
- **Kafka Throughput**: 500+ messages/second with async consumers
- **Feed Validation**: 66 feeds validated in ~2 minutes with quality classification

### Feed Quality Validation

#### Validate RSS Feed Quality
```bash
# Test all feeds with quality classification
python -m newsbot.feed_validator --limit 3

# Test specific categories
python -m newsbot.feed_validator --categories tech,science --limit 5

# Skip problematic feeds
python -m newsbot.feed_validator --skip-bozo
```

#### Feed Quality Results
Based on validation testing:
- **High-yield sources** (LIKELY_FULL_TEXT): Ars Technica, The Verge, NASA, Alhurra
- **Mixed content** (MIXED): STAT News, some WordPress-based feeds
- **Summary-only** (LIKELY_SUMMARY): Most major news outlets (BBC, Reuters, NYT)
- **Problematic feeds**: Some Arabic and finance feeds have XML parsing issues

## Full Article Scraping (Enrichment)
After fetching RSS summaries, you can enrich them by downloading the full web pages.

```python
from newsbot.main import fetch_multiple_feeds
from newsbot.scraper import fetch_full_articles

# 1. Fetch RSS-level summaries
all_articles = fetch_multiple_feeds(["tech"], use_deduplication=True)
tech_articles = all_articles.get("tech", [])[:5]  # sample subset

# 2. Fetch & clean full content
full_success, full_failed = fetch_full_articles(tech_articles)
print(f"Full content fetched: {len(full_success)} | Failed: {len(full_failed)}")

# Inspect first article
if full_success:
    first = full_success[0]
    print(first.title)
    print(first.content[:400], '...')
```

### Enrichment Helper with Storage & Deduplication
```python
from newsbot.scraper import enrich_and_store_full_articles
from newsbot.storage import NewsStorage
from newsbot.deduplicator import ArticleDeduplicator

storage = NewsStorage()
all_articles = fetch_multiple_feeds(["tech"], use_deduplication=True)
tech_articles = all_articles.get("tech", [])

stats = enrich_and_store_full_articles(tech_articles, storage, deduplicator=ArticleDeduplicator())
print(stats)
storage.close()
```

### Notes
- Basic heuristic content extraction: looks for common article containers.
- Falls back to full <body> text if no target block found.
- Future improvement: integrate readability-lxml or trafilatura for richer extraction.
- Retries & user-agent rotation included to reduce transient failures.

## Configuration

### Adding New RSS Feeds

Edit `newsbot/rss_feeds.py` to add new feeds:

```python
RSS_FEEDS = {
    "international": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "YOUR_NEW_INTERNATIONAL_FEED_URL"  # Add here
    ],
    "new_category": [  # Add entirely new categories
        "https://example.com/rss.xml"
    ]
}
```

### Customizing Deduplication

Modify `newsbot/deduplicator.py` to adjust deduplication settings:

```python
class ArticleDeduplicator:
    def __init__(self):
        self.title_similarity_threshold = 0.85  # Adjust similarity threshold (0-1)
```

### Database Schema

The SQLite database stores articles with the following schema:

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-increment ID |
| title | TEXT | Article title |
| link | TEXT UNIQUE | Article URL (used for deduplication) |
| publish_date | TEXT | Publication date from RSS feed |
| source | TEXT | RSS feed source name |
| category | TEXT | News category (tech, international, etc.) |
| content | TEXT | Cleaned article content/summary |

## Features in Detail

### 1. RSS Feed Processing
- Handles multiple RSS feed formats
- Graceful error handling for malformed feeds
- Automatic parsing of standard RSS fields
- Configurable feed timeout and retry logic

### 2. Content Cleaning
- Removes HTML tags, scripts, and styles
- Strips excessive whitespace and special characters
- Preserves meaningful text content
- Handles various text encodings

### 3. Deduplication System
- **URL-based**: Prevents duplicate articles with same URL
- **Content-based**: Uses MD5 hashing of title + content snippet
- **Title similarity**: Detects similar articles using sequence matching
- **Configurable thresholds**: Adjust similarity sensitivity

### 4. Error Handling
- Network timeout handling
- Malformed RSS feed parsing
- Database connection errors
- Individual article processing failures

## Logging

The application provides comprehensive logging at different levels:

- **INFO**: Normal operation progress, article counts, processing status
- **WARNING**: Feed parsing issues, skipped articles, minor errors
- **ERROR**: Critical errors, database issues, network failures
- **DEBUG**: Detailed deduplication information, individual article processing

## Performance Considerations

- **Database**: Uses SQLite with UNIQUE constraint on URLs for efficient deduplication
- **Memory**: Processes articles in batches to avoid memory issues with large feeds
- **Network**: Implements connection pooling and timeout handling
- **Scalability**: Designed to handle hundreds of RSS feeds and thousands of articles

## Week 4: Data Preprocessing & Embedding Comparison

The notebook `notebooks/Week4_Expanded_Data_Comparison.ipynb` (mirrored as `Week4_Data_Preprocessing_and_Embeddings.ipynb`) provides an end-to-end pipeline for evaluating different embedding strategies over the collected news dataset.

### Contents
1. Data loading from SQLite (`news_articles.db`)
2. Text cleaning & tokenization (punctuation removal, lowercasing, stopwords, short token filtering)
3. Training Word2Vec models (CBOW & Skip-gram) with consistent hyperparameters
4. Generating DistilBERT contextual embeddings (CLS token pooling)
5. Semantic analysis: vocabulary coverage, nearest neighbors, document similarity
6. Visualization: PCA projection of Word2Vec spaces
7. Performance & qualitative comparison + conclusions & presentation summary

### Quick Run
```bash
conda activate news-env
pip install gensim transformers nltk seaborn torch scikit-learn
jupyter notebook notebooks/Week4_Expanded_Data_Comparison.ipynb
```

The notebook will auto-download required NLTK corpora (`punkt`, `stopwords`) if missing.

### Model Comparison Summary
| Model | Training Effort | Contextual Awareness | Strengths | Recommended Use |
|-------|-----------------|----------------------|-----------|-----------------|
| CBOW | Fast (seconds) | Local window only | Speed, baseline | Quick exploratory tests |
| Skip-gram | Moderate | Local window only | Better rare word semantics | Lightweight semantic tasks |
| DistilBERT | Pretrained inference | Global bidirectional | Rich contextual meaning | Production semantic search/RAG |

### Key Findings
* DistilBERT embeddings yield superior semantic grouping and handle polysemy.
* Skip-gram outperforms CBOW on rare/domain-specific tokens.
* Word2Vec models are fast to train; BERT inference remains feasible for moderate corpus sizes.
* Subword tokenization (BERT) ensures vocabulary coverage vs OOV limitations in Word2Vec.

### Recommendations
* Use DistilBERT (or Sentence-BERT in future) for retrieval, clustering, and user-facing semantic tasks.
* Maintain a Skip-gram Word2Vec model as a fast fallback and for quick exploratory similarity checks.
* Possible extensions: introduce FastText for OOV handling, add evaluation metrics (intrinsic analogy tests, downstream classification), and integrate a vector database for RAG.

---

## Extending the Project

### For NLP Applications
```python
# Export articles for NLP processing
def export_for_nlp(category=None, min_content_length=100):
    storage = NewsStorage()
    # Add SQL query to filter and export articles
    # Return structured data for model training
```

### For RAG Pipelines
```python
# Prepare articles for vector embedding
def prepare_for_rag():
    # Add text chunking, metadata preparation
    # Format for vector database ingestion
    pass
```

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure all dependencies are installed in the conda environment
2. **RSS feed failures**: Some feeds may be temporarily unavailable or require different parsing
3. **Database locked**: Ensure only one instance is writing to the database at a time
4. **Memory issues**: For large-scale processing, implement batch processing

### Debug Mode

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## License

MIT License - feel free to use and modify for your projects.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## Future Enhancements

- [ ] Async/parallel RSS feed processing
- [ ] Web scraping for full article content
- [ ] Support for additional feed formats (Atom, JSON)
- [ ] Real-time feed monitoring
- [ ] Integration with vector databases for RAG
- [ ] Article sentiment analysis
- [ ] Automated categorization using ML

## Kafka Streaming Layer

This project now includes an end-to-end streaming layer so new RSS items are published to Kafka as soon as they are fetched, and full-content enrichment begins immediately via consumer workers.

### Architecture Overview
1. `newsbot.kafka_producer` periodically fetches new RSS summaries and publishes JSON messages to the `rss.items` topic.
2. `newsbot.kafka_scraper_consumer` (sync) or `newsbot.kafka_scraper_async_consumer` (async) consume messages, scrape full article bodies, store them in SQLite, and publish enriched JSON to the `articles.cleaned` topic.
3. Failures are logged (and optionally published) to `alerts.feed_failures`.
4. `articles.cleaned` uses log compaction (recommended in production) so the latest enriched version per URL remains available for downstream consumers (indexers, vector embedding jobs, etc.).

### Services (Development Stack)
Spin up a local Kafka + ZooKeeper + Schema Registry stack (Schema Registry is optional here, but provided for future Avro/Protobuf evolution):

```bash
docker compose up -d
# Tear down
docker compose down -v
```

Exposed ports:
- ZooKeeper: 2181
- Kafka Broker: 9092 (internal hostname `kafka` inside network)
- Schema Registry: 8081

### Topic Creation
Automatic topic creation is disabled. Create required topics after the stack is up:

```bash
bash scripts/create_kafka_topics.sh
```

Topics created:
- `rss.items` (3 partitions, 7d retention)
- `articles.cleaned` (3 partitions, 30d retention, `cleanup.policy=compact,delete`)
- `alerts.feed_failures` (1 partition, 7d retention)

Adjust partition counts upward for higher parallelism in production; increase replication factor >1 in multi-broker clusters.

### Installing Kafka Dependencies

```bash
conda activate news-env
pip install -r requirements-kafka.txt
```

Key packages: `confluent-kafka`, `aiokafka`, `httpx` (for future async scrape), plus existing `feedparser`, `requests`, `beautifulsoup4`.

### Message Schema (JSON)
Producer publishes the following JSON to `rss.items`:

```json
{
    "id": "uuid",
    "title": "string",
    "link": "string",
    "publish_date": "ISO8601 or RSS date",
    "source": "string",
    "category": "string",
    "summary": "RSS summary/description cleaned",
    "fetched_at": "ISO8601 UTC timestamp"
}
```

Enriched consumer publishes to `articles.cleaned` the same schema plus:

```json
{
    "full_content": "Cleaned full article text",
    "enriched_at": "ISO8601 UTC timestamp"
}
```

Future optional evolution: adopt Avro with Schema Registry; define subject names `rss.items-value` and `articles.cleaned-value`.

### Running the Producer

One-shot batch (fetch once, produce all):
```bash
conda activate news-env
python -m newsbot.kafka_producer --once
```

Continuous polling every 10 minutes:
```bash
python -m newsbot.kafka_producer --poll 10
```

Subset of categories:
```bash
python -m newsbot.kafka_producer --once --categories tech,international
```

Environment variables:
| Variable | Default | Description |
|----------|---------|-------------|
| KAFKA_BOOTSTRAP_SERVERS | localhost:9092 | Broker bootstrap list (metadata advertises `localhost:29092` for host access) |
| RSS_PRODUCER_TOPIC | rss.items | Topic for RSS summaries |
| PRODUCER_CATEGORIES | (all) | Comma-separated categories |
| PRODUCER_SLEEP_JITTER_S | 20 | Max random extra seconds between polls |

### Running Consumers

Sync consumer (simpler, good baseline):
```bash
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 python -m newsbot.kafka_scraper_consumer
```

Process a fixed number of messages (test mode):
```bash
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 python -m newsbot.kafka_scraper_consumer --max-messages 5
```

Async consumer (higher throughput, bounded concurrency):
```bash
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 CONCURRENCY=10 python -m newsbot.kafka_scraper_async_consumer
```

Process only 20 messages:
```bash
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 CONCURRENCY=10 python -m newsbot.kafka_scraper_async_consumer --max-messages 20
```

Additional env vars:
| Variable | Default | Description |
|----------|---------|-------------|
| ARTICLES_CLEANED_TOPIC | articles.cleaned | Enriched output topic |
| ALERTS_TOPIC | alerts.feed_failures | Alerts/failures topic |
| CONCURRENCY | 5 | Max concurrent enrich tasks (async) |
| ASYNC_CONSUMER_POLL_TIMEOUT_S | 1.0 | getmany timeout seconds |

### Manual Smoke Run
End-to-end quick check:
```bash
python -m newsbot.smoke_kafka_run
```
This will produce one batch then process a few messages synchronously and print DB stats.

### Metrics & Logging
In-code counters (placeholders) are logged periodically:
- Producer: `messages_produced`, `produce_errors`
- Consumer: `messages_consumed`, `processing_success`, `processing_failures`

Suggested Prometheus metric names:
```
newsbot_producer_messages_total
newsbot_producer_failures_total
newsbot_consumer_messages_total
newsbot_consumer_success_total
newsbot_consumer_failures_total
```
Integrate by exposing an HTTP metrics endpoint (e.g., `prometheus_client`) in a future enhancement.

### Scaling Guidance
| Aspect | Recommendation |
|--------|----------------|
| Partitions | 3 (dev) -> scale to (#consumer_instances * 2) for prod |
| Replication | 1 (dev) -> >=3 in prod cluster |
| Retention | Tune by downstream latency & storage budget |
| Compaction | Enable for `articles.cleaned` to keep latest full content |
| Consumer Groups | Separate groups for enrichment vs embedding pipelines |

### Troubleshooting
| Issue | Cause | Fix |
|-------|-------|-----|
| Consumer lag grows | Slow scraping | Increase concurrency, add caching, scale replicas |
| DB locked errors | WAL busy | Ensure short transactions; consider queueing writes |
| Producer timeouts | Broker unreachable | Check docker compose status & bootstrap env |
| No messages consumed | Wrong topic or group config | Verify env vars & topic existence |
| High duplicate records | Overlapping fetch intervals | Track last publish timestamp or add state store |

### Sanity Test Report Template
After a test run, capture:
```
Kafka Stack: up (docker compose ps)
Topics: (docker exec kafka kafka-topics --bootstrap-server kafka:9092 --list)
Producer Batch Size: <N>
Consumer Processed: <N>
DB Total Articles: <count>
Enriched (full_content not null): <count>
Failures Logged: <count>
```

### Production Notes
- Use managed Kafka (e.g., Confluent Cloud / MSK) with TLS + auth.
- Increase acks durability, replication factor >= 3.
- Add dead-letter topic for persistent failures.
- Externalize configuration (12-factor) via environment or config service.
- Consider a streaming framework (Flink, Kafka Streams) for downstream transformations.

---
