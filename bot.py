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

logging.basicConfig(level=logging.INFO)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

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

def save_user(uid, erp, pw):
    db.collection("users").document(str(uid)).set({
        "erp_id": erp,
        "password": pw,
        "last_active": datetime.utcnow().isoformat()
    })

def get_user(uid):
    doc = db.collection("users").document(str(uid)).get()
    return doc.to_dict() if doc.exists else None

def update_last(uid):
    db.collection("users").document(str(uid)).update({
        "last_active": datetime.utcnow().isoformat()
    })

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Today", callback_data="today")],
        [InlineKeyboardButton("📚 Subject-wise", callback_data="subject")],
        [InlineKeyboardButton("📊 Overall", callback_data="overall")],
        [InlineKeyboardButton("📆 Weekly TT", callback_data="weekly")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ])

REGISTER_ID, REGISTER_PW = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\nClick below to register.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Register", callback_data="register")]
        ])
    )

async def register_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Enter ERP ID:")
    return REGISTER_ID

async def reg_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["erp"] = update.message.text.strip()
    await update.message.reply_text("Enter ERP Password:")
    return REGISTER_PW

async def reg_pw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user.id,
              context.user_data["erp"],
              update.message.text.strip())
    await update.message.reply_text("✅ Registered", reply_markup=menu())
    return ConversationHandler.END

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = get_user(q.from_user.id)
    if not user:
        return await q.edit_message_text("❌ Please /start and register")

    update_last(q.from_user.id)

    if q.data == "about":
        msg = "ℹ️ Attendance Bot\nBuilt with Python & Firebase"
    else:
        msg = "⚠️ ERP fetching disabled in demo"

    await q.edit_message_text(msg, reply_markup=menu())

async def usercount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    count = sum(1 for _ in db.collection("users").stream())
    await update.message.reply_text(f"Users: {count}")

app = ApplicationBuilder().token(TOKEN).build()

reg_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(register_btn, pattern="^register$")],
    states={
        REGISTER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_id)],
        REGISTER_PW: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_pw)]
    },
    fallbacks=[]
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("usercount", usercount))
app.add_handler(reg_conv)
app.add_handler(CallbackQueryHandler(buttons))
