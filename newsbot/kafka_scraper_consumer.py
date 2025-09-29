"""Synchronous Kafka consumer that enriches RSS items with full article content.

Consumes from topic 'rss.items', fetches full content using existing scraper
logic, stores full content into SQLite, and publishes enriched messages to
'articles.cleaned'.

Offset commit strategy: commit after successful DB upsert + produce to cleaned topic.
Per-message error handling logs failures and optionally produces an alert record
(to alerts.feed_failures if available).
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Dict

from .scraper import fetch_full_articles
from .storage import NewsStorage
from .kafka_utils import (
    build_consumer, build_producer, from_json, to_json, now_iso,
    CONSUMER_METRICS, PRODUCER_METRICS, log_metrics, ShutdownFlag, install_signal_handlers
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RSS_TOPIC = os.environ.get("RSS_ITEMS_TOPIC", "rss.items")
CLEANED_TOPIC = os.environ.get("ARTICLES_CLEANED_TOPIC", "articles.cleaned")
ALERTS_TOPIC = os.environ.get("ALERTS_TOPIC", "alerts.feed_failures")
BATCH_FLUSH_INTERVAL = 5  # seconds


def enrich_single(article: Dict) -> Dict | None:
    """Fetch and return full content for a single RSS article dict.

    Returns enriched dict (adds full_content) or None on failure.
    """
    full_ok, full_fail = fetch_full_articles([article])
    if full_ok:
        enriched = article.copy()
        enriched["full_content"] = full_ok[0].content
        return enriched
    return None


def run_consumer(loop_forever: bool = True, max_messages: int | None = None):
    consumer = build_consumer(group_id='scraper-workers', topics=[RSS_TOPIC])
    producer = build_producer()
    storage = NewsStorage()
    flag = ShutdownFlag()
    install_signal_handlers(flag)

    processed = 0
    last_flush = time.time()
    logger.info(f"Starting scraper consumer group=scraper-workers topic={RSS_TOPIC}")

    try:
        while not flag.triggered:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                # periodic flush of metrics
                if time.time() - last_flush > BATCH_FLUSH_INTERVAL:
                    log_metrics()
                    last_flush = time.time()
                if not loop_forever and processed >= (max_messages or 0):
                    break
                continue
            if msg.error():  # type: ignore
                logger.error(f"Kafka message error: {msg.error()}")  # type: ignore
                continue

            CONSUMER_METRICS["messages_consumed"] += 1
            try:
                payload = from_json(msg.value())  # type: ignore
                link = payload.get("link")
                enriched = enrich_single({
                    "title": payload.get("title", ""),
                    "link": link,
                    "publish_date": payload.get("publish_date", ""),
                    "source": payload.get("source", "Unknown"),
                    "category": payload.get("category", "uncategorized"),
                    "content": payload.get("summary", ""),
                })
                if not enriched:
                    raise RuntimeError("Full content fetch failed")

                # DB upsert (will only update full_content if missing)
                storage.save_article({
                    "title": enriched["title"],
                    "link": enriched["link"],
                    "publish_date": enriched.get("publish_date", ""),
                    "source": enriched.get("source", "Unknown"),
                    "category": enriched.get("category", "uncategorized"),
                    "content": enriched.get("content", ""),
                    "full_content": enriched.get("full_content"),
                })

                # Produce to cleaned topic
                enriched_record = {
                    **payload,
                    "full_content": enriched["full_content"],
                    "enriched_at": now_iso(),
                }
                try:
                    producer.produce(
                        topic=CLEANED_TOPIC,
                        key=link.encode("utf-8") if link else None,
                        value=to_json(enriched_record)
                    )
                    PRODUCER_METRICS["messages_produced"] += 1
                except Exception as e:
                    PRODUCER_METRICS["produce_errors"] += 1
                    logger.error(f"Failed producing enriched record: {e}")

                consumer.commit(asynchronous=False)
                CONSUMER_METRICS["processing_success"] += 1
                processed += 1
            except Exception as e:
                CONSUMER_METRICS["processing_failures"] += 1
                logger.error(f"Processing failure: {e}")
                # Optionally send alert
                alert_payload = {
                    "type": "enrichment_failure",
                    "error": str(e),
                    "ts": now_iso(),
                }
                try:
                    producer.produce(ALERTS_TOPIC, value=to_json(alert_payload))
                except Exception:
                    pass
            if not loop_forever and processed >= (max_messages or 0):
                break
    finally:
        logger.info("Flushing producer & closing consumer")
        try:
            producer.flush(10)
        except Exception:
            pass
        consumer.close()
        storage.close()
        log_metrics()
        logger.info(f"Processed messages={processed}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Sync Kafka scraper consumer')
    parser.add_argument('--max-messages', type=int, help='Process only this many messages then exit')
    args = parser.parse_args()
    run_consumer(loop_forever=not bool(args.max_messages), max_messages=args.max_messages)
