#!/usr/bin/env bash
set -euo pipefail

# Lightweight variant of quick_run.sh that reuses previously built images.
# Assumes you've already executed `scripts/quick_run.sh` (or `docker compose build`)
# at least once so the custom images exist locally.
#
# Steps performed:
#   1. Verify docker-compose availability and cached images.
#   2. Ensure Qwen model mount directory exists.
#   3. Bring core services up WITHOUT `--build` (no heavy rebuild).
#   4. Optionally recreate Kafka topics (can skip via SKIP_TOPIC_CREATE=1).
#   5. Trigger a single RSS fetch batch to prime the pipeline.
#   6. Show Postgres article counts for a quick health check.
#
# Usage:
#   bash scripts/quick_run_fast.sh
#
# Optional environment variables:
#   QWEN_MODEL_PATH       Override the host model directory (default: ./models/qwen)
#   POSTGRES_USER         Database user (default: newsbot)
#   POSTGRES_DB           Database name (default: newsbot)
#   SKIP_TOPIC_CREATE=1   Skip running scripts/create_kafka_topics.sh
#   SKIP_MANUAL_TRIGGER=1 Skip the on-demand producer run (uses poller only)

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_FILE="${ROOT_DIR}/docker-compose.cpu.yml"
QWEN_PATH_DEFAULT="${ROOT_DIR}/models/qwen"
POSTGRES_USER=${POSTGRES_USER:-newsbot}
POSTGRES_DB=${POSTGRES_DB:-newsbot}

log() {
  local level=$1
  shift
  printf '[%s] %s\n' "$level" "$*"
}

ensure_compose() {
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose -f "$COMPOSE_FILE")
  elif command -v docker >/dev/null 2>&1; then
    COMPOSE=(docker compose -f "$COMPOSE_FILE")
  else
    log FATAL "docker-compose (or docker compose) is required but not installed"
    exit 1
  fi
}

ensure_prebuilt_images() {
  local missing=()
  local images=("news_project_rss-ingest:latest" "news_project_scraper-worker:latest")
  for image in "${images[@]}"; do
    if ! docker image inspect "$image" >/dev/null 2>&1; then
      missing+=("$image")
    fi
  done
  if (( ${#missing[@]} )); then
    log FATAL "Missing cached images: ${missing[*]}"
    log FATAL "Run scripts/quick_run.sh (or docker compose build) once before using quick_run_fast.sh"
    exit 1
  fi
}

ensure_qwen_mount() {
  local target=${QWEN_MODEL_PATH:-$QWEN_PATH_DEFAULT}
  mkdir -p "$target"
  export QWEN_MODEL_PATH="$target"
  log INFO "Using QWEN_MODEL_PATH=$QWEN_MODEL_PATH"
}

compose_up_core() {
  log INFO "Starting core services with cached images (no rebuild)"
  "${COMPOSE[@]}" up -d zookeeper kafka postgres schema-registry rss-ingest scraper-worker
}

wait_for_postgres() {
  log INFO "Waiting for postgres container to become ready"
  local attempt max_attempts=30
  for attempt in $(seq 1 "$max_attempts"); do
    if "${COMPOSE[@]}" exec -T postgres pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; then
      log INFO "Postgres is ready"
      return 0
    fi
    sleep 2
  done
  log FATAL "Postgres did not become ready after $((max_attempts*2)) seconds"
  exit 1
}

create_topics() {
  if [[ "${SKIP_TOPIC_CREATE:-0}" == "1" ]]; then
    log INFO "Skipping Kafka topic creation"
    return
  fi
  log INFO "Ensuring Kafka topics exist"
  (cd "$ROOT_DIR" && bash scripts/create_kafka_topics.sh)
}

trigger_once_batch() {
  if [[ "${SKIP_MANUAL_TRIGGER:-0}" == "1" ]]; then
    log INFO "Skipping manual producer trigger (polling loop will handle ingestion)"
    return
  fi
  log INFO "Triggering an immediate RSS fetch cycle (cached images)"
  if ! "${COMPOSE[@]}" exec -T rss-ingest python -m newsbot.kafka_producer --once; then
    log WARN "Manual producer trigger failed; falling back to scheduled poller"
  fi
}

show_postgres_counts() {
  log INFO "Sampling article counts by category"
  if ! "${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "SELECT category, COUNT(*) FROM articles GROUP BY category ORDER BY category;"; then
    log WARN "Could not retrieve article counts"
  fi
}

main() {
  cd "$ROOT_DIR"
  ensure_compose
  ensure_prebuilt_images
  ensure_qwen_mount
  compose_up_core
  wait_for_postgres
  create_topics
  trigger_once_batch
  sleep 5
  show_postgres_counts
  log INFO "quick_run_fast completed"
}

main "$@"
