# List of RSS feeds for news categories
# ENHANCED: Added more diverse sources for faster article growth
RSS_FEEDS = {
    # Global / International affairs (11 feeds - enhanced from 6)
    "international": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",  # BBC World
        "https://feeds.skynews.com/feeds/rss/world.xml",  # Sky News World
        "https://www.aljazeera.com/xml/rss/all.xml",  # Al Jazeera English All
        "https://www.reuters.com/world/rss",  # Reuters World
        "https://www.theguardian.com/world/rss",  # The Guardian World
        "https://rss.cnn.com/rss/edition_world.rss",  # CNN World
        "https://www.npr.org/rss/rss.php?id=1004",  # NPR World
        "https://www.france24.com/en/rss",  # France24 English (full article)
        "https://rss.dw.com/rdf/rss-en-world",  # Deutsche Welle World
        "https://www.al-monitor.com/rss.xml",  # Al-Monitor (full article)
        "https://www.hindustantimes.com/feeds/rss/international-news/rssfeed.xml",  # Hindustan Times
    ],
    
    # Technology & innovation (11 feeds - enhanced from 6)
    "tech": [
        "https://feeds.arstechnica.com/arstechnica/technology-lab",  # Ars Technica
        "https://www.theverge.com/rss/index.xml",  # The Verge
        "https://feeds.feedburner.com/TechCrunch/",  # TechCrunch
        "https://www.wired.com/feed/rss",  # Wired
        "https://www.zdnet.com/news/rss.xml",  # ZDNet
        "https://www.engadget.com/rss.xml",  # Engadget
        "https://venturebeat.com/feed/",  # VentureBeat (full article)
        "https://www.digitaltrends.com/news/rss/",  # Digital Trends (full article)
        "https://www.techradar.com/rss",  # TechRadar
        "https://www.androidpolice.com/feed/",  # Android Police (full article)
        "https://thenextweb.com/feed/",  # The Next Web (full article)
    ],
    
    # Finance / Markets / Economy (12 feeds - enhanced from 6)
    "finance": [
        "https://www.investing.com/rss/news_25.rss",  # Investing (Economy)
        "https://www.wsj.com/xml/rss/3_7031.xml",  # WSJ Markets
        "https://www.ft.com/?format=rss",  # Financial Times
        "https://www.marketwatch.com/rss/topstories",  # MarketWatch
        "https://www.reuters.com/finance/markets/rss",  # Reuters Markets
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",  # Dow Jones Markets
        "https://feeds.bloomberg.com/markets/news.rss",  # Bloomberg Markets
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # CNBC Markets
        "https://markets.businessinsider.com/rss/news",  # Business Insider Markets
        "https://www.globalbankingandfinance.com/feed/",  # Global Banking (full article)
        "https://www.federalreserve.gov/feeds/press_all.xml",  # Federal Reserve (full)
        "https://www.economist.com/finance-and-economics/rss.xml",  # The Economist Finance
    ],
    
    # Arabic language sources (12 feeds - enhanced from 6)
    "arabic": [
        "https://www.aljazeera.net/aljazeera/rss",  # Al Jazeera Arabic
        "https://www.alarabiya.net/rss",  # Al Arabiya
        "https://arabic.cnn.com/rss",  # CNN Arabic
        "https://www.skynewsarabia.com/web/rss",  # Sky News Arabia
        "https://www.france24.com/ar/rss",  # France24 Arabic
        "https://www.dw.com/line/rss-aleppo",  # DW Arabic
        "https://www.annahar.com/rss",  # An-Nahar Lebanese
        "https://www.alquds.co.uk/feed/",  # Al-Quds Al-Arabi (full article)
        "https://www.alhurra.com/rss",  # Alhurra
        "https://alarab.co.uk/rss.xml",  # Al-Arab
        "https://www.masrawy.com/rss/rss_topstories.aspx",  # Masrawy Egypt
        "https://www.asharq.com/feed",  # Asharq News (full article)
    ],
    
    # Science & research (8 feeds - enhanced from 4)
    "science": [
        "https://www.sciencenews.org/feed",  # Science News (full article)
        "https://www.space.com/feeds/all",  # Space.com (full article)
        "https://www.nasa.gov/rss/dyn/breaking_news.rss",  # NASA
        "https://www.newscientist.com/feed/home/",  # New Scientist
        "https://www.sciencedaily.com/rss/all.xml",  # ScienceDaily
        "https://phys.org/rss-feed/",  # Phys.org
        "https://www.scientificamerican.com/feed/",  # Scientific American
        "https://www.livescience.com/feeds/all",  # Live Science
    ],
    
    # Health & medicine (8 feeds - enhanced from 4)
    "health": [
        "https://www.medicalnewstoday.com/rss",  # Medical News Today (full article)
        "https://www.statnews.com/feed/",  # STAT (full article)
        "https://www.health.harvard.edu/blog/feed",  # Harvard Health (full article)
        "https://www.who.int/feeds/entity/mediacentre/news/en/rss.xml",  # WHO
        "https://www.healthline.com/rss",  # Healthline
        "https://www.webmd.com/rss/rss.aspx?RSSSource=RSS_PUBLIC",  # WebMD
        "https://www.nih.gov/news-events/news-releases/rss",  # NIH News
        "https://www.cdc.gov/rss/govdelivery/cdc-public-health.xml",  # CDC Public Health
    ],

    # Demo category (2 feeds) for quick pipeline smoke tests
    "demo": [
        "https://feeds.arstechnica.com/arstechnica/technology-lab",  # Ars Technica
        "http://feeds.bbci.co.uk/news/world/rss.xml",  # BBC World
    ]
}

