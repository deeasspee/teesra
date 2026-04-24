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

from datetime import datetime, timezone, timedelta
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_today():
    """Returns today's date in IST regardless of server timezone."""
    return datetime.now(IST).date()

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

_til_cache = {}
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
@app.route("/sitemap.xml")
def sitemap():
    from flask import Response
    from datetime import datetime, timezone, timedelta
    
    IST = timezone(timedelta(hours=5, minutes=30))
    today = str(datetime.now(IST).date())
    
    # Static pages
    static_urls = [
        ("https://teesra.in/", "1.0", "daily"),
        ("https://teesra.in/feed", "0.9", "daily"),
        ("https://teesra.in/about", "0.7", "monthly"),
        ("https://teesra.in/trending", "0.8", "daily"),
        ("https://teesra.in/crossword", "0.8", "daily"),
    ]
    
    # Story permalink pages from last 5 days
    story_urls = []
    try:
        from database import get_client
        client = get_client()
        cutoff = str(datetime.now(IST).date() - 
                    timedelta(days=5))
        result = client.table('article')\
            .select('id, fetched_date')\
            .gte('fetched_date', cutoff)\
            .execute()
        for row in result.data:
            story_urls.append((
                f"https://teesra.in/story/{row['id']}",
                "0.8",
                row['fetched_date']
            ))
    except Exception as e:
        print(f"Sitemap story fetch error: {e}")
    
    # Build XML
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for url, priority, changefreq in static_urls:
        xml += f'''  <url>
    <loc>{url}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>\n'''
    
    for url, priority, lastmod in story_urls:
        xml += f'''  <url>
    <loc>{url}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>never</changefreq>
    <priority>{priority}</priority>
  </url>\n'''
    
    xml += '</urlset>'
    
    return Response(xml, mimetype='application/xml')


