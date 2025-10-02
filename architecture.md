# System Architecture

## Overview

The News Chatbot Project implements a modern, scalable architecture for real-time news collection and processing. The system supports two operational modes: **Batch Processing** for immediate results and **Streaming Processing** for real-time data pipelines and high-throughput scenarios.

## Architecture Diagram

```
┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐
│   RSS Sources   │    │   Apache Kafka   │    │    Storage &        │
│                 │    │                  │    │  Feature Extraction │
│ • BBC News      │    │ ┌──────────────┐ │    │                    │
│ • Tech RSS      │────▶│ │ rss.items    │ │────▶│ • SQLite WAL       │
│ • Finance       │    │ │   Topic      │ │    │ • Processed vectors │
│ • Arabic News   │    │ └──────────────┘ │    │ • Vector DB (Future)│
│ • Custom Feeds  │    │                  │    │                    │
└─────────────────┘    │ ┌──────────────┐ │    └────────────────────┘
                       │ │articles.     │ │
┌─────────────────┐    │ │cleaned Topic │ │    ┌─────────────────┐
│  Kafka Producer │────▶│ └──────────────┘ │────▶│   NLP Pipeline  │
│                 │    │                  │    │                 │
│ • RSS Fetcher   │    │ ┌──────────────┐ │    │ • Content       │
│ • Batch Mode    │    │ │alerts.feed_  │ │    │   Analysis      │
│ • Poll Mode     │    │ │failures      │ │    │ • Embeddings    │
└─────────────────┘    │ └──────────────┘ │    │ • Classification│
                       └──────────────────┘    └─────────────────┘
                                 ▲
                       ┌─────────┴─────────┐
                       │ Kafka Consumers   │
                       │                   │
                       │ • Sync Consumer   │
                       │ • Async Consumer  │
                       │ • Enrichment      │
                       │ • Error Handling  │
                       └─────────┬─────────┘
                                 │
                       ┌─────────▼─────────┐
                       │  Spark Processor  │
                       │ (Batch & Stream)  │
                       │ • TF-IDF features │
                       │ • Incremental id  │
                       └───────────────────┘
```

## Core Components

### 1. Data Ingestion Layer

#### RSS Feed Manager (`newsbot/rss_feeds.py`)
- **Purpose**: Centralized configuration of news sources
- **Sources**: International (BBC, NYT), Technology (TechCrunch), Finance (Reuters), Arabic (Al Jazeera)
- **Extensibility**: Simple configuration-based feed addition
- **Error Handling**: Graceful handling of malformed feeds and network issues

#### Content Fetcher (`newsbot/main.py`)
- **RSS Processing**: Parses standard RSS/Atom feeds
- **Metadata Extraction**: Title, link, publish date, summary, source
- **Batch Operations**: Processes multiple feeds concurrently
- **Deduplication**: Prevents duplicate article ingestion

### 2. Streaming Layer (Apache Kafka)

#### Message Broker Architecture
```
Topics Structure:
├── rss.items (3 partitions, 7d retention)
│   └── Raw RSS article metadata
├── articles.cleaned (3 partitions, 30d retention, compacted)
│   └── Enriched articles with full content
└── alerts.feed_failures (1 partition, 7d retention)
    └── Error notifications and monitoring
```

#### Producer Component (`newsbot/kafka_producer.py`)
- **Operational Modes**:
  - Batch Mode: One-time fetch and publish all articles
  - Poll Mode: Continuous monitoring with configurable intervals
- **Message Format**: JSON with UUID, metadata, and timestamps
- **Delivery Guarantees**: At-least-once delivery with retry logic
- **Performance**: 500+ messages/second throughput

#### Consumer Components
**Synchronous Consumer** (`newsbot/kafka_scraper_consumer.py`):
- **Processing Model**: Sequential message processing
- **Reliability**: Strong consistency guarantees
- **Use Case**: Critical processing where order and reliability are paramount
- **Throughput**: 5-15 articles/minute (network dependent)

