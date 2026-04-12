# app.py
# Teesra local server
from database import get_todays_articles, save_subscriber, get_recent_articles, unsubscribe_email, get_articles_by_date
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from send_welcome import send_welcome_email
from market_data import fetch_market_data, fetch_commodity_data
from anthropic import Anthropic
import json
import os
import urllib.request
import urllib.parse
import re
import time

app = Flask(__name__)
CORS(app)

# Gzip compression
try:
    from flask_compress import Compress
    Compress(app)
except ImportError:
    pass

FEED_API_KEY        = os.getenv("FEED_API_KEY")
CRICAPI_KEY         = os.getenv("CRICAPI_KEY")
FOOTBALL_API_KEY    = os.getenv("FOOTBALL_API_KEY")
SUPABASE_ANON_KEY   = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_URL        = os.getenv("SUPABASE_URL", "")
anthropic_client = Anthropic()

# ── BIAS SCORE ────────────────────────────────────────────────────
def compute_bias_score(article):
    """Returns float -1.0 (hard left) to +1.0 (hard right). 0.0 = center."""
    base_scores = {
        'left':         -0.6,
        'center-left':  -0.3,
        'center':        0.0,
        'center-right':  0.3,
        'right':         0.6,
        'unknown':       0.0,
    }
    score = base_scores.get(article.get('source_bias', 'center'), 0.0)
    if article.get('story_type') == 'political':
        score = score * 1.2
    return max(-1.0, min(1.0, round(score, 2)))

def get_bias_label(score):
    if score <= -0.5: return "Left-leaning coverage"
    if score <= -0.2: return "Center-left coverage"
    if score <  0.2:  return "Balanced coverage"
    if score <  0.5:  return "Center-right coverage"
    return "Right-leaning coverage"

def enrich_article(article):
    """Add bias_score and bias_label to an article dict."""
    a = dict(article)
    score = compute_bias_score(a)
    a['bias_score'] = score
    a['bias_label'] = get_bias_label(score)
    return a

# Simple in-memory cache for cricket data
_cricket_cache = {"data": None, "ts": 0}

# Crossword cache keyed by date string
_crossword_cache = {}
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

# ── PUBLIC CONFIG (anon key safe to expose) ───────────────────────
@app.route("/api/config")
def get_config():
    resp = jsonify({
        "supabase_url":      SUPABASE_URL,
        "supabase_anon_key": SUPABASE_ANON_KEY,
    })
    resp.headers['Cache-Control'] = 'public, max-age=3600'
    return resp


# ── AUTH SYNC (replaces trigger) ─────────────────────────────────
@app.route("/api/auth/sync", methods=["POST"])
def sync_auth_user():
    """
    Called by frontend after Google OAuth sign-in succeeds.
    Uses service_role key (via get_client) to bypass RLS entirely.
    Replaces the Supabase trigger which failed due to schema
    permission issues.
    """
    try:
        from database import get_client
        from datetime import datetime

        data       = request.json or {}
        email      = data.get('email', '').strip().lower()
        auth_uid   = data.get('auth_uid', '').strip()
        name       = data.get('name', '').strip()
        avatar_url = data.get('avatar_url', '').strip()

        if not email or not auth_uid:
            return jsonify({"error": "Missing email or auth_uid"}), 400

        # Admin check
        ADMIN_EMAIL = 'dsp.fiem@gmail.com'
        role = 'admin' if email == ADMIN_EMAIL else 'subscriber'

        client = get_client()
        client.table('subscribers').upsert(
            {
                'email':       email,
                'auth_uid':    auth_uid,
                'name':        name,
                'avatar_url':  avatar_url,
                'is_active':   True,
                'role':        role,
                'last_sign_in': datetime.now().isoformat(),
            },
            on_conflict='email'
        ).execute()

        print(f"  ✅ Auth sync: {email} ({role})")
        return jsonify({"success": True, "role": role})

    except Exception as e:
        print(f"  ❌ Auth sync error: {e}")
        return jsonify({"error": str(e)}), 500


