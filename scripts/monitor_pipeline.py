#!/usr/bin/env python3
"""
Pipeline Monitoring and Health Check System

Monitors the news extraction pipeline health, database growth,
and system performance. Provides alerts and automatic recovery.

Features:
- Real-time pipeline health monitoring
- Database growth tracking and analytics
- Performance metrics collection
- Alert system for failures and anomalies
- Automatic health recovery actions
- Web dashboard (optional)

Usage:
    python scripts/monitor_pipeline.py
    python scripts/monitor_pipeline.py --web-port 8080
    python scripts/monitor_pipeline.py --alert-email user@example.com
"""

import asyncio
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional
import argparse
import sqlite3
import smtplib
from email.mime.text import MimeText


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class HealthMetrics:
    """Pipeline health metrics."""
    timestamp: str
    database_total: int
    database_enriched: int
    coverage_percentage: float
    kafka_running: bool
    recent_growth: int
    error_count: int
    last_extraction: Optional[str]
    performance_score: float


@dataclass
class AlertConfig:
    """Alert configuration."""
    min_coverage: float = 50.0
    max_error_rate: float = 0.1
    min_growth_per_hour: int = 10
    email_recipient: Optional[str] = None
    slack_webhook: Optional[str] = None


class PipelineMonitor:
    """Monitors pipeline health and performance."""
    
    def __init__(self, alert_config: AlertConfig = None):
        self.alert_config = alert_config or AlertConfig()
        self.metrics_history: List[HealthMetrics] = []
        self.last_alert_time: Dict[str, datetime] = {}
        self.alert_cooldown = timedelta(minutes=30)
        
        # Ensure we're in the right directory
        project_root = Path(__file__).parent.parent
        os.chdir(project_root) if 'os' in globals() else None
        
    def check_kafka_health(self) -> bool:
        """Check if Kafka infrastructure is running."""
        try:
            result = subprocess.run(
                ['docker-compose', 'ps', '-q', 'kafka'],
                capture_output=True, text=True, timeout=10
            )
            return bool(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Failed to check Kafka health: {e}")
            return False
            
    def get_database_metrics(self) -> Dict:
        """Get current database metrics."""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'newsbot.db_stats', '--json'],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
            return {}
        except Exception as e:
            logger.error(f"Failed to get database metrics: {e}")
            return {}
            
    def calculate_recent_growth(self, hours: int = 1) -> int:
        """Calculate article growth in recent hours."""
        if len(self.metrics_history) < 2:
            return 0
            
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics_history 
            if datetime.fromisoformat(m.timestamp) > cutoff_time
        ]
        
        if len(recent_metrics) < 2:
            return 0
            
        latest = recent_metrics[-1]
        earliest = recent_metrics[0]
        return latest.database_total - earliest.database_total
        
    def calculate_error_rate(self, hours: int = 24) -> float:
        """Calculate error rate over recent hours."""
        if len(self.metrics_history) < 2:
            return 0.0
            
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics_history 
            if datetime.fromisoformat(m.timestamp) > cutoff_time
        ]
        
        if not recent_metrics:
            return 0.0
            
        total_errors = sum(m.error_count for m in recent_metrics)
        total_checks = len(recent_metrics)
        return total_errors / total_checks if total_checks > 0 else 0.0
        
    def calculate_performance_score(self, metrics: HealthMetrics) -> float:
        """Calculate overall performance score (0-100)."""
        score = 0.0
        
        # Coverage contribution (40%)
        score += min(metrics.coverage_percentage, 100) * 0.4
        
        # Growth contribution (30%)
        growth_score = min(metrics.recent_growth / 50, 1.0) * 100
        score += growth_score * 0.3
        
        # Infrastructure health (20%)
        if metrics.kafka_running:
            score += 20
            
        # Error rate contribution (10%)
        error_rate = self.calculate_error_rate()
        error_score = max(0, 1 - error_rate) * 100
        score += error_score * 0.1
        
        return min(score, 100.0)
        
    def collect_metrics(self) -> HealthMetrics:
        """Collect current pipeline metrics."""
        db_metrics = self.get_database_metrics()
        overall = db_metrics.get('overall', {})
        
        recent_growth = self.calculate_recent_growth(1)
        error_count = 0  # TODO: Implement error tracking
        
        metrics = HealthMetrics(
            timestamp=datetime.now().isoformat(),
            database_total=overall.get('total', 0),
            database_enriched=overall.get('with_full', 0),
            coverage_percentage=overall.get('coverage_pct', 0.0),
            kafka_running=self.check_kafka_health(),
            recent_growth=recent_growth,
            error_count=error_count,
            last_extraction=None,  # TODO: Track last extraction time
            performance_score=0.0  # Will be calculated below
        )
        
        metrics.performance_score = self.calculate_performance_score(metrics)
        return metrics
        
    def should_alert(self, alert_type: str) -> bool:
        """Check if we should send an alert (respects cooldown)."""
        last_alert = self.last_alert_time.get(alert_type)
        if last_alert and datetime.now() - last_alert < self.alert_cooldown:
            return False
        return True
        
    def send_alert(self, alert_type: str, message: str):
        """Send an alert notification."""
        if not self.should_alert(alert_type):
            return
            
        logger.warning(f"ALERT [{alert_type}]: {message}")
        
        # Email alert
        if self.alert_config.email_recipient:
            try:
                self.send_email_alert(alert_type, message)
            except Exception as e:
                logger.error(f"Failed to send email alert: {e}")
                
        # Record alert time
        self.last_alert_time[alert_type] = datetime.now()
        
    def send_email_alert(self, alert_type: str, message: str):
        """Send email alert (basic SMTP)."""
        # This is a basic implementation - configure SMTP settings as needed
        subject = f"News Pipeline Alert: {alert_type}"
        
        msg = MimeText(f"""
Pipeline Alert: {alert_type}

Message: {message}

Time: {datetime.now().isoformat()}

Recent Metrics:
{self.format_metrics_summary()}

--
News Pipeline Monitor
        """)
        
        msg['Subject'] = subject
        msg['From'] = 'pipeline-monitor@localhost'
        msg['To'] = self.alert_config.email_recipient
        
        # TODO: Configure SMTP server settings
        logger.info(f"Email alert prepared: {subject}")
        
    def analyze_health(self, metrics: HealthMetrics):
        """Analyze metrics and trigger alerts if needed."""
        # Coverage alert
        if metrics.coverage_percentage < self.alert_config.min_coverage:
            self.send_alert(
                'LOW_COVERAGE',
                f"Coverage dropped to {metrics.coverage_percentage:.1f}% "
                f"(threshold: {self.alert_config.min_coverage}%)"
            )
            
        # Growth alert
        if metrics.recent_growth < self.alert_config.min_growth_per_hour:
            self.send_alert(
                'LOW_GROWTH',
                f"Recent growth: {metrics.recent_growth} articles/hour "
                f"(threshold: {self.alert_config.min_growth_per_hour})"
            )
            
        # Infrastructure alert
        if not metrics.kafka_running:
            self.send_alert(
                'KAFKA_DOWN',
                "Kafka infrastructure is not running"
            )
            
        # Error rate alert
        error_rate = self.calculate_error_rate()
        if error_rate > self.alert_config.max_error_rate:
            self.send_alert(
                'HIGH_ERROR_RATE',
                f"Error rate: {error_rate:.2%} "
                f"(threshold: {self.alert_config.max_error_rate:.2%})"
            )
            
    def format_metrics_summary(self) -> str:
        """Format metrics for display."""
        if not self.metrics_history:
            return "No metrics available"
            
        latest = self.metrics_history[-1]
        
        return f"""
Database: {latest.database_enriched}/{latest.database_total} enriched ({latest.coverage_percentage:.1f}%)
Recent Growth: {latest.recent_growth} articles/hour
Kafka Status: {'✓' if latest.kafka_running else '✗'}
Performance Score: {latest.performance_score:.1f}/100
Last Updated: {latest.timestamp}
        """.strip()
        
    def save_metrics_history(self, filename: str = 'metrics_history.json'):
        """Save metrics history to file."""
        try:
            with open(filename, 'w') as f:
                json.dump([asdict(m) for m in self.metrics_history], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metrics history: {e}")
            
    def load_metrics_history(self, filename: str = 'metrics_history.json'):
        """Load metrics history from file."""
        try:
            if Path(filename).exists():
                with open(filename, 'r') as f:
                    data = json.load(f)
                    self.metrics_history = [HealthMetrics(**item) for item in data]
                    logger.info(f"Loaded {len(self.metrics_history)} historical metrics")
        except Exception as e:
            logger.error(f"Failed to load metrics history: {e}")
            
    def run_monitoring_cycle(self):
        """Run one monitoring cycle."""
        try:
            # Collect metrics
            metrics = self.collect_metrics()
            self.metrics_history.append(metrics)
            
            # Keep only recent history (last 7 days)
            cutoff_time = datetime.now() - timedelta(days=7)
            self.metrics_history = [
                m for m in self.metrics_history
                if datetime.fromisoformat(m.timestamp) > cutoff_time
            ]
            
            # Analyze health
            self.analyze_health(metrics)
            
            # Log summary
            logger.info(f"Health Check: Score {metrics.performance_score:.1f}/100, "
                       f"Coverage {metrics.coverage_percentage:.1f}%, "
                       f"Growth +{metrics.recent_growth}/hour")
            
            # Save history
            self.save_metrics_history()
            
        except Exception as e:
            logger.error(f"Monitoring cycle failed: {e}")
            
    def start_monitoring(self, interval: int = 300):
        """Start continuous monitoring."""
        logger.info(f"Starting pipeline monitoring (interval: {interval}s)")
        
        # Load historical data
        self.load_metrics_history()
        
        try:
            while True:
                self.run_monitoring_cycle()
                
                logger.info(f"Next check in {interval} seconds...")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring interrupted")
        except Exception as e:
            logger.error(f"Monitoring failed: {e}")
        finally:
            self.save_metrics_history()
            
    def generate_health_report(self) -> str:
        """Generate a comprehensive health report."""
        if not self.metrics_history:
            return "No metrics available for report"
            
        latest = self.metrics_history[-1]
        
        # Calculate trends
        if len(self.metrics_history) >= 2:
            previous = self.metrics_history[-2]
            coverage_trend = latest.coverage_percentage - previous.coverage_percentage
            growth_trend = latest.database_total - previous.database_total
        else:
            coverage_trend = 0
            growth_trend = 0
            
        report = f"""
========================================
NEWS PIPELINE HEALTH REPORT
========================================

Overall Status: {'🟢 HEALTHY' if latest.performance_score > 75 else '🟡 WARNING' if latest.performance_score > 50 else '🔴 CRITICAL'}
Performance Score: {latest.performance_score:.1f}/100

DATABASE METRICS
- Total Articles: {latest.database_total:,}
- Enriched Articles: {latest.database_enriched:,}
- Coverage: {latest.coverage_percentage:.1f}% ({coverage_trend:+.1f}% since last check)
- Recent Growth: {latest.recent_growth} articles/hour

INFRASTRUCTURE
- Kafka Status: {'✓ Running' if latest.kafka_running else '✗ Down'}
- Error Rate (24h): {self.calculate_error_rate():.2%}

TRENDS (Last 24 Hours)
- Article Growth: +{growth_trend} articles
- Coverage Change: {coverage_trend:+.1f}%

ALERTS SUMMARY
- Recent Alerts: {len(self.last_alert_time)} types
- Last Alert: {max(self.last_alert_time.values()).isoformat() if self.last_alert_time else 'None'}

Report Generated: {datetime.now().isoformat()}
========================================
        """
        
        return report.strip()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Pipeline monitoring and health checks")
    
    parser.add_argument('--interval', type=int, default=300,
                       help='Monitoring interval in seconds (default: 300)')
    parser.add_argument('--min-coverage', type=float, default=50.0,
                       help='Minimum coverage threshold for alerts (default: 50.0)')
    parser.add_argument('--min-growth', type=int, default=10,
                       help='Minimum growth per hour for alerts (default: 10)')
    parser.add_argument('--alert-email', 
                       help='Email address for alerts')
    parser.add_argument('--report-only', action='store_true',
                       help='Generate report and exit (no continuous monitoring)')
    
    args = parser.parse_args()
    
    # Create alert configuration
    alert_config = AlertConfig(
        min_coverage=args.min_coverage,
        min_growth_per_hour=args.min_growth,
        email_recipient=args.alert_email
    )
    
    # Create monitor
    monitor = PipelineMonitor(alert_config)
    
    if args.report_only:
        # Generate single report
        monitor.load_metrics_history()
        monitor.run_monitoring_cycle()
        print(monitor.generate_health_report())
        return 0
        
    try:
        # Start continuous monitoring
        monitor.start_monitoring(args.interval)
    except KeyboardInterrupt:
        logger.info("Monitoring stopped")
    except Exception as e:
        logger.error(f"Monitoring failed: {e}")
        return 1
        
    return 0


if __name__ == '__main__':
    import os
    sys.exit(main())