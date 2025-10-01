#!/usr/bin/env python3
"""
Quick Pipeline Automation

Simple automation script that runs the complete pipeline:
1. Starts Kafka infrastructure
2. Runs producer to fetch RSS articles
3. Runs consumer to extract full content
4. Shows results

Usage:
    python scripts/quick_automation.py
    python scripts/quick_automation.py --categories tech,science --articles 20
    python scripts/quick_automation.py --continuous --interval 300
"""

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
import os


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QuickPipeline:
    """Simple pipeline automation."""
    
    def __init__(self):
        # Ensure we're in the right directory
        project_root = Path(__file__).parent.parent
        os.chdir(project_root)
        
        # Set environment
        os.environ['KAFKA_BOOTSTRAP_SERVERS'] = 'localhost:29092'
        
    def ensure_kafka_running(self):
        """Start Kafka if not running."""
        logger.info("Checking Kafka infrastructure...")
        
        try:
            result = subprocess.run(
                ['docker-compose', 'ps', '-q', 'kafka'],
                capture_output=True, text=True, timeout=10
            )
            if not result.stdout.strip():
                logger.info("Starting Kafka infrastructure...")
                subprocess.run(['docker-compose', 'up', '-d'], check=True, timeout=60)
                time.sleep(10)
                
                # Create topics
                if Path('scripts/create_kafka_topics.sh').exists():
                    subprocess.run(['bash', 'scripts/create_kafka_topics.sh'], timeout=30)
                    
                logger.info("Kafka infrastructure started")
            else:
                logger.info("Kafka already running")
                
        except Exception as e:
            logger.error(f"Failed to start Kafka: {e}")
            raise
            
    def run_extraction_cycle(self, categories=None, max_articles=30):
        """Run one complete extraction cycle."""
        logger.info("=" * 60)
        logger.info(f"Starting extraction cycle at {datetime.now().strftime('%H:%M:%S')}")
        
        try:
            # Ensure Kafka is running
            self.ensure_kafka_running()
            
            # Run producer
            logger.info("Fetching RSS articles...")
            cmd = [sys.executable, '-m', 'newsbot.kafka_producer', '--once']
            if categories:
                cmd.extend(['--categories', ','.join(categories)])
                
            result = subprocess.run(cmd, timeout=120, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Producer failed: {result.stderr}")
                return False
                
            # Extract produced count
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                if 'Producing' in line or 'messages_produced' in line:
                    logger.info(f"Producer: {line.strip()}")
                    
            # Small delay
            time.sleep(3)
            
            # Run consumer
            logger.info("Extracting full article content...")
            cmd = [
                sys.executable, '-m', 'newsbot.kafka_scraper_async_consumer',
                '--max-messages', str(max_articles)
            ]
            
            result = subprocess.run(cmd, timeout=300, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Consumer failed: {result.stderr}")
                return False
                
            # Extract consumer metrics
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                if any(word in line.lower() for word in ['consumed', 'enriched', 'success', 'processed']):
                    logger.info(f"Consumer: {line.strip()}")
                    
            # Show database stats
            logger.info("Updated database statistics:")
            result = subprocess.run(
                [sys.executable, '-m', 'newsbot.db_stats'],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                # Show overall stats line
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'Overall coverage' in line:
                        logger.info(f"Database: {line}")
                        break
                        
            logger.info("Extraction cycle completed successfully")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Extraction cycle timed out")
            return False
        except Exception as e:
            logger.error(f"Extraction cycle failed: {e}")
            return False
            
    def run_continuous(self, interval=600, categories=None, max_articles=30):
        """Run continuous extraction cycles."""
        logger.info(f"Starting continuous extraction (interval: {interval}s)")
        logger.info(f"Categories: {categories or 'all'}")
        logger.info(f"Max articles per cycle: {max_articles}")
        
        cycle_count = 0
        try:
            while True:
                cycle_count += 1
                logger.info(f"\n--- CYCLE {cycle_count} ---")
                
                success = self.run_extraction_cycle(categories, max_articles)
                
                if success:
                    logger.info(f"Cycle {cycle_count} completed successfully")
                else:
                    logger.warning(f"Cycle {cycle_count} had errors")
                    
                # Wait for next cycle
                next_time = datetime.now().replace(second=0, microsecond=0)
                next_time = next_time.replace(minute=(next_time.minute + interval // 60) % 60)
                
                logger.info(f"Next cycle at {next_time.strftime('%H:%M')} (sleeping {interval}s)")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info(f"\nContinuous extraction stopped after {cycle_count} cycles")
        except Exception as e:
            logger.error(f"Continuous extraction failed: {e}")
            
    def quick_test(self):
        """Run a quick test extraction."""
        logger.info("Running quick pipeline test...")
        
        success = self.run_extraction_cycle(['tech', 'science'], 10)
        
        if success:
            logger.info("✓ Quick test completed successfully")
            logger.info("Pipeline is working correctly")
        else:
            logger.error("✗ Quick test failed")
            logger.error("Check the logs above for issues")
            
        return success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Quick pipeline automation")
    
    parser.add_argument('--categories', 
                       help='Comma-separated categories (e.g., tech,science)')
    parser.add_argument('--articles', type=int, default=30,
                       help='Max articles per cycle (default: 30)')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuously instead of once')
    parser.add_argument('--interval', type=int, default=600,
                       help='Interval for continuous mode in seconds (default: 600)')
    parser.add_argument('--test', action='store_true',
                       help='Run quick test with tech+science categories')
    
    args = parser.parse_args()
    
    # Parse categories
    categories = None
    if args.categories:
        categories = [cat.strip() for cat in args.categories.split(',')]
        
    # Create pipeline
    pipeline = QuickPipeline()
    
    try:
        if args.test:
            success = pipeline.quick_test()
            return 0 if success else 1
        elif args.continuous:
            pipeline.run_continuous(args.interval, categories, args.articles)
        else:
            success = pipeline.run_extraction_cycle(categories, args.articles)
            return 0 if success else 1
            
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        return 1
        
    return 0


if __name__ == '__main__':
    sys.exit(main())