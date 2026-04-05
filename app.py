# app.py
# Teesra local server
from database import get_todays_articles, save_subscriber
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from send_welcome import send_welcome_email
from market_data import fetch_market_data
from anthropic import Anthropic
import json
import os
import urllib.request
import urllib.parse
import re
import time

app = Flask(__name__)
CORS(app)

FEED_API_KEY    = os.getenv("FEED_API_KEY")
CRICAPI_KEY     = os.getenv("CRICAPI_KEY")
anthropic_client = Anthropic()

# Simple in-memory cache for cricket data
_cricket_cache = {"data": None, "ts": 0}
IPL_CACHE_SECS = 1800  # 30 minutes

# ── API KEY CHECK ─────────────────────────────────────────────────
def is_authorised() -> bool:
    referer = request.headers.get('Referer', '')
    origin  = request.headers.get('Origin', '')
    trusted = ['teesra.in', 'teesra.vercel.app', 'localhost', '127.0.0.1']
    if any(t in referer or t in origin for t in trusted):
        return True
    if FEED_API_KEY:
        provided = request.headers.get('X-API-Key') or request.args.get('api_key', '')
        return provided == FEED_API_KEY
    return True

# ── SERVE FRONTEND ────────────────────────────────────────────────
@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/feed")
def feed():
    return send_from_directory(".", "feed.html")

@app.route("/about")
def about():
    return send_from_directory(".", "about.html")

@app.route("/upi-qr.png")
def upi_qr():
    return send_from_directory(".", "upi-qr.png")

# ── MARKET DATA ───────────────────────────────────────────────────
@app.route("/api/market")
def get_market():
    if not is_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = fetch_market_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── GOOGLE TRENDS ─────────────────────────────────────────────────
@app.route("/api/trends")
def get_trends():
    """Fetch Google India trending searches server-side (no CORS issues)"""
    try:
        url = "https://trends.google.com/trending/rss?geo=IN"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=8) as response:
            xml = response.read().decode('utf-8')

        # Try CDATA titles first, then plain titles (skip channel title)
        titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', xml)
        if not titles:
            all_titles = re.findall(r'<title>(.*?)</title>', xml)
            titles = [t for t in all_titles[1:] if t and 'trends.google.com' not in t and t != 'Daily Search Trends']

        trends = [
            {
                "title": t.strip(),
                "link": f"https://www.google.com/search?q={urllib.parse.quote(t.strip())}&gl=in",
                "rank": i + 1
            }
            for i, t in enumerate(titles[:15]) if t.strip()
        ]
        return jsonify({"trends": trends})
    except Exception as e:
        return jsonify({"trends": [], "error": str(e)})

# ── SERVE ANALYZED ARTICLES ───────────────────────────────────────
@app.route("/api/articles")
def get_articles():
    if not is_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        articles = get_todays_articles()
        if not articles:
            try:
                with open("analyzed_articles.json", "r", encoding="utf-8") as f:
                    articles = json.load(f)
            except FileNotFoundError:
                articles = []
        return jsonify({"articles": articles, "count": len(articles)})
    except Exception as e:
        return jsonify({"articles": [], "count": 0, "error": str(e)})

