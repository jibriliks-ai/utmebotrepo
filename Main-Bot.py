
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
import json

# Lazy imports with fallback
try:
    from cbt_engine import CBTEngine
    cbt = CBTEngine()
    print("✅ CBT Engine loaded")
except Exception as e:
    print(f"⚠️ CBT Engine failed: {e}, using dummy")
    cbt = None

try:
    from ai_tutor import explain_with_ai, text_to_voice
except:
    def explain_with_ai(q): return q.get("explanation","Answer is "+q.get("answer",""))
    def text_to_voice(t,q_id=None): return None

try:
    from config import BOT_TOKEN, SUBJECTS
except:
    import os
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    SUBJECTS = ["English","Mathematics","Biology","Chemistry","Physics","Economics","Government","Literature"]

try:
    from payment import create_flutterwave_link, is_premium, get_premium_info, grant_premium, verify_by_tx_ref, PREMIUM_PRICE
except:
    PREMIUM_PRICE=2000
    def is_premium(uid): return False
    def get_premium_info(uid): return None
    def create_flutterwave_link(uid,email="",name=""): return None,"payment.py missing"
    def verify_by_tx_ref(tx): return False,"missing"
    def grant_premium(uid,days=30,tx_ref=None,email=None): return None

FREE_EXPLAIN_LIMIT = 3

def format_question(q, idx, total, time_left=None):
    time_str = f"⏱ {time_left//60}:{time_left%60:02d} | " if time_left else ""
    header = f"📝 Q{idx+1}/{total} | {q['subject']} {q.get('year','')} {time_str}\n\n"
    body = f"<b>{q['question']}</b>\n\n"
    opts = "\n".join([f"<b>{k}</b>: {v}" for k,v in q['options'].items()])
    return header + body + opts

def get_options_keyboard(q, current_idx):
    row = [InlineKeyboardButton(f"{k}", callback_data=f"ans_{k}") for k in q['options'].keys()]
    nav_row = [InlineKeyboardButton("⬅️ Prev", callback_data="nav_prev"), InlineKeyboardButton("➡️ Next", callback_data="nav_next"), InlineKeyboardButton("🏁 Submit", callback_data="submit")]
    explain_row = [InlineKeyboardButton("🧠 Explain + Voice", callback_data=f"explain_{current_idx}")]
    return InlineKeyboardMarkup([row, nav_row, explain_row])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        premium = is_premium(user_id)
    except:
        premium=False
    status = "💎 PREMIUM" if premium else f"🆓 FREE (N{PREMIUM_PRICE})"
    welcome = f"🎓 *UTME SUCCESS BOT* 🎓\n{status}\n\nCommands:\n/mock - Full mock\n/practice - One subject\n/subscribe - Premium\n"
    await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN)

async def subscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_premium(user_id):
        await update.message.reply_text("💎 You are already PREMIUM!")
        return
    await update.message.reply_text(f"💳 Premium N{PREMIUM_PRICE}/30 days\nBenefits: Unlimited AI + Voice\n\nSend your email (e.g. you@gmail.com):", parse_mode=ParseMode.MARKDOWN)
    context.user_data["awaiting_email"] = True

