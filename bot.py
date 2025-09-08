import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler
)
from firebase_admin import credentials, firestore, initialize_app
import requests
from bs4 import BeautifulSoup

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)

# ---------- Load env ----------
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # put your own Telegram ID in .env

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is missing!")

# ---------- Firebase Setup ----------
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
        "password": password,
        "last_active": datetime.utcnow().isoformat()
    })

def get_user(user_id):
    doc = db.collection("users").document(str(user_id)).get()
    return doc.to_dict() if doc.exists else None

def update_last_active(user_id):
    db.collection("users").document(str(user_id)).update({
        "last_active": datetime.utcnow().isoformat()
    })

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
    can_skip = max(0, int(present / 0.75 - total)) if total > 0 else 0
    return perc, color, need_for_75, can_skip

def menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Today Attendance", callback_data="today")],
        [InlineKeyboardButton("📚 Subject-wise Attendance", callback_data="subject")],
        [InlineKeyboardButton("📊 Overall Attendance", callback_data="overall")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ])

# ---------- ERP ----------
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
    overall = data[-1]
    subjects = data[:-1]
    return subjects, overall

# ---------- Registration Flow ----------
REGISTER_ID, REGISTER_PW = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📝 Register", callback_data="register")]]
    await update.message.reply_text("👋 Welcome!\nTap below to register.", reply_markup=InlineKeyboardMarkup(keyboard))

async def register_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("🔑 Enter your ERP ID:")
    return REGISTER_ID

async def register_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["erp_id"] = update.message.text.strip()
    await update.message.reply_text("🔒 Now enter your ERP Password:")
    return REGISTER_PW

async def register_pw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    erp_id = context.user_data["erp_id"]
    password = update.message.text.strip()
    save_user(update.effective_user.id, erp_id, password)
    await update.message.reply_text("✅ Registered successfully!", reply_markup=menu_keyboard())
    return ConversationHandler.END

# ---------- Menu ----------
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_last_active(update.effective_user.id)
    await update.message.reply_text("📌 Choose an option:", reply_markup=menu_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    update_last_active(query.from_user.id)
    await query.answer()
    user = get_user(query.from_user.id)
    if not user:
        return await query.edit_message_text("❌ Not registered. Use /start to register.")

    session = login_erp(user["erp_id"], user["password"])
    if not session:
        return await query.edit_message_text("❌ Login failed. Please re-register.")

    if query.data == "today":
        today = fetch_today_attendance(session)
        if not today:
            msg = "📭 No classes today"
        else:
            # fixed new time slots
            timeslots = [
                "9:30-10:24", "10:25-11:19", "11:20-12:14",
                "12:15-1:09", "1:10-2:04", "2:05-2:59", "3:00-3:54"
            ]
            msg = "📅 *Today's Attendance:*\n\n"
            for idx, t in enumerate(today):
                slot = timeslots[idx] if idx < len(timeslots) else t.get("TimeSlot", "")
                status = "✅ Present" if t["Tag"] == "P" else "❌ Absent"
                msg += f"• {t['NAME']} ({slot}) → {status}\n"

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

    elif query.data == "about":
        msg = ("ℹ️ *About This Bot*\n\n"
               "📌 Tracks ERP attendance.\n"
               "🛠 Built with Python, Telegram API, Firebase.\n\n"
               "👨‍💻 Developer: Aryan (B.Tech CSE)")

    else:
        msg = "❓ Unknown option."

    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=menu_keyboard())

# ---------- Admin Commands ----------
async def user_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Unauthorized")
    users = db.collection("users").stream()
    count = sum(1 for _ in users)
    await update.message.reply_text(f"👥 Total registered users: {count}")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Unauthorized")
    users = db.collection("users").stream()
    user_list = []
    count = 0
    for doc in users:
        data = doc.to_dict()
        count += 1
        last_seen = data.get("last_active", "❌ Never")
        user_list.append(f"👤 {doc.id} → {data.get('erp_id')} (🕒 {last_seen})")
    if not user_list:
        await update.message.reply_text("📭 No users registered.")
    else:
        msg = f"📋 *Registered Users* ({count}):\n\n" + "\n".join(user_list)
        await update.message.reply_text(msg, parse_mode="Markdown")

# ---------- Main ----------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    reg_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(register_button, pattern="^register$")],
        states={
            REGISTER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_id)],
            REGISTER_PW: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_pw)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("usercount", user_count))
    app.add_handler(CommandHandler("listusers", list_users))
    app.add_handler(reg_conv)
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Bot is running...")
    app.run_polling()
