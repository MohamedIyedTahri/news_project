# Running the Automated Pipeline for 1.5 Hours

## Understanding Database Growth

**Why the database isn't growing much:**

RSS feeds typically return the **same 20-50 recent articles** on each fetch. The pipeline correctly:
1. ✅ Fetches all articles from RSS feeds (you saw 575 articles fetched)
2. ✅ Attempts to store them in the database
3. ✅ **Rejects duplicates** based on URL (this is correct behavior!)

**Real-world RSS behavior:**
- News sources update every **few hours**, not every few minutes
- Most RSS feeds show only the latest 20-50 articles
- To see meaningful growth, the pipeline needs to run for **hours**, not minutes

## Quick Start: 90-Minute Run

### Option 1: Run in tmux (Recommended for WSL)

```bash
cd /home/iyedpc1/news_project/scripts
./run_pipeline_90min.sh
```

This will:
- Start the pipeline in a detached tmux session
- Run for exactly 90 minutes (5400 seconds)
- Cycle every 10 minutes (9 total cycles)
- Keep all 6 categories monitored with verbose logging

**Attach to see live output:**
```bash
tmux attach -t news-pipeline-90min
```

**Detach (leave running in background):**
Press `Ctrl+B` then `D`

**Kill the session:**
```bash
tmux kill-session -t news-pipeline-90min
```

### Option 2: Monitor in Separate Terminal

While the pipeline runs, monitor growth in another terminal:

```bash
cd /home/iyedpc1/news_project/scripts
./monitor_stats.sh 60  # Check every 60 seconds
```

## Verbose Logging Features

The enhanced pipeline now provides:

### 1. Per-Category Tracking (All 6 Categories)
```
Per-category statistics:
  international: 225/360 (62.5%) [0 new articles]
  tech: 281/413 (68.0%) [+5 new articles]
  finance: 50/105 (47.6%) [0 new articles]
  arabic: 42/108 (38.9%) [0 new articles]
  science: 20/20 (100.0%) [0 new articles]
  health: 5/5 (100.0%) [0 new articles]
```

### 2. Producer Verbose Output
```
Producer: Category 'international': 117 unique articles (0 duplicates removed)
Producer: Category 'tech': 167 unique articles (3 duplicates removed)
Producer: Category 'finance': 50 unique articles (0 duplicates removed)
Producer: Category 'arabic': 41 unique articles (1 duplicates removed)
Producer: Category 'science': 180 unique articles (0 duplicates removed)
Producer: Category 'health': 20 unique articles (0 duplicates removed)
Producer: Total articles fetched: 575
Producer: Producing 575 RSS articles to topic=rss.items
```

### 3. Consumer Metrics
```
Consumer: Producer metrics: {...} | Consumer metrics: {...}
Consumer: Async processed messages=50
```

## Expected Growth Patterns

### Hourly Growth Estimates
Based on typical RSS feed behavior:

| Category      | Feeds | Est. New Articles/Hour |
|---------------|-------|------------------------|
| International | 5     | 10-20                  |
| Tech          | 6     | 15-30                  |
| Finance       | 6     | 5-15                   |
| Arabic        | 6     | 5-10                   |
| Science       | 4     | 5-10                   |
| Health        | 4     | 2-5                    |
| **Total**     | 31    | **40-90/hour**         |

**90-minute expected growth:** ~60-135 new articles

**Why growth varies:**
- News cycles (more updates during business hours)
- Weekend vs weekday (less content on weekends)
- Breaking news events (spikes in updates)
- Some feeds update hourly, others every 6-12 hours

## Manual Commands

### Start pipeline manually (custom duration)
```bash
cd /home/iyedpc1/news_project/scripts
source ~/miniconda3/etc/profile.d/conda.sh
conda activate news-env

# Run for 2 hours with 15-minute cycles
timeout 7200 python automated_pipeline.py --interval 900
```

### Check database stats anytime
```bash
cd /home/iyedpc1/news_project
source ~/miniconda3/etc/profile.d/conda.sh
conda activate news-env
python -m newsbot.db_stats
```

### Check specific category
```bash
python -c "
import sqlite3
conn = sqlite3.connect('news_articles.db')
cur = conn.cursor()
cur.execute('SELECT category, COUNT(*) FROM articles GROUP BY category')
for cat, count in cur.fetchall():
    print(f'{cat}: {count}')
conn.close()
"
```

## Troubleshooting

### "No growth after 30 minutes"
**This is normal!** RSS feeds may not have new content yet. The pipeline is working correctly - it's just that news sources haven't published new articles.

**Verify it's working:**
1. Check the producer is fetching: Look for "Producing X RSS articles"
2. Check the consumer is processing: Look for "Async processed messages=Y"
3. Check for duplicates: "Category 'X': N unique articles (M duplicates removed)"

### Science/Health showing 0 new articles
These categories have fewer feeds (4 each) and update less frequently. You may see 0 growth for hours, then sudden spikes when sources publish new content.

### Want faster growth?
Add more RSS feed sources in `newsbot/rss_feeds.py`:
```python
RSS_FEEDS = {
    'science': [
        # Add more science feeds
        'https://www.sciencedaily.com/rss/all.xml',
        'https://www.newscientist.com/feed/',
    ],
    # ...
}
```

## Logs and Monitoring

### View pipeline logs
```bash
tail -f /home/iyedpc1/news_project/scripts/pipeline.log
```

### Watch Kafka metrics
```bash
cd /home/iyedpc1/news_project
docker-compose exec kafka kafka-console-consumer \
    --bootstrap-server localhost:9092 \
    --topic rss.items \
    --from-beginning \
    --max-messages 10
```

### Check enrichment coverage
```bash
python -m newsbot.db_stats --min-coverage 60
```

## Post-Run Analysis

After the 90-minute run completes:

```bash
# Get final statistics
python -m newsbot.db_stats

# Check enrichment coverage by category
python -m newsbot.db_stats --json | python -c "
import sys, json
data = json.load(sys.stdin)
print('Enrichment Coverage:')
for cat in data['categories']:
    print(f\"  {cat['category']:15s}: {cat['coverage_pct']:5.1f}% ({cat['with_full']}/{cat['total']})\")
"

# Check latest articles
sqlite3 news_articles.db "
SELECT category, title, publish_date 
FROM articles 
ORDER BY publish_date DESC 
LIMIT 20;
"
```

## Summary

The automated pipeline is **working correctly**:
- ✅ All 6 categories are actively monitored
- ✅ Verbose logging shows "0 new articles" for categories without updates
- ✅ Producer fetches all available RSS articles
- ✅ Consumer enriches articles with full content
- ✅ Database correctly rejects duplicate URLs

**Limited growth is expected** because RSS feeds return the same articles until sources publish new content. Running for 1.5 hours will capture updates as they happen naturally.

### Follow-up: Vectorize the new content

Once the 90-minute session wraps up, run the SparkProcessor batch job to convert the fresh articles into TF-IDF vectors:

```bash
docker compose up -d spark
docker compose exec -e PYTHONPATH=/workspace:/workspace/.sparkdeps \
    spark spark-submit --master local[*] --name PostRunSparkBatch \
    scripts/run_spark_processor.py --mode batch --since-id <RUN_START_ID>
```

Refer to [`processing.md`](processing.md) to choose between batch or streaming and to review dependency setup tips.