# ── AUTH MIDDLEWARE ───────────────────────────────────────────────
def get_auth_user(req):
    """Extract and verify Supabase JWT from Authorization header."""
    auth_header = req.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ', 1)[1]
    try:
        from database import get_client
        client = get_client()
        response = client.auth.get_user(token)
        return response.user if response and response.user else None
    except Exception:
        return None


def require_admin(f):
    """Decorator — 401 if no valid JWT, 403 if not admin role."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_auth_user(request)
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        try:
            from database import get_client
            client = get_client()
            result = client.table('subscribers')\
                .select('role')\
                .eq('auth_uid', user.id)\
                .limit(1)\
                .execute()
            role = result.data[0].get('role') if result.data else None
            if role != 'admin':
                return jsonify({"error": "Forbidden"}), 403
        except Exception:
            return jsonify({"error": "Forbidden"}), 403
        return f(*args, **kwargs)
    return decorated


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

@app.route("/icon.svg")
def serve_icon():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
      <rect width="512" height="512" rx="80" fill="#0a120e"/>
      <text x="256" y="380" text-anchor="middle"
        font-size="360" font-family="Georgia,serif"
        font-weight="900" fill="#d4a820">T</text>
    </svg>'''
    from flask import Response
    return Response(svg, mimetype='image/svg+xml')

@app.route("/manifest.json")
def manifest():
    import json as _json
    data = {
        "name": "Teesra",
        "short_name": "Teesra",
        "description": "India's news from three perspectives",
        "start_url": "/feed",
        "display": "standalone",
        "background_color": "#0a120e",
        "theme_color": "#0a120e",
        "icons": [
            {"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}
        ]
    }
    from flask import Response
    return Response(_json.dumps(data), mimetype='application/manifest+json')

# ── MARKET DATA ───────────────────────────────────────────────────
@app.route("/api/market")
def get_market():
    if not is_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = fetch_market_data()
        try:
            c = fetch_commodity_data()
            if c:
                data.update(c)
        except Exception:
            pass
        resp = jsonify(data)
        resp.headers['Cache-Control'] = 'public, max-age=300'
        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── WEATHER ───────────────────────────────────────────────────────
@app.route("/api/weather")
def get_weather():
    lat = request.args.get("lat", "28.6139")
    lon = request.args.get("lon", "77.2090")
    try:
        url = (f"https://api.open-meteo.com/v1/forecast"
               f"?latitude={lat}&longitude={lon}"
               f"&current=temperature_2m,relative_humidity_2m,"
               f"wind_speed_10m,weather_code,apparent_temperature"
               f"&timezone=Asia%2FKolkata")
        req = urllib.request.Request(url, headers={"User-Agent": "Teesra/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read().decode())

        cur   = d["current"]
        temp  = round(cur["temperature_2m"])
        feels = round(cur["apparent_temperature"])
        humid = cur["relative_humidity_2m"]
        wind  = round(cur["wind_speed_10m"])
        code  = cur["weather_code"]

        def decode_wmo(c):
            if c == 0:  return "Clear Sky",     "01d"
            if c <= 2:  return "Partly Cloudy", "02d"
            if c == 3:  return "Overcast",      "03d"
            if c <= 49: return "Foggy",         "50d"
            if c <= 55: return "Drizzle",       "09d"
            if c <= 65: return "Rain",          "10d"
            if c <= 77: return "Snow",          "13d"
            if c <= 82: return "Rain Showers",  "09d"
            if c <= 99: return "Thunderstorm",  "11d"
            return "Cloudy", "03d"

        desc, icon = decode_wmo(code)
        import datetime as _dt
        hour = _dt.datetime.now().hour
        tod  = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"

        if temp >= 38:   phrase = f"Extreme heat — {temp}°C, stay hydrated 🥵"
        elif temp >= 32: phrase = f"Hot {tod}, stay cool 🌡️"
        elif temp <= 10: phrase = f"Cold {tod}, dress warm 🧥"
        elif code == 0:  phrase = f"Clear skies for your {tod} ☀️"
        elif code <= 2:  phrase = f"Partly cloudy {tod} 🌤️"
        elif code <= 49: phrase = f"Foggy conditions, drive carefully 🌫️"
        elif code <= 65: phrase = f"Carry an umbrella today 🌧️"
        elif code <= 77: phrase = f"Snow today, dress warm ❄️"
        elif code <= 99: phrase = f"Thunderstorms expected ⛈️"
        else:            phrase = f"Stay prepared for the {tod}"

        city = "Your Location"
        try:
            geo_url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
            geo_req = urllib.request.Request(geo_url, headers={"User-Agent": "Teesra/1.0"})
            with urllib.request.urlopen(geo_req, timeout=5) as gr:
                geo  = json.loads(gr.read().decode())
            addr = geo.get("address", {})
            city = addr.get("city") or addr.get("town") or addr.get("village") or "Your Location"
        except Exception:
            pass

        resp = jsonify({"city": city, "temp": temp, "feels": feels,
                        "humidity": humid, "desc": desc, "icon": icon,
                        "wind": wind, "phrase": phrase})
        resp.headers['Cache-Control'] = 'public, max-age=1800'
        return resp
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
        resp = jsonify({"trends": trends})
        resp.headers['Cache-Control'] = 'public, max-age=900'
        return resp
    except Exception as e:
        return jsonify({"trends": [], "error": str(e)})

# ── SERVE ANALYZED ARTICLES ───────────────────────────────────────
@app.route("/api/articles")
def get_articles():
    if not is_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from datetime import date, timedelta
        days_back = int(request.args.get('days', 1))
        days_back = max(1, min(days_back, 5))        # clamp 1-5
        target_date = date.today() - timedelta(days=days_back - 1)
        articles = get_articles_by_date(target_date)
        # Fallback to local JSON for today if DB is empty
        if not articles and days_back == 1:
            try:
                with open("analyzed_articles.json", "r", encoding="utf-8") as f:
                    articles = json.load(f)
            except FileNotFoundError:
                articles = []
        enriched = [enrich_article(a) for a in articles]
        resp = jsonify({"articles": enriched, "count": len(enriched)})
        resp.headers['Cache-Control'] = 'public, max-age=120'
        return resp
    except Exception as e:
        return jsonify({"articles": [], "count": 0, "error": str(e)})

# ── SINGLE STORY PERMALINK ────────────────────────────────────────
@app.route("/story/<int:story_id>")
def story_page(story_id):
    return send_from_directory(".", "story.html")

@app.route("/api/story/<int:story_id>")
def get_story(story_id):
    try:
        from database import get_client
        client = get_client()
        resp = client.table("article").select("*").eq("id", story_id).limit(1).execute()
        if not resp.data:
            return jsonify({"error": "not_found"}), 404
        return jsonify({"article": enrich_article(resp.data[0])})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

        MAJOR_NATIONS = {"australia", "england", "india", "south africa", "new zealand",
                         "west indies", "pakistan", "bangladesh", "sri lanka", "afghanistan"}
        PSL_KEYWORDS  = ["pakistan super league", "psl 2", "psl-", "psl,"]
        PSL_TEAMS     = {"karachi kings", "lahore qalandars", "peshawar zalmi",
                         "islamabad united", "quetta gladiators", "multan sultans"}
        IPL_TEAMS = {"mumbai indians", "chennai super kings", "royal challengers",
                     "kolkata knight riders", "delhi capitals", "punjab kings",
                     "rajasthan royals", "sunrisers hyderabad", "gujarat titans",
                     "lucknow super giants"}

        def is_wanted(m):
            name = (m.get("name", "") or "").lower()
            t1   = (m.get("t1",   "") or "").lower()
            t2   = (m.get("t2",   "") or "").lower()
            # Exclude women's cricket
            if "women" in name or "women" in t1 or "women" in t2:
                return False
            # IPL — check name OR team names
            if "ipl" in name or "indian premier league" in name:
                return True
            if any(t in t1 for t in IPL_TEAMS) or any(t in t2 for t in IPL_TEAMS):
                return True
            # PSL
            if any(k in name for k in PSL_KEYWORDS):
                return True
            if any(t in t1 for t in PSL_TEAMS) or any(t in t2 for t in PSL_TEAMS):
                return True
            # International men's: both teams are major nations
            t1_major = any(n in t1 for n in MAJOR_NATIONS)
            t2_major = any(n in t2 for n in MAJOR_NATIONS)
            return t1_major and t2_major

        results = []
        for m in all_matches:
            if not is_relevant(m):
                continue
            if not is_wanted(m):
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

        # Sort: live → completed (newest first) → upcoming (soonest first)
        live_r      = [m for m in results if m["live"]]
        completed_r = list(reversed([m for m in results if m["completed"]]))
        upcoming_r  = [m for m in results if m["upcoming"]]
        results     = (live_r + completed_r + upcoming_r)[:20]
        print(f"Cricket API returned {len(all_matches)} matches, filtered to {len(results)}")
        for m in results[:3]:
            print(f"  - {m.get('t1','')} vs {m.get('t2','')} | status: {m.get('status','')[:50]}")

        out = {"matches": results, "count": len(results)}
        _cricscore_cache = {"data": out, "ts": time.time()}
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": str(e), "matches": [], "count": 0}), 500

# ── FOOTBALL ─────────────────────────────────────────────────────
_football_cache = {"data": None, "ts": 0}
FOOTBALL_CACHE_SECS = 1800  # 30 minutes

@app.route("/api/football")
def get_football():
    global _football_cache
    if not FOOTBALL_API_KEY:
        return jsonify({"error": "No FOOTBALL_API_KEY", "matches": []}), 200
    if _football_cache["data"] and (time.time() - _football_cache["ts"]) < FOOTBALL_CACHE_SECS:
        return jsonify(_football_cache["data"])
    try:
        from datetime import date, timedelta
        today     = date.today()
        date_from = today.strftime("%Y-%m-%d")
        date_to   = (today + timedelta(days=3)).strftime("%Y-%m-%d")

        headers = {"X-Auth-Token": FOOTBALL_API_KEY}

        def fetch_football(url):
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode())

        # 2021=PL, 2001=UCL, 2014=La Liga, 2019=Serie A
        competitions = [2021, 2001, 2014, 2019]
        all_matches  = []

        for comp_id in competitions:
            try:
                url  = f"https://api.football-data.org/v4/competitions/{comp_id}/matches?dateFrom={date_from}&dateTo={date_to}&status=SCHEDULED,LIVE,IN_PLAY,PAUSED,FINISHED"
                data = fetch_football(url)
                for m in data.get("matches", []):
                    all_matches.append({
                        "id":               m.get("id"),
                        "competition":      m.get("competition", {}).get("name", ""),
                        "competition_code": m.get("competition", {}).get("code", ""),
                        "home":             m.get("homeTeam", {}).get("shortName") or m.get("homeTeam", {}).get("name", ""),
                        "away":             m.get("awayTeam", {}).get("shortName") or m.get("awayTeam", {}).get("name", ""),
                        "home_crest":       m.get("homeTeam", {}).get("crest", ""),
                        "away_crest":       m.get("awayTeam", {}).get("crest", ""),
                        "status":           m.get("status", ""),
                        "score_home":       m.get("score", {}).get("fullTime", {}).get("home"),
                        "score_away":       m.get("score", {}).get("fullTime", {}).get("away"),
                        "utc_date":         m.get("utcDate", ""),
                        "minute":           m.get("minute"),
                    })
            except Exception as comp_err:
                print(f"Football comp {comp_id} failed: {comp_err}")
                continue

        order = {"LIVE": 0, "IN_PLAY": 0, "PAUSED": 0, "SCHEDULED": 1, "TIMED": 1, "FINISHED": 2}
        all_matches.sort(key=lambda x: (order.get(x["status"], 3), x.get("utc_date", "")))
        all_matches = all_matches[:15]

        result = {"matches": all_matches, "count": len(all_matches)}
        _football_cache = {"data": result, "ts": time.time()}
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "matches": []}), 500

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


# ── UNSUBSCRIBE ───────────────────────────────────────────────────
@app.route("/unsubscribe")
def unsubscribe():
    email = request.args.get("email", "").strip()
    if not email or "@" not in email:
        return """
        <html><body style="font-family:sans-serif;max-width:480px;margin:80px auto;text-align:center;padding:20px;">
          <h2>Invalid unsubscribe link</h2>
          <p>This link appears to be invalid. Please contact brief@teesra.in</p>
        </body></html>
        """, 400

    success = unsubscribe_email(email)

    if success:
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8"/>
          <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
          <title>Unsubscribed — Teesra</title>
          <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@300;400&family=DM+Mono:wght@400&display=swap" rel="stylesheet">
          <style>
            body{{background:#0a120e;color:#e8f0e4;font-family:'DM Sans',sans-serif;
              display:flex;align-items:center;justify-content:center;
              min-height:100vh;margin:0;padding:20px;box-sizing:border-box;}}
            .card{{max-width:440px;text-align:center;}}
            .logo{{font-family:'Playfair Display',serif;font-size:32px;color:#d4a820;margin-bottom:32px;}}
            h1{{font-family:'Playfair Display',serif;font-size:28px;font-weight:700;margin-bottom:16px;}}
            p{{color:#90b094;line-height:1.7;margin-bottom:12px;}}
            .email{{font-family:'DM Mono',monospace;font-size:12px;color:#d4a820;margin:16px 0;}}
            .resubscribe{{display:inline-block;margin-top:24px;background:#d4a820;color:#0a120e;
              padding:12px 28px;text-decoration:none;font-weight:500;border-radius:4px;}}
            .home{{display:inline-block;margin-top:12px;color:#426048;font-family:'DM Mono',monospace;
              font-size:11px;text-decoration:none;letter-spacing:1px;}}
          </style>
        </head>
        <body>
          <div class="card">
            <div class="logo">Teesra</div>
            <h1>You've been unsubscribed.</h1>
            <p>We're sorry to see you go.</p>
            <div class="email">{email}</div>
            <p>You won't receive any more emails from us.<br>Changed your mind?</p>
            <a href="https://teesra.in/#signup" class="resubscribe">Resubscribe</a><br>
            <a href="https://teesra.in" class="home">← Back to Teesra</a>
          </div>
        </body>
        </html>
        """
    else:
        return f"""
        <!DOCTYPE html>
        <html><head><meta charset="UTF-8"/>
        <style>
          body{{background:#0a120e;color:#e8f0e4;font-family:sans-serif;
            display:flex;align-items:center;justify-content:center;
            min-height:100vh;margin:0;text-align:center;padding:20px;}}
        </style></head>
        <body>
          <div>
            <h2>Something went wrong</h2>
            <p style="color:#90b094;">We couldn't process your request.<br>
            Please email us at brief@teesra.in to unsubscribe.</p>
            <a href="https://teesra.in" style="color:#d4a820;">← Back to Teesra</a>
          </div>
        </body></html>
        """, 500


