#!/usr/bin/env bash
set -euo pipefail

declare -a ARGS=()
if [[ -n "${CONSUMER_MAX_MESSAGES:-}" ]]; then
  ARGS+=("--max-messages" "${CONSUMER_MAX_MESSAGES}")
fi

exec python -m newsbot.kafka_scraper_consumer "${ARGS[@]}"
