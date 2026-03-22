# app.py
# Teesra local server — connects frontend to backend

from flask import Flask, request, jsonify
from flask_cors import CORS
from send_welcome import send_welcome_email

app = Flask(__name__)
CORS(app)

# Store subscribers in a simple list for now
# In Week 2 we'll move this to Supabase
subscribers = []

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


@app.route("/")
def home():
    return f"Teesra backend running. Subscribers so far: {len(subscribers)}"


if __name__ == "__main__":
    print("🚀 Teesra backend starting on http://localhost:5000")
    app.run(debug=True, port=5000)