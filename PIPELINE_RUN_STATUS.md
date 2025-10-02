# 🚀 90-Minute Pipeline Run - Started!

## ✅ Current Status: RUNNING

**Start Time**: October 1, 2025, 21:19:43  
**End Time**: October 1, 2025, 22:49:43 (estimated)  
**Session**: `news-pipeline-90min` (tmux)

## 📊 Starting Statistics

```
Database: 623/1011 enriched (61.6%)

Per-category breakdown:
  international: 225/360 (62.5%)
  tech: 281/413 (68.0%)
  finance: 50/105 (47.6%)
  arabic: 42/108 (38.9%)
  science: 20/20 (100.0%)
  health: 5/5 (100.0%)
```

## 🎯 Enhanced Feed Performance

**Feeds per category:**
- International: 11 feeds (was 6) → **171 articles/cycle**
- Tech: 11 feeds (was 6) → **236 articles/cycle**
- Finance: 12 feeds (was 6) → **437 articles/cycle** 🔥
- Arabic: 12 feeds (was 6) → **113 articles/cycle**
- Science: 8 feeds (was 4) → **320 articles/cycle**
- Health: 8 feeds (was 4) → **20 articles/cycle**

**Total: 62 feeds → 1,297 articles per cycle!**

## 📈 Expected Results (90 minutes)

### Conservative Estimate
- **New articles**: 200-400
- **Hourly rate**: 130-265 articles/hour
- **Final database size**: ~1,200-1,400 articles

### Optimistic Estimate  
- **New articles**: 400-700
- **Hourly rate**: 265-465 articles/hour
- **Final database size**: ~1,400-1,700 articles

### Most Likely
- **New articles**: 300-550
- **Hourly rate**: 200-365 articles/hour
- **Final database size**: ~1,300-1,550 articles

## 🔍 How to Monitor Progress

### Option 1: Attach to live tmux session
```bash
tmux attach -t news-pipeline-90min
```
- See real-time logs
- Press `Ctrl+B` then `D` to detach (leave running)

### Option 2: Check database stats
```bash
cd /home/iyedpc1/news_project
source ~/miniconda3/etc/profile.d/conda.sh
conda activate news-env
python -m newsbot.db_stats
```

### Option 3: Run the monitoring script
```bash
cd /home/iyedpc1/news_project/scripts
./monitor_stats.sh 60  # Check every 60 seconds
```

### Option 4: Capture current tmux output
```bash
tmux capture-pane -t news-pipeline-90min -p | tail -100
```

## ⏰ Timeline

| Time    | Cycle | Expected Activity |
|---------|-------|-------------------|
| 21:19   | 1     | Initial fetch (1,297 articles) - mostly duplicates |
| 21:29   | 2     | Check for updates (~50-100 new) |
| 21:39   | 3     | Gradual growth (~30-80 new) |
| 21:49   | 4     | Continue accumulating (~40-90 new) |
| 21:59   | 5     | Mid-point check (~40-90 new) |
| 22:09   | 6     | Evening news cycle (~60-120 new) |
| 22:19   | 7     | Continue growth (~50-100 new) |
| 22:29   | 8     | Late updates (~40-80 new) |
| 22:39   | 9     | Final cycle (~30-70 new) |
| 22:49   | END   | **Automatic shutdown** |

## 📝 What to Expect Per Cycle

### Cycle Output Pattern:
```
============================================================
Starting pipeline cycle
Starting producer batch: ...
Producer batch completed successfully
Producer: Category 'international': 171 unique articles (11 duplicates removed)
Producer: Category 'tech': 236 unique articles (4 duplicates removed)
Producer: Category 'finance': 437 unique articles (3 duplicates removed)
Producer: Category 'arabic': 113 unique articles (9 duplicates removed)
Producer: Category 'science': 320 unique articles (0 duplicates removed)
Producer: Category 'health': 20 unique articles (0 duplicates removed)
Producer: Total articles fetched: 1297
Producer: Producing 1297 RSS articles to topic=rss.items

Starting consumer batch: ...
Consumer batch completed successfully
Consumer: Async processed messages=50

Database: XXX/YYYY enriched (ZZ.Z%)
Pipeline growth: +N articles since last check
Per-category statistics:
  international: XXX/YYY (ZZ.Z%) [+N new articles]
  tech: XXX/YYY (ZZ.Z%) [+N new articles]
  finance: XXX/YYY (ZZ.Z%) [+N new articles]
  arabic: XXX/YYY (ZZ.Z%) [+N new articles]
  science: XXX/YYY (ZZ.Z%) [+N new articles]
  health: XXX/YYY (ZZ.Z%) [+N new articles]
Pipeline cycle completed successfully
Next cycle at 22:XX:XX (sleeping 600s)
```

