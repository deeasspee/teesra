# analyze_article.py
# Teesra — Day 6
# This is the AI brain. Takes a real article, returns Teesra format.

import anthropic
import json
import os
from dotenv import load_dotenv
from fetch_news import fetch_all_news
from database import save_article

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ── 1. THE STORY TYPE DETECTOR ────────────────────────────────────
# Decides what kind of story this is
# This directly implements our product philosophy

def detect_story_type(title, summary):

    title_lower = title.lower()

    # Sports keywords
    sports_keywords = [
        "cricket", "ipl", "match", "test", "odi", "t20",
        "fifa", "football", "hockey", "olympic", "tournament",
        "player", "team", "score", "wicket", "goal", "trophy"
    ]

    # Sensitive keywords — extra caution needed
    sensitive_keywords = [
        "riot", "communal", "mob", "lynching", "caste",
        "religious", "temple", "mosque", "church", "minority"
    ]

    # Political keywords
    political_keywords = [
        "parliament", "minister", "government", "party", "election",
        "bjp", "congress", "modi", "rahul", "opposition", "policy",
        "law", "bill", "vote", "constitution", "court", "judge"
    ]

    # Check story type in order of priority
    for word in sensitive_keywords:
        if word in title_lower:
            return "sensitive"

    for word in sports_keywords:
        if word in title_lower:
            return "sports"

    for word in political_keywords:
        if word in title_lower:
            return "political"

    return "general"


# ── 2. THE PROMPT BUILDER ─────────────────────────────────────────
# Builds different prompts based on story type
# This is our product philosophy translated into AI instructions

def build_prompt(article, story_type):

    base_context = f"""
You are the AI engine behind Teesra — an Indian news platform for young Indians aged 18-30.
Your job is to analyze news articles and return structured JSON only. No extra text.

Article title: {article['title']}
Article summary: {article['summary']}
Source: {article['source']}
Source bias: {article['bias']}

CRITICAL RULES:
- Write in simple, clear English. No jargon.
- Facts must be verifiable — no opinions in the facts section
- Keep each section to 2-3 sentences maximum
- Return ONLY raw JSON — no markdown, no ```json fences, no extra text before or after

HEADLINE RULES:
- Must be a clean, grammatical English sentence
- No unnecessary words like "in 2025" or "says report"
- Read like a newspaper headline, not a search query
- Maximum 12 words

IMPACT RULES:
- One sentence maximum
- Think "what changed in the real world because of this"
- Write like a smart friend texting you — casual, direct, no drama
- Good example: "Home loans could get slightly cheaper in the next few weeks"
- Bad example: "This will have significant implications for the Indian economy"
- Never start with "This", "The", or a person's name
"""

    if story_type == "sports":
        return base_context + """
Since this is a SPORTS story, political framing is less relevant.
Focus heavily on public sentiment and fan reaction.

Return this exact JSON:
{
  "story_type": "sports",
  "headline": "rewritten headline in plain english, max 12 words",
  "facts": "what exactly happened, just the facts",
  "impact": "what this means for the sport or the moment — keep it like fan conversation",
  "public_pulse": "how fans and general public are likely reacting to this",
  "left_lens": "brief left-media angle if relevant, else write: Not applicable for this story",
  "right_lens": "brief right-media angle if relevant, else write: Not applicable for this story"
}"""

    elif story_type == "sensitive":
        return base_context + """
This is a SENSITIVE story. Handle with extreme care.
Do NOT inflame. Present only verified facts. No speculation.

Return this exact JSON:
{
  "story_type": "sensitive",
  "headline": "neutral, careful rewrite of headline, max 12 words",
  "facts": "only what is confirmed and verified, nothing speculative",
  "impact": "factual impact on citizens, no emotional language",
  "public_pulse": "general public concern around this topic",
  "left_lens": "left media framing with label: [LEFT VIEW]",
  "right_lens": "right media framing with label: [RIGHT VIEW]",
  "caution_note": "one line reminding reader to verify before sharing"
}"""

    elif story_type == "political":
        return base_context + """
This is a POLITICAL story. Left and right lenses are most important here.
Show how different sides frame this clearly and fairly.

Return this exact JSON:
{
  "story_type": "political",
  "headline": "neutral rewrite of headline, max 12 words",
  "facts": "what happened, stripped of all political framing",
  "impact": "what this actually changes in daily life — jobs, prices, rights, opportunities",
  "left_lens": "how left-leaning outlets frame this — their angle and concern",
  "right_lens": "how right-leaning outlets frame this — their angle and concern",
  "public_pulse": "what general public and social media sentiment looks like"
}"""

    else:  # general
        return base_context + """
This is a GENERAL news story. Balance all three perspectives equally.

Return this exact JSON:
{
  "story_type": "general",
  "headline": "plain english rewrite of headline, max 12 words",
  "facts": "what happened, clear and simple",
  "impact": "real world consequence of this — keep it conversational, no preaching",
  "left_lens": "left media framing of this story",
  "right_lens": "right media framing of this story",
  "public_pulse": "general public reaction and sentiment"
}"""


