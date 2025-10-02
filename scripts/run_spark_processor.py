"""Utility script to run the SparkProcessor in batch or streaming mode."""

import argparse
import logging
from contextlib import suppress

from newsbot.spark_processor import SparkProcessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Newsbot SparkProcessor")
    parser.add_argument(
        "--mode",
        choices=["batch", "stream"],
        default="batch",
        help="Execution mode: single batch run or continuous micro-batch stream.",
    )
    parser.add_argument(
        "--db-path",
        default="news_articles.db",
        help="Path to the SQLite database containing articles.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of articles processed per batch.",
    )
    parser.add_argument(
        "--since-id",
        type=int,
        default=None,
        help="Only process articles with id greater than this value.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Interval in seconds between streaming micro-batches.",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Optional number of streaming micro-batches before shutting down.",
    )
    parser.add_argument(
        "--rows-per-second",
        type=int,
        default=1,
        help="Trigger frequency for the synthetic rate source.",
    )
    parser.add_argument(
        "--prefer-summaries",
        action="store_true",
        help="Prioritise RSS summaries instead of full_content when available.",
    )
    parser.add_argument(
        "--app-name",
        default="NewsbotSparkProcessor",
        help="Custom Spark application name.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prefer_full = not args.prefer_summaries

    logger.info("Starting SparkProcessor in %s mode", args.mode)
    processor = SparkProcessor.for_local_mode(app_name=args.app_name, db_path=args.db_path)

    try:
        if args.mode == "batch":
            written = processor.run_batch_processing(
                limit=args.limit,
                since_article_id=args.since_id,
                prefer_full_content=prefer_full,
            )
            logger.info("Batch processing complete: %s records written", written)
        else:
            logger.info("Entering streaming mode – use CTRL+C to exit")
            with suppress(KeyboardInterrupt):
                processor.run_streaming_processing(
                    interval_seconds=args.interval,
                    max_batches=args.max_batches,
                    rows_per_second=args.rows_per_second,
                    prefer_full_content=prefer_full,
                )
    finally:
        processor.close()
        logger.info("SparkProcessor shutdown complete")


if __name__ == "__main__":
    main()
