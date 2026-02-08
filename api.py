from flask import Flask, request, jsonify
from erp_api import login_erp, fetch_today_attendance

app = Flask(__name__)

@app.route("/today-attendance", methods=["POST"])
def today_attendance():
    data = request.json
    session = login_erp(data["erp_id"], data["password"])
    if not session:
        return jsonify({"error": "Login failed"}), 401
    return jsonify(fetch_today_attendance(session))
