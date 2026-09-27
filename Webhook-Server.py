
from flask import Flask, request, jsonify
import os
import threading
import time

app = Flask(__name__)

@app.route("/")
def home():
    return "🎓 UTME Bot Running - Telegram Bot is Polling + Webhook Active - OK"

@app.route("/flw-webhook", methods=["POST"])
def flw_webhook():
    data = request.json or {}
    print(f"💳 Webhook received: {data}")
    try:
        from payment import grant_premium
        event = data.get("event")
        txn_data = data.get("data", {})
        if event == "charge.completed" and txn_data.get("status") == "successful":
            tx_ref = txn_data.get("tx_ref", "")
            parts = tx_ref.split("-")
            user_id = int(parts[1])
            print(f"✅ Payment success for user {user_id}")
            grant_premium(user_id, days=30, tx_ref=tx_ref, email=txn_data.get("customer", {}).get("email"))
            return jsonify({"status": "premium granted", "user_id": user_id}), 200
    except Exception as e:
        print(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    return jsonify({"status": "ignored"}), 200

@app.route("/health")
def health():
    try:
        from payment import load_db
        return jsonify({"status": "ok", "premium_users": len(load_db())})
    except:
        return jsonify({"status": "ok"})

# Auto-start bot in background when imported by gunicorn
def start_bot_thread():
    time.sleep(2)
    try:
        from main_bot import main as bot_main
        print("🤖 Starting Telegram Bot in background...")
        bot_main()
    except Exception as e:
        print(f"Bot thread error: {e}")

# Start bot thread only once
bot_started = False
if not bot_started:
    bot_started = True
    t = threading.Thread(target=start_bot_thread, daemon=True)
    t.start()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
