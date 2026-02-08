import subprocess
from threading import Thread
from api import app as flask_app

def run_api():
    flask_app.run(
        host="0.0.0.0",
        port=8000,
        debug=False
    )

def run_bot():
    subprocess.Popen(["python", "bot.py"])

if __name__ == "__main__":
    Thread(target=run_api).start()
    run_bot()