## 🎯 Key Improvements in This Run

### 1. **Verbose Category Tracking**
- ✅ All 6 categories explicitly shown
- ✅ "[0 new articles]" displayed when no growth
- ✅ "[+N new articles]" shows growth per category

### 2. **Enhanced RSS Feeds**
- ✅ 62 feeds (was 32) - nearly doubled!
- ✅ 1,297 articles/cycle (was 575) - 2.3x increase!
- ✅ More diverse sources across time zones

### 3. **Improved Logging**
- ✅ Producer shows per-category fetch results
- ✅ Consumer shows processing metrics
- ✅ Database growth tracked between cycles

### 4. **Better Coverage**
- ✅ Finance: 437 articles/cycle (was 50) - 8.7x! 🚀
- ✅ Science: 320 articles/cycle (was 180) - 1.8x
- ✅ International: 171 articles/cycle (was 117) - 1.5x

## 🔧 Management Commands

### Check if pipeline is running
```bash
tmux ls
```
Should show: `news-pipeline-90min: 1 windows ...`

### View last 100 lines of output
```bash
tmux capture-pane -t news-pipeline-90min -p | tail -100
```

### Stop the pipeline early (if needed)
```bash
tmux kill-session -t news-pipeline-90min
```

### Check pipeline log file
```bash
tail -f /home/iyedpc1/news_project/scripts/pipeline.log
```

## 📊 Real-Time Database Query

Check current article counts anytime:
```bash
cd /home/iyedpc1/news_project
source ~/miniconda3/etc/profile.d/conda.sh
conda activate news-env

python -c "
import sqlite3
conn = sqlite3.connect('news_articles.db')
cur = conn.cursor()
cur.execute('SELECT category, COUNT(*) FROM articles GROUP BY category ORDER BY COUNT(*) DESC')
print('\nCurrent article counts:')
print('-' * 40)
for cat, count in cur.fetchall():
    print(f'{cat:15s}: {count:4d}')
print('-' * 40)
cur.execute('SELECT COUNT(*) FROM articles')
total = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM articles WHERE full_content IS NOT NULL AND length(trim(full_content))>0')
enriched = cur.fetchone()[0]
print(f'{'TOTAL':15s}: {total:4d}')
print(f'{'Enriched':15s}: {enriched:4d} ({enriched/total*100:.1f}%)')
conn.close()
"
```

## ✨ After 90 Minutes

### Automatic Actions:
1. ✅ Pipeline will stop automatically (timeout)
2. ✅ Final statistics will be displayed
3. ✅ Tmux session remains open for review

### What to Check:
```bash
# Attach to see final results
tmux attach -t news-pipeline-90min

# Get final database stats
cd /home/iyedpc1/news_project
python -m newsbot.db_stats

# Compare growth
python -m newsbot.db_stats --json | python -c "
import sys, json
data = json.load(sys.stdin)
overall = data['overall']
print(f\"Final: {overall['with_full']}/{overall['total']} enriched ({overall['coverage_pct']:.1f}%)\")
print(f\"Growth from start: {overall['total'] - 1011} new articles\")
print(f\"\nPer-category final counts:\")
for cat in data['categories']:
    print(f\"  {cat['category']:15s}: {cat['total']:4d} articles\")
"
```

### Clean Up (optional):
```bash
# After reviewing results, kill the tmux session
tmux kill-session -t news-pipeline-90min
```

## 🎉 Success Criteria

The run will be considered successful if:
- ✅ Pipeline runs for 90 minutes without errors
- ✅ At least 150+ new articles added (conservative)
- ✅ All 6 categories are actively monitored
- ✅ Enrichment coverage maintained or improved
- ✅ Science and health categories show activity

## 📚 Related Documentation

- **Setup Guide**: `RUNNING_90MIN.md`
- **Feed Enhancements**: `RSS_FEED_ENHANCEMENTS.md`
- **RSS Behavior**: See above explanation
- **Project README**: `README.md`

---

**Current Time**: ~21:20  
**Time Remaining**: ~89 minutes  
**Status**: 🟢 RUNNING  

**Sit back and watch the articles roll in!** 🚀📰

---

**Post-run tip:** After the session stops, kick off `spark-submit` from the Spark
container to populate the `processed_articles` table. The exact commands live in
[`processing.md`](processing.md) and take only a couple of minutes for a full batch.
