
"""
Combined Runner - Runs Telegram Bot (polling) + Flutterwave Webhook (Flask) together
This lets you use ONE free Render service instead of two
"""
import threading
import os
from dotenv import load_dotenv
load_dotenv()

def run_telegram_bot():
    print("🤖 Starting Telegram Bot (polling mode)...")
    # Import main from main_bot but prevent it from blocking
    from main_bot import main as bot_main
    bot_main()

def run_webhook():
    print("💳 Starting Flutterwave Webhook Server...")
    from webhook_server import app
    port = int(os.getenv("PORT", 10000))  # Render sets PORT
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Webhook in thread, bot in main thread
    webhook_thread = threading.Thread(target=run_webhook, daemon=True)
    webhook_thread.start()

    run_telegram_bot()
