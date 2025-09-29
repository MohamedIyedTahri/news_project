#!/usr/bin/env python3
"""
Enrichment Pipeline Test Script

This script tests the full-content enrichment functionality by:
1. Connecting to the SQLite database
2. Running enrichment on a small sample of articles
3. Displaying before/after comparison
4. Providing detailed logging and statistics

Usage:
    python test_enrichment_pipeline.py

Requirements:
    - Run from news_project directory
    - news-env conda environment activated
    - Existing articles in database (run main.py first if needed)
"""

import logging
import sys
from typing import List, Dict, Optional, Tuple

# Configure detailed logging for the test
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('enrichment_test.log')
    ]
)
logger = logging.getLogger(__name__)

# Import our modules
try:
    from newsbot.storage import NewsStorage
    from newsbot.main import enrich_database_with_full_articles
    from newsbot.scraper import fetch_full_articles
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Make sure you're running from the news_project directory with news-env activated")
    sys.exit(1)


class EnrichmentTester:
    """Handles enrichment testing workflow with detailed reporting."""
    
    def __init__(self, sample_limit: int = 5):
        """Initialize tester with sample size limit."""
        self.sample_limit = sample_limit
        self.storage: Optional[NewsStorage] = None
        
    def __enter__(self):
        """Context manager entry - initialize storage."""
        try:
            self.storage = NewsStorage()
            logger.info("Connected to SQLite database successfully")
            return self
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup storage."""
        if self.storage:
            self.storage.close()
            logger.info("Database connection closed")
    
    def get_database_stats(self) -> Dict:
        """Get current database statistics."""
        try:
            # Overall stats
            stats = self.storage.get_statistics()
            
            # Check full_content coverage
            cursor = self.storage.conn.execute("""
                SELECT 
                    COUNT(*) as total_articles,
                    COUNT(full_content) as with_full_content,
                    COUNT(CASE WHEN full_content IS NOT NULL AND length(full_content) > 0 THEN 1 END) as non_empty_full_content
                FROM articles
            """)
            coverage = cursor.fetchone()
            
            return {
                'total_articles': stats.get('total_articles', 0),
                'by_category': stats.get('by_category', {}),
                'top_sources': dict(list(stats.get('top_sources', {}).items())[:3]),
                'full_content_coverage': {
                    'total': coverage[0] if coverage else 0,
                    'with_full_content': coverage[1] if coverage else 0,
                    'non_empty_full_content': coverage[2] if coverage else 0
                }
            }
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
    
    def get_sample_articles_needing_enrichment(self) -> List[Tuple[int, str, str, str, str, int]]:
        """Get sample articles that need full_content enrichment."""
        try:
            cursor = self.storage.conn.execute("""
                SELECT id, title, link, source, category, length(COALESCE(content, '')) as summary_length
                FROM articles
                WHERE (full_content IS NULL OR length(full_content) = 0)
                ORDER BY id DESC
                LIMIT ?
            """, (self.sample_limit,))
            
            results = cursor.fetchall()
            logger.info(f"Found {len(results)} articles needing enrichment")
            return results
        except Exception as e:
            logger.error(f"Error fetching sample articles: {e}")
            return []
    
    def get_enriched_articles_sample(self) -> List[Tuple[int, str, str, int, int]]:
        """Get sample of articles that have been enriched."""
        try:
            cursor = self.storage.conn.execute("""
                SELECT 
                    id, title, source, 
                    length(COALESCE(content, '')) as summary_length,
                    length(COALESCE(full_content, '')) as full_length
                FROM articles
                WHERE full_content IS NOT NULL AND length(full_content) > 0
                ORDER BY id DESC
                LIMIT ?
            """, (3,))
            
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error fetching enriched articles: {e}")
            return []
    
    def display_article_details(self, articles: List[Tuple], title: str):
        """Display article details in a formatted way."""
        print(f"\n{'='*60}")
        print(f"{title}")
        print(f"{'='*60}")
        
        if not articles:
            print("No articles found.")
            return
        
        for i, article in enumerate(articles, 1):
            if len(article) == 6:  # Before enrichment format
                art_id, title_text, link, source, category, summary_len = article
                print(f"\n{i}. Article ID: {art_id}")
                print(f"   Title: {title_text[:80]}{'...' if len(title_text) > 80 else ''}")
                print(f"   Source: {source}")
                print(f"   Category: {category}")
                print(f"   Summary length: {summary_len} chars")
                print(f"   Link: {link[:60]}{'...' if len(link) > 60 else ''}")
            elif len(article) == 5:  # After enrichment format
                art_id, title_text, source, summary_len, full_len = article
                ratio = f"{full_len/summary_len:.1f}x" if summary_len > 0 else "N/A"
                print(f"\n{i}. Article ID: {art_id}")
                print(f"   Title: {title_text[:80]}{'...' if len(title_text) > 80 else ''}")
                print(f"   Source: {source}")
                print(f"   Summary: {summary_len} chars")
                print(f"   Full content: {full_len} chars ({ratio} expansion)")
    
    def run_enrichment_test(self) -> Dict:
        """Run the enrichment process and return statistics."""
        logger.info(f"Starting enrichment test with sample limit: {self.sample_limit}")
        
        try:
            # Run the enrichment process
            enrichment_stats = enrich_database_with_full_articles(
                self.storage, 
                limit=self.sample_limit,
                min_full_length=500  # Require at least 500 chars for valid full content
            )
            
            logger.info(f"Enrichment completed: {enrichment_stats}")
            return enrichment_stats
            
        except Exception as e:
            logger.error(f"Error during enrichment: {e}")
            return {"error": str(e), "requested": 0, "updated": 0}
    
    def run_full_test(self):
        """Run the complete test workflow."""
        print("🚀 News Article Enrichment Pipeline Test")
        print("=" * 50)
        
        # 1. Show initial database state
        print("\n📊 INITIAL DATABASE STATUS")
        initial_stats = self.get_database_stats()
        self._print_stats(initial_stats)
        
        # 2. Show articles needing enrichment
        print("\n📝 ARTICLES NEEDING ENRICHMENT")
        articles_to_enrich = self.get_sample_articles_needing_enrichment()
        self.display_article_details(articles_to_enrich, f"Sample of {len(articles_to_enrich)} Articles Needing Full Content")
        
        if not articles_to_enrich:
            print("✅ All articles already have full content! Testing completed.")
            enriched_sample = self.get_enriched_articles_sample()
            self.display_article_details(enriched_sample, "Sample of Already Enriched Articles")
            return
        
        # 3. Run enrichment
        print(f"\n🔄 RUNNING ENRICHMENT (limit: {self.sample_limit})")
        enrichment_results = self.run_enrichment_test()
        
        # 4. Show results
        print("\n📈 ENRICHMENT RESULTS")
        self._print_enrichment_results(enrichment_results)
        
        # 5. Show final database state
        print("\n📊 FINAL DATABASE STATUS")
        final_stats = self.get_database_stats()
        self._print_stats(final_stats)
        
        # 6. Show sample enriched articles
        print("\n✨ ENRICHED ARTICLES SAMPLE")
        enriched_sample = self.get_enriched_articles_sample()
        self.display_article_details(enriched_sample, "Sample of Recently Enriched Articles")
        
        # 7. Summary
        print("\n🎯 TEST SUMMARY")
        self._print_test_summary(initial_stats, final_stats, enrichment_results)
    
    def _print_stats(self, stats: Dict):
        """Print database statistics in a formatted way."""
        if not stats:
            print("❌ Could not retrieve database statistics")
            return
        
        coverage = stats.get('full_content_coverage', {})
        total = coverage.get('total', 0)
        with_full = coverage.get('non_empty_full_content', 0)
        coverage_pct = (with_full / total * 100) if total > 0 else 0
        
        print(f"   Total articles: {total}")
        print(f"   With full content: {with_full} ({coverage_pct:.1f}%)")
        print(f"   Categories: {dict(list(stats.get('by_category', {}).items())[:3])}")
        print(f"   Top sources: {stats.get('top_sources', {})}")
    
    def _print_enrichment_results(self, results: Dict):
        """Print enrichment results in a formatted way."""
        if "error" in results:
            print(f"❌ Enrichment failed: {results['error']}")
            return
        
        requested = results.get('requested', 0)
        updated = results.get('updated', 0)
        fetched = results.get('fetched_full', 0)
        failed = results.get('failed_full', 0)
        
        print(f"   📤 Articles requested for enrichment: {requested}")
        print(f"   🌐 Successfully fetched full content: {fetched}")
        print(f"   💾 Articles updated in database: {updated}")
        print(f"   ❌ Failed to fetch: {failed}")
        
        if requested > 0:
            success_rate = (updated / requested * 100)
            print(f"   📊 Success rate: {success_rate:.1f}%")
    
    def _print_test_summary(self, initial_stats: Dict, final_stats: Dict, enrichment_results: Dict):
        """Print overall test summary."""
        initial_coverage = initial_stats.get('full_content_coverage', {})
        final_coverage = final_stats.get('full_content_coverage', {})
        
        initial_enriched = initial_coverage.get('non_empty_full_content', 0)
        final_enriched = final_coverage.get('non_empty_full_content', 0)
        improvement = final_enriched - initial_enriched
        
        print(f"   🔄 Articles enriched this run: {improvement}")
        print(f"   📈 Total enriched articles: {final_enriched}")
        
        if "error" not in enrichment_results:
            print("   ✅ Test completed successfully!")
        else:
            print(f"   ❌ Test completed with errors: {enrichment_results.get('error', 'Unknown')}")
        
        print(f"   📝 Detailed logs saved to: enrichment_test.log")


def main():
    """Main test function."""
    try:
        # Run the test with context manager for proper cleanup
        with EnrichmentTester(sample_limit=8) as tester:
            tester.run_full_test()
            
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during testing: {e}")
        print(f"\n❌ Test failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()