async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_email"): return
    email = update.message.text.strip()
    if "@" not in email:
        await update.message.reply_text("❌ Invalid email")
        return
    user_id = update.effective_user.id
    name = update.effective_user.full_name
    await update.message.reply_text("⏳ Creating payment link...")
    link, tx_ref = create_flutterwave_link(user_id, email=email, name=name)
    if not link:
        await update.message.reply_text(f"❌ Could not create link: {tx_ref}")
        return
    context.user_data["awaiting_email"] = False
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(f"💳 Pay N{PREMIUM_PRICE}", url=link)],[InlineKeyboardButton("✅ Verify", callback_data=f"verify_{tx_ref}")]])
    await update.message.reply_text(f"🔗 Pay N{PREMIUM_PRICE}:\nAfter pay click Verify\nTx: {tx_ref}", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    if data.startswith("verify_"):
        tx_ref = data.replace("verify_","")
        await query.message.reply_text("🔍 Verifying...")
        success,_ = verify_by_tx_ref(tx_ref)
        if success:
            grant_premium(user_id,30,tx_ref)
            await query.message.reply_text("✅ Payment Confirmed! PREMIUM for 30 days")
        else:
            await query.message.reply_text(f"❌ Not yet. Tx: {tx_ref}")
        return
    if cbt is None:
        await query.message.reply_text("⚠️ Question DB not loaded")
        return
    if data.startswith("combo_"):
        subs = ["English","Mathematics","Biology","Chemistry"] if "science" in data else ["English","Literature","Government","CRS"]
        try:
            q,total = cbt.start_mock(user_id, subs, duration=120*60)
            await query.message.reply_text(f"🔥 Mock {','.join(subs)} - {total} Qs", parse_mode=ParseMode.MARKDOWN)
            left = cbt.get_time_left(user_id)
            await query.message.reply_text(format_question(q,0,total,left), reply_markup=get_options_keyboard(q,0), parse_mode=ParseMode.HTML)
        except Exception as e:
            await query.message.reply_text(f"Error starting mock: {e}")
        return
    elif data.startswith("prac_"):
        subj = data.replace("prac_","")
        try:
            q,total = cbt.start_mock(user_id, [subj], duration=45*60)
            left = cbt.get_time_left(user_id)
            await query.message.reply_text(format_question(q,0,total,left), reply_markup=get_options_keyboard(q,0), parse_mode=ParseMode.HTML)
        except Exception as e:
            await query.message.reply_text(f"Error: {e}")
        return
    elif data.startswith("ans_"):
        opt = data.replace("ans_","")
        try:
            result,status = cbt.answer_current(user_id, opt)
            if status == "NO_EXAM":
                await query.message.reply_text("No exam. /mock")
                return
            if status == "FINISHED":
                txt = f"🏁 Finished! Score: {result['raw_score']}/{result['total']} JAMB: {result['jamb_score']}/400"
                await query.message.reply_text(txt)
            else:
                next_q,next_idx = result
                left = cbt.get_time_left(user_id)
                total = len(cbt.active_exams[user_id]['questions'])
                await query.message.reply_text(format_question(next_q,next_idx,total,left), reply_markup=get_options_keyboard(next_q,next_idx), parse_mode=ParseMode.HTML)
        except Exception as e:
            await query.message.reply_text(f"Error: {e}")
    elif data.startswith("nav_"):
        exam = cbt.active_exams.get(user_id)
        if not exam: return
        if data=="nav_prev": exam['current_idx']=max(0,exam['current_idx']-1)
        else: exam['current_idx']=min(len(exam['questions'])-1,exam['current_idx']+1)
        q,idx = cbt.get_current_question(user_id)
        left=cbt.get_time_left(user_id)
        await query.message.reply_text(format_question(q,idx,len(exam['questions']),left), reply_markup=get_options_keyboard(q,idx), parse_mode=ParseMode.HTML)
    elif data=="submit":
        final=cbt.finish_exam(user_id)
        if final: await query.message.reply_text(f"🏁 Submitted! {final['raw_score']}/{final['total']} JAMB: {final['jamb_score']}/400")
    elif data.startswith("explain_"):
        if not is_premium(user_id):
            await query.message.reply_text(f"🚫 Free limit {FREE_EXPLAIN_LIMIT}/day. /subscribe for N{PREMIUM_PRICE}")
            return
        try:
            idx=int(data.replace("explain_",""))
            exam=cbt.active_exams.get(user_id)
            q=exam['questions'][idx] if exam and idx < len(exam['questions']) else None
            if not q:
                await query.message.reply_text("No question")
                return
            await query.message.reply_text("🧠 Generating...")
            exp=explain_with_ai(q)
            await query.message.reply_text(f"🧠 {exp}", parse_mode=ParseMode.MARKDOWN)
            vp=text_to_voice(exp,q_id=q.get('id'))
            if vp and os.path.exists(vp):
                await context.bot.send_voice(chat_id=query.message.chat_id, voice=open(vp,'rb'))
                os.remove(vp)
        except Exception as e:
            await query.message.reply_text(f"Error: {e}")

async def mock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard=[[InlineKeyboardButton("🔬 Science", callback_data="combo_science")],[InlineKeyboardButton("🎨 Art", callback_data="combo_art")]]
    await update.message.reply_text("Choose:", reply_markup=InlineKeyboardMarkup(keyboard))
async def practice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons=[[InlineKeyboardButton(s, callback_data=f"prac_{s}")] for s in SUBJECTS[:8]]
    await update.message.reply_text("Select subject:", reply_markup=InlineKeyboardMarkup(buttons))

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not set - set it in Render Environment")
        return
    print(f"BOT_TOKEN found: {BOT_TOKEN[:5]}...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mock", mock))
    app.add_handler(CommandHandler("practice", practice))
    app.add_handler(CommandHandler("subscribe", subscribe_cmd))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email))
    print("UTME Bot polling started...")
    app.run_polling()

if __name__ == "__main__":
    main()