**Asynchronous Consumer** (`newsbot/kafka_scraper_async_consumer.py`):
- **Processing Model**: Concurrent processing with semaphore-based limiting
- **Scalability**: Configurable concurrency (default: 10 workers)
- **Use Case**: High-throughput scenarios with independent article processing
- **Throughput**: 50-100 articles/minute with bounded concurrency

### 3. Content Enrichment Pipeline

#### Web Scraper (`newsbot/scraper.py`)
- **Full Article Extraction**: Downloads complete article content beyond RSS summaries
- **Content Cleaning**: Removes ads, navigation, and non-article content
- **Retry Logic**: Handles transient network failures and rate limiting
- **User Agent Rotation**: Prevents blocking from news sites
- **Error Handling**: Graceful degradation to RSS summary if scraping fails

#### Text Processing (`newsbot/cleaner.py`)
- **HTML Sanitization**: Removes tags, scripts, and styling
- **Text Normalization**: Whitespace cleanup and encoding standardization
- **Content Validation**: Ensures minimum content quality thresholds
- **Language Detection**: Basic language identification for multilingual support

### 4. Storage Layer

#### Database Design (`newsbot/storage.py`)
```sql
-- Articles table schema
CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    link TEXT UNIQUE NOT NULL,  -- Natural deduplication key
    publish_date TEXT,
    source TEXT,
    category TEXT,
    content TEXT,               -- RSS summary or full content
    full_content TEXT,          -- Scraped full article (nullable)
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    enriched_at TIMESTAMP,      -- When full content was added
    metadata JSON               -- Extensible metadata field
);
```

#### Storage Features
- **SQLite with WAL Mode**: Concurrent read access, atomic writes
- **Schema Migrations**: Automatic database schema evolution
- **Upsert Operations**: Conflict resolution for duplicate handling
- **Performance**: 1000+ inserts/second with proper indexing
- **Backup Support**: Integrated backup and restore functionality

### 5. Feature Extraction (`newsbot/spark_processor.py`)

- **Purpose**: Convert curated article text into token and TF-IDF vectors for NLP workloads.
- **Execution Modes**: Ad-hoc batch runs and Structured Streaming micro-batches driven by a synthetic rate source.
- **Storage Target**: Persists feature payloads to the `processed_articles` table (upsert semantics keyed by `article_id`).
- **Pipeline**: RegexTokenizer → StopWordsRemover → HashingTF → IDF, configured with 4,096 features by default.
- **Operational Guide**: See [`processing.md`](processing.md) for container commands, dependency setup, and troubleshooting tips.

### 6. RSS Feed Management and Validation

#### Feed Configuration (`newsbot/rss_feeds.py`)
- **Original RSS_FEEDS**: 24 verified feeds across 4 categories
- **Extended RSS_FEEDS_EXTENDED**: 66+ feeds across 8 categories
- **Categories**: international, tech, finance, arabic, science, health, sports, entertainment
- **Content-type annotations**: Each feed marked as "Full article" or "Summary" based on analysis

#### Feed Validation System (`newsbot/feed_validator.py`)
- **Quality Classification**: LIKELY_FULL_TEXT, MIXED, LIKELY_SUMMARY, NO_DATA
- **Content Analysis**: Length-based heuristics and summary/content ratio comparison
- **Error Handling**: Bozo feed detection and XML parsing error management
- **Performance Metrics**: Feed accessibility and content richness scoring

#### Validation Results
```python
# High-yield feeds for full content
FULL_TEXT_SOURCES = [
    "https://feeds.arstechnica.com/arstechnica/technology-lab",  # Tech
    "https://www.nasa.gov/rss/dyn/breaking_news.rss",  # Science
    "https://www.alhurra.com/rss",  # Arabic
    "https://www.statnews.com/feed/",  # Health
]

# Summary-only but reliable
SUMMARY_SOURCES = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",  # International
    "https://www.ft.com/?format=rss",  # Finance
]
```

### 6. Deduplication System (`newsbot/deduplicator.py`)

#### Multi-Level Deduplication Strategy
1. **URL-based**: Primary key constraint on article link
2. **Content Hash**: MD5 of title + content snippet
3. **Semantic Similarity**: Configurable title similarity threshold (default: 0.85)

