# app.py
# Teesra local server

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from send_welcome import send_welcome_email
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

# ── SERVE ANALYZED ARTICLES ───────────────────────────────────────
@app.route("/api/articles")
def get_articles():
    try:
        with open("analyzed_articles.json", "r", encoding="utf-8") as f:
            articles = json.load(f)
        return jsonify({"articles": articles, "count": len(articles)})
    except FileNotFoundError:
        return jsonify({"articles": [], "count": 0, "error": "No articles yet"})

# ── EMAIL SUBSCRIPTION ────────────────────────────────────────────
@app.route("/subscribe", methods=["POST"])
def subscribe():
    data = request.get_json()
    email = data.get("email", "").strip()

    if not email or "@" not in email:
        return jsonify({"error": "Invalid email"}), 400

    if email in subscribers:
        return jsonify({"message": "already_subscribed"}), 200

    subscribers.append(email)
    send_welcome_email(email)

    print(f"📧 New subscriber: {email} (total: {len(subscribers)})")
    return jsonify({"message": "subscribed"}), 200


if __name__ == "__main__":
    print("🚀 Teesra backend starting on http://localhost:5000")
    app.run(debug=True, port=5000)