
import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ALOC_TOKEN = os.getenv("ALOC_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY")
FLW_PUBLIC_KEY = os.getenv("FLW_PUBLIC_KEY")

SUBJECTS = ["English","Mathematics","Biology","Chemistry","Physics","Economics","Government","Literature","CRS","Commerce","Geography","Accounting"]
