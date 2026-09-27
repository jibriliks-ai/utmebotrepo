
import os
import threading
import time
from dotenv import load_dotenv
load_dotenv()

def run_bot():
    print("🤖 Starting Telegram Bot polling...")
    try:
        from main_bot import main
        main()
    except Exception as e:
        print(f"Bot crashed: {e}")
        import traceback; traceback.print_exc()
        # Keep alive to show error
        while True:
            time.sleep(60)

def run_flask():
    port = int(os.getenv("PORT", 10000))
    print(f"💳 Starting Flask on {port}")
    from webhook_server import app
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # If RUN_MODE=bot, run only bot (for Background Worker)
    # If RUN_MODE=web, run only Flask (for Web Service)
    # If not set, run Flask in main, bot in thread
    mode = os.getenv("RUN_MODE","both")
    print(f"RUN_MODE={mode}")
    if mode == "bot":
        run_bot()
    elif mode == "web":
        run_flask()
    else:
        # Both: Flask in main thread (Render needs this), bot in background
        t = threading.Thread(target=run_bot, daemon=True)
        t.start()
        run_flask()
