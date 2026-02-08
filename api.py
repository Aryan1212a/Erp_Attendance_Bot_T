from flask import Flask, request, jsonify
import os
from erp_api import (
    login_erp,
    fetch_today_attendance,
    fetch_subject_attendance,
    fetch_overall_attendance,
    fetch_timetable
)

app = Flask(__name__)

def get_session():
    data = request.json
    return login_erp(data["erp_id"], data["password"])

@app.route("/today-attendance", methods=["POST"])
def today_attendance():
    session = get_session()
    if not session:
        return jsonify({"error": "Login failed"}), 401
    return jsonify(fetch_today_attendance(session))

@app.route("/subject-attendance", methods=["POST"])
def subject_attendance():
    session = get_session()
    if not session:
        return jsonify({"error": "Login failed"}), 401
    return jsonify(fetch_subject_attendance(session))

@app.route("/overall-attendance", methods=["POST"])
def overall_attendance():
    session = get_session()
    if not session:
        return jsonify({"error": "Login failed"}), 401
    return jsonify(fetch_overall_attendance(session))

@app.route("/timetable", methods=["POST"])
def timetable():
    session = get_session()
    if not session:
        return jsonify({"error": "Login failed"}), 401
    return jsonify(fetch_timetable(session))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
