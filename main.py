from threading import Thread
from bot import app as telegram_app
from api import app as flask_app

def run_api():
    flask_app.run(
        host="0.0.0.0",
        port=8000,
        debug=False
    )

if __name__ == "__main__":
    # Start REST API for Android
    Thread(target=run_api).start()

    # Start Telegram bot
    telegram_app.run_polling()
    