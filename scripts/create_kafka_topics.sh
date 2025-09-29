#!/usr/bin/env bash
set -euo pipefail

# Helper script to create required Kafka topics for the News Chatbot streaming layer.
# Usage (from project root after docker compose up):
#   bash scripts/create_kafka_topics.sh
#
# The script assumes the broker container is named 'kafka'.
# Adjust KAFKA_CONTAINER if you changed docker-compose service names.

KAFKA_CONTAINER=${KAFKA_CONTAINER:-kafka}
BOOTSTRAP=${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}

create_topic () {
  local topic=$1
  local partitions=$2
  local retention=$3
  local extra_config=$4
  echo "Creating topic $topic (partitions=$partitions retention=$retention extra=$extra_config)"
  docker exec -i "$KAFKA_CONTAINER" bash -c \
    "/usr/bin/kafka-topics --create --if-not-exists --bootstrap-server ${BOOTSTRAP} \
      --topic ${topic} --partitions ${partitions} --replication-factor 1 \
      --config retention.ms=${retention} ${extra_config}" || true
}

# 7 days retention: 7 * 24 * 60 * 60 * 1000
RET_7D=$((7*24*60*60*1000))
# 30 days retention
RET_30D=$((30*24*60*60*1000))

# rss.items: raw RSS entries (summary level)
create_topic "rss.items" 3 "$RET_7D" ""

# articles.cleaned: enriched + full content, we keep longer and compact on key (link)
# Using log compaction + longer retention ensures the latest full content version is retained.
create_topic "articles.cleaned" 3 "$RET_30D" "--config cleanup.policy=compact,delete"

# optional alerts topic for failures
create_topic "alerts.feed_failures" 1 "$RET_7D" ""

echo "Listing topics:"
docker exec -i "$KAFKA_CONTAINER" bash -c "/usr/bin/kafka-topics --bootstrap-server ${BOOTSTRAP} --list"

echo "Done."
