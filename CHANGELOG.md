# Changelog

## [Latest] - September 30, 2025

### Added
- **Extended RSS feed coverage**: Added `RSS_FEEDS_EXTENDED` dictionary with 66+ feeds across 8 categories
  - New categories: science, health, sports, entertainment
  - Enhanced existing categories with additional high-quality sources
  - Content-type annotations for each feed (full article vs summary)

- **Feed validation system**: New `feed_validator.py` module for RSS feed quality assessment
  - Automated classification: LIKELY_FULL_TEXT, MIXED, LIKELY_SUMMARY, NO_DATA
  - Content length analysis and summary/content ratio detection
  - Bozo feed error handling and XML parsing validation
  - CLI tool with filtering options (`--categories`, `--limit`, `--skip-bozo`)

- **Kafka streaming architecture**: Complete real-time processing pipeline
  - Producer: `kafka_producer.py` with batch and polling modes
  - Sync consumer: `kafka_scraper_consumer.py` for reliable processing
  - Async consumer: `kafka_scraper_async_consumer.py` for high throughput
  - Utilities: `kafka_utils.py` with producer/consumer builders and metrics
  - Docker compose stack with Kafka, Zookeeper, and Schema Registry

### Enhanced
- **Database enrichment**: Improved full-content extraction pipeline
  - Full-content coverage increased from 11 to 71 articles (545% improvement)
  - Tech category shows 34% full-content rate (64/190 articles)
  - Enhanced scraper with retry logic and user-agent rotation

- **Documentation**: Comprehensive project documentation
  - Updated `README.md` with streaming capabilities and validation tools
  - New `architecture.md` with system design and data flow diagrams
  - Performance metrics and scaling recommendations

### Performance Results
- **RSS Processing**: 373 articles processed in 2 minutes (186 articles/min)
- **Content Enrichment**: 60 articles enriched in 3 minutes (20 articles/min) 
- **Kafka Throughput**: 373 messages produced with zero errors
- **Feed Validation**: 66 feeds validated in under 2 minutes
- **Success Rate**: 100% message processing success (60/60 messages)

### Technical Improvements
- Enhanced error handling for malformed RSS feeds
- Improved deduplication across 373+ articles (only 6 duplicates found)
- Better logging with structured metrics and performance tracking
- Support for both original `RSS_FEEDS` and extended `RSS_FEEDS_EXTENDED`

### Categories Coverage
| Category | Feeds | Sample Sources |
|----------|-------|----------------|
| Tech | 11 feeds | Ars Technica, The Verge, Wired, Engadget |
| International | 11 feeds | BBC, Al Jazeera, Guardian, France24 |
| Finance | 12 feeds | WSJ, Bloomberg, MarketWatch, FT |
| Arabic | 12 feeds | Al Jazeera Arabic, CNN Arabic, Alhurra |
| Science | 5 feeds | NASA, Science News, Space.com |
| Health | 5 feeds | STAT News, Medical News Today, NYT Health |
| Sports | 5 feeds | ESPN, BBC Sport, Sky Sports |
| Entertainment | 5 feeds | Variety, Hollywood Reporter, Rolling Stone |

## Previous Versions
- [2025-09-29] Initial Kafka streaming implementation
- [2025-09-28] RSS feed collection and SQLite storage
- [2025-09-27] Project initialization and basic architecture