# ── CROSSWORD ─────────────────────────────────────────────────────
@app.route("/privacy")
def privacy():
    return send_from_directory(".", "privacy.html")

@app.route("/terms")
def terms():
    return send_from_directory(".", "terms.html")

@app.route("/crossword")
def crossword():
    return send_from_directory(".", "crossword.html")

@app.route("/api/crossword")
def get_crossword():
    from datetime import date as _date
    today_str = str(_date.today())

    if today_str in _crossword_cache:
        return jsonify(_crossword_cache[today_str])

    articles = get_todays_articles()
    if len(articles) < 5:
        return jsonify({"error": "not_enough_articles"})

    facts_text = "\n".join(
        f"- {a.get('facts', '')} (Source: {a.get('source', '')}, Headline: {a.get('headline', '')})"
        for a in articles if a.get("facts")
    )

    prompt = f"""Based on these news facts from today's Indian news brief, generate exactly 12 crossword clue-answer pairs.

Rules for answers:
- Must be a SINGLE word, ALL CAPS, 4-10 letters
- Must be a proper noun or key term directly from the facts (person name, city, organisation, country, number spelled out like FIFTEEN)
- No common words like SAID, ALSO, THAT
- Answers must be specific enough that reading the brief helps

Rules for clues:
- Clue should be solvable if you read today's Teesra brief
- Write in classic crossword style — terse, no "The article says"
- Example good clue: "PM who chaired today's cabinet meet"
- Example bad clue: "According to the article, this person..."

Today's facts:
{facts_text}

Return this exact JSON structure with no markdown, no explanation:
{{
  "pairs": [
    {{"answer": "MODI", "clue": "PM who chaired today's cabinet meet", "length": 4}},
    ... 12 total
  ]
}}"""

    try:
        response = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            system="You are a crossword puzzle generator. Return ONLY valid JSON, no markdown, no explanation.",
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)
        # Ensure length field is correct
        for p in data.get("pairs", []):
            p["length"] = len(p["answer"])
        _crossword_cache[today_str] = data
        return jsonify(data)
    except Exception as e:
        print(f"❌ Crossword generation failed: {e}")
        return jsonify({"error": str(e)}), 500


