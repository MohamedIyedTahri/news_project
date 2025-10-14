#!/usr/bin/env bash
# Run the Kafka producer inside a Docker container with the kafka/ folder mounted.
set -euo pipefail

IMAGE_NAME="newsbot"
KAFKA_SCRIPT="/app/kafka/kafka_producer.py"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
  echo "Building ${IMAGE_NAME} image from services/rss_ingest/Dockerfile ..."
  docker build -t "${IMAGE_NAME}" -f "${PROJECT_ROOT}/services/rss_ingest/Dockerfile" "${PROJECT_ROOT}"
fi

docker run --rm \
  --network news-net \
  -e KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}" \
  -v "${PROJECT_ROOT}/kafka:/app/kafka" \
  "${IMAGE_NAME}" python "${KAFKA_SCRIPT}" "$@"
