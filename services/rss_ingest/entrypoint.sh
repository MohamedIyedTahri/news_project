#!/usr/bin/env bash
set -euo pipefail

POLL_MODE=${PRODUCER_MODE:-poll}

declare -a ARGS=()
if [[ -n "${PRODUCER_CATEGORIES:-}" ]]; then
  ARGS+=("--categories" "${PRODUCER_CATEGORIES}")
fi

if [[ "${POLL_MODE}" == "once" ]]; then
  exec python -m newsbot.kafka_producer --once "${ARGS[@]}"
else
  INTERVAL=${PRODUCER_POLL_INTERVAL:-300}
  exec python -m newsbot.kafka_producer --poll "${INTERVAL}" "${ARGS[@]}"
fi