# ── CRICKET DATA ──────────────────────────────────────────────────
@app.route("/api/cricket")
def get_cricket():
    global _cricket_cache
    if not CRICAPI_KEY:
        return jsonify({"error": "No CRICAPI_KEY"}), 500
    if _cricket_cache["data"] and (time.time() - _cricket_cache["ts"]) < IPL_CACHE_SECS:
        return jsonify(_cricket_cache["data"])
    try:
        base = f"https://api.cricapi.com/v1"
        def fetch(endpoint):
            url = f"{base}/{endpoint}&apikey={CRICAPI_KEY}"
            req = urllib.request.Request(url, headers={"User-Agent": "Teesra/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode())

        matches_data = fetch("currentMatches?offset=0")
        all_matches = matches_data.get("data", [])

        # IPL filter
        ipl_teams = ["Mumbai Indians","Chennai Super Kings","Royal Challengers","Kolkata Knight Riders",
                     "Delhi Capitals","Punjab Kings","Rajasthan Royals","Sunrisers Hyderabad",
                     "Gujarat Titans","Lucknow Super Giants"]
        ipl_keywords = ["indian premier league","ipl 2026","ipl"]

        def is_ipl(m):
            name = m.get("name","").lower()
            teams = m.get("teams", [])
            return (any(k in name for k in ipl_keywords) or
                    sum(1 for t in teams if any(it in t for it in ipl_teams)) >= 2)

        ipl_matches = [m for m in all_matches if is_ipl(m)]
        other_matches = [m for m in all_matches if not is_ipl(m)]

        # For all cricket: show live first, then recent completed, then upcoming — max 8
        def classify(m):
            started = m.get("matchStarted", False)
            ended   = m.get("matchEnded", False)
            if started and not ended: return "live"
            if ended: return "completed"
            return "upcoming"

        for m in all_matches:
            m["_status"] = classify(m)

        live_matches      = [m for m in other_matches if m["_status"] == "live"]
        completed_matches = [m for m in other_matches if m["_status"] == "completed"]
        upcoming_matches  = [m for m in other_matches if m["_status"] == "upcoming"]

        cricket_feed = (live_matches + list(reversed(completed_matches[-4:])) + upcoming_matches[:2])[:8]

        # IPL
        ipl_live     = next((m for m in ipl_matches if m["_status"] == "live"), None)
        ipl_recent   = next((m for m in reversed(ipl_matches) if m["_status"] == "completed"), None)
        ipl_upcoming = next((m for m in ipl_matches if m["_status"] == "upcoming"), None)

        result = {
            "cricket_feed": cricket_feed,
            "ipl_live":     ipl_live,
            "ipl_recent":   ipl_recent,
            "ipl_upcoming": ipl_upcoming,
            "has_ipl":      len(ipl_matches) > 0
        }
        _cricket_cache = {"data": result, "ts": time.time()}
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "cricket_feed": [], "has_ipl": False}), 500

# ── CRICSCORE — live scores with logos and abbr ───────────────────
_cricscore_cache = {"data": None, "ts": 0}
CRICSCORE_CACHE_SECS = 300  # 5 minutes

def convert_gmt_to_ist(status_str):
    """Convert GMT time mentions to IST (+5:30) in status strings"""
    from datetime import datetime, timedelta
    def replace_time(match):
        try:
            t = datetime.strptime(match.group(1), "%H:%M")
            ist = t + timedelta(hours=5, minutes=30)
            return f"{ist.strftime('%H:%M')} IST"
        except:
            return match.group(0)
    return re.sub(r'(\d{2}:\d{2})\s*GMT', replace_time, status_str or "")

