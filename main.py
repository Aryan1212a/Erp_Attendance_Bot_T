import os
import subprocess
from threading import Thread
from api import app as flask_app

def run_api():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )

def run_bot():
    subprocess.Popen(["python", "bot.py"])

if __name__ == "__main__":
    Thread(target=run_api).start()
    run_bot()
