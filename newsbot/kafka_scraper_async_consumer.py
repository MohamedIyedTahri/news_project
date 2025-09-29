"""Async Kafka consumer for high-throughput enrichment.

Uses aiokafka for consumption and (optionally) async full-article fetching.
Falls back to sync scraping in a thread executor if async version unavailable.
"""
from __future__ import annotations

import asyncio
import logging
import os
import json
from functools import partial
from typing import Dict, List

from .kafka_utils import (
    build_async_consumer, build_async_producer, from_json, to_json, now_iso,
    CONSUMER_METRICS, PRODUCER_METRICS, ShutdownFlag, install_signal_handlers, log_metrics
)
from .storage import NewsStorage
from .scraper import fetch_full_articles  # sync fallback

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RSS_TOPIC = os.environ.get("RSS_ITEMS_TOPIC", "rss.items")
CLEANED_TOPIC = os.environ.get("ARTICLES_CLEANED_TOPIC", "articles.cleaned")
ALERTS_TOPIC = os.environ.get("ALERTS_TOPIC", "alerts.feed_failures")
CONCURRENCY = int(os.environ.get("CONCURRENCY", "5"))
POLL_TIMEOUT = float(os.environ.get("ASYNC_CONSUMER_POLL_TIMEOUT_S", "1.0"))
METRICS_INTERVAL = 10

# Attempt to import hypothetical async fetch (not implemented yet)
try:
    from .scraper_async import fetch_full_articles_async  # type: ignore
except Exception:  # pragma: no cover
    fetch_full_articles_async = None  # type: ignore


async def _enrich_one(loop, article_dict: Dict) -> Dict | None:
    """Enrich a single article dict returning enriched record or None.

    If async fetch not available, uses sync version in executor.
    """
    if fetch_full_articles_async is not None:  # pragma: no cover (feature stub)
        try:
            ok, fail = await fetch_full_articles_async([article_dict])  # type: ignore
        except Exception as e:
            logger.error(f"Async fetch error: {e}")
            return None
    else:
        # Run sync fetch in executor
        ok, fail = await loop.run_in_executor(None, fetch_full_articles, [article_dict])
    if ok:
        enriched = article_dict.copy()
        enriched['full_content'] = ok[0].content
        return enriched
    return None


async def process_message(loop, msg, producer, storage, semaphore):  # type: ignore
    async with semaphore:
        CONSUMER_METRICS['messages_consumed'] += 1
        try:
            payload = from_json(msg.value) if callable(getattr(msg, 'value', None)) else from_json(msg.value)  # aiokafka msg.value is bytes
            link = payload.get('link')
            base_article = {
                'title': payload.get('title', ''),
                'link': link,
                'publish_date': payload.get('publish_date', ''),
                'source': payload.get('source', 'Unknown'),
                'category': payload.get('category', 'uncategorized'),
                'content': payload.get('summary', ''),
            }
            enriched = await _enrich_one(loop, base_article)
            if not enriched:
                raise RuntimeError('Full content fetch failed')

            storage.save_article({
                'title': enriched['title'],
                'link': enriched['link'],
                'publish_date': enriched.get('publish_date', ''),
                'source': enriched.get('source', 'Unknown'),
                'category': enriched.get('category', 'uncategorized'),
                'content': enriched.get('content', ''),
                'full_content': enriched.get('full_content'),
            })

            enriched_record = {**payload, 'full_content': enriched['full_content'], 'enriched_at': now_iso()}
            try:
                await producer.send_and_wait(CLEANED_TOPIC, to_json(enriched_record), key=(link.encode('utf-8') if link else None))
                PRODUCER_METRICS['messages_produced'] += 1
            except Exception as e:
                PRODUCER_METRICS['produce_errors'] += 1
                logger.error(f"Async produce error: {e}")
            CONSUMER_METRICS['processing_success'] += 1
        except Exception as e:
            CONSUMER_METRICS['processing_failures'] += 1
            logger.error(f"Async processing failure: {e}")
            alert_payload = {'type': 'enrichment_failure', 'error': str(e), 'ts': now_iso()}
            try:
                await producer.send_and_wait(ALERTS_TOPIC, to_json(alert_payload))
            except Exception:
                pass


async def run_async_consumer(max_messages: int | None = None):
    loop = asyncio.get_running_loop()
    consumer = await build_async_consumer(group_id='scraper-workers-async', topics=[RSS_TOPIC])
    producer = await build_async_producer()
    storage = NewsStorage()
    semaphore = asyncio.Semaphore(CONCURRENCY)
    flag = ShutdownFlag()
    install_signal_handlers(flag)

    await consumer.start()
    await producer.start()

    processed = 0
    last_metrics = 0.0

    try:
        logger.info(f"Async consumer started group=scraper-workers-async topic={RSS_TOPIC} concurrency={CONCURRENCY}")
        while not flag.triggered:
            msgs = await consumer.getmany(timeout_ms=int(POLL_TIMEOUT * 1000), max_records=CONCURRENCY)
            tasks: List[asyncio.Task] = []
            for tp, batch in msgs.items():  # type: ignore
                for m in batch:
                    if max_messages and processed >= max_messages:
                        break
                    task = asyncio.create_task(process_message(loop, m, producer, storage, semaphore))
                    tasks.append(task)
                    processed += 1
                if max_messages and processed >= max_messages:
                    break
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                # manual commits per partition at end of batch
                await consumer.commit()
            now = asyncio.get_event_loop().time()
            if now - last_metrics > METRICS_INTERVAL:
                log_metrics()
                last_metrics = now
            if max_messages and processed >= max_messages:
                break
    finally:
        logger.info("Async consumer shutting down")
        try:
            await producer.stop()
        except Exception:
            pass
        try:
            await consumer.stop()
        except Exception:
            pass
        storage.close()
        log_metrics()
        logger.info(f"Async processed messages={processed}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Async Kafka scraper consumer')
    parser.add_argument('--max-messages', type=int, help='Process only this many then exit')
    args = parser.parse_args()
    asyncio.run(run_async_consumer(max_messages=args.max_messages))

if __name__ == '__main__':
    main()
