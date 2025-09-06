import os
import logging
from dotenv import load_dotenv

# Load .env variables locally
load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from firebase_admin import credentials, firestore, initialize_app
import requests
from bs4 import BeautifulSoup

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)

# ---------- Telegram Bot Token ----------
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is missing!")

# ---------- Firebase Setup ----------
if not os.getenv("FIREBASE_PROJECT_ID"):
    raise ValueError("FIREBASE_PROJECT_ID environment variable is missing!")

cred_dict = {
    "type": "service_account",
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL")
}

cred = credentials.Certificate(cred_dict)
initialize_app(cred)
db = firestore.client()

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

# ---------- ERP Functions ----------
LOGIN_URL = "https://dbit.servergi.com:8079/MISIMDBITLatest/LoginMob"
TODAY_ATT_URL = "https://dbit.servergi.com:8079/MISIMDBITLatest/Service/WSDataServices.asmx/TodayAttendenceRecord"
SUBJECT_ATT_URL = "https://dbit.servergi.com:8079/MISIMDBITLatest/Service/WSDataServices.asmx/AttendenceSubject"
DATE_RANGE_URL = "https://dbit.servergi.com:8079/MISIMDBITLatest/Service/WSDataServices.asmx/GetAttDateFor"

def login_erp(username, password):
    session = requests.Session()
    r = session.get(LOGIN_URL)
    soup = BeautifulSoup(r.text, "html.parser")
    try:
        viewstate = soup.find("input", {"id": "__VIEWSTATE"})["value"]
        viewstate_gen = soup.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"]
        event_val = soup.find("input", {"id": "__EVENTVALIDATION"})["value"]
    except TypeError:
        return None

    payload = {
        "__VIEWSTATE": viewstate,
        "__VIEWSTATEGENERATOR": viewstate_gen,
        "__EVENTVALIDATION": event_val,
        "_txtUserName": username,
        "txtPassword": password,
        "btnLogin": "Login",
        "txtDeviceId": "",
        "txtUserName": "",
        "txtdateofBirth": ""
    }

    r2 = session.post(LOGIN_URL, data=payload)
    if "Login failed" in r2.text or "Invalid" in r2.text:
        return None
    return session

def fetch_today_attendance(session):
    r = session.post(TODAY_ATT_URL, json={"param": ""})
    return r.json().get("d", [])

def fetch_attendance_dates(session):
    r = session.post(DATE_RANGE_URL, json={"param": ""})
    data = r.json().get("d", {})
    return data.get("Item1"), data.get("Item2")

def fetch_subject_attendance(session, from_date, to_date):
    r = session.post(SUBJECT_ATT_URL, json={"dtStart": from_date, "dtEnd": to_date})
    data = r.json().get("d", [])
    if not data:
        return [], {}
    overall = data[-1]  # last row = total
    subjects = data[:-1]
    return subjects, overall

# ---------- Registration Conversation ----------
ASK_ERP, ASK_PASS = range(2)
temp_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Register", callback_data="register")],
        [InlineKeyboardButton("📊 Menu", callback_data="menu")]
    ]
    await update.message.reply_text(
        "👋 Welcome!\nChoose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def register_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]
    ]
    await query.message.reply_text("✏️ Please enter your ERP ID:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ASK_ERP

async def ask_erp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    temp_data[user_id] = {"erp_id": update.message.text}
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]
    ]
    await update.message.reply_text("🔑 Now enter your ERP Password:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ASK_PASS

async def ask_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in temp_data:
        await update.message.reply_text("⚠️ Something went wrong. Please try again.")
        return ConversationHandler.END

    temp_data[user_id]["password"] = update.message.text
    erp_id = temp_data[user_id]["erp_id"]
    password = temp_data[user_id]["password"]

    save_user(user_id, erp_id, password)

    temp_data.pop(user_id, None)

    keyboard = [
        [InlineKeyboardButton("📊 Menu", callback_data="menu")]
    ]
    await update.message.reply_text(
        f"✅ Registered successfully!\nERP ID: {erp_id}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Menu", callback_data="menu")]
    ]
    await update.message.reply_text("❌ Registration cancelled.", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

# ---------- Menu + Buttons ----------
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

    if query.data == "menu":
        keyboard = [
            [InlineKeyboardButton("📝 Register", callback_data="register")],
            [InlineKeyboardButton("📅 Today Attendance", callback_data="today")],
            [InlineKeyboardButton("📚 Subject-wise Attendance", callback_data="subject")],
            [InlineKeyboardButton("📊 Overall Attendance", callback_data="overall")],
            [InlineKeyboardButton("ℹ️ About", callback_data="about")]
        ]
        return await query.edit_message_text("📊 Main Menu:", reply_markup=InlineKeyboardMarkup(keyboard))

    user = get_user(query.from_user.id)
    if not user:
        return await query.edit_message_text("❌ Not registered. Please register first from /start")

    session = login_erp(user["erp_id"], user["password"])
    if not session:
        return await query.edit_message_text("❌ Login failed. Check your ERP credentials")

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
               "🛠 Built with Python, Telegram API, Firebase.\n\n"
               "👨‍💻 Developer: Aryan (B.Tech CSE)")
        await query.edit_message_text(msg, parse_mode="Markdown")

# ---------- Main ----------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    # Register conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(register_button, pattern="register")],
        states={
            ASK_ERP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_erp),
                CallbackQueryHandler(button_handler, pattern="menu")
            ],
            ASK_PASS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_pass),
                CallbackQueryHandler(button_handler, pattern="menu")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler, pattern=".*"))

    print("✅ Bot is running...")
    app.run_polling()