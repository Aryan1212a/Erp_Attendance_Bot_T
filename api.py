from flask import Flask, request, jsonify
from erp_api import (
    login_erp,
    fetch_today_attendance,
    fetch_attendance_dates,
    fetch_subject_attendance,
    fetch_timetable   # ← REAL function
)

app = Flask(__name__)

def get_session(data):
    session = login_erp(data.get("erp_id"), data.get("password"))
    return session

@app.route("/today-attendance", methods=["POST"])
def today_attendance():
    session = get_session(request.json)
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401
    return jsonify(fetch_today_attendance(session))

@app.route("/subject-attendance", methods=["POST"])
def subject_attendance():
    session = get_session(request.json)
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401

    start, end = fetch_attendance_dates(session)
    subjects, _ = fetch_subject_attendance(session, start, end)
    return jsonify(subjects)

@app.route("/overall-attendance", methods=["POST"])
def overall_attendance():
    session = get_session(request.json)
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401

    start, end = fetch_attendance_dates(session)
    _, overall = fetch_subject_attendance(session, start, end)
    return jsonify(overall)

@app.route("/timetable", methods=["POST"])
def timetable():
    session = get_session(request.json)
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify(fetch_timetable(session))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
