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

subscribers = []

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
    try:
        data = fetch_market_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── SERVE ANALYZED ARTICLES ───────────────────────────────────────
@app.route("/api/articles")
def get_articles():
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
    print("🚀 Teesra backend starting on http://localhost:5000")
    app.run(debug=True, port=5000)