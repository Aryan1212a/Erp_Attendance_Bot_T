import requests
from bs4 import BeautifulSoup

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
    overall = data[-1]  # last row = total
    subjects = data[:-1]
    return subjects, overall
