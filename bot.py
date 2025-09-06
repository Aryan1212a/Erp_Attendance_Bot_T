import os
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from firebase_config import db
from erp_api import login_erp, fetch_today_attendance, fetch_subject_attendance, fetch_attendance_dates

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(TOKEN)
app = Flask(__name__)
dp = Dispatcher(bot, None, workers=0)

# ---------- Firebase Utils ----------
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
    if perc >= 85:
        color = "🟢"
    elif perc >= 75:
        color = "🟡"
    elif perc >= 60:
        color = "🔵"
    else:
        color = "🔴"
    need_for_75 = max(0, int((0.75 * total - present) / 0.25))
    can_skip = int(present / 0.75 - total) if total > 0 else 0
    return perc, color, need_for_75, can_skip

# ---------- Bot Handlers ----------
def start(update, context):
    update.message.reply_text("👋 Welcome!\nRegister using:\n/register <ERP_ID> <Password>")

def register(update, context):
    try:
        erp_id, password = context.args
        save_user(update.effective_user.id, erp_id, password)
        update.message.reply_text("✅ Registered! Use /menu to continue")
    except:
        update.message.reply_text("⚠️ Usage: /register <ERP_ID> <Password>")

def menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📅 Today Attendance", callback_data="today")],
        [InlineKeyboardButton("📚 Subject-wise Attendance", callback_data="subject")],
        [InlineKeyboardButton("📊 Overall Attendance", callback_data="overall")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ]
    update.message.reply_text("Choose:", reply_markup=InlineKeyboardMarkup(keyboard))

def button_handler(update, context):
    query = update.callback_query
    query.answer()
    user = get_user(query.from_user.id)
    if not user:
        return query.edit_message_text("❌ Not registered. Use /register first")

    session = login_erp(user["erp_id"], user["password"])
    if not session:
        return query.edit_message_text("❌ Login failed. Check credentials")

    if query.data == "today":
        today = fetch_today_attendance(session)
        if not today:
            return query.edit_message_text("📭 No classes today")
        msg = "📅 *Today's Attendance:*\n\n"
        for t in today:
            status = "✅ Present" if t["Tag"] == "P" else "❌ Absent"
            msg += f"• {t['NAME']} ({t['TimeSlot']}) → {status}\n"
        query.edit_message_text(msg, parse_mode="Markdown")

    elif query.data in ("subject", "overall"):
        start_date, end_date = fetch_attendance_dates(session)
        subjects, overall = fetch_subject_attendance(session, start_date, end_date)
        if query.data == "subject":
            msg = "📚 *Subject-wise Attendance:*\n\n"
            for s in subjects:
                present, total = int(s["Present"]), int(s["Total"])
                perc, color, need, skip = calculate_insights(present, total)
                msg += f"{color} {s['NAME']}\n   ✅ {present}/{total} ({perc:.2f}%)\n   ➕ Need {need} more for 75%\n   ➖ Can skip {skip}\n\n"
        else:
            present, total = int(overall["Present"]), int(overall["Total"])
            perc, color, need, skip = calculate_insights(present, total)
            msg = f"📊 *Overall Attendance*\n\n{color} ✅ {present}/{total} ({perc:.2f}%)\n➕ Need {need} more for 75%\n➖ Can skip {skip}"
        query.edit_message_text(msg, parse_mode="Markdown")

    elif query.data == "about":
        msg = ("ℹ️ *About This Bot*\n\n"
               "📌 Tracks ERP attendance.\n"
               "🛠 Built with Python, Telegram API, Firebase.\n"
               "👨‍💻 Developer: Aryan (B.Tech CSE)")
        query.edit_message_text(msg, parse_mode="Markdown")

# ---------- Register Handlers ----------
dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("register", register))
dp.add_handler(CommandHandler("menu", menu))
dp.add_handler(CallbackQueryHandler(button_handler))

# ---------- Flask Webhook ----------
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dp.process_update(update)
    return "OK"

@app.route("/")
def index():
    return "ERP Attendance Bot is running!"

# ---------- Run Server ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
