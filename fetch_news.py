# fetch_news.py
# Teesra — Day 5
# This file fetches real headlines from Indian news sources

import feedparser
import urllib.request
from datetime import datetime

# ── 1. OUR NEWS SOURCES ──────────────────────────────────────────
# Each source has a name, RSS feed URL, and political lean
# This is a LIST OF DICTIONARIES — exactly what you learned in the video

SOURCES = [
    {
        "name": "The Hindu",
        "url": "https://www.thehindu.com/news/national/feeder/default.rss",
        "bias": "center-left"
    },
    {
        "name": "Indian Express",
        "url": "https://indianexpress.com/feed/",
        "bias": "center-left"
    },
    {
        "name": "NDTV",
        "url": "https://feeds.feedburner.com/ndtvnews-india-news",
        "bias": "center-left"
    },
    {
        "name": "Times of India",
        "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
        "bias": "center"
    },
    {
        "name": "Mint",
        "url": "https://www.livemint.com/rss/news",
        "bias": "center"
    },
    {
        "name": "Scroll",
        "url": "https://feeds.feedburner.com/ScrollinArticles",
        "bias": "left"
    },
    {
        "name": "Hindustan Times",
        "url": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
        "bias": "center"
    },
    {
        "name": "News18",
        "url": "https://www.news18.com/rss/india.xml",
        "bias": "right"
    },
    {
        "name": "BBC India",
        "url": "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml",
        "bias": "center"
    },
    {
        "name": "OpIndia",
        "url": "https://www.opindia.com/feed/",
        "bias": "right"
    },
    {
        "name": "The Caravan",
        "url": "https://caravanmagazine.in/feed",
        "bias": "left"
    },
    {
        "name": "The Quint",
        "url": "https://www.thequint.com/feed",
        "bias": "left"
    },
    {
        "name": "ESPNCricinfo",
        "url": "https://www.espncricinfo.com/rss/content/story/feeds/0.xml",
        "bias": "center"
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "bias": "center"
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "bias": "center"
    },
    {
        "name": "BBC World",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "bias": "center"
    },
    {
        "name": "Reuters",
        "url": "https://feeds.reuters.com/reuters/topNews",
        "bias": "center"
    },
    {
        "name": "Google News India",
        "url": "https://news.google.com/rss/search?q=india&hl=en-IN&gl=IN&ceid=IN:en",
        "bias": "center"
    },
    {
        "name": "Google News Politics",
        "url": "https://news.google.com/rss/search?q=india+politics&hl=en-IN&gl=IN&ceid=IN:en",
        "bias": "center"
    },
    {
        "name": "Google News Economy",
        "url": "https://news.google.com/rss/search?q=india+economy+budget&hl=en-IN&gl=IN&ceid=IN:en",
        "bias": "center"
    },
    {
        "name": "Google News Tech",
        "url": "https://news.google.com/rss/search?q=india+technology+startup&hl=en-IN&gl=IN&ceid=IN:en",
        "bias": "center"
    },
    {
        "name": "Google News Top Stories",
        "url": "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en",
        "bias": "center"
    },
    {
        "name": "Google News IPL",
        "url": "https://news.google.com/rss/search?q=IPL+2026+match+result&hl=en-IN&gl=IN&ceid=IN:en",
        "bias": "center"
    },
    {
        "name": "Cricbuzz",
        "url": "https://www.cricbuzz.com/rss-feeds/ipl",
        "bias": "center"
    }

]


# ── GOOGLE URL HELPER ─────────────────────────────────────────────
# Google News RSS links are sometimes proxied through news.google.com.
# This helper follows the redirect to recover the real article URL.

def resolve_google_url(url):
    """If url is a Google News proxy link, follow redirect to get real URL."""
    if "news.google.com" not in url:
        return url
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            method="HEAD"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.url
    except Exception:
        return url


# ── 2. THE FETCHER FUNCTION ───────────────────────────────────────
# A function that takes one source and returns its articles
# This uses everything you learned — functions, loops, dictionaries

def fetch_from_source(source):
    articles = []  # empty list to collect articles

    try:
        feed = feedparser.parse(source["url"])

        # Loop through first 5 articles from this source
        for entry in feed.entries[:5]:

            raw_url = entry.get("link", "")
            title = entry.get("title", "No title")
            # For Google News feeds, extract the real publisher from the title suffix
            if source["name"].startswith("Google News") and ' - ' in title:
                real_source = title.rsplit(' - ', 1)[-1].strip()
                title       = title.rsplit(' - ', 1)[0].strip()
            else:
                real_source = source["name"]
                if ' - ' in title:
                    title = title.rsplit(' - ', 1)[0].strip()
            article = {
                "title":     title,
                "summary":   entry.get("summary", "No summary"),
                "url":       resolve_google_url(raw_url),
                "source":    real_source,
                "bias":      source["bias"],
                "fetched_at": str(datetime.now())
            }

            if not is_likely_paywalled(article):
                articles.append(article)

    except Exception as e:
        print(f"  ⚠️  Could not fetch {source['name']}: {e}")

    return articles


# ── 3. THE MAIN FUNCTION ──────────────────────────────────────────
# This loops through ALL sources and collects everything
PAYWALLED_SOURCES = [
    "Indian Express",
    "Mint",
    "The Hindu",
    "Hindustan Times"
]

def is_likely_paywalled(article: dict) -> bool:
    """Skip articles from known paywall sources with thin summaries"""
    source = article.get("source", "")
    summary = article.get("summary", "")

    if source in PAYWALLED_SOURCES and len(summary) < 200:
        return True
    return False

def fetch_all_news():
    all_articles = []

    print("\n🗞️  Teesra — Fetching today's news...\n")
    print("─" * 50)

    for source in SOURCES:
        print(f"  Fetching → {source['name']} [{source['bias']}]")
        articles = fetch_from_source(source)
        all_articles.extend(articles)
        print(f"  ✅ Got {len(articles)} articles\n")

    print("─" * 50)
    print(f"\n📦 Total articles fetched: {len(all_articles)}")
    return all_articles


# ── 4. DISPLAY FUNCTION ───────────────────────────────────────────
# Print a clean summary so we can see what we got

def display_articles(articles):
    print("\n📰 Sample headlines from each source:\n")
    print("─" * 50)

    # Group by source and show first article from each
    seen_sources = []

    for article in articles:
        if article["source"] not in seen_sources:
            seen_sources.append(article["source"])

            # Color code by bias
            if article["bias"] == "left":
                tag = "🔵 LEFT"
            elif article["bias"] == "right":
                tag = "🔴 RIGHT"
            else:
                tag = "⚪ CENTER"

            print(f"[{tag}] {article['source']}")
            print(f"  → {article['title']}")
            print()


# ── 5. RUN IT ─────────────────────────────────────────────────────
# This only runs when you execute this file directly

if __name__ == "__main__":
    articles = fetch_all_news()
    display_articles(articles)
    print(f"\n✅ fetch_news.py working. {len(articles)} articles ready for Teesra.\n")