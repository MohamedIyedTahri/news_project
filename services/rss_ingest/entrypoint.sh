#!/usr/bin/env bash
set -euo pipefail

POLL_MODE=${PRODUCER_MODE:-poll}

declare -a ARGS=()
if [[ -n "${PRODUCER_CATEGORIES:-}" ]]; then
  ARGS+=("--categories" "${PRODUCER_CATEGORIES}")
fi

cmd=(python -m newsbot.kafka_producer)

if [[ "${POLL_MODE}" == "once" ]]; then
  cmd+=(--once)
else
  INTERVAL=${PRODUCER_POLL_INTERVAL:-300}
  cmd+=(--poll "${INTERVAL}")
fi

# Append any constructed arguments (categories, etc.)
cmd+=("${ARGS[@]}")

echo "Starting RSS producer: ${cmd[*]}" >&2
exec "${cmd[@]}"
