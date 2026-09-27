
import os, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
from cbt_engine import CBTEngine
from ai_tutor import explain_with_ai, text_to_voice
from config import BOT_TOKEN, SUBJECTS, YEARS
import json

cbt = CBTEngine()
# In production, use a DB like SQLite/Postgres. For now dict is okay.
user_sessions = {}  # user_id -> last_q

def format_question(q, idx, total, time_left=None):
    time_str = f"⏱ {time_left//60}:{time_left%60:02d} left | " if time_left else ""
    header = f"📝 Q{idx+1}/{total} | {q['subject']} {q.get('year','')} {time_str}\n\n"
    body = f"<b>{q['question']}</b>\n\n"
    opts = "\n".join([f"<b>{k}</b>: {v}" for k,v in q['options'].items()])
    return header + body + opts

def get_options_keyboard(q, current_idx):
    # A,B,C,D buttons
    row = [InlineKeyboardButton(f"{k}", callback_data=f"ans_{k}") for k in q['options'].keys()]
    nav_row = [
        InlineKeyboardButton("⬅️ Prev", callback_data=f"nav_prev"),
        InlineKeyboardButton("➡️ Next", callback_data=f"nav_next"),
        InlineKeyboardButton("🏁 Submit", callback_data=f"submit"),
    ]
    explain_row = [InlineKeyboardButton("🧠 Explain + Voice", callback_data=f"explain_{current_idx}")]
    return InlineKeyboardMarkup([row, nav_row, explain_row])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🎓 *UTME SUCCESS BOT - PRO* 🎓\n\n"
        "I be your personal JAMB CBT tutor wey dey talk!\n\n"
        "🔥 *What I fit do:*\n"
        "• Full JAMB mock (4 subjects, 2hrs timer)\n"
        "• Practice by subject/year/topic\n"
        "• Instant AI explanation + voice note\n"
        "• Score tracking & weak topics detection\n\n"
        "*Commands:*\n"
        "/mock - Start full 4-subject JAMB mock\n"
        "/practice - Practice one subject\n"
        "/pastquestion - Random question\n"
        "/explain - Explain last question\n"
        "/review - Review last exam\n"
        "/stats - Your progress\n"
        "/subjects - List all subjects\n\n"
        "Type /mock to start!"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN)

async def subjects_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Available subjects:\n" + ", ".join(SUBJECTS))

async def mock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /mock - show subject selection
    keyboard = []
    # Quick combos
    keyboard.append([InlineKeyboardButton("🔬 Science: Eng, Math, Bio, Chem", callback_data="combo_science")])
    keyboard.append([InlineKeyboardButton("🎨 Art: Eng, Lit, Govt, CRS", callback_data="combo_art")])
    keyboard.append([InlineKeyboardButton("📚 Custom - Choose 4 subjects", callback_data="combo_custom")])
    await update.message.reply_text("Choose your JAMB combo for full mock (100 Qs, 2hrs):", reply_markup=InlineKeyboardMarkup(keyboard))

async def practice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /practice Biology 2022 or /practice
    if context.args:
        subj = context.args[0].capitalize()
        year = context.args[1] if len(context.args)>1 else None
        q, total = cbt.start_mock(update.effective_user.id, [subj], duration=45*60)
        user_sessions[update.effective_user.id] = q
        left = cbt.get_time_left(update.effective_user.id)
        await update.message.reply_text(format_question(q, 0, total, left), reply_markup=get_options_keyboard(q, 0), parse_mode=ParseMode.HTML)
    else:
        # show subjects buttons
        buttons = [[InlineKeyboardButton(s, callback_data=f"prac_{s}")] for s in SUBJECTS[:8]]
        await update.message.reply_text("Select subject to practice (40 Qs, 45 mins):", reply_markup=InlineKeyboardMarkup(buttons))