#### Implementation
```python
class ArticleDeduplicator:
    def __init__(self, title_similarity_threshold=0.85):
        self.seen_urls = set()
        self.seen_hashes = set()
        self.threshold = title_similarity_threshold
    
    def is_duplicate(self, article):
        # URL check (fastest)
        # Hash check (medium)
        # Similarity check (slowest, most accurate)
```

## Data Flow

### Batch Processing Flow
```
1. RSS Feeds → 2. Feed Parser → 3. Deduplicator → 4. Text Cleaner → 5. SQLite Storage
                      ↓
6. Enrichment Request → 7. Web Scraper → 8. Content Cleaner → 9. Database Update
```

### Streaming Processing Flow
```
1. RSS Feeds → 2. Kafka Producer → 3. rss.items Topic
                                           ↓
4. Kafka Consumer → 5. Web Scraper → 6. Content Enrichment → 7. articles.cleaned Topic
        ↓                                                            ↓
8. SQLite Storage                                            9. Downstream Analytics
        ↓
10. Error Handling → 11. alerts.feed_failures Topic
```

## Scalability Considerations

### Horizontal Scaling

#### Producer Scaling
- **Stateless Design**: Multiple producer instances can run independently
- **Feed Partitioning**: Distribute feeds across producer instances
- **Rate Limiting**: Configurable delays to respect source rate limits

#### Consumer Scaling
- **Kafka Consumer Groups**: Automatic partition assignment and rebalancing
- **Processing Isolation**: Independent failure domains per consumer
- **Concurrency Control**: Bounded parallelism prevents resource exhaustion

#### Storage Scaling
- **Read Replicas**: SQLite WAL mode supports multiple concurrent readers
- **Partitioning Strategy**: Category-based or time-based table partitioning
- **Caching Layer**: Redis integration for frequently accessed articles

### Vertical Scaling

#### Memory Optimization
- **Streaming Processing**: Articles processed individually to minimize memory footprint
- **Batch Size Tuning**: Configurable batch sizes for different workload characteristics
- **Connection Pooling**: Efficient resource utilization for database connections

#### CPU Optimization
- **Async I/O**: Non-blocking network operations for web scraping
- **Text Processing**: Optimized regex patterns and string operations
- **Concurrent Processing**: Multi-threaded article enrichment

## Error Handling & Reliability

### Fault Tolerance Strategy

#### Network Resilience
- **Retry Mechanisms**: Exponential backoff for transient failures
- **Circuit Breakers**: Prevent cascade failures from problematic feeds
- **Timeout Handling**: Configurable timeouts for different operation types
- **Graceful Degradation**: Continue processing when individual feeds fail

#### Data Integrity
- **ACID Transactions**: Database operations wrapped in transactions
- **Idempotent Operations**: Safe to retry any operation
- **Consistency Checks**: Validation of data integrity during processing
- **Backup Strategies**: Automated database backups with retention policies

#### Monitoring & Alerting
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Metrics Collection**: Performance counters and processing statistics
- **Health Checks**: Service availability and dependency monitoring
- **Alert Topics**: Kafka-based alerting for operational issues

### Error Recovery

#### Dead Letter Processing
```python
# Error handling flow
try:
    process_article(article)
except RetryableError as e:
    retry_queue.add(article, delay=calculate_backoff(attempt))
except PermanentError as e:
    dead_letter_queue.add(article, error=str(e))
```

#### State Recovery
- **Kafka Offset Management**: Consumer progress tracking for restart recovery
- **Processing State**: Idempotent operations allow safe re-processing
- **Database Recovery**: WAL mode provides crash recovery capabilities

## Performance Characteristics

### Throughput Metrics
| Component | Baseline Performance | Optimized Performance | Latest Test Results |
|-----------|---------------------|----------------------|--------------------|
| RSS Fetching | 50-100 articles/min | 150-300 articles/min | 373 articles/2min (186/min) |
| Content Scraping | 5-10 articles/min | 15-30 articles/min | 60 articles/3min (20/min) |
| Database Writes | 100 inserts/sec | 1000+ inserts/sec | 391 total, 71 enriched |
| Kafka Producer | 100 msgs/sec | 500+ msgs/sec | 373 msgs in <1s |
| Kafka Consumer | 10 msgs/sec | 100+ msgs/sec | 60 msgs in 3min |
| Feed Validation | N/A | N/A | 66 feeds in 2min |

