
from flask import Flask, request, jsonify
import os
from payment import grant_premium, load_db

app = Flask(__name__)

@app.route("/")
def home():
    return "🎓 UTME Bot Running - Telegram Bot is Polling + Webhook Active"

@app.route("/flw-webhook", methods=["POST"])
def flw_webhook():
    data = request.json
    print(f"💳 Webhook received: {data}")

    event = data.get("event")
    txn_data = data.get("data", {})

    if event == "charge.completed" and txn_data.get("status") == "successful":
        tx_ref = txn_data.get("tx_ref", "")
        try:
            # tx_ref format: utme-{user_id}-{timestamp}-{rand}
            parts = tx_ref.split("-")
            user_id = int(parts[1])
            print(f"✅ Payment success for user {user_id}")
            expiry = grant_premium(user_id, days=30, tx_ref=tx_ref, email=txn_data.get("customer", {}).get("email"))
            return jsonify({"status": "premium granted", "user_id": user_id}), 200
        except Exception as e:
            print(f"Webhook error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"status": "ignored"}), 200

@app.route("/health")
def health():
    return jsonify({"status": "ok", "premium_users": len(load_db())})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
