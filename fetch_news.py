# fetch_news.py
# Teesra — Day 5
# This file fetches real headlines from Indian news sources

import feedparser
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
    }
]


# ── 2. THE FETCHER FUNCTION ───────────────────────────────────────
# A function that takes one source and returns its articles
# This uses everything you learned — functions, loops, dictionaries

def fetch_from_source(source):
    articles = []  # empty list to collect articles

    try:
        feed = feedparser.parse(source["url"])

        # Loop through first 5 articles from this source
        for entry in feed.entries[:5]:

            article = {
                "title":     entry.get("title", "No title"),
                "summary":   entry.get("summary", "No summary"),
                "url":       entry.get("link", ""),
                "source":    source["name"],
                "bias":      source["bias"],
                "fetched_at": str(datetime.now())
            }

            articles.append(article)

    except Exception as e:
        print(f"  ⚠️  Could not fetch {source['name']}: {e}")

    return articles


# ── 3. THE MAIN FUNCTION ──────────────────────────────────────────
# This loops through ALL sources and collects everything

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