# ── ADMIN PAGE + API ──────────────────────────────────────────────
@app.route("/admin")
def admin_page():
    return send_from_directory(".", "admin.html")


@app.route("/api/admin/stats")
@require_admin
def admin_stats():
    from datetime import date, timedelta
    try:
        from database import get_client
        client = get_client()
        total    = client.table('subscribers').select('id', count='exact').execute()
        active   = client.table('subscribers').select('id', count='exact').eq('is_active', True).execute()
        google   = client.table('subscribers').select('id', count='exact').not_.is_('auth_uid', 'null').execute()
        week_ago = str(date.today() - timedelta(days=7))
        new_week = client.table('subscribers').select('id', count='exact').gte('created_at', week_ago).execute()
        return jsonify({
            "total":        total.count or 0,
            "active":       active.count or 0,
            "google_users": google.count or 0,
            "new_this_week": new_week.count or 0,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/subscribers")
@require_admin
def admin_subscribers():
    try:
        from database import get_client
        client = get_client()
        result = client.table('subscribers')\
            .select('id, email, name, role, is_active, auth_uid, created_at')\
            .order('created_at', desc=True)\
            .execute()
        return jsonify(result.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/pipeline")
@require_admin
def admin_pipeline():
    try:
        from datetime import date
        from database import get_client
        client = get_client()
        today  = str(date.today())
        result = client.table('article')\
            .select('story_type, fetched_date, created_at')\
            .eq('fetched_date', today)\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
        all_today = client.table('article').select('story_type').eq('fetched_date', today).execute()
        topic_counts = {}
        for row in all_today.data:
            t = row.get('story_type', 'general')
            topic_counts[t] = topic_counts.get(t, 0) + 1
        last_run = result.data[0].get('created_at') if result.data else None
        return jsonify({
            "today_count": len(all_today.data),
            "date":        today,
            "last_run":    last_run,
            "topics":      topic_counts,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/toggle-subscriber", methods=["POST"])
@require_admin
def toggle_subscriber():
    try:
        from database import get_client
        client = get_client()
        data      = request.json
        email     = data.get('email', '')
        is_active = data.get('is_active', True)
        if not email:
            return jsonify({"error": "Missing email"}), 400
        client.table('subscribers').update({'is_active': is_active}).eq('email', email).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/set-role", methods=["POST"])
@require_admin
def set_role():
    try:
        from database import get_client
        client = get_client()
        data  = request.json
        email = data.get('email', '')
        role  = data.get('role', 'subscriber')
        if not email or role not in ('subscriber', 'admin'):
            return jsonify({"error": "Invalid params"}), 400
        client.table('subscribers').update({'role': role}).eq('email', email).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    print(f"Teesra backend starting on port {port}")
    app.run(debug=debug, port=port, host="0.0.0.0")