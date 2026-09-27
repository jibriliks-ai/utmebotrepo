
import os, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from cbt_engine import CBTEngine
from ai_tutor import explain_with_ai, text_to_voice
from config import BOT_TOKEN, SUBJECTS
from payment import create_flutterwave_link, is_premium, get_premium_info, grant_premium, verify_by_tx_ref, PREMIUM_PRICE
import json

cbt = CBTEngine()
user_sessions = {}

FREE_EXPLAIN_LIMIT = 3  # free users get 3 AI explanations per day

def format_question(q, idx, total, time_left=None):
    time_str = f"⏱ {time_left//60}:{time_left%60:02d} left | " if time_left else ""
    header = f"📝 Q{idx+1}/{total} | {q['subject']} {q.get('year','')} {time_str}\n\n"
    body = f"<b>{q['question']}</b>\n\n"
    opts = "\n".join([f"<b>{k}</b>: {v}" for k,v in q['options'].items()])
    return header + body + opts

def get_options_keyboard(q, current_idx):
    row = [InlineKeyboardButton(f"{k}", callback_data=f"ans_{k}") for k in q['options'].keys()]
    nav_row = [
        InlineKeyboardButton("⬅️ Prev", callback_data=f"nav_prev"),
        InlineKeyboardButton("➡️ Next", callback_data=f"nav_next"),
        InlineKeyboardButton("🏁 Submit", callback_data=f"submit"),
    ]
    explain_row = [InlineKeyboardButton("🧠 Explain + Voice", callback_data=f"explain_{current_idx}")]
    return InlineKeyboardMarkup([row, nav_row, explain_row])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    premium = is_premium(user_id)
    status = "💎 PREMIUM ACTIVE" if premium else f"🆓 FREE (Upgrade for {PREMIUM_PRICE} Naira)"
    info = get_premium_info(user_id)
    expiry = f" - expires {info['expiry_date']}" if info else ""

    welcome = (
        f"🎓 *UTME SUCCESS BOT - PRO* 🎓\n{status}{expiry}\n\n"
        "I be your personal JAMB CBT tutor wey dey talk!\n\n"
        "🔥 *What I fit do:*\n"
        "• Full JAMB mock (4 subjects, 2hrs timer)\n"
        "• Practice by subject/year/topic\n"
        "• Instant AI explanation + voice note\n"
        "• Score tracking & weak topics\n\n"
        "*Commands:*\n"
        "/mock - Full 4-subject mock\n"
        "/practice - Practice one subject\n"
        "/pastquestion - Random Q\n"
        "/stats - Your progress\n"
        "/subscribe - Get Premium (Unlimited AI + Voice)\n"
        "/review - Review last exam\n\n"
    )
    if not premium:
        welcome += f"⚠️ Free plan: {FREE_EXPLAIN_LIMIT} AI explanations/day. Go premium for unlimited!"

    await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN)

