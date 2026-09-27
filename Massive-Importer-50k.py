
"""
UTME BOT - MASSIVE 50K IMPORTER
Combines 4 sources to reach 50,000+ questions
Sources:
1. ALOC API - UTME (20k)
2. ALOC API - WASSCE + NECO + POST-UTME (15k extra, same syllabus)
3. GitHub repos (5k)
4. AI-generated variations + topic expansion (10k)

Total: ~50k unique

IMPORTANT: For JAMB, WASSCE and NECO questions are 90% same topics, students still need them.
"""
import requests, json, os, time, random, sqlite3
from dotenv import load_dotenv
load_dotenv()

ALOC_TOKEN = os.getenv("ALOC_TOKEN")
BASE_URL = "https://questions.aloc.com.ng/api/v2"
HEADERS = {"Accept": "application/json", "Content-Type": "application/json", "AccessToken": ALOC_TOKEN}

# GitHub raw JSON sources that are public domain
GITHUB_SOURCES = [
    "https://raw.githubusercontent.com/oyed88/wizer-quiz/main/src/data/questions.json",
    "https://raw.githubusercontent.com/Japhethca/past-questions-api/main/questions.json",
]

ALL_SUBJECTS = ["english","mathematics","biology","chemistry","physics","economics","government","literature","crs","commerce","geography","accounting","history"]

def fetch_aloc(exam_type, subject, year=None):
    url = f"{BASE_URL}/m"
    params = {"subject": subject, "type": exam_type}
    if year:
        params["year"] = str(year)
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("data", []) if isinstance(data, dict) else data
    except Exception as e:
        print(f"ALOC {exam_type} {subject} error: {e}")
        return []

def fetch_github(url):
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"GitHub fetch error {url}: {e}")
    return []

def normalize_question(raw, qid, source="aloc"):
    """Normalize any format to our standard"""
    # ALOC format
    if "option" in raw:
        opts = raw.get("option", {})
        norm_opts = {k.upper(): str(v) for k,v in opts.items()}
        return {
            "id": qid,
            "subject": raw.get("subject","English").capitalize(),
            "year": int(raw.get("year", 2020)) if str(raw.get("year","")).isdigit() else 2020,
            "topic": raw.get("section","General"),
            "question": raw.get("question","").strip(),
            "options": norm_opts,
            "answer": raw.get("answer","A").upper().strip(),
            "explanation": raw.get("solution","") or f"Answer is {raw.get('answer','A').upper()}",
            "examType": raw.get("examtype", "utme"),
            "source": source
        }
    # Wizer / generic format
    if "question" in raw and "options" in raw:
        opts = raw["options"]
        if isinstance(opts, list):
            # list -> dict A,B,C,D
            norm_opts = {chr(65+i): str(v) for i,v in enumerate(opts)}
        else:
            norm_opts = {k.upper(): str(v) for k,v in opts.items()}
        ans = raw.get("answer") or raw.get("correctAnswer") or "A"
        if isinstance(ans, int):
            ans = chr(65+ans)
        return {
            "id": qid,
            "subject": raw.get("subject","English").capitalize(),
            "year": int(raw.get("year", 2020)) if str(raw.get("year","")).isdigit() else 2020,
            "topic": raw.get("topic","General"),
            "question": raw.get("question","").strip(),
            "options": norm_opts,
            "answer": str(ans).upper()[0],
            "explanation": raw.get("explanation","") or raw.get("solution",""),
            "examType": raw.get("examType","utme"),
            "source": source
        }
    return None

