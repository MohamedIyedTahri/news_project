#!/usr/bin/env python3
"""
Scheduled News Extraction Service

Provides cron-like scheduled extraction with different strategies:
- Continuous mode: Runs 24/7 with configurable intervals
- Daily mode: Runs once per day at specified time
- Hourly mode: Runs at specified minute of each hour
- Custom cron: Uses cron expression for complex scheduling

Usage:
    python scripts/scheduled_extraction.py --mode continuous --interval 300
    python scripts/scheduled_extraction.py --mode daily --time "06:00"
    python scripts/scheduled_extraction.py --mode hourly --minute 30
    python scripts/scheduled_extraction.py --mode cron --cron "0 */4 * * *"
"""

import asyncio
import logging
import schedule
import time
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import sys
import os
import subprocess
import threading
from croniter import croniter


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduled_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ScheduledExtractor:
    """Manages scheduled news extraction with various timing strategies."""
    
    def __init__(self, mode='continuous', **kwargs):
        self.mode = mode
        self.kwargs = kwargs
        self.running = False
        self.thread = None
        
        # Ensure we're in the right directory
        project_root = Path(__file__).parent.parent
        os.chdir(project_root)
        
        # Set environment
        os.environ['KAFKA_BOOTSTRAP_SERVERS'] = kwargs.get('kafka_bootstrap', 'localhost:29092')
        
    def extract_articles(self, categories=None, max_articles=30):
        """Run a single extraction cycle."""
        logger.info("Starting scheduled extraction cycle")
        
        try:
            # Check Kafka infrastructure
            self._ensure_kafka_running()
            
            # Run producer
            cmd = [sys.executable, '-m', 'newsbot.kafka_producer', '--once']
            if categories:
                cmd.extend(['--categories', ','.join(categories)])
                
            logger.info("Running producer...")
            result = subprocess.run(cmd, timeout=120, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Producer failed: {result.stderr}")
                return False
                
            # Small delay
            time.sleep(3)
            
            # Run consumer
            cmd = [
                sys.executable, '-m', 'newsbot.kafka_scraper_async_consumer',
                '--max-messages', str(max_articles)
            ]
            
            logger.info("Running consumer...")
            result = subprocess.run(cmd, timeout=300, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Consumer failed: {result.stderr}")
                return False
                
            # Get updated stats
            self._log_extraction_stats()
            
            logger.info("Extraction cycle completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return False
            
    def _ensure_kafka_running(self):
        """Ensure Kafka infrastructure is running."""
        try:
            result = subprocess.run(
                ['docker-compose', 'ps', '-q', 'kafka'],
                capture_output=True, text=True, timeout=10
            )
            if not result.stdout.strip():
                logger.info("Starting Kafka infrastructure...")
                subprocess.run(['docker-compose', 'up', '-d'], check=True, timeout=60)
                time.sleep(10)
                subprocess.run(['bash', 'scripts/create_kafka_topics.sh'], timeout=30)
        except Exception as e:
            logger.error(f"Failed to ensure Kafka running: {e}")
            raise
            
    def _log_extraction_stats(self):
        """Log current database statistics."""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'newsbot.db_stats'],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                # Log the summary line
                for line in lines:
                    if 'Overall coverage' in line:
                        logger.info(f"Database state: {line}")
                        break
        except Exception as e:
            logger.warning(f"Failed to get stats: {e}")
            
    def run_continuous(self, interval=600, categories=None, max_articles=30):
        """Run continuous extraction with fixed intervals."""
        logger.info(f"Starting continuous extraction (interval: {interval}s)")
        
        self.running = True
        while self.running:
            try:
                self.extract_articles(categories, max_articles)
                
                if self.running:  # Check if we should continue
                    logger.info(f"Sleeping for {interval} seconds...")
                    for _ in range(interval):
                        if not self.running:
                            break
                        time.sleep(1)
                        
            except KeyboardInterrupt:
                logger.info("Continuous extraction interrupted")
                break
            except Exception as e:
                logger.error(f"Continuous extraction error: {e}")
                time.sleep(60)  # Wait before retry
                
    def run_scheduled(self):
        """Run scheduled extraction based on mode."""
        categories = self.kwargs.get('categories')
        max_articles = self.kwargs.get('max_articles', 30)
        
        if self.mode == 'daily':
            time_str = self.kwargs.get('time', '06:00')
            schedule.every().day.at(time_str).do(
                self.extract_articles, categories, max_articles
            )
            logger.info(f"Scheduled daily extraction at {time_str}")
            
        elif self.mode == 'hourly':
            minute = self.kwargs.get('minute', 0)
            schedule.every().hour.at(f":{minute:02d}").do(
                self.extract_articles, categories, max_articles
            )
            logger.info(f"Scheduled hourly extraction at minute {minute}")
            
        elif self.mode == 'cron':
            cron_expr = self.kwargs.get('cron', '0 */6 * * *')  # Every 6 hours default
            logger.info(f"Scheduled cron extraction: {cron_expr}")
            return self._run_cron_schedule(cron_expr, categories, max_articles)
            
        else:
            logger.error(f"Unknown scheduled mode: {self.mode}")
            return
            
        # Run schedule loop
        self.running = True
        logger.info("Scheduled extraction service started")
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
            except KeyboardInterrupt:
                logger.info("Scheduled extraction interrupted")
                break
            except Exception as e:
                logger.error(f"Scheduled extraction error: {e}")
                time.sleep(60)
                
    def _run_cron_schedule(self, cron_expr, categories, max_articles):
        """Run extraction based on cron expression."""
        try:
            cron = croniter(cron_expr, datetime.now())
        except Exception as e:
            logger.error(f"Invalid cron expression '{cron_expr}': {e}")
            return
            
        self.running = True
        
        while self.running:
            try:
                next_run = cron.get_next(datetime)
                now = datetime.now()
                
                if next_run <= now:
                    # Time to run
                    self.extract_articles(categories, max_articles)
                    # Get next occurrence
                    next_run = cron.get_next(datetime)
                    
                # Calculate sleep time
                sleep_time = (next_run - datetime.now()).total_seconds()
                sleep_time = max(1, min(sleep_time, 3600))  # Between 1s and 1h
                
                logger.info(f"Next extraction at {next_run.strftime('%Y-%m-%d %H:%M:%S')} "
                           f"(sleeping {sleep_time:.0f}s)")
                
                # Sleep in chunks to allow interruption
                for _ in range(int(sleep_time)):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info("Cron extraction interrupted")
                break
            except Exception as e:
                logger.error(f"Cron extraction error: {e}")
                time.sleep(60)
                
    def start(self):
        """Start the scheduled extraction service."""
        if self.mode == 'continuous':
            interval = self.kwargs.get('interval', 600)
            categories = self.kwargs.get('categories')
            max_articles = self.kwargs.get('max_articles', 30)
            
            self.thread = threading.Thread(
                target=self.run_continuous,
                args=(interval, categories, max_articles)
            )
            self.thread.daemon = True
            self.thread.start()
            
        else:
            self.thread = threading.Thread(target=self.run_scheduled)
            self.thread.daemon = True
            self.thread.start()
            
        logger.info(f"Scheduled extraction service started in {self.mode} mode")
        
    def stop(self):
        """Stop the scheduled extraction service."""
        logger.info("Stopping scheduled extraction service...")
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=10)
            
        logger.info("Scheduled extraction service stopped")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Scheduled news extraction service")
    
    parser.add_argument('--mode', choices=['continuous', 'daily', 'hourly', 'cron'],
                       default='continuous', help='Extraction scheduling mode')
    
    # Continuous mode options
    parser.add_argument('--interval', type=int, default=600,
                       help='Interval in seconds for continuous mode (default: 600)')
    
    # Daily mode options
    parser.add_argument('--time', default='06:00',
                       help='Time for daily extraction in HH:MM format (default: 06:00)')
    
    # Hourly mode options
    parser.add_argument('--minute', type=int, default=0,
                       help='Minute of hour for hourly extraction (default: 0)')
    
    # Cron mode options
    parser.add_argument('--cron', default='0 */6 * * *',
                       help='Cron expression for custom scheduling (default: every 6 hours)')
    
    # General options
    parser.add_argument('--categories', 
                       help='Comma-separated categories to extract (default: all)')
    parser.add_argument('--max-articles', type=int, default=30,
                       help='Maximum articles per extraction cycle (default: 30)')
    parser.add_argument('--kafka-bootstrap', default='localhost:29092',
                       help='Kafka bootstrap servers (default: localhost:29092)')
    
    args = parser.parse_args()
    
    # Parse categories
    categories = None
    if args.categories:
        categories = [cat.strip() for cat in args.categories.split(',')]
        
    # Create extractor
    extractor = ScheduledExtractor(
        mode=args.mode,
        interval=args.interval,
        time=args.time,
        minute=args.minute,
        cron=args.cron,
        categories=categories,
        max_articles=args.max_articles,
        kafka_bootstrap=args.kafka_bootstrap
    )
    
    try:
        if args.mode == 'continuous':
            # Run directly for continuous mode
            extractor.run_continuous(
                interval=args.interval,
                categories=categories,
                max_articles=args.max_articles
            )
        else:
            # Start service for scheduled modes
            extractor.start()
            
            # Keep main thread alive
            while extractor.running and extractor.thread.is_alive():
                time.sleep(1)
                
    except KeyboardInterrupt:
        logger.info("Extraction service interrupted")
    except Exception as e:
        logger.error(f"Extraction service failed: {e}")
        return 1
    finally:
        extractor.stop()
        
    return 0


if __name__ == '__main__':
    sys.exit(main())