
import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

SUBJECTS = ["English", "Mathematics", "Biology", "Chemistry", "Physics", "Economics", "Government", "Literature", "CRS", "Commerce", "Geography", "Accounting"]
YEARS = list(range(2010, 2026))
JAMB_SUBJECTS_COMBO = {
    "science": ["English", "Mathematics", "Biology", "Chemistry"],
    "art": ["English", "Literature", "Government", "CRS"]
}
MOCK_DURATION = 120 * 60  # 2 hours for 4 subjects like real JAMB
QUESTIONS_PER_SUBJECT = 40  # Real JAMB is 40 per subject for 4 subjects, but for practice we use 40 total if 1 subject