# Extended feed catalogue prioritizing full-article availability
RSS_FEEDS_EXTENDED = {
    # Global / International affairs
    "international": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",  # Summary; BBC World Service digest
        "https://feeds.skynews.com/feeds/rss/world.xml",  # Summary; Sky News world headlines
        "https://www.aljazeera.com/xml/rss/all.xml",  # Full article; Al Jazeera English includes story body
        "https://www.reuters.com/world/rss",  # Summary; Reuters wire leads only
        "https://www.theguardian.com/world/rss",  # Summary; Guardian world desk excerpts
        "https://rss.cnn.com/rss/edition_world.rss",  # Summary; CNN world brief summaries
        "https://www.npr.org/rss/rss.php?id=1004",  # Summary; NPR global coverage capsules
        "https://www.france24.com/en/rss",  # Full article; France24 English publishes full text
        "https://rss.dw.com/rdf/rss-en-world",  # Summary; Deutsche Welle world updates
        "https://www.al-monitor.com/rss.xml",  # Full article; Al-Monitor analysis long-form
        "https://www.hindustantimes.com/feeds/rss/international-news/rssfeed.xml",  # Summary; Hindustan Times international desk
    ],
    # Technology & innovation
    "tech": [
        "https://feeds.arstechnica.com/arstechnica/technology-lab",  # Full article; Ars Technica publishes complete posts
        "https://www.theverge.com/rss/index.xml",  # Summary; The Verge provides abridged copy
        "https://feeds.feedburner.com/TechCrunch/",  # Summary; TechCrunch truncated feeds
        "https://www.wired.com/feed/rss",  # Summary; Wired syndication excerpts
        "https://www.zdnet.com/news/rss.xml",  # Summary; ZDNet highlights
        "https://www.engadget.com/rss.xml",  # Summary; Engadget teaser paragraphs
        "https://venturebeat.com/feed/",  # Full article; VentureBeat WordPress full text
        "https://www.digitaltrends.com/news/rss/",  # Full article; Digital Trends complete stories
        "https://www.techradar.com/rss",  # Summary; TechRadar condensed articles
        "https://www.androidpolice.com/feed/",  # Full article; Android Police full-text feed
        "https://thenextweb.com/feed/",  # Full article; TNW full body content
    ],
    # Finance / Markets / Economy
    "finance": [
        "https://www.investing.com/rss/news_25.rss",  # Summary; Investing.com economy briefs
        "https://www.wsj.com/xml/rss/3_7031.xml",  # Summary; WSJ markets abstracts (paywall)
        "https://www.ft.com/?format=rss",  # Summary; Financial Times snippets (paywall)
        "https://www.marketwatch.com/rss/topstories",  # Summary; MarketWatch top stories
        "https://www.reuters.com/finance/markets/rss",  # Summary; Reuters markets wire
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",  # Summary; Dow Jones markets headlines
        "https://feeds.bloomberg.com/markets/news.rss",  # Summary; Bloomberg markets headlines (paywall)
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # Summary; CNBC markets digest
        "https://markets.businessinsider.com/rss/news",  # Summary; Business Insider markets updates
        "https://www.globalbankingandfinance.com/feed/",  # Full article; WordPress feed with complete text
        "https://www.federalreserve.gov/feeds/press_all.xml",  # Full article; Federal Reserve full releases
        "https://www.economist.com/finance-and-economics/rss.xml",  # Summary; The Economist finance briefs
    ],
    # Arabic language sources
    "arabic": [
        "https://www.aljazeera.net/aljazeera/rss",  # Full article; Al Jazeera Arabic complete text
        "https://www.alarabiya.net/rss",  # Summary; Al Arabiya news summaries
        "https://arabic.cnn.com/rss",  # Summary; CNN Arabic briefs
        "https://www.skynewsarabia.com/web/rss",  # Summary; Sky News Arabia highlights
        "https://www.france24.com/ar/rss",  # Summary; France24 Arabic excerpts
        "https://www.dw.com/line/rss-aleppo",  # Summary; DW Arabic regional feed
        "https://www.annahar.com/rss",  # Summary; An-Nahar Lebanese news digests
        "https://www.alquds.co.uk/feed/",  # Full article; Al-Quds Al-Arabi full-text WordPress
        "https://www.alhurra.com/rss",  # Summary; Alhurra brief reports
        "https://alarab.co.uk/rss.xml",  # Summary; Al-Arab pan-Arab analysis excerpts
        "https://www.masrawy.com/rss/rss_topstories.aspx",  # Summary; Masrawy Egypt top stories
        "https://www.asharq.com/feed",  # Full article; Asharq News full-length pieces
    ],
    # Science & research
    "science": [
        "https://www.sciencenews.org/feed",  # Full article; Science News WordPress full text
        "https://www.space.com/feeds/all",  # Full article; Space.com long-form coverage
        "https://www.nasa.gov/rss/dyn/breaking_news.rss",  # Summary; NASA press highlights
        "https://www.newscientist.com/feed/home/",  # Summary; New Scientist teasers
    ],
    # Health & medicine
    "health": [
        "https://www.medicalnewstoday.com/rss",  # Full article; Medical News Today full text
        "https://www.statnews.com/feed/",  # Full article; STAT publishes complete stories
        "https://www.health.harvard.edu/blog/feed",  # Full article; Harvard Health blog posts
        "https://www.who.int/feeds/entity/mediacentre/news/en/rss.xml",  # Summary; WHO media releases
    ],
    # Sports & athletics
    "sports": [
        "https://www.espn.com/espn/rss/news",  # Summary; ESPN national sports wrap-ups
        "https://feeds.bbci.co.uk/sport/rss.xml?edition=uk",  # Summary; BBC Sport short-form updates
        "https://www.si.com/.rss/full",  # Full article; Sports Illustrated full-text feed
        "https://www.skysports.com/rss/12040",  # Summary; Sky Sports top stories
        "https://www.goal.com/feeds/en/news",  # Summary; Goal.com football news snippets
    ],
    # Entertainment & culture
    "entertainment": [
        "https://www.hollywoodreporter.com/feed/",  # Full article; Hollywood Reporter complete content
        "https://variety.com/feed/",  # Full article; Variety publishes full stories
        "https://www.rollingstone.com/music/music-news/feed/",  # Full article; Rolling Stone music news
        #"https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml",  # Summary; NYT arts section previews
        "https://www.eonline.com/syndication/rss/topstories.xml",  # Summary; E! News entertainment briefs
    ],
}

# NOTE: Some feeds may occasionally change or rate-limit. If persistent failures occur,
# consider implementing exponential backoff or rotating the active subset per run.
