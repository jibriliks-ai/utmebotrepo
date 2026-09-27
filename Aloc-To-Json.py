
"""
UTME SUCCESS BOT - ALOC API IMPORTER (PRO)
Gets 20,000+ JAMB/WAEC/NECO questions from ALOC and converts to your bot format

ALOC Docs: https://questions.aloc.com.ng
Free: 1000 requests/day
"""
import requests
import json
import time
import os
from dotenv import load_dotenv
load_dotenv()

# 1. GET YOUR FREE TOKEN FROM https://questions.aloc.com.ng/api
ALOC_TOKEN = os.getenv("ALOC_TOKEN") or input("Enter your ALOC Access Token (from questions.aloc.com.ng): ").strip()
BASE_URL = "https://questions.aloc.com.ng/api/v2"

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "AccessToken": ALOC_TOKEN
}

# Map ALOC subjects to our format
SUBJECTS = ["english", "mathematics", "biology", "chemistry", "physics", "economics", "government", "literature", "crs", "commerce", "geography", "accounting"]

def fetch_aloc_questions(subject, exam_type="utme", year=None, limit=500):
    """Fetch from ALOC"""
    url = f"{BASE_URL}/m"
    params = {
        "subject": subject,
        "type": exam_type,  # utme, wassce, neco
        "year": year
    }
    try:
        print(f"Fetching {subject} {year or ''}...")
        res = requests.get(url, headers=HEADERS, params=params, timeout=20)
        if res.status_code == 401:
            print("❌ Invalid Token! Go to https://questions.aloc.com.ng/api and copy your token")
            return []
        res.raise_for_status()
        data = res.json()
        # ALOC returns { "subject": ..., "data": [ {question, option: {a,b,c,d}, answer, ...} ] }
        return data.get("data", []) if isinstance(data, dict) else data
    except Exception as e:
        print(f"Error fetching {subject}: {e}")
        return []

def convert_aloc_to_bot_format(aloc_qs, start_id=1):
    """Convert ALOC format to UTME Bot format"""
    converted = []
    curr_id = start_id
    for q in aloc_qs:
        # ALOC format: {"question": "...", "option": {"a":"...", "b":...}, "answer":"c", "section":"...", "year":"2020" }
        # Our format: id, subject, year, question, options {A,B,C,D}, answer, explanation
        options = q.get("option", {})
        # Normalize to A,B,C,D uppercase
        norm_options = {}
        for k,v in options.items():
            norm_options[k.upper()] = v

        converted.append({
            "id": curr_id,
            "subject": q.get("subject", "English").capitalize(),
            "year": int(q.get("year", 2022)) if str(q.get("year","2022")).isdigit() else 2022,
            "topic": q.get("section", "General"),
            "question": q.get("question", "").strip(),
            "options": norm_options,
            "answer": q.get("answer", "A").upper(),
            "explanation": q.get("solution", "") or f"The correct answer is {q.get('answer','').upper()}.",
            "examType": q.get("examtype", "utme")
        })
        curr_id += 1
    return converted

def main():
    print("🎓 UTME BOT - ALOC IMPORTER")
    if not ALOC_TOKEN:
        print("Set ALOC_TOKEN in .env or paste when asked")

    all_questions = []
    # Try to load existing questions.json to append
    if os.path.exists("questions.json"):
        with open("questions.json", "r", encoding="utf-8") as f:
            try:
                all_questions = json.load(f)
                print(f"Loaded {len(all_questions)} existing questions")
            except:
                all_questions = []

    start_id = len(all_questions) + 1

    # Fetch UTME for last 10 years
    for subject in SUBJECTS:
        for year in range(2015, 2025):  # 2015-2024
            raw = fetch_aloc_questions(subject, exam_type="utme", year=str(year))
            if raw:
                conv = convert_aloc_to_bot_format(raw, start_id=start_id)
                all_questions.extend(conv)
                start_id += len(conv)
                print(f"  + {len(conv)} {subject} {year}")
            time.sleep(0.5)  # avoid rate limit
        # Also fetch without year filter (gets random mix)
        if len(all_questions) < 100:
            raw = fetch_aloc_questions(subject, exam_type="utme")
            if raw:
                conv = convert_aloc_to_bot_format(raw, start_id=start_id)
                all_questions.extend(conv)
                start_id += len(conv)

    # Deduplicate by question text
    seen = set()
    unique = []
    for q in all_questions:
        key = q['question'][:100].lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)

    # Re-assign IDs
    for i, q in enumerate(unique):
        q['id'] = i+1

    with open("questions.json", "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    print(f"\n✅ DONE! Saved {len(unique)} unique questions to questions.json")
    print(f"File size: {os.path.getsize('questions.json')/1024/1024:.2f} MB")
    print("\nYou can now run: python main_bot.py")

if __name__ == "__main__":
    main()
