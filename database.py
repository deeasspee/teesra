# database.py
# Teesra — Supabase connection layer
# All database operations live here

import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import date, timedelta, datetime, timezone

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_today():
    """Always returns today's date in IST regardless of server timezone.
    GitHub Actions runs on UTC — this ensures articles are dated correctly
    for Indian users."""
    return datetime.now(IST).date()

load_dotenv()

# ── CONNECT ───────────────────────────────────────────────────────
def get_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise Exception("Missing SUPABASE_URL or SUPABASE_KEY in .env file")

    return create_client(url, key)


# ── SAVE ARTICLE ──────────────────────────────────────────────────
def save_article(analysis: dict) -> bool:
    try:
        client = get_client()

        row = {
            "headline":       analysis.get("headline", ""),
            "story_type":     analysis.get("story_type", "general"),
            "facts":          analysis.get("facts", ""),
            "impact":         analysis.get("impact", ""),
            "left_lens":      analysis.get("left_lens", ""),
            "right_lens":     analysis.get("right_lens", ""),
            "public_pulse":   analysis.get("public_pulse", ""),
            "caution_note":   analysis.get("caution_note", None),
            "source":         analysis.get("source", ""),
            "source_bias":    analysis.get("source_bias", ""),
            "original_title": analysis.get("original_title", ""),
            "url":            analysis.get("url", ""),
            "score":          analysis.get("score", 0),
            "fetched_date":   str(get_ist_today())
        }

        client.table("article").insert(row).execute()
        print(f"  💾 Saved to Supabase: {analysis.get('headline', '')[:50]}...")
        return True

    except Exception as e:
        print(f"  ❌ Supabase save failed: {e}")
        return False

# ── GET YESTERDAY'S HEADLINES ─────────────────────────────────────
def get_yesterday_headlines() -> list:
    """Return headline strings from yesterday for cross-day dedup."""
    try:
        client = get_client()
        yesterday = str(get_ist_today() - timedelta(days=1))
        response = (
            client.table("article")
            .select("headline")
            .eq("fetched_date", yesterday)
            .execute()
        )
        return [row["headline"] for row in response.data if row.get("headline")]
    except Exception as e:
        print(f"❌ Failed to fetch yesterday's headlines: {e}")
        return []


# ── GET RECENT HEADLINES (MULTI-DAY DEDUP) ────────────────────────
def get_recent_headlines(days: int = 4) -> list:
    """Return headline + original_title strings from last N days (excludes today) for cross-day dedup."""
    try:
        client = get_client()
        cutoff = str(get_ist_today() - timedelta(days=days))
        today  = str(get_ist_today())
        response = (
            client.table("article")
            .select("headline, original_title, fetched_date")
            .gte("fetched_date", cutoff)
            .lt("fetched_date", today)
            .execute()
        )
        headlines = []
        for row in response.data:
            if row.get("headline"):
                headlines.append(row["headline"])
            if row.get("original_title"):
                headlines.append(row["original_title"])
        print(f"  📋 Loaded {len(headlines)} recent headlines for dedup (last {days} days)")
        return headlines
    except Exception as e:
        print(f"  ⚠️ Could not fetch recent headlines: {e}")
        return []


# ── GET ARTICLES BY DATE ──────────────────────────────────────────
def get_articles_by_date(target_date) -> list:
    """Return articles for a specific date (date object or ISO string)."""
    try:
        client = get_client()
        response = (
            client.table("article")
            .select("*")
            .eq("fetched_date", str(target_date))
            .order("id", desc=False)
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"❌ Failed to fetch articles for {target_date}: {e}")
        return []


# ── CLEAR TODAY'S ARTICLES ────────────────────────────────────────
def clear_todays_articles():
    """Delete articles older than 5 days; keeps a rolling 5-day window"""
    cutoff = str(get_ist_today() - timedelta(days=5))
    try:
        client = get_client()
        client.table("article").delete().lt("fetched_date", cutoff).execute()
        print(f"  🧹 Cleared articles older than {cutoff}")
    except Exception as e:
        print(f"  ⚠️ Could not clear old articles: {e}")
# ── GET TODAY'S ARTICLES ──────────────────────────────────────────
def get_todays_articles() -> list:
    try:
        client = get_client()

        response = (
            client.table("article")
            .select("*")
            .eq("fetched_date", str(get_ist_today()))
            .order("id", desc=False)
            .execute()
        )

        return response.data

    except Exception as e:
        print(f"❌ Failed to fetch articles: {e}")
        return []


# ── GET RECENT ARTICLES ───────────────────────────────────────────
def get_recent_articles(days=5) -> list:
    """Fetch articles from last N days, ordered by date descending"""
    try:
        client = get_client()
        cutoff = str(get_ist_today() - timedelta(days=days))
        response = (
            client.table("article")
            .select("*")
            .gte("fetched_date", cutoff)
            .order("fetched_date", desc=True)
            .order("id", desc=False)
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"❌ Failed to fetch recent articles: {e}")
        return []


# ── GET ARTICLES BY TYPE ──────────────────────────────────────────
def get_articles_by_type(story_type: str) -> list:
    try:
        client = get_client()

        response = (
            client.table("article")
            .select("*")
            .eq("story_type", story_type)
            .eq("fetched_date", str(get_ist_today()))
            .execute()
        )

        return response.data

    except Exception as e:
        print(f"❌ Failed to fetch {story_type} articles: {e}")
        return []

# ── SAVE SUBSCRIBER ───────────────────────────────────────────────
def save_subscriber(email: str) -> bool:
    try:
        client = get_client()
        client.table("subscribers").insert({
            "email": email,
            "is_active": True
        }).execute()
        print(f"  💾 Subscriber saved: {email}")
        return True
    except Exception as e:
        # Unique constraint means already subscribed
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            print(f"  ℹ️  Already subscribed: {email}")
            return False
        print(f"  ❌ Failed to save subscriber: {e}")
        return False


# ── UNSUBSCRIBE ───────────────────────────────────────────────────
def unsubscribe_email(email: str) -> bool:
    """Mark subscriber as inactive"""
    try:
        client = get_client()
        client.table("subscribers").update(
            {"is_active": False}
        ).eq("email", email).execute()
        print(f"  ✅ Unsubscribed: {email}")
        return True
    except Exception as e:
        print(f"  ❌ Failed to unsubscribe: {e}")
        return False


# ── GET ALL SUBSCRIBERS ───────────────────────────────────────────
def get_all_subscribers() -> list:
    try:
        client = get_client()
        response = (
            client.table("subscribers")
            .select("email")
            .eq("is_active", True)
            .execute()
        )
        return [row["email"] for row in response.data]
    except Exception as e:
        print(f"❌ Failed to fetch subscribers: {e}")
        return []

# ── TEST CONNECTION ───────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing Supabase connection...")

    try:
        client = get_client()
        response = client.table("article").select("id").limit(1).execute()
        print("✅ Supabase connected successfully!")

        all_rows = client.table("article").select("id", count="exact").execute()
        print(f"   Total articles stored: {all_rows.count}")

    except Exception as e:
        print(f"❌ Connection failed: {e}")