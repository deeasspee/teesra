# story_of_week.py
# Generates and stores the Story of the Week
# Runs every Sunday via run_daily.py

import os
import json
import re
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_today():
    return datetime.now(IST).date()


def generate_story_of_week():
    """
    Fetch all articles from last 7 days,
    use Claude to pick and summarise the
    most significant story of the week.
    """
    print("\n📰 GENERATING STORY OF THE WEEK")
    print("=" * 50)

    from database import get_client

    today = get_ist_today()
    week_start = today - timedelta(days=6)

    try:
        client = get_client()
        result = client.table('article')\
            .select('headline, facts, impact, '
                    'story_type, source, fetched_date')\
            .gte('fetched_date', str(week_start))\
            .lte('fetched_date', str(today))\
            .execute()
        articles = result.data or []
    except Exception as e:
        print(f"❌ Failed to fetch articles: {e}")
        return None

    if not articles:
        print("❌ No articles found for this week")
        return None

    print(f"  ✅ Found {len(articles)} articles from "
          f"{week_start} to {today}")

    # Build article list for Claude
    article_list = "\n".join([
        f"- [{a['fetched_date']}] {a['headline']} "
        f"(Type: {a['story_type']}, "
        f"Source: {a['source']})\n"
        f"  Facts: {a.get('facts','')[:200]}"
        for a in articles
    ])

    prompt = f"""You are an editor reviewing this week's Indian news coverage from {week_start} to {today}.

Here are all the stories covered this week:

{article_list}

Select the single most significant story of the week — the one with the most impact on India, the most public interest, or the most lasting consequence.

Return ONLY this JSON, no markdown:
{{
  "headline": "A clear, direct headline for the story of the week",
  "summary": "3-4 sentences explaining what happened this week on this story, written for a young Indian reader. Direct voice, no meta-language.",
  "why_it_matters": "2-3 sentences on why this story matters for India's future or present.",
  "story_type": "political/economy/tech/sports/general/security",
  "source": "Primary source name"
}}"""

    try:
        anthropic_client = Anthropic()
        response = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system="Return only valid JSON. No markdown. No explanation.",
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        data = json.loads(raw)
        data['week_start'] = str(week_start)
        data['week_end'] = str(today)

        print(f"  ✅ Story selected: {data['headline']}")
        return data

    except Exception as e:
        print(f"❌ Claude generation failed: {e}")
        return None


def save_story_of_week(story: dict) -> bool:
    """Save story of week to Supabase"""
    try:
        from database import get_client
        client = get_client()

        # Check if this week already has an entry
        existing = client.table('story_of_week')\
            .select('id')\
            .eq('week_start', story['week_start'])\
            .execute()

        if existing.data:
            # Update existing
            client.table('story_of_week')\
                .update({
                    'headline':       story['headline'],
                    'summary':        story['summary'],
                    'why_it_matters': story['why_it_matters'],
                    'story_type':     story.get('story_type', 'general'),
                    'source':         story.get('source', '')
                })\
                .eq('week_start', story['week_start'])\
                .execute()
            print("  ✅ Updated existing story of week")
        else:
            # Insert new
            client.table('story_of_week').insert({
                'week_start':     story['week_start'],
                'week_end':       story['week_end'],
                'headline':       story['headline'],
                'summary':        story['summary'],
                'why_it_matters': story['why_it_matters'],
                'story_type':     story.get('story_type', 'general'),
                'source':         story.get('source', '')
            }).execute()
            print("  ✅ Saved new story of week")

        return True
    except Exception as e:
        print(f"❌ Save failed: {e}")
        return False


def get_latest_story_of_week() -> dict:
    """Fetch most recent story of week from Supabase"""
    try:
        from database import get_client
        client = get_client()
        result = client.table('story_of_week')\
            .select('*')\
            .order('week_start', desc=True)\
            .limit(1)\
            .execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"❌ Failed to fetch story of week: {e}")
        return None


if __name__ == "__main__":
    story = generate_story_of_week()
    if story:
        save_story_of_week(story)
        print(f"\n✅ Story of the Week saved!")
        print(f"   {story['headline']}")
    else:
        print("❌ Failed to generate story of week")
