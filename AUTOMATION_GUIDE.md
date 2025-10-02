# Automated News Pipeline - Quick Start Guide

## 🚀 Quick Start (Easiest Way)

**Run the complete automation with one command:**

```bash
cd /home/iyedpc1/news_project
./scripts/start_pipeline.sh test
```

This will:
- ✅ Activate the conda environment
- ✅ Check and install dependencies
- ✅ Start Kafka infrastructure
- ✅ Run a quick test extraction (tech + science categories)
- ✅ Show database statistics

## 📋 Automation Options

### 1. Interactive Menu
```bash
./scripts/start_pipeline.sh
```
Provides a menu with options:
1. Quick test (10 articles from tech + science)
2. Single extraction (30 articles, all categories)
3. Custom single extraction
4. Continuous extraction (every 10 minutes)
5. Custom continuous extraction
6. Check database statistics

### 2. Command Line Options

**Quick test:**
```bash
./scripts/start_pipeline.sh test
```

**Single extraction:**
```bash
./scripts/start_pipeline.sh single
./scripts/start_pipeline.sh single "tech,science" 20
```

**Continuous extraction:**
```bash
./scripts/start_pipeline.sh continuous
./scripts/start_pipeline.sh continuous "tech,international" 600 30
```

**Database statistics:**
```bash
./scripts/start_pipeline.sh stats
```

## 🔄 Continuous Automation

### Run 24/7 Pipeline
```bash
# Every 10 minutes, all categories, 30 articles max
./scripts/start_pipeline.sh continuous "" 600 30

# Every 5 minutes, tech only, 15 articles max  
./scripts/start_pipeline.sh continuous "tech" 300 15

# Every hour, specific categories
./scripts/start_pipeline.sh continuous "tech,science,international" 3600 50
```

### Background Operation
```bash
# Run in background with nohup
nohup ./scripts/start_pipeline.sh continuous > pipeline.log 2>&1 &

# Check if running
ps aux | grep start_pipeline

# Stop background process
pkill -f start_pipeline
```

## 📊 Monitoring

### Real-time Database Growth
```bash
# Check current stats
./scripts/start_pipeline.sh stats

# Or directly
python -m newsbot.db_stats

# JSON format for scripting
python -m newsbot.db_stats --json

# Health check with threshold
python -m newsbot.db_stats --min-coverage 50
```

### View Recent Articles
```bash
python - <<'PY'
from newsbot.storage import NewsStorage
s = NewsStorage()
print("Recent articles:")
for row in s.conn.execute("SELECT title, category, source FROM articles ORDER BY id DESC LIMIT 10"):
    print(f"• {row[0][:60]}... [{row[1]}] from {row[2]}")
s.close()
PY
```

## 🛠 Advanced Automation Scripts

The project includes several automation scripts:

### 1. `start_pipeline.sh` (Recommended)
- Complete setup and environment management
- Interactive menu or command-line usage
- Handles conda activation automatically

### 2. `quick_automation.py`
- Direct Python automation
- Requires manual environment setup
- More programmatic control

### 3. `automated_pipeline.py`
- Full-featured automation with error handling
- Continuous monitoring and restart
- Advanced configuration options

### 4. `scheduled_extraction.py`
- Cron-like scheduling
- Daily/hourly/custom schedules
- Background service mode

## 📈 Current Performance

After running the quick test:
- **Database**: 359/584 articles enriched (61.47% coverage)
- **Growth**: +5 articles from the test run
- **Categories**: Tech and Science working perfectly
- **Infrastructure**: Kafka running properly

## 🎯 Recommended Usage Patterns

### For Development/Testing
```bash
# Quick verification
./scripts/start_pipeline.sh test

# Single extraction to test changes
./scripts/start_pipeline.sh single "tech" 10
```

### For Daily News Collection
```bash
# Morning update (run once per day)
./scripts/start_pipeline.sh single "" 100

# Or schedule with cron
echo "0 6 * * * cd /home/iyedpc1/news_project && ./scripts/start_pipeline.sh single" | crontab -
```

### For Real-time Pipeline
```bash
# Continuous operation (restart if needed)
while true; do
    ./scripts/start_pipeline.sh continuous "" 600 30
    echo "Pipeline stopped, restarting in 60 seconds..."
    sleep 60
done
```

## 🔧 Troubleshooting

### Environment Issues
```bash
# If conda environment missing
conda create -n news-env python=3.12
conda activate news-env
pip install -r requirements-kafka.txt

# If dependencies missing, the script will auto-install them
```

### Kafka Issues
```bash
# Restart Kafka
docker-compose down
docker-compose up -d

# Check Kafka status
docker-compose ps
```

### Database Issues
```bash
# Check database size
ls -lh news_articles.db*

# Backup database
cp news_articles.db news_articles.backup.$(date +%Y%m%d).db

# View table schema
python - <<'PY'
import sqlite3
conn = sqlite3.connect('news_articles.db')
print(conn.execute("PRAGMA table_info(articles)").fetchall())
PY
```

## 🎉 Success!

Your automated news pipeline is now running! The system will:

1. **Fetch** articles from 66+ RSS feeds
2. **Extract** full article content via web scraping  
3. **Deduplicate** to avoid duplicate articles
4. **Store** in SQLite with metadata
5. **Monitor** coverage and health
6. **Continue** automatically at specified intervals

### Optional: Kick off Spark feature extraction

Once a pipeline cycle completes, you can generate TF-IDF vectors for the newly
enriched articles using the Spark container:

```bash
docker compose up -d spark
docker compose exec spark pip install --target /workspace/.sparkdeps numpy  # first run only
docker compose exec -e PYTHONPATH=/workspace:/workspace/.sparkdeps \
    spark spark-submit --master local[*] --name ContainerSparkBatch \
    scripts/run_spark_processor.py --mode batch --since-id <LAST_PROCESSED_ID>
```

- Replace `<LAST_PROCESSED_ID>` with the latest `articles.id` processed (or omit for full backfill).
- Streaming mode is also available for continuous feature generation; see [`processing.md`](processing.md) for full instructions.

The database grows continuously with fresh news content, ready for NLP analysis, embedding generation, and RAG applications.