#!/usr/bin/env bash
set -euo pipefail

# Automates the end-to-end restart of the NewsBot fetching pipeline.
# It mirrors the manual steps from the troubleshooting session:
#   1. Ensure a Qwen model mount point exists (even if empty).
#   2. Tear down any running stack from docker-compose.cpu.yml.
#   3. Bring up the core services needed for ingestion.
#   4. Provision Kafka topics.
#   5. Run a quick Postgres health check / stats query.
#
# Usage:
#   bash scripts/quick_run.sh
#
# Environment overrides (optional):
#   POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, QWEN_MODEL_PATH,
#   PRODUCER_POLL_INTERVAL, PRODUCER_CATEGORIES, etc.
#   (They follow the same semantics as the docker-compose file.)

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

ensure_qwen_mount() {
  local target=${QWEN_MODEL_PATH:-$QWEN_PATH_DEFAULT}
  mkdir -p "$target"
  export QWEN_MODEL_PATH="$target"
  log INFO "Using QWEN_MODEL_PATH=$QWEN_MODEL_PATH"
}

compose_down() {
  log INFO "Stopping any existing stack (compose down)"
  if ! "${COMPOSE[@]}" down --remove-orphans >/dev/null 2>&1; then
    log WARN "Compose down reported issues (possibly nothing was running); continuing"
  fi
}

compose_up_core() {
  log INFO "Starting core services (zookeeper, kafka, postgres, schema-registry, rss-ingest, scraper-worker)"
  "${COMPOSE[@]}" up -d --build \
    zookeeper kafka postgres schema-registry rss-ingest scraper-worker
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
  log INFO "Creating Kafka topics via scripts/create_kafka_topics.sh"
  (cd "$ROOT_DIR" && bash scripts/create_kafka_topics.sh)
}

trigger_once_batch() {
  log INFO "Triggering an immediate RSS fetch cycle inside rss-ingest"
  "${COMPOSE[@]}" exec -T rss-ingest python -m newsbot.kafka_producer --once || \
    log WARN "Manual producer trigger failed; the polling loop should still run automatically"
}

show_postgres_counts() {
  log INFO "Sampling article counts by category"
  "${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "SELECT category, COUNT(*) FROM articles GROUP BY category ORDER BY category;" || \
    log WARN "Could not retrieve article counts"
}

main() {
  cd "$ROOT_DIR"
  ensure_compose
  ensure_qwen_mount
  compose_down
  compose_up_core
  wait_for_postgres
  create_topics
  trigger_once_batch
  # Give scraper-worker a moment to consume the fresh batch before querying counts.
  sleep 5
  show_postgres_counts
  log INFO "quick_run completed"
}

main "$@"
