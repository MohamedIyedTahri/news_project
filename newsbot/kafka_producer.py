"""Compatibility wrapper forwarding to ``kafka.kafka_producer``.

Existing tooling imports ``newsbot.kafka_producer``. The actual implementation
now lives under the top-level ``kafka/`` package mounted into Docker
containers, so this shim re-exports the public API and ensures the CLI entry
point continues to work.
"""

from kafka.kafka_producer import *  # noqa: F401,F403
from kafka.kafka_producer import main as _main


if __name__ == "__main__":
	_main()
