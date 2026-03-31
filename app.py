# app.py
# Teesra local server
from database import get_todays_articles, save_subscriber
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from send_welcome import send_welcome_email
from market_data import fetch_market_data
import json
import os

app = Flask(__name__)
CORS(app)

FEED_API_KEY = os.getenv("FEED_API_KEY")  # set in .env + GitHub Secrets

# ── API KEY CHECK ─────────────────────────────────────────────────
def is_authorised() -> bool:
    """
    Allow requests from:
      1. Teesra's own frontend (same-origin via Referer/Origin)
      2. Localhost during development
      3. Requests with valid X-API-Key header or ?api_key= param
    Block everything else.
    """
    referer = request.headers.get('Referer', '')
    origin  = request.headers.get('Origin', '')

    # Own site — always allow
    trusted = ['teesra.vercel.app', 'teesra.in', 'localhost', '127.0.0.1']
    if any(t in referer or t in origin for t in trusted):
        return True

    # API key — for any external programmatic access
    if FEED_API_KEY:
        provided = (
            request.headers.get('X-API-Key') or
            request.args.get('api_key', '')
        )
        if provided == FEED_API_KEY:
            return True
        return False  # Key configured but not provided/wrong

    # No key configured (local dev without .env) — allow
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
@app.route("/api/market")
def get_market():
    if not is_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = fetch_market_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── SERVE ANALYZED ARTICLES ───────────────────────────────────────
@app.route("/api/articles")
def get_articles():
    if not is_authorised():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        # Try Supabase first
        articles = get_todays_articles()

        # Fall back to local JSON if Supabase empty
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

    # Save to Supabase
    saved = save_subscriber(email)

    if not saved:
        return jsonify({"message": "already_subscribed"}), 200

    # Send welcome email
    send_welcome_email(email)

    print(f"📧 New subscriber saved to Supabase: {email}")
    return jsonify({"message": "subscribed"}), 200


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    print(f"🚀 Teesra backend starting on port {port}")
    app.run(debug=debug, port=port, host="0.0.0.0")