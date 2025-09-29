# News Chatbot Project

A scalable Python application that collects news articles from multiple RSS feeds, preprocesses them, and stores them for NLP model training and retrieval-based RAG pipelines.

## Features

- **Multi-source RSS fetching**: Supports international, tech, finance, and Arabic news sources
- **Intelligent text cleaning**: Removes HTML tags, scripts, ads, and excessive whitespace
- **Advanced deduplication**: URL-based and content-based duplicate detection with title similarity matching
- **Flexible storage**: SQLite database with metadata (title, link, publish date, source, category)
- **Scalable architecture**: Easy to add new RSS feeds and categories
- **Comprehensive logging**: Detailed logging for monitoring and debugging
- **Error handling**: Graceful handling of feed parsing errors and network issues

## Project Structure

```
news_project/
├── newsbot/
│   ├── __init__.py          # Package initialization
│   ├── main.py              # Main execution script with examples
│   ├── rss_feeds.py         # RSS feed URLs configuration
│   ├── cleaner.py           # HTML cleaning and text processing
│   ├── storage.py           # SQLite database operations
│   └── deduplicator.py      # Article deduplication logic
├── news_articles.db         # SQLite database (created automatically)
├── README.md                # This file
└── .github/
    └── copilot-instructions.md
```

## Setup

### 1. Environment Setup
```bash
# Ensure you have conda installed, then activate your environment
conda activate news-env

# Install required dependencies
pip install feedparser beautifulsoup4 requests
```

### 2. Quick Start
```bash
# Navigate to project directory
cd /path/to/news_project

# Run the main script (demonstrates both single and multiple feed fetching)
python -m newsbot.main
```

## Usage Examples

### Basic Usage - Fetch All Categories
```python
from newsbot.main import fetch_multiple_feeds, save_articles_batch
from newsbot.storage import NewsStorage

# Initialize storage
storage = NewsStorage()

# Fetch articles from all configured RSS feeds with deduplication
all_articles = fetch_multiple_feeds(use_deduplication=True)

# Save articles to database
stats = save_articles_batch(all_articles, storage)

# Print statistics
for category, stat in stats.items():
    print(f"{category}: {stat['saved']}/{stat['total']} saved")

storage.close()
```

### Fetch Specific Categories
```python
# Fetch only tech and international news
specific_categories = ["tech", "international"]
articles = fetch_multiple_feeds(specific_categories, use_deduplication=True)
```

### Single Feed Processing
```python
from newsbot.main import fetch_rss_feed

# Fetch from a single RSS feed
articles = fetch_rss_feed("http://feeds.bbci.co.uk/news/world/rss.xml", "international")
```

### Database Operations
```python
from newsbot.storage import NewsStorage

storage = NewsStorage()

# Get database statistics
stats = storage.get_statistics()
print(f"Total articles: {stats['total_articles']}")
print(f"By category: {stats['by_category']}")
print(f"Top sources: {stats['top_sources']}")

storage.close()
```

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