@app.route("/robots.txt")
def robots():
    from flask import Response
    txt = """User-agent: *
Allow: /
Disallow: /api/
Disallow: /admin
Sitemap: https://teesra.in/sitemap.xml"""
    return Response(txt, mimetype='text/plain')

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
        from datetime import datetime, timezone, timedelta
        _IST = timezone(timedelta(hours=5, minutes=30))
        ist_now   = datetime.now(_IST)
        ist_today = ist_now.date()

        days_back = int(request.args.get('days', 1))
        days_back = max(1, min(days_back, 5))
        target_date = ist_today - timedelta(days=days_back - 1)

        articles = get_articles_by_date(target_date)

        # Local JSON safety net for today
        if not articles and days_back == 1:
            try:
                with open("analyzed_articles.json", "r", encoding="utf-8") as f:
                    articles = json.load(f)
            except FileNotFoundError:
                pass

        # Before 9 AM IST: if today truly has no articles, serve yesterday
        # with is_fallback flag so the frontend can show the right tab + banner
        if not articles and days_back == 1 and ist_now.hour < 9:
            yesterday = ist_today - timedelta(days=1)
            print(f"  📰 No articles for today before 9 AM — serving {yesterday}")
            fallback_articles = get_articles_by_date(yesterday)
            if fallback_articles:
                enriched = [enrich_article(a) for a in fallback_articles]
                resp = jsonify({
                    "articles":       enriched,
                    "is_fallback":    True,
                    "serving_date":   str(yesterday),
                    "requested_date": str(target_date),
                })
                resp.headers['Cache-Control'] = 'public, max-age=120'
                return resp

        enriched = [enrich_article(a) for a in articles]
        resp = jsonify(enriched)
        resp.headers['Cache-Control'] = 'public, max-age=120'
        return resp
    except Exception as e:
        print(f"Articles route error: {e}")
        return jsonify([])

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
    try:
        from datetime import datetime, timezone, timedelta as _td
        import traceback as _tb

        _IST = timezone(_td(hours=5, minutes=30))
        ist_now = datetime.now(_IST)
        today_str = str(ist_now.date())
        yesterday_str = str(ist_now.date() - _td(days=1))

        def _cors(resp):
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Cache-Control'] = 'public, max-age=14400'
            return resp

        from database import get_client
        client = get_client()

        def fetch_articles_for_date(date_str):
            try:
                result = client.table('article')\
                    .select('id, headline, facts, story_type, source')\
                    .eq('fetched_date', date_str)\
                    .execute()
                return result.data or []
            except Exception as e:
                print(f"  Article fetch error for {date_str}: {e}")
                return []

        # ?refresh=1 forces regeneration (no server cache; logs intent)
        if request.args.get('refresh') == '1':
            print("  🔄 refresh=1 requested — generating fresh crossword")

        articles = fetch_articles_for_date(today_str)
        used_date = today_str

        if len(articles) < 5:
            print(f"  📰 Only {len(articles)} articles for {today_str} — trying {yesterday_str}")
            articles = fetch_articles_for_date(yesterday_str)
            used_date = yesterday_str

        if len(articles) < 5:
            return _cors(jsonify({
                "error": "not_enough_articles",
                "message": "Crossword not ready. Check back after 8 AM IST."
            }))

        print(f"  ✅ Generating crossword from {len(articles)} articles ({used_date})")

        facts_text = "\n".join([
            f"- {a.get('facts','')[:300]}"
            for a in articles[:15]
            if a.get('facts') and
            'INSUFFICIENT' not in str(a.get('facts', '')).upper()
        ])

        if not facts_text.strip():
            return _cors(jsonify({
                "error": "no_valid_facts",
                "message": "Crossword generation failed. Try again later."
            }))

        prompt = f"""You are a crossword editor. Generate 10 crossword clue-answer pairs from ONLY the facts provided below.

ABSOLUTE RULES — NEVER BREAK THESE:

1. ONLY use information explicitly written in the Facts section below.
   DO NOT use any knowledge from training. DO NOT assume ANY facts not written.

2. CLUES must be DIRECTLY VERIFIABLE from the text below.
   If the text does not say "X is captain", do NOT write "captain" in the clue. Ever.

3. ANSWERS must be:
   - 5-10 letters, single word, ALL CAPS
   - Proper nouns only: states, countries, cities, organisations, official titles
   - NOT: village names, accused persons, victims, private individuals,
     casualty numbers, small localities

4. PREFERRED answers (in order):
   - Indian states (TAMILNADU, RAJASTHAN)
   - Major Indian cities (MUMBAI, DELHI)
   - Countries (PAKISTAN, AMERICA)
   - Major organisations if 5-10 letters (GOOGLE, ISRO, SEBI)
   - Official titles used in text (MINISTER, GOVERNOR, DIRECTOR)

5. CLUE FORMAT:
   - Use only what the text says
   - If text says "PM Modi" — clue can say "India's Prime Minister"
   - If text says a person's name without their role — DO NOT assign them a role
   - Keep clues under 10 words
   - No "accused of", "who was killed", "death toll", "blast killed"

6. SELF-CHECK before returning:
   For each clue, ask: "Is every word in this clue directly supported by the facts text?"
   If NO — rewrite the clue or choose a different answer.

Return ONLY this JSON, no markdown:
{{
  "pairs": [
    {{"answer": "TAMILNADU", "clue": "State holding elections today", "length": 9}}
  ],
  "date": "{used_date}"
}}

FACTS (use ONLY these, nothing else):
{facts_text}"""

        response = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            system="Return only valid JSON. No markdown. No explanation.",
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()
        if raw.startswith('```'):
            raw = re.sub(r'^```[a-z]*\n?', '', raw)
            raw = re.sub(r'\n?```$', '', raw)
        raw = raw.strip()

        data = json.loads(raw)
        pairs = data.get('pairs', [])

        # Filter invalid length answers
        valid_pairs = [
            p for p in pairs
            if p.get('answer') and 4 <= len(p.get('answer', '')) <= 12
        ]

        # Deduplicate answers
        seen = set()
        deduped = []
        for p in valid_pairs:
            ans = p.get('answer', '')
            if ans not in seen:
                seen.add(ans)
                deduped.append(p)

        print(f"  Pairs: {len(pairs)} received, {len(deduped)} valid after length/dedup filter")

        # Quality filter — reject generic words and factually risky clues
        SKIP_ANSWERS = {
            'INDIA', 'TODAY', 'AFTER', 'FIRST', 'THIRD', 'BEING', 'THEIR',
            'ABOUT', 'WHICH', 'THESE', 'OTHER', 'WHILE', 'WHERE', 'UNDER',
            'SINCE', 'THERE', 'THOSE', 'WOULD', 'COULD', 'EVERY', 'ALONG',
        }
        RED_FLAGS = [
            # IPL captaincy errors
            'captain of csk', 'captain of rcb', 'captain of mi',
            'captain of kkr', 'captain of srh', 'captain of dc',
            'captain of gt', 'captain of lsg', 'captain of pbks', 'captain of rr',
            # Assumed leadership roles
            'who leads', 'who heads', 'who commands', 'who captains',
            # Crime/victim related
            'accused of', 'who was killed', 'who was murdered',
            'victim of', 'who died in', 'who was raped',
            # Location of crimes
            'village where', 'town where', 'place where crime',
            # Casualty counts
            'death toll', 'people died', 'killed in blast',
            'blast killed', 'factory explosion',
        ]
        quality_pairs = []
        for p in deduped:
            answer = p.get('answer', '').upper()
            clue_lower = p.get('clue', '').lower()
            if answer in SKIP_ANSWERS:
                print(f"  ⚠️ Generic answer skipped: {answer}")
                continue
            if any(flag in clue_lower for flag in RED_FLAGS):
                print(f"  ⚠️ Quality filter rejected: {answer} — {p.get('clue','')[:50]}")
                continue
            quality_pairs.append(p)

        if len(quality_pairs) >= 5:
            deduped = quality_pairs
        else:
            print(f"  ⚠️ Quality filter too strict ({len(quality_pairs)} left) — using pre-filter pairs")

        print(f"  Pairs final: {len(deduped)} after all filters")

        if len(deduped) < 5:
            return _cors(jsonify({
                "error": "insufficient_valid_pairs",
                "message": "Crossword generation failed. Try refreshing."
            }))

        for p in deduped:
            p['length'] = len(p['answer'])

        data['pairs'] = deduped
        data['clues_date'] = used_date
        data['articles_count'] = len(articles)

        return _cors(jsonify(data))

    except json.JSONDecodeError as e:
        print(f"❌ Crossword JSON parse error: {e}")
        return jsonify({
            "error": "parse_error",
            "message": "Crossword generation failed. Try refreshing."
        }), 500
    except Exception as e:
        print(f"❌ Crossword error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "message": "Crossword unavailable. Try again in a few minutes."
        }), 500


