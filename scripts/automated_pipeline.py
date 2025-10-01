#!/usr/bin/env python3
"""
Automated News Pipeline Runner

Continuously runs the full news extraction pipeline:
1. Fetches RSS articles via Kafka producer
2. Processes articles with async consumer for full content
3. Monitors database growth and pipeline health
4. Handles errors and restarts automatically

Usage:
    python scripts/automated_pipeline.py
    python scripts/automated_pipeline.py --interval 300  # 5-minute intervals
    python scripts/automated_pipeline.py --categories tech,science
"""

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
import argparse


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for automated pipeline."""
    interval_seconds: int = 600  # 10 minutes default
    categories: Optional[List[str]] = None
    max_articles_per_batch: int = 50
    consumer_timeout: int = 300  # 5 minutes
    health_check_interval: int = 60  # 1 minute
    restart_on_failure: bool = True
    kafka_bootstrap: str = "localhost:29092"


class PipelineManager:
    """Manages the automated news extraction pipeline."""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.running = False
        self.producer_process: Optional[subprocess.Popen] = None
        self.consumer_process: Optional[subprocess.Popen] = None
        self.last_stats = None
        self.start_time = datetime.now()
        
        # Set environment variables
        os.environ['KAFKA_BOOTSTRAP_SERVERS'] = config.kafka_bootstrap
        
        # Ensure we're in the right directory
        project_root = Path(__file__).parent.parent
        os.chdir(project_root)
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down pipeline...")
        self.stop()
        sys.exit(0)
        
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def check_kafka_infrastructure(self) -> bool:
        """Verify Kafka infrastructure is running."""
        try:
            result = subprocess.run(
                ['docker-compose', 'ps', '-q', 'kafka'],
                capture_output=True, text=True, timeout=10
            )
            if not result.stdout.strip():
                logger.warning("Kafka not running, starting infrastructure...")
                self.start_kafka_infrastructure()
                time.sleep(10)  # Wait for startup
                
            return True
        except Exception as e:
            logger.error(f"Failed to check Kafka infrastructure: {e}")
            return False
            
    def start_kafka_infrastructure(self):
        """Start Kafka infrastructure if not running."""
        try:
            logger.info("Starting Kafka infrastructure...")
            subprocess.run(['docker-compose', 'up', '-d'], check=True, timeout=60)
            
            # Create topics if needed
            time.sleep(5)  # Wait for Kafka to be ready
            subprocess.run(['bash', 'scripts/create_kafka_topics.sh'], 
                         timeout=30, capture_output=True)
            
            logger.info("Kafka infrastructure started successfully")
        except subprocess.TimeoutExpired:
            logger.error("Timeout starting Kafka infrastructure")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start Kafka infrastructure: {e}")
            raise
            
    def get_database_stats(self) -> dict:
        """Get current database statistics."""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'newsbot.db_stats', '--json'],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                import json
                return json.loads(result.stdout)
            else:
                logger.warning(f"Failed to get DB stats: {result.stderr}")
                return {}
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
            
    def run_producer_batch(self) -> bool:
        """Run producer to fetch new RSS articles."""
        try:
            cmd = [sys.executable, '-m', 'newsbot.kafka_producer', '--once']
            
            if self.config.categories:
                cmd.extend(['--categories', ','.join(self.config.categories)])
                
            logger.info(f"Starting producer batch: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd, timeout=120, capture_output=True, text=True
            )
            
            if result.returncode == 0:
                logger.info("Producer batch completed successfully")
                if "messages_produced" in result.stdout:
                    # Extract message count if available
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if "Producing" in line or "messages_produced" in line:
                            logger.info(f"Producer: {line.strip()}")
                return True
            else:
                logger.error(f"Producer failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Producer timeout")
            return False
        except Exception as e:
            logger.error(f"Producer error: {e}")
            return False
            
    def run_consumer_batch(self) -> bool:
        """Run consumer to process articles."""
        try:
            cmd = [
                sys.executable, '-m', 'newsbot.kafka_scraper_async_consumer',
                '--max-messages', str(self.config.max_articles_per_batch)
            ]
            
            logger.info(f"Starting consumer batch: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd, timeout=self.config.consumer_timeout, 
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                logger.info("Consumer batch completed successfully")
                # Log key metrics
                lines = result.stdout.split('\n')
                for line in lines:
                    if any(keyword in line for keyword in 
                          ['consumed', 'enriched', 'success', 'processed']):
                        logger.info(f"Consumer: {line.strip()}")
                return True
            else:
                logger.error(f"Consumer failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Consumer timeout")
            return False
        except Exception as e:
            logger.error(f"Consumer error: {e}")
            return False
            
    def log_pipeline_stats(self):
        """Log current pipeline statistics."""
        current_stats = self.get_database_stats()
        if not current_stats:
            return
            
        overall = current_stats.get('overall', {})
        logger.info(f"Database: {overall.get('with_full', 0)}/{overall.get('total', 0)} "
                   f"enriched ({overall.get('coverage_pct', 0):.1f}%)")
        
        # Calculate growth since start
        if self.last_stats:
            last_total = self.last_stats.get('overall', {}).get('total', 0)
            current_total = overall.get('total', 0)
            growth = current_total - last_total
            if growth > 0:
                logger.info(f"Pipeline growth: +{growth} articles since last check")
                
        # Log per-category stats
        categories = current_stats.get('categories', [])
        for cat in categories[:3]:  # Top 3 categories
            logger.info(f"  {cat['category']}: {cat['with_full']}/{cat['total']} "
                       f"({cat['coverage_pct']:.1f}%)")
                       
        self.last_stats = current_stats
        
    def run_pipeline_cycle(self) -> bool:
        """Run one complete pipeline cycle."""
        logger.info("=" * 60)
        logger.info("Starting pipeline cycle")
        
        # Check infrastructure
        if not self.check_kafka_infrastructure():
            logger.error("Kafka infrastructure check failed")
            return False
            
        # Run producer
        producer_success = self.run_producer_batch()
        if not producer_success and self.config.restart_on_failure:
            logger.warning("Producer failed, but continuing with consumer...")
            
        # Small delay between producer and consumer
        time.sleep(5)
        
        # Run consumer
        consumer_success = self.run_consumer_batch()
        
        # Log statistics
        self.log_pipeline_stats()
        
        cycle_success = producer_success or consumer_success
        if cycle_success:
            logger.info("Pipeline cycle completed successfully")
        else:
            logger.error("Pipeline cycle failed")
            
        return cycle_success
        
    def start(self):
        """Start the automated pipeline."""
        logger.info("Starting automated news pipeline...")
        logger.info(f"Configuration: {self.config}")
        
        self.setup_signal_handlers()
        self.running = True
        
        # Initial infrastructure check
        if not self.check_kafka_infrastructure():
            logger.error("Failed to start Kafka infrastructure")
            return False
            
        # Initial statistics
        self.last_stats = self.get_database_stats()
        logger.info("Initial database state:")
        self.log_pipeline_stats()
        
        failed_cycles = 0
        max_failures = 3
        
        try:
            while self.running:
                cycle_start = time.time()
                
                success = self.run_pipeline_cycle()
                
                if success:
                    failed_cycles = 0
                else:
                    failed_cycles += 1
                    logger.error(f"Pipeline cycle failed ({failed_cycles}/{max_failures})")
                    
                    if failed_cycles >= max_failures:
                        logger.error("Too many consecutive failures, stopping pipeline")
                        break
                        
                # Calculate next run time
                cycle_duration = time.time() - cycle_start
                sleep_time = max(0, self.config.interval_seconds - cycle_duration)
                
                if sleep_time > 0:
                    next_run = datetime.now() + timedelta(seconds=sleep_time)
                    logger.info(f"Next cycle at {next_run.strftime('%H:%M:%S')} "
                               f"(sleeping {sleep_time:.0f}s)")
                    time.sleep(sleep_time)
                    
        except KeyboardInterrupt:
            logger.info("Pipeline interrupted by user")
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
        finally:
            self.stop()
            
        return True
        
    def stop(self):
        """Stop the pipeline."""
        logger.info("Stopping automated pipeline...")
        self.running = False
        
        # Kill any running processes
        for process in [self.producer_process, self.consumer_process]:
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    
        # Final statistics
        if self.last_stats:
            logger.info("Final pipeline statistics:")
            self.log_pipeline_stats()
            
        uptime = datetime.now() - self.start_time
        logger.info(f"Pipeline uptime: {uptime}")
        logger.info("Pipeline stopped")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Automated news extraction pipeline")
    parser.add_argument('--interval', type=int, default=600,
                       help='Interval between cycles in seconds (default: 600)')
    parser.add_argument('--categories', type=str,
                       help='Comma-separated list of categories (default: all)')
    parser.add_argument('--max-articles', type=int, default=50,
                       help='Max articles per batch (default: 50)')
    parser.add_argument('--no-restart', action='store_true',
                       help='Disable automatic restart on failure')
    parser.add_argument('--kafka-bootstrap', default='localhost:29092',
                       help='Kafka bootstrap servers (default: localhost:29092)')
    
    args = parser.parse_args()
    
    # Parse categories
    categories = None
    if args.categories:
        categories = [cat.strip() for cat in args.categories.split(',')]
        
    # Create configuration
    config = PipelineConfig(
        interval_seconds=args.interval,
        categories=categories,
        max_articles_per_batch=args.max_articles,
        restart_on_failure=not args.no_restart,
        kafka_bootstrap=args.kafka_bootstrap
    )
    
    # Create and start pipeline
    pipeline = PipelineManager(config)
    try:
        pipeline.start()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        return 1
        
    return 0


if __name__ == '__main__':
    sys.exit(main())