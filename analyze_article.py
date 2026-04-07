# analyze_article.py
# Teesra — Day 6
# This is the AI brain. Takes a real article, returns Teesra format.

import anthropic
import json
import os
from dotenv import load_dotenv
from fetch_news import fetch_all_news
#from database import save_article
from database import save_article, clear_todays_articles

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ── 1. THE STORY TYPE DETECTOR ────────────────────────────────────
# Decides what kind of story this is
# This directly implements our product philosophy

def detect_story_type(title, summary, source=""):

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
     # Tech keywords
    tech_keywords = [
        "ai", "artificial intelligence", "chatgpt", "openai", "google",
        "apple", "microsoft", "startup", "smartphone", "cybersecurity",
        "robot", "machine learning", "chip", "semiconductor", "app",
        "software", "tech", "elon", "meta", "samsung", "iphone"
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
    
    for word in tech_keywords:
        if word in title_lower:
            return "tech"

    # International keywords
    international_sources = ['Reuters World', 'Al Jazeera']
    if source in ['BBC World', 'Reuters']:
        return "international"

    
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
- Facts must be ONLY from the article provided — never add outside knowledge
- If the article doesn't mention a stadium, score, or detail — do NOT invent it
- Do not use your training knowledge to fill gaps — only use what is in the article text
- Keep each section to 2-3 sentences maximum
- Return ONLY raw JSON — no markdown, no ```json fences, no extra text before or after

ACCURACY RULES:
- Never state specific venues, scores, or names unless explicitly mentioned in the article
- If you are unsure of a fact, omit it rather than guess
- Facts section must read like a wire report — dry, sourced, no color

WRITING STYLE RULES:
- Write facts in direct journalistic voice. Never say "The article states", "The article mentions", "The article examines", "According to the article", or any meta-reference to the source material. State facts directly: "X happened" not "The article says X happened".
- Write all sections in direct active voice: not "The article says X happened" but "X happened."
- Never reference "the article", "the piece", or "the source" in any section.
- If the article does not contain enough information for 3 or more factual sentences, return exactly: INSUFFICIENT_CONTENT

STREET PULSE RULES:
- NEVER use the words "mixed", "divided", "varied", "split" or "reactions"
- NEVER start with "People" or "The public"
- Every story has nuance — find the specific angle, debate or emotion
- Name a specific group, community, profession or fanbase who cares about this
- Focus on ONE dominant sentiment or ONE interesting tension
- Good examples:
  "Farmers in Punjab are cautiously optimistic, while urban economists worry this changes little on the ground"
  "Cricket Twitter is going berserk — this chase will be debated for years"
  "Students and young job seekers are the most anxious about this — LinkedIn is flooded with worried posts"
  "Startup founders are celebrating this policy shift, but legacy businesses see it as a threat"
- Bad examples:
  "Mixed reactions from the public"
  "People have divided opinions on this issue"
  "There are varied sentiments across different groups"

HEADLINE RULES:
- Must be a clean, grammatical English sentence
- No unnecessary words like "in 2025" or "says report"
- Read like a newspaper headline, not a search query
- Maximum 12 words

LEFT/RIGHT LENS RULES:
- Write IN the voice of that perspective — not about it
- NEVER say "left outlets may report" or "conservative media could frame"
- Instead write AS IF you are that outlet — first person plural is fine
- Good: "The government's freebies signal a return to populist politics that deepens fiscal stress"
- Bad: "Left outlets may highlight the fiscal burden of these promises"
- Each lens is 4 sentences maximum, confident and direct

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
Since this is a SPORTS story, political framing is NOT relevant.
STRICT RULE: Only use facts explicitly stated in the article above.
Do NOT add stadium names, scores, or player details from your training knowledge.
If the article is a match preview, say so — do not invent match results.

Return this exact JSON:
{
  "story_type": "sports",
  "headline": "rewritten headline in plain english, max 12 words",
  "facts": "only what the article explicitly states — no invented details. 3-4 sentences.",
  "impact": "what this means for the tournament or fans — one conversational sentence",
  "public_pulse": "specific fan reactions — name groups, emotions, debates. No generic language."
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

    elif story_type == "international":
        return base_context + """
This is an INTERNATIONAL story. Focus on how it affects India or the broader world.

STRICT RULE: Only use facts from the article. No invented details.

Return this exact JSON:
{
  "story_type": "international",
  "headline": "neutral rewrite of headline, max 12 words",
  "facts": "what happened, where, who is involved — dry wire-report style, 2-3 sentences",
  "impact": "how this affects India or Indians specifically — one direct sentence",
  "left_lens": "how progressive outlets frame this globally",
  "right_lens": "how conservative outlets frame this globally",
  "public_pulse": "what Indians and global audiences are saying about this"
}"""

    else:  # general
        return base_context + """
This is a GENERAL news story. Balance all three perspectives equally.

IMPORTANT: left_lens and right_lens must NEVER be empty.
Every story has a left and right framing — find it even if subtle.
- Left lens tends to focus on: systemic issues, institutional failure, impact on vulnerable groups, need for regulation
- Right lens tends to focus on: individual responsibility, national security, economic growth, traditional values

Return this exact JSON:
{
  "story_type": "general",
  "headline": "plain english rewrite of headline, max 12 words",
  "facts": "what happened, clear and simple. 2-3 sentences only.",
  "impact": "real world consequence — conversational, one sentence, no preaching",
  "left_lens": "how a left-leaning outlet would frame this — must not be empty",
  "right_lens": "how a right-leaning outlet would frame this — must not be empty",
  "public_pulse": "specific reaction from a named group — no mixed reactions language"
}"""


# ── 3. THE ANALYZER ───────────────────────────────────────────────
# Sends article to Claude and gets Teesra analysis back

def analyze_article(article):

    story_type = detect_story_type(article["title"], article["summary"], article.get("source", ""))
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

        # Reject weak Claude outputs
        weak_phrases = [
            "the article mentions", "the article states", "the article examines",
            "according to the article", "insufficient_content",
            "cannot process", "unable to", "does not provide",
            "no substantive content", "social media prompt"
        ]
        facts_text = analysis.get("facts", "").lower()
        if any(p in facts_text for p in weak_phrases):
            print(f"  ⚠️  Rejected weak analysis (facts field flagged)")
            return None

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
    from article_selector import select_top_stories

    print("\n🗞️  Teesra AI Brain — Starting up...\n")

    # Step 1 — Fetch
    print("📡 Fetching live articles...")
    all_articles = fetch_all_news()

    # Clear today's old runs before saving fresh ones
    clear_todays_articles()

    # Step 2 — Smart selection
    top_articles = select_top_stories(all_articles, n=20)

    print(f"\n🧠 Analyzing {len(top_articles)} articles with Claude...\n")

    results = []
    failed = 0

    for i, article in enumerate(top_articles):
        print(f"─── Article {i+1} of {len(top_articles)} ───")
        print(f"  Original: {article['title'][:70]}...")
        print(f"  Covered by {article.get('source_count', 1)} sources")

        analysis = analyze_article(article)

        if analysis:
            display_analysis(analysis)
            save_article(analysis)
            results.append(analysis)
        else:
            failed += 1
            print(f"  ⚠️ Skipped")

        print()

    # Save backup JSON
    with open("analyzed_articles.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("─" * 50)
    print(f"✅ Done. {len(results)} articles analyzed, {failed} failed")
    print(f"💾 Saved to Supabase + analyzed_articles.json")
    print(f"🌐 Open http://localhost:5000/feed to see today's brief\n")