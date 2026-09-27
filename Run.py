
# Simple runner - just runs Flask, which auto-starts bot thread
# This is fallback if you use python run.py
import os
port = int(os.getenv("PORT", 10000))
print(f"Starting on port {port}")
from webhook_server import app
app.run(host="0.0.0.0", port=port)
