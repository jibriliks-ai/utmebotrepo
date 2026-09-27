
"""
UTME BOT - Flutterwave Monetization
Handles payments, verification, and premium status
"""
import os
import json
import time
import uuid
import requests
from dotenv import load_dotenv
load_dotenv()

FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY")  # FLWSECK_TEST- or FLWSECK_LIVE-
FLW_PUBLIC_KEY = os.getenv("FLW_PUBLIC_KEY")
PREMIUM_PRICE = int(os.getenv("PREMIUM_PRICE", "2000"))  # N2000 default
PREMIUM_DURATION_DAYS = 30

DB_FILE = "premium_users.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def is_premium(user_id):
    db = load_db()
    user_data = db.get(str(user_id))
    if not user_data:
        return False
    expiry = user_data.get("expiry", 0)
    return time.time() < expiry

def get_premium_info(user_id):
    db = load_db()
    return db.get(str(user_id))

def grant_premium(user_id, days=30, tx_ref=None, email=None):
    db = load_db()
    expiry = time.time() + (days * 24 * 60 * 60)
    # if already premium, extend
    existing = db.get(str(user_id))
    if existing and existing.get("expiry", 0) > time.time():
        expiry = existing["expiry"] + (days * 24 * 60 * 60)

    db[str(user_id)] = {
        "user_id": user_id,
        "expiry": expiry,
        "expiry_date": time.strftime("%Y-%m-%d", time.localtime(expiry)),
        "tx_ref": tx_ref,
        "email": email,
        "granted_at": time.time()
    }
    save_db(db)
    return expiry

def create_flutterwave_link(user_id, email="user@example.com", name="UTME Student"):
    """
    Creates a Flutterwave payment link
    Returns: payment_link_url, tx_ref
    """
    if not FLW_SECRET_KEY:
        return None, "FLW_SECRET_KEY not set in .env"

    tx_ref = f"utme-{user_id}-{int(time.time())}-{uuid.uuid4().hex[:4]}"

    url = "https://api.flutterwave.com/v3/payments"
    headers = {
        "Authorization": f"Bearer {FLW_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "tx_ref": tx_ref,
        "amount": PREMIUM_PRICE,
        "currency": "NGN",
        "redirect_url": "https://t.me/your_bot_username",  # CHANGE THIS to your bot link
        "payment_options": "card,banktransfer,ussd",
        "customer": {
            "email": email,
            "name": name
        },
        "customizations": {
            "title": "UTME Success Bot Premium",
            "description": f"30 days unlimited AI explanations + voice notes - {PREMIUM_PRICE} Naira",
            "logo": "https://cdn-icons-png.flaticon.com/512/2232/2232688.png"
        },
        "meta": {
            "user_id": str(user_id),
            "bot": "utme_success"
        }
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        data = res.json()
        if data.get("status") == "success":
            link = data["data"]["link"]
            return link, tx_ref
        else:
            print(f"FLW Error: {data}")
            return None, str(data)
    except Exception as e:
        print(f"FLW Exception: {e}")
        return None, str(e)

def verify_transaction(transaction_id):
    """Verify by Flutterwave transaction ID (from webhook or redirect)"""
    if not FLW_SECRET_KEY:
        return False, "No secret key"
    url = f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify"
    headers = {"Authorization": f"Bearer {FLW_SECRET_KEY}"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        data = res.json()
        if data.get("status") == "success" and data["data"]["status"] == "successful":
            amount = data["data"]["amount"]
            tx_ref = data["data"]["tx_ref"]
            meta = data["data"].get("meta", {})
            user_id = meta.get("user_id") or tx_ref.split("-")[1]
            return True, {"user_id": user_id, "tx_ref": tx_ref, "amount": amount, "email": data["data"]["customer"]["email"]}
        return False, data
    except Exception as e:
        return False, str(e)

def verify_by_tx_ref(tx_ref):
    """Verify by tx_ref (you created)"""
    if not FLW_SECRET_KEY:
        return False, "No secret key"
    # Flutterwave allows verify by tx_ref via ?tx_ref=
    url = f"https://api.flutterwave.com/v3/transactions?tx_ref={tx_ref}"
    headers = {"Authorization": f"Bearer {FLW_SECRET_KEY}"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        data = res.json()
        if data.get("status") == "success" and data.get("data"):
            # data is list
            txn = data["data"][0] if isinstance(data["data"], list) else data["data"]
            if txn.get("status") == "successful":
                return True, txn
        return False, data
    except Exception as e:
        return False, str(e)
