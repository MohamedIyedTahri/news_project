import os
import socket
import time
import pytest

from newsbot.kafka_producer import produce_batch, build_message  # type: ignore
from newsbot.kafka_utils import build_producer, build_consumer, from_json
from newsbot.storage import NewsStorage
from newsbot.kafka_scraper_consumer import run_consumer

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
RSS_TOPIC = os.environ.get("RSS_ITEMS_TOPIC", "rss.items")


def _kafka_reachable(hostport: str) -> bool:
    host, port = hostport.split(":")
    try:
        with socket.create_connection((host, int(port)), timeout=1):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _kafka_reachable(KAFKA_BOOTSTRAP), reason="Kafka not reachable on bootstrap servers")
def test_end_to_end_smoke(monkeypatch):
    """Smoke test: produce 2 synthetic messages and ensure consumer processes them.

    We mock fetch_multiple_feeds by directly producing two messages (bypassing network)."""
    prod = build_producer()

    # Create two synthetic RSS items
    msgs = [
        {
            "id": "test-1",
            "title": "Test Article 1",
            "link": "https://example.com/test1",
            "publish_date": "2025-09-29",
            "source": "TestSource",
            "category": "test",
            "summary": "Short summary 1",
            "fetched_at": "2025-09-29T00:00:00Z",
        },
        {
            "id": "test-2",
            "title": "Test Article 2",
            "link": "https://example.com/test2",
            "publish_date": "2025-09-29",
            "source": "TestSource",
            "category": "test",
            "summary": "Short summary 2",
            "fetched_at": "2025-09-29T00:00:00Z",
        },
    ]
    for m in msgs:
        prod.produce(RSS_TOPIC, key=m['link'].encode('utf-8'), value=__import__('json').dumps(m).encode('utf-8'))
    prod.flush()

    # Run consumer limited mode
    run_consumer(loop_forever=False, max_messages=2)

    # Validate DB entries (full_content may be empty because external fetch disabled)
    s = NewsStorage()
    cur = s.conn.execute("SELECT link, full_content FROM articles WHERE link IN (?, ?)", (msgs[0]['link'], msgs[1]['link']))
    rows = cur.fetchall()
    # At least entries exist (full_content may not be set due to network isolation)
    assert len(rows) == 2
    s.close()
