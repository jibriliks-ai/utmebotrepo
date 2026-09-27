
import os
import threading
import time
from dotenv import load_dotenv
load_dotenv()

# Check env immediately
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ CRITICAL: BOT_TOKEN not set in Environment Variables!")
    print("Go to Render -> Environment -> Add BOT_TOKEN")
else:
    print(f"✅ BOT_TOKEN found: {BOT_TOKEN[:10]}...")

def run_flask():
    # This MUST bind to PORT within 60 seconds or Render gives status 2
    port = int(os.getenv("PORT", 10000))
    print(f"💳 Starting Flask webhook on port {port}...")
    try:
        from webhook_server import app
        # Use 0.0.0.0 and PORT from Render
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"❌ Flask failed: {e}")
        import traceback
        traceback.print_exc()

def run_bot():
    # Wait a bit so Flask binds first
    time.sleep(3)
    print("🤖 Starting Telegram Bot (polling)...")
    try:
        from main_bot import main as bot_main
        bot_main()
    except Exception as e:
        print(f"❌ Bot failed: {e}")
        import traceback
        traceback.print_exc()
        # Keep process alive so Render doesn't restart loop
        while True:
            time.sleep(60)

if __name__ == "__main__":
    # Flask in main thread? Actually Render needs main thread to be web server
    # So run Flask in main thread, bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=False)
    bot_thread.start()

    # Flask runs in main thread - this is what Render monitors
    run_flask()