@app.route("/api/cricscore")
def get_cricscore():
    global _cricscore_cache
    if not CRICAPI_KEY:
        return jsonify({"error": "No CRICAPI_KEY"}), 500
    if _cricscore_cache["data"] and (time.time() - _cricscore_cache["ts"]) < CRICSCORE_CACHE_SECS:
        return jsonify(_cricscore_cache["data"])
    try:
        from datetime import date, timedelta
        today     = date.today()
        yesterday = today - timedelta(days=1)
        tomorrow  = today + timedelta(days=1)

        url = f"https://api.cricapi.com/v1/cricScore?apikey={CRICAPI_KEY}"
        req = urllib.request.Request(url, headers={"User-Agent": "Teesra/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = json.loads(r.read().decode())

        all_matches = raw.get("data", [])

        def parse_team(name):
            m = re.search(r'\[(\w+)\]', name or "")
            abbr     = m.group(1) if m else (name or "")[:4].upper()
            fullname = re.sub(r'\s*\[.*?\]', '', name or "").strip()
            return abbr, fullname

        def classify(m):
            started = m.get("matchStarted", False)
            ended   = m.get("matchEnded",   False)
            if started and not ended:
                return "live"
            if ended:
                return "completed"
            return "upcoming"

        def get_date_variants(d):
            day   = d.day
            month = d.strftime('%b')
            return [f"{month} {day}", f"{month} {day:02d}", f"{day} {month}"]

        allowed_dates = []
        for d in [yesterday, today, tomorrow]:
            allowed_dates.extend(get_date_variants(d))

        def is_relevant(m):
            status  = (m.get("status", "") or "")
            started = m.get("matchStarted", False)
            ended   = m.get("matchEnded",   False)
            if started and not ended:
                return True  # always include live
            for date_str in allowed_dates:
                if date_str in status:
                    return True
            return False

        results = []
        for m in all_matches:
            if not is_relevant(m):
                continue
            status_str = convert_gmt_to_ist(m.get("status", "") or "")
            t_status   = classify(m)

            t1abbr, t1name = parse_team(m.get("t1", ""))
            t2abbr, t2name = parse_team(m.get("t2", ""))

            results.append({
                "name":      m.get("name", ""),
                "t1":        t1name,
                "t2":        t2name,
                "t1abbr":    t1abbr,
                "t2abbr":    t2abbr,
                "t1img":     m.get("t1img", ""),
                "t2img":     m.get("t2img", ""),
                "t1s":       m.get("t1s", ""),
                "t2s":       m.get("t2s", ""),
                "status":    status_str,
                "live":      t_status == "live",
                "completed": t_status == "completed",
                "upcoming":  t_status == "upcoming",
            })

        # Sort: live first, completed newest→oldest, upcoming soonest→farthest
        live_r      = [m for m in results if m["live"]]
        completed_r = list(reversed([m for m in results if m["completed"]]))
        upcoming_r  = [m for m in results if m["upcoming"]]
        results     = (upcoming_r + completed_r + live_r)[:20]
        print(f"Cricket API returned {len(all_matches)} matches, filtered to {len(results)}")
        for m in results[:3]:
            print(f"  - {m.get('t1','')} vs {m.get('t2','')} | status: {m.get('status','')[:50]}")

        out = {"matches": results, "count": len(results)}
        _cricscore_cache = {"data": out, "ts": time.time()}
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": str(e), "matches": [], "count": 0}), 500

# ── CHAT HELPER ───────────────────────────────────────────────────
def format_articles_for_prompt(articles):
    if not articles:
        return "No articles available today yet."
    lines = []
    for a in articles:
        lines.append("---")
        lines.append(f"[{a.get('story_type','general').upper()}] {a.get('headline','')}")
        lines.append(f"Source: {a.get('source','')}")
        lines.append(f"Facts: {a.get('facts','')}")
        lines.append(f"Left lens: {a.get('left_lens','')}")
        lines.append(f"Right lens: {a.get('right_lens','')}")
        lines.append(f"Street pulse: {a.get('public_pulse','')}")
        lines.append("---")
    return "\n".join(lines)

# ── CHAT ──────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    data    = request.get_json()
    message = data.get("message", "").strip()
    history = data.get("history", [])

    if not message:
        return jsonify({"reply": "Please send a message.", "history": history}), 400

    try:
        articles      = get_todays_articles()
        articles_text = format_articles_for_prompt(articles)

        system_prompt = f"""You are Teesra Assistant — a smart, friendly news companion built into Teesra, India's bias-aware news digest for young Indians aged 18–30.

You have access to today's curated articles below. Use them as your primary context when answering questions about today's news. You also have web search capability for anything beyond today's articles.

Keep responses concise and conversational. Use plain English. No jargon. When referencing an article, briefly mention the headline. If asked for a summary, give a punchy 3–5 bullet rundown of today's top stories.

TODAY'S TEESRA ARTICLES:
{articles_text}"""

        messages = history + [{"role": "user", "content": message}]

        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=system_prompt,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages,
        )

        full_text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )

        updated_history = history + [
            {"role": "user",      "content": message},
            {"role": "assistant", "content": full_text},
        ]
        return jsonify({"reply": full_text, "history": updated_history})

    except Exception as e:
        print(f"❌ Chat error: {e}")
        return jsonify({"reply": "Sorry, something went wrong. Try again.", "history": history})

# ── EMAIL SUBSCRIPTION ────────────────────────────────────────────
@app.route("/subscribe", methods=["POST"])
def subscribe():
    data = request.get_json()
    email = data.get("email", "").strip()

    if not email or "@" not in email:
        return jsonify({"error": "Invalid email"}), 400

    saved = save_subscriber(email)

    if not saved:
        return jsonify({"message": "already_subscribed"}), 200

    send_welcome_email(email)
    print(f"📧 New subscriber saved to Supabase: {email}")
    return jsonify({"message": "subscribed"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    print(f"🚀 Teesra backend starting on port {port}")
    app.run(debug=debug, port=port, host="0.0.0.0")