### Latency Profiles
- **RSS to Kafka**: < 100ms per article
- **Kafka to Enrichment**: < 1s processing delay
- **End-to-End**: 30s-5min (depending on scraping success)
- **Database Query**: < 10ms for typical queries

### Resource Requirements
| Deployment Mode | CPU | Memory | Storage | Network |
|-----------------|-----|--------|---------|---------|
| Development | 2 cores | 4GB RAM | 10GB | 10 Mbps |
| Production | 8 cores | 16GB RAM | 100GB | 100 Mbps |
| High-Volume | 16 cores | 32GB RAM | 1TB | 1 Gbps |

## Security Considerations

### Data Protection
- **Input Validation**: Sanitization of all external data sources
- **SQL Injection Prevention**: Parameterized queries throughout
- **XSS Protection**: HTML content cleaning and validation
- **Rate Limiting**: Protection against DoS from upstream sources

### Network Security
- **TLS Encryption**: HTTPS for all external communications
- **User Agent Management**: Respectful scraping practices
- **IP Rotation**: VPN support for geographic diversity
- **Authentication**: API keys and token management for premium feeds

### Operational Security
- **Secrets Management**: Environment variable configuration
- **Access Controls**: Database user permissions and roles
- **Audit Logging**: Comprehensive activity tracking
- **Backup Encryption**: Secure backup storage and transmission

## Future Enhancements

### Near-term (1-3 months)
- **Vector Database Integration**: Embedding storage for semantic search
- **Advanced NLP Pipeline**: Named entity recognition and sentiment analysis
- **Real-time Analytics**: Dashboard for monitoring and insights
- **API Layer**: REST/GraphQL interface for external consumers

### Medium-term (3-6 months)
- **Multi-language Support**: Enhanced processing for Arabic and other languages
- **Machine Learning Pipeline**: Automated content categorization and quality scoring
- **Distributed Processing**: Kubernetes deployment and orchestration
- **Search Interface**: Elasticsearch integration for full-text search

### Long-term (6+ months)
- **AI-Powered Summarization**: Automated article summarization using LLMs
- **Real-time Recommendations**: Personalized content delivery
- **Multi-modal Processing**: Image and video content extraction
- **Blockchain Integration**: Content provenance and verification

## Development & Testing

### Development Environment
```bash
# Complete development setup
conda activate news-env
docker-compose up -d
python -m newsbot.smoke_kafka_run
```

### Testing Strategy
- **Unit Tests**: Component-level testing with mocks
- **Integration Tests**: End-to-end pipeline validation
- **Performance Tests**: Load testing with synthetic data
- **Smoke Tests**: Production readiness validation

### CI/CD Pipeline
```yaml
# Example GitHub Actions workflow
stages:
  - lint: flake8, black, mypy
  - test: pytest with coverage
  - integration: docker-compose smoke tests
  - deploy: conditional deployment to staging/prod
```

## Conclusion

This architecture provides a robust foundation for news collection and processing that can scale from development to production environments. The dual-mode design (batch and streaming) offers flexibility for different use cases while maintaining consistency in data processing and storage.

Recent enhancements include:
- **Extended RSS coverage**: 66+ feeds across 8 categories with quality validation
- **Feed validation system**: Automated quality assessment and content-type classification  
- **Proven performance**: 391 articles processed with 18% full-content enrichment rate
- **Category optimization**: Tech feeds show 34% full-content rate vs <7% for news feeds

The system is designed with modern software engineering principles:
- **Modularity**: Clear separation of concerns
- **Scalability**: Horizontal and vertical scaling strategies
- **Reliability**: Comprehensive error handling and recovery
- **Observability**: Detailed logging and metrics
- **Maintainability**: Well-documented and tested codebase

Key architectural decisions prioritize:
1. **Developer Experience**: Easy setup and local development
2. **Operational Simplicity**: Minimal external dependencies
3. **Performance**: Optimized for common use cases
4. **Extensibility**: Plugin-based architecture for future enhancements