async def pastquestion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = cbt.get_questions(limit=1)[0]
    user_sessions[update.effective_user.id] = q
    # store as single exam for explain feature
    cbt.active_exams[update.effective_user.id] = {
        "questions": [q],
        "current_idx": 0,
        "score": 0,
        "answers": {},
        "subjects": [q['subject']],
        "start_time": __import__('time').time(),
        "duration": 5*60,
        "finished": False
    }
    await update.message.reply_text(format_question(q, 0, 1), reply_markup=get_options_keyboard(q, 0), parse_mode=ParseMode.HTML)

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = cbt.user_stats[update.effective_user.id]
    if stats['total_attempted']==0:
        await update.message.reply_text("You never attempt any question yet. Use /practice to start.")
        return
    acc = int((stats['total_correct']/stats['total_attempted'])*100)
    txt = f"📊 *Your Stats*\nTotal: {stats['total_attempted']} | Correct: {stats['total_correct']} | Accuracy: {acc}%\n\nBy Subject:\n"
    for subj, d in stats['by_subject'].items():
        acc_s = int((d['correct']/d['attempted'])*100) if d['attempted'] else 0
        txt += f"- {subj}: {d['correct']}/{d['attempted']} ({acc_s}%)\n"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def review_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last = cbt.active_exams.get(f"{update.effective_user.id}_last")
    if not last:
        await update.message.reply_text("No recent exam found. Take a mock first with /mock")
        return
    # Send summary
    txt = f"✅ *Last Exam Review*\nScore: {last['raw_score']}/{last['total']} | JAMB: {last['jamb_score']}/400\n\n"
    for subj, d in last['breakdown'].items():
        txt += f"{subj}: {d['score']}/{d['total']}\n"
    txt += "\nSend number (e.g. 5) to see Q5 explanation"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("combo_"):
        if data == "combo_science":
            subs = ["English","Mathematics","Biology","Chemistry"]
        elif data == "combo_art":
            subs = ["English","Literature","Government","CRS"]
        else:
            await query.message.reply_text("Send 4 subjects comma-separated e.g: English, Mathematics, Physics, Chemistry")
            return
        q, total = cbt.start_mock(user_id, subs, duration=120*60)
        await query.message.reply_text(f"🔥 Mock started! {', '.join(subs)} - {total} Questions, 2hrs\nUse buttons to answer.", parse_mode=ParseMode.MARKDOWN)
        left = cbt.get_time_left(user_id)
        await query.message.reply_text(format_question(q, 0, total, left), reply_markup=get_options_keyboard(q, 0), parse_mode=ParseMode.HTML)

    elif data.startswith("prac_"):
        subj = data.replace("prac_","")
        q, total = cbt.start_mock(user_id, [subj], duration=45*60)
        left = cbt.get_time_left(user_id)
        await query.message.reply_text(format_question(q, 0, total, left), reply_markup=get_options_keyboard(q, 0), parse_mode=ParseMode.HTML)

    elif data.startswith("ans_"):
        opt = data.replace("ans_","")
        result, status = cbt.answer_current(user_id, opt)
        if status == "NO_EXAM":
            await query.message.reply_text("No active exam. Start with /mock or /practice")
            return
        if status == "FINISHED":
            # result is final dict
            txt = f"🏁 *Exam Finished!*\n\nScore: {result['raw_score']}/{result['total']}\nJAMB Equivalent: *{result['jamb_score']}/400*\n\n"
            for subj, d in result['breakdown'].items():
                txt += f"{subj}: {d['score']}/{d['total']}\n"
            txt += "\nType /review to see corrections\n/re Stats to see progress"
            await query.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)
        else:
            # NEXT
            next_q, next_idx = result
            # check expiry
            if cbt.is_expired(user_id):
                final = cbt.finish_exam(user_id)
                await query.message.reply_text(f"⏰ Time up! Score: {final['raw_score']}/{final['total']} JAMB: {final['jamb_score']}/400")
                return
            left = cbt.get_time_left(user_id)
            total = len(cbt.active_exams[user_id]['questions'])
            # Edit previous message? Send new for simplicity
            await query.message.reply_text(format_question(next_q, next_idx, total, left), reply_markup=get_options_keyboard(next_q, next_idx), parse_mode=ParseMode.HTML)

    elif data.startswith("nav_"):
        exam = cbt.active_exams.get(user_id)
        if not exam: return
        if data == "nav_prev":
            new_idx = max(0, exam['current_idx']-1)
            exam['current_idx'] = new_idx
        else:
            new_idx = min(len(exam['questions'])-1, exam['current_idx']+1)
            exam['current_idx'] = new_idx
        q, idx = cbt.get_current_question(user_id)
        left = cbt.get_time_left(user_id)
        await query.message.reply_text(format_question(q, idx, len(exam['questions']), left), reply_markup=get_options_keyboard(q, idx), parse_mode=ParseMode.HTML)

    elif data == "submit":
        final = cbt.finish_exam(user_id)
        if final:
            await query.message.reply_text(f"🏁 Submitted! Score: {final['raw_score']}/{final['total']} | JAMB: {final['jamb_score']}/400\n/review for corrections")

    elif data.startswith("explain_"):
        try:
            idx = int(data.replace("explain_",""))
            # get from last exam or active
            last = cbt.active_exams.get(f"{user_id}_last")
            if last:
                q = last['questions'][idx] if idx < len(last['questions']) else last['questions'][0]
            else:
                exam = cbt.active_exams.get(user_id)
                q = exam['questions'][idx] if exam else user_sessions.get(user_id)
            if not q:
                await query.message.reply_text("No question found to explain")
                return
            await query.message.reply_text("🧠 Generating explanation + voice...")
            explanation = explain_with_ai(q)
            voice_path = text_to_voice(explanation, q_id=q.get('id'))

            await query.message.reply_text(f"🧠 *Explanation:*\n{explanation}", parse_mode=ParseMode.MARKDOWN)
            if voice_path and os.path.exists(voice_path):
                await context.bot.send_voice(chat_id=query.message.chat_id, voice=open(voice_path, 'rb'))
                os.remove(voice_path)
        except Exception as e:
            await query.message.reply_text(f"Error explaining: {e}")

def main():
    if not BOT_TOKEN:
        print("Set BOT_TOKEN in .env")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mock", mock))
    app.add_handler(CommandHandler("practice", practice))
    app.add_handler(CommandHandler("pastquestion", pastquestion))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("review", review_cmd))
    app.add_handler(CommandHandler("subjects", subjects_cmd))
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("UTME Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
