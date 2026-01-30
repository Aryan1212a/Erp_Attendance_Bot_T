import json
from http.server import BaseHTTPRequestHandler
from telegram import Update
from bot import app

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        update = Update.de_json(json.loads(body), app.bot)
        app.process_update(update)

        self.send_response(200)
        self.end_headers()
