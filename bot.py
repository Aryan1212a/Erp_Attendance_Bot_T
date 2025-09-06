import os
import logging
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from firebase_config import db
from erp_api import login_erp, fetch_today_attendance, fetch_subject_attendance, fetch_attendance_dates
import requests

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g., https://your-vercel-url.vercel.app/

app = Flask(__name__)
bot_app = ApplicationBuilder().token(TOKEN).build()

# ---------- Utils ----------
def save_user(user_id, erp_id, password):
    db.collection("users").document(str(user_id)).set({
        "erp_id": erp_id,
        "password": password
    })

def get_user(user_id):
    doc = db.collection("users").document(str(user_id)).get()
    return doc.to_dict() if doc.exists else None

def calculate_insights(present, total):
    perc = (present / total) * 100 if total > 0 else 0
    if perc >= 85: color = "🟢"
    elif perc >= 75: color = "🟡"
    elif perc >= 60: color = "🔵"
    else: color = "🔴"
    need_for_75 = max(0, int((0.75*total - present)/0.25))
    can_skip = int(present/0.75 - total) if total>0 else 0
    return perc, color, need_for_75, can_skip

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\nRegister using:\n`/register <ERP_ID> <Password>`",
        parse_mode="Markdown"
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        erp_id, password = context.args
        save_user(update.effective_user.id, erp_id, password)
        await update.message.reply_text("✅ Registered! Use /menu to continue")
    except:
        await update.message.reply_text("⚠️ Usage: `/register <ERP_ID> <Password>`", parse_mode="Markdown")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 Today Attendance", callback_data="today")],
        [InlineKeyboardButton("📚 Subject-wise Attendance", callback_data="subject")],
        [InlineKeyboardButton("📊 Overall Attendance", callback_data="overall")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ]
    await update.message.reply_text("Choose:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = get_user(query.from_user.id)
    if not user:
        return await query.edit_message_text("❌ Not registered. Use /register first")

    session = login_erp(user["erp_id"], user["password"])
    if not session:
        return await query.edit_message_text("❌ Login failed. Check credentials")

    if query.data == "today":
        today = fetch_today_attendance(session)
        if not today:
            return await query.edit_message_text("📭 No classes today")
        msg = "📅 *Today's Attendance:*\n\n"
        for t in today:
            status = "✅ Present" if t["Tag"] == "P" else "❌ Absent"
            msg += f"• {t['NAME']} ({t['TimeSlot']}) → {status}\n"
        await query.edit_message_text(msg, parse_mode="Markdown")

    elif query.data in ("subject", "overall"):
        start_date, end_date = fetch_attendance_dates(session)
        subjects, overall = fetch_subject_attendance(session, start_date, end_date)

        if query.data == "subject":
            msg = "📚 *Subject-wise Attendance:*\n\n"
            for s in subjects:
                present, total = int(s["Present"]), int(s["Total"])
                perc, color, need, skip = calculate_insights(present, total)
                msg += (f"{color} {s['NAME']}\n"
                        f"   ✅ {present}/{total} ({perc:.2f}%)\n"
                        f"   ➕ Need {need} more for 75%\n"
                        f"   ➖ Can skip {skip}\n\n")
        else:
            present, total = int(overall["Present"]), int(overall["Total"])
            perc, color, need, skip = calculate_insights(present, total)
            msg = (f"📊 *Overall Attendance*\n\n"
                   f"{color} ✅ {present}/{total} ({perc:.2f}%)\n"
                   f"➕ Need {need} more for 75%\n"
                   f"➖ Can skip {skip}")

        await query.edit_message_text(msg, parse_mode="Markdown")

    elif query.data == "about":
        msg = ("ℹ️ *About This Bot*\n\n"
               "📌 Tracks ERP attendance.\n"
               "🛠 Built with Python, Telegram API, Firebase.\n"
               "☁️ Deployable on Vercel.\n\n"
               "👨‍💻 Developer: Aryan (B.Tech CSE)")
        await query.edit_message_text(msg, parse_mode="Markdown")

# ---------- Flask routes ----------
@app.route("/", methods=["GET"])
def index():
    return "✅ Bot is running!"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    bot_app.update_queue.put(update)
    return jsonify({"ok": True})

# ---------- Set Telegram webhook ----------
def set_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}/{TOKEN}"
    resp = requests.get(url)
    print(resp.text)

# ---------- Register handlers ----------
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("register", register))
bot_app.add_handler(CommandHandler("menu", menu))
bot_app.add_handler(CallbackQueryHandler(button_handler))

# ---------- Run ----------
if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
