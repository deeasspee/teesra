# app.py
# Teesra local server
from database import get_todays_articles, save_subscriber
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from send_welcome import send_welcome_email
from market_data import fetch_market_data
import json
import os
import urllib.request
import urllib.parse
import re

app = Flask(__name__)
CORS(app)

FEED_API_KEY = os.getenv("FEED_API_KEY")

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