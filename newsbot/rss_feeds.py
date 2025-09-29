# List of RSS feeds for news categories
RSS_FEEDS = {
    # Global / International affairs
    "international": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",  # BBC World
        #"https://rss.nytimes.com/services/xml/rss/nyt/World.xml",  # NYT World
        "https://feeds.skynews.com/feeds/rss/world.xml",  # Sky News World
        "https://www.aljazeera.com/xml/rss/all.xml",  # Al Jazeera English All
        "https://www.reuters.com/world/rss",  # Reuters World
        "https://www.theguardian.com/world/rss"  # The Guardian World
    ],
    # Technology & innovation
    "tech": [
        "https://feeds.arstechnica.com/arstechnica/technology-lab",  # Ars Technica
        "https://www.theverge.com/rss/index.xml",  # The Verge
        "https://feeds.feedburner.com/TechCrunch/",  # TechCrunch
        "https://www.wired.com/feed/rss",  # Wired
        "https://www.zdnet.com/news/rss.xml",  # ZDNet
        "https://www.engadget.com/rss.xml"  # Engadget
    ],
    # Finance / Markets / Economy
    "finance": [
        "https://www.investing.com/rss/news_25.rss",  # Investing (Economy)
        "https://www.wsj.com/xml/rss/3_7031.xml",  # WSJ Markets
        "https://www.ft.com/?format=rss",  # Financial Times (main)
        "https://www.marketwatch.com/rss/topstories",  # MarketWatch
        "https://www.reuters.com/finance/markets/rss",  # Reuters Markets
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"  # Dow Jones Markets
    ],
    # Arabic language sources
    "arabic": [
        "https://www.aljazeera.net/aljazeera/rss",  # Al Jazeera Arabic
        "https://www.alarabiya.net/rss",  # Al Arabiya
        "https://arabic.cnn.com/rss",  # CNN Arabic
        "https://www.skynewsarabia.com/web/rss",  # Sky News Arabia
        "https://www.france24.com/ar/rss",  # France24 Arabic
        "https://www.dw.com/line/rss-aleppo"  # DW Arabic (example regional feed)
    ]
}

# NOTE: Some feeds may occasionally change or rate-limit. If persistent failures occur,
# consider implementing exponential backoff or rotating the active subset per run.
