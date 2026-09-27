
from flask import Flask, request, jsonify
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "🎓 UTME Bot Webhook OK - Telegram bot runs separately"

@app.route("/flw-webhook", methods=["POST"])
def flw_webhook():
    data = request.json or {}
    print(f"WEBHOOK: {data}")
    try:
        # Lazy import so Flask can start even if payment.py missing
        from payment import grant_premium
        event = data.get("event")
        txn_data = data.get("data", {})
        if event == "charge.completed" and txn_data.get("status") == "successful":
            tx_ref = txn_data.get("tx_ref", "")
            try:
                parts = tx_ref.split("-")
                user_id = int(parts[1])
                grant_premium(user_id, days=30, tx_ref=tx_ref, email=txn_data.get("customer",{}).get("email"))
                print(f"Premium granted to {user_id}")
                return jsonify({"status":"premium granted","user_id":user_id}), 200
            except Exception as e:
                print(f"Parse error: {e}")
    except Exception as e:
        print(f"Webhook error: {e}")
        import traceback; traceback.print_exc()
    return jsonify({"status":"ignored"}), 200

@app.route("/health")
def health():
    try:
        from payment import load_db
        return jsonify({"status":"ok","premium":len(load_db())})
    except:
        return jsonify({"status":"ok"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    print(f"Starting Flask on port {port}")
    app.run(host="0.0.0.0", port=port)