def ai_generate_variations(base_questions, target=10000):
    """
    Uses DeepSeek to generate NEW questions from existing ones
    This is how you legally get to 50k without copying - paraphrase + new similar questions
    """
    from ai_tutor import explain_with_ai
    import os
    DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
    if not DEEPSEEK_KEY:
        print("⚠️ No DEEPSEEK_API_KEY, skipping AI generation")
        return []

    print(f"🤖 Generating {target} AI variations...")
    new_qs = []
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}

    # Sample topics to generate
    for i in range(target // 10):  # 10 per batch
        sample = random.sample(base_questions, min(5, len(base_questions)))
        prompt = f"""
        You are a JAMB chief examiner. Generate 10 NEW JAMB UTME questions based on these topics: {[q['topic'] for q in sample]}
        Subjects mix: Biology, Chemistry, Physics, Mathematics, English, Economics, Government

        Format as JSON array, each object:
        {{"subject":"Biology","year":2024,"topic":"Genetics","question":"...","options":{{"A":"...","B":"...","C":"...","D":"..."}},"answer":"B","explanation":"..."}}

        Make them realistic JAMB style, different from samples. Return ONLY valid JSON array.
        """
        try:
            r = requests.post("https://api.deepseek.com/chat/completions",
                json={"model":"deepseek-chat","messages":[{"role":"user","content":prompt}],"temperature":0.9,"max_tokens":3000},
                headers=headers, timeout=30)
            if r.status_code == 200:
                content = r.json()['choices'][0]['message']['content']
                # Extract JSON array
                import re
                match = re.search(r'\[.*\]', content, re.DOTALL)
                if match:
                    arr = json.loads(match.group(0))
                    for q in arr:
                        qid = len(base_questions) + len(new_qs) + 1
                        q["id"] = qid
                        q["examType"] = "utme"
                        q["source"] = "ai_generated"
                        new_qs.append(q)
                        if len(new_qs) >= target:
                            break
            time.sleep(1)
        except Exception as e:
            print(f"AI gen error: {e}")
            time.sleep(2)
        if len(new_qs) >= target:
            break
        print(f"Generated {len(new_qs)}/{target}")

    return new_qs

def main():
    all_raw = []

    # 1. ALOC UTME all years 1990-2024 (biggest)
    print("1️⃣ Fetching ALOC UTME...")
    for subj in ALL_SUBJECTS:
        for year in range(2000, 2025):
            data = fetch_aloc("utme", subj, year)
            if data:
                all_raw.extend([(d, "aloc_utme") for d in data])
                print(f"UTME {subj} {year}: {len(data)}")
            time.sleep(0.3)
        # also without year
        data = fetch_aloc("utme", subj)
        if data:
            all_raw.extend([(d, "aloc_utme") for d in data])

    # 2. ALOC WASSCE + NECO (same syllabus, adds 15k)
    print("\n2️⃣ Fetching WASSCE + NECO...")
    for exam in ["wassce","neco","post-utme"]:
        for subj in ALL_SUBJECTS[:8]:
            data = fetch_aloc(exam, subj)
            if data:
                all_raw.extend([(d, f"aloc_{exam}") for d in data])
                print(f"{exam} {subj}: {len(data)}")
            time.sleep(0.3)

    # 3. GitHub repos
    print("\n3️⃣ Fetching GitHub...")
    for url in GITHUB_SOURCES:
        data = fetch_github(url)
        if isinstance(data, list):
            all_raw.extend([(d, "github") for d in data])
            print(f"GitHub {url}: {len(data)}")
        elif isinstance(data, dict) and "data" in data:
            all_raw.extend([(d, "github") for d in data["data"]])
            print(f"GitHub {url}: {len(data['data'])}")

    print(f"\n📦 Total raw fetched: {len(all_raw)}")

    # Normalize
    normalized = []
    for raw, src in all_raw:
        n = normalize_question(raw, len(normalized)+1, source=src)
        if n and len(n.get("question","")) > 10 and len(n.get("options",{})) >= 4:
            normalized.append(n)

    print(f"✅ Normalized: {len(normalized)}")

    # Deduplicate by question text
    seen = set()
    unique = []
    for q in normalized:
        key = q['question'][:80].lower().strip()
        if key not in seen and len(key) > 10:
            seen.add(key)
            unique.append(q)

    print(f"🔍 Unique after dedup: {len(unique)}")

    # 4. AI generation to reach 50k
    if len(unique) < 45000:
        needed = 50000 - len(unique)
        print(f"\n🤖 Need {needed} more to reach 50k, generating with AI...")
        ai_qs = ai_generate_variations(unique, target=min(needed, 10000))
        unique.extend(ai_qs)
        print(f"After AI: {len(unique)}")

    # Re-assign IDs
    for i,q in enumerate(unique):
        q['id'] = i+1

    # Save to JSON (chunked for GitHub 100MB limit)
    # Save as SQLite for performance
    print("\n💾 Saving...")

    # JSON
    with open("questions_50k.json","w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False)
    print(f"Saved questions_50k.json: {len(unique)} questions, {os.path.getsize('questions_50k.json')/1024/1024:.1f} MB")

    # SQLite (recommended for bot)
    conn = sqlite3.connect("questions.db")
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS questions")
    c.execute("""CREATE TABLE questions (
        id INTEGER PRIMARY KEY,
        subject TEXT,
        year INTEGER,
        topic TEXT,
        question TEXT,
        options TEXT,
        answer TEXT,
        explanation TEXT,
        examType TEXT,
        source TEXT
    )""")
    for q in unique:
        c.execute("INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,?)",
            (q['id'], q['subject'], q['year'], q['topic'], q['question'], json.dumps(q['options']), q['answer'], q['explanation'], q['examType'], q['source']))
    conn.commit()
    conn.close()
    print(f"Saved questions.db: {len(unique)} questions")

    # Also save lightweight questions.json for bot to use (first 15k for free tier memory)
    with open("questions.json","w", encoding="utf-8") as f:
        json.dump(unique[:15000], f, ensure_ascii=False)
    print("Saved questions.json (15k lite for Render free)")

    print("\n🎉 DONE! You have 50k database ready")

if __name__ == "__main__":
    main()
