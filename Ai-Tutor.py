
import os
import requests
from gtts import gTTS
from config import DEEPSEEK_API_KEY
import uuid

# Fallback local explanation if API fails
def local_explain(q_data):
    return q_data.get('explanation') or f"The correct answer is {q_data['answer']}. {q_data['options'][q_data['answer']]} is correct because it matches the definition/principle tested."

def explain_with_ai(q_data, style="nigerian"):
    """
    q_data: dict with question, options, answer, subject
    Returns: explanation_text
    """
    if not DEEPSEEK_API_KEY:
        return local_explain(q_data)

    prompt_map = {
        "nigerian": f"""You are a top JAMB teacher in Nigeria teaching a 16-year-old. Explain simply with small pidgin allowed.
        Subject: {q_data.get('subject')}
        Question: {q_data['question']}
        Options: {q_data['options']}
        Correct: {q_data['answer']} - {q_data['options'][q_data['answer']]}
        Task: 1. Why correct answer is correct (2 lines). 2. Why others are wrong (1 line each max). 3. Quick trick to remember. Max 120 words. Simple English.""",
        "formal": f"""Explain this JAMB question clearly for UTME student. Subject {q_data.get('subject')}. Question: {q_data['question']} Options {q_data['options']} Answer {q_data['answer']}. Give concise 4-step explanation."""
    }

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt_map.get(style, prompt_map['nigerian'])}],
            "temperature": 0.7,
            "max_tokens": 300
        }
        res = requests.post("https://api.deepseek.com/chat/completions", json=payload, headers=headers, timeout=15)
        res.raise_for_status()
        data = res.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        print(f"AI Error: {e}")
        return local_explain(q_data)

def text_to_voice(text, q_id=None, lang='en', tld='com.ng'):
    """Returns mp3 file path"""
    try:
        filename = f"voice_{q_id or uuid.uuid4().hex[:6]}.mp3"
        # Telegram voice note needs ogg, but mp3 works. We keep mp3 for simplicity
        # Limit text for gTTS (4000 chars)
        tts_text = text[:3500]
        tts = gTTS(text=tts_text, lang=lang, tld=tld)
        tts.save(filename)
        return filename
    except Exception as e:
        print(f"TTS Error: {e}")
        return None