async def subscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_premium(user_id):
        info = get_premium_info(user_id)
        await update.message.reply_text(f"💎 You are already PREMIUM till {info['expiry_date']}!")
        return

    # Ask for email (required by Flutterwave)
    await update.message.reply_text(
        "💳 *Upgrade to Premium*\n\n"
        f"Price: *N{PREMIUM_PRICE} for 30 days*\n\n"
        "Benefits:\n"
        "✅ Unlimited AI explanations\n"
        "✅ Unlimited voice notes (Nigerian accent)\n"
        "✅ Full mock exams + detailed corrections\n"
        "✅ Weak topic detection\n\n"
        "Please send your *email address* for receipt (e.g. you@gmail.com):",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data["awaiting_email"] = True

async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_email"):
        return

    email = update.message.text.strip()
    if "@" not in email:
        await update.message.reply_text("❌ Invalid email. Send correct email e.g. you@gmail.com")
        return

    user_id = update.effective_user.id
    name = update.effective_user.full_name

    await update.message.reply_text("⏳ Creating secure Flutterwave payment link...")

    link, tx_ref = create_flutterwave_link(user_id, email=email, name=name)

    if not link:
        await update.message.reply_text(f"❌ Could not create payment link: {tx_ref}\nContact admin.")
        return

    context.user_data["awaiting_email"] = False
    context.user_data["last_tx_ref"] = tx_ref

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💳 Pay N{PREMIUM_PRICE} with Flutterwave", url=link)],
        [InlineKeyboardButton("✅ I have paid - Verify", callback_data=f"verify_{tx_ref}")]
    ])

    await update.message.reply_text(
        f"🔗 *Your Payment Link*\n\n"
        f"Click below to pay N{PREMIUM_PRICE}:\n"
        f"After payment, click *Verify* button\n\n"
        f"Tx Ref: `{tx_ref}`",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    # VERIFY PAYMENT
    if data.startswith("verify_"):
        tx_ref = data.replace("verify_", "")
        await query.message.reply_text("🔍 Verifying payment...")
        success, result = verify_by_tx_ref(tx_ref)
        if success:
            grant_premium(user_id, days=30, tx_ref=tx_ref)
            await query.message.reply_text(f"✅ *Payment Confirmed!*\n💎 You are now PREMIUM for 30 days!\nTx: {tx_ref}\n\nSend /mock to start", parse_mode=ParseMode.MARKDOWN)
        else:
            await query.message.reply_text(f"❌ Not yet confirmed. If you paid, wait 2 mins and try again.\nIf issue persists, send tx_ref to admin: {tx_ref}")
        return

    # ... rest of your existing callbacks (combo, prac, ans, nav, explain)
    if data.startswith("combo_"):
        if data == "combo_science":
            subs = ["English","Mathematics","Biology","Chemistry"]
        elif data == "combo_art":
            subs = ["English","Literature","Government","CRS"]
        else:
            await query.message.reply_text("Send 4 subjects comma-separated e.g: English, Mathematics, Physics, Chemistry")
            return
        q, total = cbt.start_mock(user_id, subs, duration=120*60)
        await query.message.reply_text(f"🔥 Mock started! {', '.join(subs)} - {total} Qs, 2hrs", parse_mode=ParseMode.MARKDOWN)
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
            txt = f"🏁 *Exam Finished!*\nScore: {result['raw_score']}/{result['total']} JAMB: *{result['jamb_score']}/400*\n\n"
            for subj, d in result['breakdown'].items():
                txt += f"{subj}: {d['score']}/{d['total']}\n"
            await query.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)
        else:
            next_q, next_idx = result
            if cbt.is_expired(user_id):
                final = cbt.finish_exam(user_id)
                await query.message.reply_text(f"⏰ Time up! Score: {final['raw_score']}/{final['total']} JAMB: {final['jamb_score']}/400")
                return
            left = cbt.get_time_left(user_id)
            total = len(cbt.active_exams[user_id]['questions'])
            await query.message.reply_text(format_question(next_q, next_idx, total, left), reply_markup=get_options_keyboard(next_q, next_idx), parse_mode=ParseMode.HTML)

    elif data.startswith("nav_"):
        exam = cbt.active_exams.get(user_id)
        if not exam: return
        if data == "nav_prev":
            exam['current_idx'] = max(0, exam['current_idx']-1)
        else:
            exam['current_idx'] = min(len(exam['questions'])-1, exam['current_idx']+1)
        q, idx = cbt.get_current_question(user_id)
        left = cbt.get_time_left(user_id)
        await query.message.reply_text(format_question(q, idx, len(exam['questions']), left), reply_markup=get_options_keyboard(q, idx), parse_mode=ParseMode.HTML)

    elif data == "submit":
        final = cbt.finish_exam(user_id)
        if final:
            await query.message.reply_text(f"🏁 Submitted! Score: {final['raw_score']}/{final['total']} | JAMB: {final['jamb_score']}/400")

    elif data.startswith("explain_"):
        # CHECK PREMIUM / FREE LIMIT
        if not is_premium(user_id):
            # simple daily limit using file
            import time, json, os
            limit_file = f"limits_{user_id}.json"
            today = time.strftime("%Y-%m-%d")
            count = 0
            if os.path.exists(limit_file):
                try:
                    with open(limit_file) as f:
                        d = json.load(f)
                        if d.get("date") == today:
                            count = d.get("count",0)
                except:
                    pass
            if count >= FREE_EXPLAIN_LIMIT:
                await query.message.reply_text(f"🚫 Free limit reached ({FREE_EXPLAIN_LIMIT}/day).\n💎 Upgrade with /subscribe for N{PREMIUM_PRICE} to get unlimited AI + voice!")
                return
            # increment
            with open(limit_file, "w") as f:
                json.dump({"date": today, "count": count+1}, f)

        try:
            idx = int(data.replace("explain_",""))
            last = cbt.active_exams.get(f"{user_id}_last")
            if last:
                q = last['questions'][idx] if idx < len(last['questions']) else last['questions'][0]
            else:
                exam = cbt.active_exams.get(user_id)
                q = exam['questions'][idx] if exam else None
            if not q:
                await query.message.reply_text("No question found")
                return
            await query.message.reply_text("🧠 Generating explanation + voice...")
            explanation = explain_with_ai(q)
            voice_path = text_to_voice(explanation, q_id=q.get('id'))
            await query.message.reply_text(f"🧠 *Explanation:*\n{explanation}", parse_mode=ParseMode.MARKDOWN)
            if voice_path and os.path.exists(voice_path):
                await context.bot.send_voice(chat_id=query.message.chat_id, voice=open(voice_path, 'rb'))
                os.remove(voice_path)
        except Exception as e:
            await query.message.reply_text(f"Error: {e}")

async def mock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔬 Science: Eng, Math, Bio, Chem", callback_data="combo_science")],
        [InlineKeyboardButton("🎨 Art: Eng, Lit, Govt, CRS", callback_data="combo_art")],
    ]
    await update.message.reply_text("Choose combo:", reply_markup=InlineKeyboardMarkup(keyboard))

async def practice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import SUBJECTS
    buttons = [[InlineKeyboardButton(s, callback_data=f"prac_{s}")] for s in SUBJECTS[:8]]
    await update.message.reply_text("Select subject:", reply_markup=InlineKeyboardMarkup(buttons))

async def pastquestion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = cbt.get_questions(limit=1)[0]
    cbt.active_exams[update.effective_user.id] = {
        "questions": [q], "current_idx": 0, "score": 0, "answers": {},
        "subjects": [q['subject']], "start_time": __import__('time').time(),
        "duration": 5*60, "finished": False
    }
    await update.message.reply_text(format_question(q, 0, 1), reply_markup=get_options_keyboard(q, 0), parse_mode=ParseMode.HTML)

def main():
    if not BOT_TOKEN:
        print("Set BOT_TOKEN")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mock", mock))
    app.add_handler(CommandHandler("practice", practice))
    app.add_handler(CommandHandler("pastquestion", pastquestion))
    app.add_handler(CommandHandler("subscribe", subscribe_cmd))
    app.add_handler(CallbackQueryHandler(handle_callback))
    # email handler must be last
    app.add_handler( __import__('telegram.ext').ext.MessageHandler(__import__('telegram.ext').filters.TEXT & ~__import__('telegram.ext').filters.COMMAND, handle_email))

    print("UTME Bot with Flutterwave running... (Polling mode)")
    app.run_polling()

if __name__ == "__main__":
    main()
