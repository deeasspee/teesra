# database.py
# Teesra — Supabase connection layer
# All database operations live here

import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import date, timedelta

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
            "fetched_date":   str(date.today())
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
        yesterday = str(date.today() - timedelta(days=1))
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


# ── CLEAR TODAY'S ARTICLES ────────────────────────────────────────
def clear_todays_articles():
    """Delete articles older than 5 days; keeps a rolling 5-day window"""
    cutoff = str(date.today() - timedelta(days=5))
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
            .eq("fetched_date", str(date.today()))
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
        cutoff = str(date.today() - timedelta(days=days))
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
            .eq("fetched_date", str(date.today()))
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