# ── 3. THE ANALYZER ───────────────────────────────────────────────
# Sends article to Claude and gets Teesra analysis back

def analyze_article(article):

    story_type = detect_story_type(article["title"], article["summary"])
    prompt = build_prompt(article, story_type)

    print(f"\n  🤖 Sending to Claude [{story_type.upper()} story]...")

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",  # cheap + fast for testing
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        raw_response = message.content[0].text

        # Parse JSON response
        # Parse JSON response — strip markdown fences if Claude adds them
        clean_response = raw_response.strip()
        if clean_response.startswith("```"):
            clean_response = clean_response.split("```")[1]
            if clean_response.startswith("json"):
                clean_response = clean_response[4:]
        analysis = json.loads(clean_response.strip())
        analysis["original_title"] = article["title"]
        analysis["source"] = article["source"]
        analysis["source_bias"] = article["bias"]
        analysis["url"] = article["url"]

        return analysis

    except json.JSONDecodeError:
        print(f"  ⚠️  Claude returned non-JSON. Raw response:")
        print(raw_response)
        return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


# ── 4. THE DISPLAY ────────────────────────────────────────────────
# Prints analysis in clean readable format

def display_analysis(analysis):
    if not analysis:
        return

    type_emoji = {
        "political": "🏛️  POLITICAL",
        "sports":    "🏏 SPORTS",
        "sensitive": "⚠️  SENSITIVE",
        "general":   "📰 GENERAL"
    }

    # Extract only the fields we need — no repetition possible
    story_type = analysis.get("story_type", "general")
    headline = analysis.get("headline", "No headline")
    source = analysis.get("source", "")
    source_bias = analysis.get("source_bias", "")
    facts = analysis.get("facts", "")
    impact = analysis.get("impact", "")
    left_lens = analysis.get("left_lens", "")
    right_lens = analysis.get("right_lens", "")
    public_pulse = analysis.get("public_pulse", "")
    caution_note = analysis.get("caution_note", "")
    url = analysis.get("url", "")

    print("\n" + "═" * 60)
    print(f"  {type_emoji.get(story_type, '📰 GENERAL')}")
    print("═" * 60)
    print(f"\n  📌 {headline}")
    print(f"  Source: {source} [{source_bias}]")
    print(f"\n  ⚖️  FACTS")
    print(f"  {facts}")
    print(f"\n  💥 IMPACT")
    print(f"  {impact}")
    print(f"\n  🔵 LEFT LENS")
    print(f"  {left_lens}")
    print(f"\n  🔴 RIGHT LENS")
    print(f"  {right_lens}")
    print(f"\n  💬 PUBLIC PULSE")
    print(f"  {public_pulse}")

    if caution_note:
        print(f"\n  ⚠️  CAUTION")
        print(f"  {caution_note}")

    print(f"\n  🔗 {url}")
    print("═" * 60)


# ── 5. RUN IT ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n🗞️  Teesra AI Brain — Starting up...\n")

    print("📡 Fetching live articles...")
    all_articles = fetch_all_news()

    test_articles = [
        all_articles[0],
        all_articles[25],
        all_articles[40],
    ]

    print(f"\n🧠 Analyzing 3 articles with Claude...\n")

    results = []

    for i, article in enumerate(test_articles):
        print(f"─── Article {i+1} of 3 ───")
        print(f"  Original: {article['title']}")

        analysis = analyze_article(article)

        if analysis:
            display_analysis(analysis)
            results.append(analysis)
            save_article(analysis)  # save to Supabase

        print("\n")

    # Save results to JSON file for the UI to read
    with open("analyzed_articles.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved {len(results)} analyzed articles to analyzed_articles.json")
    print("✅ Day 6 complete. Teesra AI brain is working.\n")