# ── TRENDING PAGE ─────────────────────────────────────────────────
@app.route("/trending")
def trending_page():
    return send_from_directory(".", "trending.html")


# ── STORY OF THE WEEK ─────────────────────────────────────────────
@app.route("/api/story-of-week")
def get_story_of_week():
    try:
        from story_of_week import get_latest_story_of_week
        story = get_latest_story_of_week()
        if not story:
            return jsonify({"error": "not_available"})
        resp = jsonify(story)
        resp.headers['Cache-Control'] = 'public, max-age=3600'
        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── REDDIT INDIA ──────────────────────────────────────────────────
def fetch_reddit_rss(url, subreddit, category):
    """Fetch posts from a subreddit RSS feed using xml.etree.ElementTree."""
    import xml.etree.ElementTree as ET
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Teesra/1.0 RSS Reader",
                "Accept":     "application/rss+xml, application/xml",
            }
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            content = r.read().decode('utf-8')

        root = ET.fromstring(content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        # Reddit uses Atom format; fall back to plain RSS <item>
        entries = root.findall('.//atom:entry', ns)
        if not entries:
            entries = root.findall('.//entry', ns)
        if not entries:
            entries = root.findall('.//item')

        posts = []
        for entry in entries[:5]:
            title = entry.find('atom:title', ns) or entry.find('title')
            link  = entry.find('atom:link',  ns) or entry.find('link')

            title_text = title.text if title is not None else ''
            if link is not None:
                link_text = link.get('href', '') or link.text or ''
            else:
                link_text = ''

            if not title_text or '[deleted]' in title_text:
                continue

            posts.append({
                'title':     title_text,
                'url':       link_text,
                'subreddit': subreddit,
                'category':  category,
                'score':     0,
                'comments':  0,
                'flair':     category,
            })
        return posts
    except Exception as e:
        print(f"RSS fetch failed for {subreddit}: {e}")
        return []


# ── REDDIT INDIA ──────────────────────────────────────────────────
@app.route("/api/reddit-india")
def get_reddit_india():
    """Fetch top posts from multiple India-focused subreddits via RSS"""
    FEEDS = [
        ("https://www.reddit.com/r/india/.rss",             "r/india",            "General"),
        ("https://www.reddit.com/r/Cricket/.rss",           "r/Cricket",          "Sports"),
        ("https://www.reddit.com/r/bollywood/.rss",         "r/bollywood",        "Entertainment"),
        ("https://www.reddit.com/r/IndiaInvestments/.rss",  "r/IndiaInvestments", "Finance"),
    ]

    all_posts = []
    for url, subreddit, category in FEEDS:
        posts = fetch_reddit_rss(url, subreddit, category)
        all_posts.extend(posts)
        time.sleep(0.3)

    if not all_posts:
        return jsonify({"posts": [], "error": "All RSS feeds failed"})

    resp = jsonify({
        "posts":   all_posts[:15],
        "count":   len(all_posts[:15]),
        "sources": [f[1] for f in FEEDS],
    })
    resp.headers['Cache-Control'] = 'public, max-age=900'
    return resp


# ── YOUTUBE TRENDING INDIA ────────────────────────────────────────
@app.route("/api/youtube-trending")
def get_youtube_trending():
    """Fetch YouTube trending videos for India"""
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
    if not YOUTUBE_API_KEY:
        return jsonify({"error": "no_api_key"})

    try:
        import json as _json

        params = urllib.parse.urlencode({
            'part':       'snippet,statistics',
            'chart':      'mostPopular',
            'regionCode': 'IN',
            'maxResults': 10,
            'key':        YOUTUBE_API_KEY
        })
        url = f"https://www.googleapis.com/youtube/v3/videos?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = _json.loads(r.read().decode())

        videos = []
        for item in data.get('items', []):
            snippet = item.get('snippet', {})
            stats   = item.get('statistics', {})
            videos.append({
                'id':        item.get('id', ''),
                'title':     snippet.get('title', ''),
                'channel':   snippet.get('channelTitle', ''),
                'thumbnail': snippet.get('thumbnails', {}).get('medium', {}).get('url', ''),
                'views':     int(stats.get('viewCount', 0)),
                'likes':     int(stats.get('likeCount', 0)),
                'url':       f"https://youtube.com/watch?v={item.get('id', '')}",
                'category':  snippet.get('categoryId', '')
            })

        resp = jsonify(videos)
        resp.headers['Cache-Control'] = 'public, max-age=1800'
        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── TMDB TRENDING ────────────────────────────────────────────────
@app.route("/api/tmdb-trending")
def get_tmdb_trending():
    """Fetch trending movies and TV shows in India from TMDB"""
    TMDB_READ_TOKEN = os.getenv('TMDB_READ_TOKEN', '')
    TMDB_API_KEY    = os.getenv('TMDB_API_KEY', '')

    if not TMDB_READ_TOKEN and not TMDB_API_KEY:
        return jsonify({"error": "no_api_key", "movies": [], "shows": []})

    try:
        import json as _json

        def fetch_tmdb(endpoint):
            if TMDB_READ_TOKEN:
                url = f"https://api.themoviedb.org/3{endpoint}"
                req = urllib.request.Request(url, headers={
                    "Authorization": f"Bearer {TMDB_READ_TOKEN}",
                    "accept": "application/json"
                })
            else:
                sep = '&' if '?' in endpoint else '?'
                url = f"https://api.themoviedb.org/3{endpoint}{sep}api_key={TMDB_API_KEY}"
                req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as r:
                return _json.loads(r.read().decode())

        movies_data = fetch_tmdb("/trending/movie/week?language=en-IN&region=IN")
        shows_data  = fetch_tmdb("/trending/tv/week?language=en-IN")

        def format_movie(item):
            poster = item.get('poster_path', '')
            return {
                'id':           item.get('id'),
                'title':        item.get('title', item.get('name', '')),
                'overview':     item.get('overview', '')[:150],
                'rating':       round(item.get('vote_average', 0), 1),
                'votes':        item.get('vote_count', 0),
                'release_date': item.get('release_date', item.get('first_air_date', '')),
                'poster':       f"https://image.tmdb.org/t/p/w200{poster}" if poster else '',
                'url':          f"https://www.themoviedb.org/movie/{item.get('id')}",
                'media_type':   'movie',
            }

        def format_show(item):
            poster = item.get('poster_path', '')
            return {
                'id':           item.get('id'),
                'title':        item.get('name', item.get('title', '')),
                'overview':     item.get('overview', '')[:150],
                'rating':       round(item.get('vote_average', 0), 1),
                'votes':        item.get('vote_count', 0),
                'release_date': item.get('first_air_date', ''),
                'poster':       f"https://image.tmdb.org/t/p/w200{poster}" if poster else '',
                'url':          f"https://www.themoviedb.org/tv/{item.get('id')}",
                'media_type':   'tv',
            }

        movies = [format_movie(m) for m in movies_data.get('results', [])[:8]]
        shows  = [format_show(s) for s in shows_data.get('results', [])[:8]]

        resp = jsonify({
            "movies":       movies,
            "shows":        shows,
            "total_movies": len(movies),
            "total_shows":  len(shows),
        })
        resp.headers['Cache-Control'] = 'public, max-age=3600'
        return resp

    except Exception as e:
        print(f"TMDB error: {e}")
        return jsonify({"error": str(e), "movies": [], "shows": []}), 500


# ── YOUTUBE MUSIC TRENDING ───────────────────────────────────────
@app.route("/api/youtube-music")
def get_youtube_music():
    """Fetch trending music videos in India (YouTube category 10)"""
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
    if not YOUTUBE_API_KEY:
        return jsonify({"error": "no_api_key", "videos": []})

    try:
        def fmt_views(n):
            try:
                n = int(n)
                if n >= 10_000_000: return f"{n // 1_000_000}M"
                if n >= 1_000_000:  return f"{n / 1_000_000:.1f}M"
                if n >= 1_000:      return f"{n // 1_000}K"
                return str(n)
            except Exception:
                return "0"

        params = urllib.parse.urlencode({
            'part':            'snippet,statistics',
            'chart':           'mostPopular',
            'regionCode':      'IN',
            'videoCategoryId': '10',
            'maxResults':      10,
            'key':             YOUTUBE_API_KEY,
        })
        url = f"https://www.googleapis.com/youtube/v3/videos?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())

        videos = []
        for i, item in enumerate(data.get('items', [])):
            snippet = item.get('snippet', {})
            stats   = item.get('statistics', {})
            views   = int(stats.get('viewCount', 0))
            videos.append({
                'rank':       i + 1,
                'id':         item.get('id', ''),
                'title':      snippet.get('title', ''),
                'channel':    snippet.get('channelTitle', ''),
                'thumbnail':  snippet.get('thumbnails', {}).get('medium', {}).get('url', ''),
                'views':      views,
                'views_fmt':  fmt_views(views),
                'url':        f"https://youtube.com/watch?v={item.get('id', '')}",
            })

        resp = jsonify({"videos": videos, "count": len(videos)})
        resp.headers['Cache-Control'] = 'public, max-age=3600'
        return resp
    except Exception as e:
        print(f"YouTube Music error: {e}")
        return jsonify({"error": str(e), "videos": []}), 500


# ── BOOKS TRENDING ────────────────────────────────────────────────
@app.route("/api/books-trending")
def get_books_trending():
    """NYT bestsellers (optional key) + Google Books India titles"""
    NYT_API_KEY = os.getenv("NYT_API_KEY", "")

    try:
        books_data = {"nyt_fiction": [], "nyt_nonfiction": [], "india_books": []}

        if NYT_API_KEY:
            def fetch_nyt(list_name):
                url = (f"https://api.nytimes.com/svc/books/v3/lists/"
                       f"current/{list_name}.json?api-key={NYT_API_KEY}")
                req = urllib.request.Request(url, headers={"User-Agent": "Teesra/1.0"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read().decode())
                return [
                    {
                        'rank':          b.get('rank'),
                        'title':         b.get('title', ''),
                        'author':        b.get('author', ''),
                        'description':   b.get('description', '')[:120],
                        'cover':         b.get('book_image', ''),
                        'amazon_url':    b.get('amazon_product_url', ''),
                        'weeks_on_list': b.get('weeks_on_list', 0),
                    }
                    for b in data.get('results', {}).get('books', [])[:6]
                ]

            try:
                books_data['nyt_fiction']    = fetch_nyt('hardcover-fiction')
            except Exception as e:
                print(f"NYT fiction error: {e}")
            try:
                books_data['nyt_nonfiction'] = fetch_nyt('hardcover-nonfiction')
            except Exception as e:
                print(f"NYT nonfiction error: {e}")

        # Google Books — India/Indian authors (no key needed)
        try:
            india_books = []
            for q in ["india+2024+bestseller", "indian+author+fiction+2024"]:
                params = urllib.parse.urlencode({
                    'q':           q,
                    'orderBy':     'relevance',
                    'maxResults':  5,
                    'printType':   'books',
                    'langRestrict':'en',
                })
                url = f"https://www.googleapis.com/books/v1/volumes?{params}"
                req = urllib.request.Request(url, headers={"User-Agent": "Teesra/1.0"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    gdata = json.loads(r.read().decode())
                for item in gdata.get('items', [])[:4]:
                    vol   = item.get('volumeInfo', {})
                    img   = vol.get('imageLinks', {})
                    title = vol.get('title', '')
                    if any(b['title'] == title for b in india_books):
                        continue
                    india_books.append({
                        'title':       title,
                        'author':      ', '.join(vol.get('authors', ['Unknown'])),
                        'description': vol.get('description', '')[:120],
                        'cover':       img.get('thumbnail', img.get('smallThumbnail', '')),
                        'url':         vol.get('infoLink', ''),
                        'published':   vol.get('publishedDate', '')[:4],
                        'rating':      vol.get('averageRating', 0),
                        'source':      'Google Books',
                    })
            books_data['india_books'] = india_books[:8]
        except Exception as e:
            print(f"Google Books error: {e}")

        resp = jsonify(books_data)
        resp.headers['Cache-Control'] = 'public, max-age=7200'
        return resp

    except Exception as e:
        print(f"Books route error: {e}")
        return jsonify({"nyt_fiction": [], "nyt_nonfiction": [], "india_books": [], "error": str(e)}), 500


# ── TODAY I LEARNED ──────────────────────────────────────────────
@app.route("/api/til")
def get_til():
    import random
    today_str = str(get_ist_today())

    # Return cached result — one TIL per day
    if today_str in _til_cache:
        resp = jsonify(_til_cache[today_str])
        resp.headers['Cache-Control'] = 'public, max-age=3600'
        return resp

    # Fetch ALL articles analyzed today from Supabase
    # — not just the 20 selected for the feed
    # This gives 40-60 articles for a broader,
    # more surprising fact range
    try:
        from database import get_client
        client = get_client()
        result = client.table('article')\
            .select('facts, headline, story_type')\
            .eq('fetched_date', today_str)\
            .not_.is_('facts', 'null')\
            .execute()
        all_articles = result.data or []
    except Exception as e:
        print(f"  ⚠️ TIL fetch error: {e}")
        all_articles = get_todays_articles()

    if not all_articles:
        return jsonify({"error": "no_articles"})

    # Shuffle for variety — don't always pick
    # from the same top articles each day
    shuffled = all_articles.copy()
    random.shuffle(shuffled)

    # Use up to 30 articles for broad range
    facts_text = "\n".join(
        f"- {a.get('facts', '')[:300]}"
        for a in shuffled[:30]
        if a.get('facts')
    )

    prompt = f"""From these news facts, extract ONE \
surprising, specific, and interesting fact that most \
people would not know. It should be genuinely \
surprising — a number, a contrast, an unexpected \
connection, or a little-known detail.

Rules:
- Must be a single sentence, max 35 words
- Must be specific — include numbers, names, \
  or places where possible
- Must be factual — directly from the text below
- Do NOT start with "Did you know" or "TIL"
- Do NOT include source attribution in the fact
- Write it as a clean declarative statement

Facts:
{facts_text}

Return ONLY this JSON, nothing else:
{{
  "fact": "your single surprising fact here",
  "topic": "one word topic like ECONOMY or POLITICS or SPORTS"
}}"""

    try:
        response = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            system="Return only valid JSON. No markdown.",
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)
        _til_cache[today_str] = data
        resp = jsonify(data)
        resp.headers['Cache-Control'] = 'public, max-age=3600'
        return resp
    except Exception as e:
        print(f"❌ TIL generation failed: {e}")
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
        week_ago = str(get_ist_today() - timedelta(days=7))
        new_week = client.table('subscribers').select('id', count='exact').gte('created_at', week_ago).execute()
        try:
            ratings_result = client.table('story_ratings')\
                .select('rating', count='exact')\
                .gte('rated_at', week_ago)\
                .execute()
            ratings_count = ratings_result.count or 0
        except Exception:
            ratings_count = 0
        return jsonify({
            "total":             total.count or 0,
            "active":            active.count or 0,
            "google_users":      google.count or 0,
            "new_this_week":     new_week.count or 0,
            "ratings_this_week": ratings_count,
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
        from database import get_client
        client = get_client()
        today  = str(get_ist_today())
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


# ── STORY RATING ──────────────────────────────────────────────────
@app.route('/api/rate-story', methods=['POST'])
def rate_story():
    try:
        from database import get_client
        from datetime import datetime, timezone, timedelta
        data = request.json or {}
        article_id = data.get('article_id')
        rating = data.get('rating', '')
        story_type = data.get('story_type', '')

        if not article_id or rating not in ['yes', 'partial', 'no']:
            return jsonify({"error": "Invalid data"}), 400

        IST = timezone(timedelta(hours=5, minutes=30))
        client = get_client()
        client.table('story_ratings').insert({
            'article_id': int(article_id),
            'rating': rating,
            'story_type': story_type,
            'rated_at': datetime.now(IST).isoformat(),
        }).execute()

        print(f"  ⭐ Rating saved: {rating} for article {article_id}")
        return jsonify({"success": True})
    except Exception as e:
        print(f"  ❌ Rating error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/ratings')
@require_admin
def admin_ratings():
    try:
        from database import get_client
        from datetime import datetime, timedelta
        client = get_client()
        week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

        result = client.table('story_ratings')\
            .select('rating, article_id')\
            .gte('rated_at', week_ago)\
            .execute()

        counts = {'yes': 0, 'partial': 0, 'no': 0}
        for row in result.data:
            r = row.get('rating')
            if r in counts:
                counts[r] += 1

        total = sum(counts.values())

        return jsonify({
            'total': total,
            'yes': counts['yes'],
            'partial': counts['partial'],
            'no': counts['no'],
            'yes_pct': round(counts['yes'] / total * 100) if total else 0,
            'partial_pct': round(counts['partial'] / total * 100) if total else 0,
            'no_pct': round(counts['no'] / total * 100) if total else 0,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/ratings-detail')
@require_admin
def admin_ratings_detail():
    try:
        from database import get_client
        from datetime import datetime, timedelta, timezone
        from collections import defaultdict

        IST = timezone(timedelta(hours=5, minutes=30))
        client = get_client()

        all_result = client.table('story_ratings')\
            .select('rating, rated_at, article_id, story_type')\
            .execute()
        all_ratings = all_result.data or []

        week_ago = (datetime.now(IST) - timedelta(days=7)).isoformat()
        week_result = client.table('story_ratings')\
            .select('rating, rated_at, story_type')\
            .gte('rated_at', week_ago)\
            .execute()
        week_ratings = week_result.data or []

        two_weeks_ago = (datetime.now(IST) - timedelta(days=14)).isoformat()
        last_week_result = client.table('story_ratings')\
            .select('rating')\
            .gte('rated_at', two_weeks_ago)\
            .lt('rated_at', week_ago)\
            .execute()
        last_week = last_week_result.data or []

        def calc_pcts(ratings_list):
            total = len(ratings_list)
            if not total:
                return {'total': 0, 'yes': 0, 'partial': 0, 'no': 0,
                        'yes_pct': 0, 'partial_pct': 0, 'no_pct': 0}
            yes     = sum(1 for r in ratings_list if r['rating'] == 'yes')
            partial = sum(1 for r in ratings_list if r['rating'] == 'partial')
            no      = sum(1 for r in ratings_list if r['rating'] == 'no')
            return {
                'total': total, 'yes': yes, 'partial': partial, 'no': no,
                'yes_pct':     round(yes / total * 100, 1),
                'partial_pct': round(partial / total * 100, 1),
                'no_pct':      round(no / total * 100, 1),
            }

        all_time  = calc_pcts(all_ratings)
        this_week = calc_pcts(week_ratings)
        prev_week = calc_pcts(last_week)
        wow_change = round(this_week['yes_pct'] - prev_week['yes_pct'], 1)

        # Daily breakdown last 14 days
        daily = defaultdict(lambda: {'yes': 0, 'partial': 0, 'no': 0})
        for r in all_ratings:
            try:
                dt  = datetime.fromisoformat(r['rated_at'].replace('Z', ''))
                day = dt.strftime('%b %d')
                daily[day][r['rating']] += 1
            except Exception:
                pass

        daily_list = []
        for day, counts in sorted(daily.items(), reverse=True)[:14]:
            total = sum(counts.values())
            if not total:
                continue
            daily_list.append({
                'day': day, 'total': total,
                'yes': counts['yes'], 'partial': counts['partial'], 'no': counts['no'],
                'yes_pct': round(counts['yes'] / total * 100),
                'partial_pct': round(counts['partial'] / total * 100),
            })

        # Weekly breakdown last 8 weeks
        weekly = defaultdict(lambda: {'yes': 0, 'partial': 0, 'no': 0})
        for r in all_ratings:
            try:
                dt     = datetime.fromisoformat(r['rated_at'].replace('Z', ''))
                monday = dt - timedelta(days=dt.weekday())
                weekly[monday.strftime('%b %d')][r['rating']] += 1
            except Exception:
                pass

        weekly_list = []
        for week, counts in sorted(weekly.items(), reverse=True)[:8]:
            total = sum(counts.values())
            if not total:
                continue
            weekly_list.append({
                'week': week, 'total': total,
                'yes': counts['yes'], 'partial': counts['partial'], 'no': counts['no'],
                'yes_pct':     round(counts['yes'] / total * 100),
                'partial_pct': round(counts['partial'] / total * 100),
                'no_pct':      round(counts['no'] / total * 100),
            })

        # Story type breakdown
        type_data = defaultdict(lambda: {'yes': 0, 'partial': 0, 'no': 0})
        for r in all_ratings:
            stype = r.get('story_type') or 'unknown'
            type_data[stype][r['rating']] += 1

        type_list = []
        for stype, counts in type_data.items():
            total = sum(counts.values())
            if total < 2:
                continue
            type_list.append({
                'type': stype.upper(), 'total': total,
                'yes': counts['yes'], 'partial': counts['partial'], 'no': counts['no'],
                'yes_pct': round(counts['yes'] / total * 100),
            })
        type_list.sort(key=lambda x: x['yes_pct'], reverse=True)

        return jsonify({
            'all_time': all_time, 'this_week': this_week,
            'prev_week': prev_week, 'wow_change': wow_change,
            'daily': daily_list, 'weekly': weekly_list, 'by_type': type_list,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    print(f"Teesra backend starting on port {port}")
    app.run(debug=debug, port=port, host="0.0.0.0")