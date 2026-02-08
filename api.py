from flask import Flask, request, jsonify
from erp_api import (
    login_erp,
    fetch_today_attendance,
    fetch_today_timetable,
    fetch_weekly_timetable,
    fetch_subject_attendance,
    fetch_attendance_dates
)


app = Flask(__name__)

def get_session(data):
    session = login_erp(data.get("erp_id"), data.get("password"))
    return session

@app.route("/today-attendance", methods=["POST"])
def today_attendance():
    data = request.json
    session = login_erp(data["erp_id"], data["password"])
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify(fetch_today_attendance(session))


@app.route("/subject-attendance", methods=["POST"])
def subject_attendance():
    data = request.json
    session = login_erp(data["erp_id"], data["password"])
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401

    start, end = fetch_attendance_dates(session)
    subjects, _ = fetch_subject_attendance(session, start, end)
    return jsonify(subjects)


@app.route("/overall-attendance", methods=["POST"])
def overall_attendance():
    data = request.json
    session = login_erp(data["erp_id"], data["password"])
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401

    start, end = fetch_attendance_dates(session)
    _, overall = fetch_subject_attendance(session, start, end)
    return jsonify(overall)

@app.route("/timetable", methods=["POST"])
def timetable():
    data = request.json
    session = login_erp(data["erp_id"], data["password"])
    if not session:
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify(fetch_weekly_timetable(session))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
