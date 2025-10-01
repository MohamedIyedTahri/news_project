"""Kafka utility helpers for the News Chatbot streaming layer.

Centralizes JSON serialization, UUID/time helpers, producer/consumer builders
and generic retry/backoff utilities.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, Optional

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Generic helpers
# ----------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

def gen_uuid() -> str:
    return str(uuid.uuid4())

# ----------------------------------------------------------------------------
# JSON (de)serialization
# ----------------------------------------------------------------------------

def to_json(data: Dict[str, Any]) -> bytes:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def from_json(raw: bytes | str) -> Dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)

# ----------------------------------------------------------------------------
# Exponential backoff utility
# ----------------------------------------------------------------------------

def backoff_generator(base: float = 0.8, factor: float = 2.0, max_sleep: float = 30.0):
    sleep = base
    while True:
        yield min(sleep, max_sleep)
        sleep *= factor

# ----------------------------------------------------------------------------
# Graceful shutdown handling
# ----------------------------------------------------------------------------

@dataclass
class ShutdownFlag:
    triggered: bool = False

    def set(self, *_):  # signal handler signature
        logger.info("Shutdown signal received; will exit after current batch.")
        self.triggered = True


def install_signal_handlers(flag: ShutdownFlag):
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, flag.set)

# ----------------------------------------------------------------------------
# Kafka Builder Functions (Confluent client and aiokafka)
# ----------------------------------------------------------------------------

# Lazily import inside builders to avoid forcing deps where unused.

DEFAULT_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")

def _resolve_bootstrap(bootstrap: str) -> str:
    """Return a bootstrap string preferring an already working endpoint.

    In docker-compose setups the internal listener may be advertised as 'kafka:9092'.
    From the host network that hostname often does NOT resolve. If the user forgot
    to export KAFKA_BOOTSTRAP_SERVERS=localhost:29092 we attempt a best-effort
    fallback:
        1. If hostname part contains 'kafka' and port 9092, try 'localhost:29092'.
        2. Otherwise return the given value.

    This keeps existing behaviour but avoids silent zero-message runs due to DNS
    failures ("Failed to resolve 'kafka:9092'"). A log line documents adjustments.
    """
    try:
        host, port = bootstrap.split(":", 1)
    except ValueError:
        return bootstrap
    if host == "kafka" and port == "9092":
        # prefer external mapped listener if present
        alt = "localhost:29092"
        logger.info(f"Bootstrap '{bootstrap}' not resolvable from host context; using fallback '{alt}'. Set KAFKA_BOOTSTRAP_SERVERS to override.")
        return alt
    return bootstrap

RESOLVED_BOOTSTRAP = _resolve_bootstrap(DEFAULT_BOOTSTRAP)


def build_producer(config: Optional[Dict[str, Any]] = None):  # type: ignore
    """Create a confluent-kafka producer with sensible defaults.

    Set enable.idempotence for safe retries. Caller can pass extra config.
    """
    from confluent_kafka import Producer
    base = {
    "bootstrap.servers": RESOLVED_BOOTSTRAP,
        "enable.idempotence": True,
        "linger.ms": 100,
        "batch.num.messages": 1000,
        "compression.type": "lz4",
        "delivery.timeout.ms": 120000,
        "acks": "all",
        "retries": 5,
        "message.timeout.ms": 90000,
    }
    if config:
        base.update(config)
    logger.info(f"Building Kafka Producer bootstrap={base['bootstrap.servers']}")
    return Producer(base)


def build_consumer(group_id: str, topics: Iterable[str], config: Optional[Dict[str, Any]] = None):  # type: ignore
    """Create a confluent-kafka consumer subscribed to topics.

    Caller must poll loop. Offsets should be committed manually after side-effects.
    """
    from confluent_kafka import Consumer
    base = {
    "bootstrap.servers": RESOLVED_BOOTSTRAP,
        "group.id": group_id,
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
        "max.poll.interval.ms": 300000,
        "session.timeout.ms": 45000,
    }
    if config:
        base.update(config)
    logger.info(f"Building Kafka Consumer group={group_id} topics={list(topics)} bootstrap={RESOLVED_BOOTSTRAP}")
    consumer = Consumer(base)
    consumer.subscribe(list(topics))
    return consumer

# Async aiokafka builders
async def build_async_consumer(group_id: str, topics: Iterable[str], config: Optional[Dict[str, Any]] = None):  # type: ignore
    from aiokafka import AIOKafkaConsumer
    merged = {
    "bootstrap_servers": RESOLVED_BOOTSTRAP,
        "group_id": group_id,
        "enable_auto_commit": False,
        "auto_offset_reset": "earliest",
        "session_timeout_ms": 45000,
    }
    if config:
        merged.update(config)
    consumer = AIOKafkaConsumer(*topics, **merged)
    return consumer

async def build_async_producer(config: Optional[Dict[str, Any]] = None):  # type: ignore
    from aiokafka import AIOKafkaProducer
    # Detect lz4 availability; aiokafka requires python-lz4 native extension when using lz4 compression
    compression = "lz4"
    try:
        import lz4.frame  # type: ignore
        _lz4_ok = True
    except Exception:
        _lz4_ok = False
        compression = "gzip"  # safer widely-available fallback
        logger.warning(
            "lz4 compression not available (install 'lz4' package for optimal performance); falling back to gzip"
        )
    merged = {
        "bootstrap_servers": RESOLVED_BOOTSTRAP,
        "linger_ms": 5,
        "compression_type": compression,
        "acks": "all",
        "enable_idempotence": True,
    }
    if config:
        merged.update(config)
    producer = AIOKafkaProducer(**merged)
    return producer

# ----------------------------------------------------------------------------
# Metrics placeholders (for future Prometheus integration)
# ----------------------------------------------------------------------------
PRODUCER_METRICS = {
    "messages_produced": 0,
    "produce_errors": 0,
}
CONSUMER_METRICS = {
    "messages_consumed": 0,
    "processing_success": 0,
    "processing_failures": 0,
    "processing_partial": 0,
}

# Suggested Prometheus metric names:
#   newsbot_producer_messages_total
#   newsbot_producer_failures_total
#   newsbot_consumer_messages_total
#   newsbot_consumer_success_total
#   newsbot_consumer_failures_total


def log_metrics():
    logger.info(f"Producer metrics: {PRODUCER_METRICS} | Consumer metrics: {CONSUMER_METRICS}")

# ----------------------------------------------------------------------------
# Utility for bounded batch flush in sync producer
# ----------------------------------------------------------------------------

def flush_producer(producer, timeout: float = 10.0):  # type: ignore
    try:
        producer.flush(timeout)
    except Exception as e:
        logger.warning(f"Producer flush error: {e}")

# ----------------------------------------------------------------------------
# Simple retry wrapper
# ----------------------------------------------------------------------------

def retry(func: Callable[[], Any], attempts: int = 3, base_sleep: float = 0.5) -> Any:
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as e:
            if attempt == attempts:
                raise
            sleep = base_sleep * (2 ** (attempt - 1))
            logger.warning(f"Retry attempt={attempt} error={e} sleeping={sleep:.1f}s")
            time.sleep(sleep)

__all__ = [
    "now_iso", "gen_uuid", "to_json", "from_json", "build_producer", "build_consumer",
    "build_async_producer", "build_async_consumer", "PRODUCER_METRICS", "CONSUMER_METRICS",
    "log_metrics", "flush_producer", "retry", "ShutdownFlag", "install_signal_handlers"
]
