import streamlit as st
import sqlite3
import uuid
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="SchoolOS Pro", layout="wide")

# ---------------- RESET DB ----------------
if st.sidebar.button("⚠️ Reset Database"):
    if os.path.exists("schoolos.db"):
        os.remove("schoolos.db")
    st.success("Database reset! Refresh app.")
    st.stop()

# ---------------- DATABASE ----------------
@st.cache_resource
def get_db():
    conn = sqlite3.connect("schoolos.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def run_query(query, params=(), fetch=False):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        if fetch:
            return cur.fetchall()
        conn.commit()
    except sqlite3.IntegrityError:
        return None

# ---------------- INIT DB ----------------
def init_db():
    run_query("""CREATE TABLE IF NOT EXISTS schools (
        id TEXT PRIMARY KEY,
        name TEXT,
        pass TEXT,
        plan TEXT,
        expiry TEXT,
        extra_students INTEGER DEFAULT 0
    )""")

    run_query("""CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY,
        name TEXT,
        blood TEXT,
        allergy TEXT,
        parent_name TEXT,
        parent_phone TEXT,
        parent_pass TEXT,
        school_id TEXT
    )""")

    run_query("""CREATE TABLE IF NOT EXISTS fees (
        id TEXT PRIMARY KEY,
        student_id TEXT,
        student_name TEXT,
        amount INTEGER,
        month TEXT,
        status TEXT,
        payment_date TEXT,
        school_id TEXT
    )""")

    run_query("""CREATE TABLE IF NOT EXISTS care_logs (
        id TEXT PRIMARY KEY,
        student_id TEXT,
        student_name TEXT,
        activity TEXT,
        notes TEXT,
        time TEXT,
        school_id TEXT
    )""")

    run_query("""CREATE TABLE IF NOT EXISTS gallery (
        id TEXT PRIMARY KEY,
        student_id TEXT,
        student_name TEXT,
        caption TEXT,
        image BLOB,
        school_id TEXT
    )""")

init_db()

# ---------------- SESSION ----------------
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None, "student_id": None}

# ---------------- LOGIN ----------------
if not st.session_state.auth["logged_in"]:

    st.title("🏫 SchoolOS Pro")

    role = st.selectbox("Login As", ["School/Admin", "Parent"])
    user = st.text_input("User ID / Phone")
    pw = st.text_input("Password", type="password")

    if st.button("Login"):

        # ADMIN LOGIN
        if role == "School/Admin" and user == "admin" and pw == "admin123":
            st.session_state.auth = {"logged_in": True, "role": "admin"}
            st.rerun()

        # SCHOOL LOGIN
        school = run_query(
            "SELECT * FROM schools WHERE id=? AND pass=?",
            (user, pw), True
        )

        if role == "School/Admin" and school:
            school = school[0]
            if datetime.now() < datetime.strptime(school["expiry"], "%Y-%m-%d"):
                st.session_state.auth = {"logged_in": True, "role": "school", "school_id": user}
                st.rerun()
            else:
                st.error("Subscription expired")

        # PARENT LOGIN
        parent = run_query(
            "SELECT * FROM students WHERE parent_phone=? AND parent_pass=?",
            (user, pw), True
        )

        if role == "Parent" and parent:
            parent = parent[0]
            st.session_state.auth = {
                "logged_in": True,
                "role": "parent",
                "school_id": parent["school_id"],
                "student_id": parent["id"]
            }
            st.rerun()

        st.error("Invalid credentials")

# ---------------- MAIN ----------------
else:

    if st.sidebar.button("Logout"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

    # ================= ADMIN =================
    if st.session_state.auth["role"] == "admin":
        st.title("👑 Admin Dashboard")

        sid = st.text_input("School ID")
        name = st.text_input("School Name")
        pw = st.text_input("Password")
        plan = st.selectbox("Plan", ["Basic","Standard","Premium","Enterprise"])

        if st.button("Create School"):

            if not sid or not name or not pw:
                st.error("All fields required")
            else:
                existing = run_query("SELECT * FROM schools WHERE id=?", (sid,), True)

                if existing:
                    st.warning("School ID already exists")
                else:
                    expiry = (datetime.now()+timedelta(days=365)).strftime("%Y-%m-%d")

                    run_query(
                        "INSERT INTO schools VALUES (?, ?, ?, ?, ?, ?)",
                        (sid,name,pw,plan,expiry,0)
                    )
                    st.success("School created")

    # ================= SCHOOL =================
    elif st.session_state.auth["role"] == "school":
        sid = st.session_state.auth["school_id"]

        students = run_query(
            "SELECT * FROM students WHERE school_id=?",
            (sid,), True
        ) or []

        menu = st.sidebar.selectbox("Menu", ["Students","Fees","Care Logs","Gallery"])

        # -------- STUDENTS --------
        if menu == "Students":
            with st.form("student_form"):
                name = st.text_input("Student Name")
                blood = st.selectbox("Blood Group", ["O+","O-","A+","A-","B+","B-","AB+","AB-"])
                parent = st.text_input("Parent Name")
                phone = st.text_input("Parent Phone")
                ppass = st.text_input("Parent Password")

                if st.form_submit_button("Add Student"):
                    if name and phone:
                        run_query(
                            "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (str(uuid.uuid4()),name,blood,"",parent,phone,ppass,sid)
                        )
                        st.success("Student added")
                        st.rerun()
                    else:
                        st.error("Fill required fields")

            st.write("### Students")
            for s in students:
                st.write(f"{s['name']} | Parent: {s['parent_name']}")

        # -------- FEES --------
        elif menu == "Fees":
            student_map = {s["name"]: s["id"] for s in students}

            with st.form("fee_form"):
                st_name = st.selectbox("Student", list(student_map.keys()))
                amount = st.number_input("Amount", min_value=0)
                month = st.selectbox("Month", ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])

                if st.form_submit_button("Add Fee"):
                    run_query(
                        "INSERT INTO fees VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()),student_map[st_name],st_name,amount,month,"Pending","",sid)
                    )
                    st.success("Fee added")
                    st.rerun()

            fees = run_query("SELECT * FROM fees WHERE school_id=?", (sid,), True) or []

            for f in fees:
                col1, col2, col3 = st.columns(3)
                col1.write(f["student_name"])
                col2.write(f["month"])
                col3.write(f"{f['status']}")

        # -------- CARE LOGS --------
        elif menu == "Care Logs":
            student_map = {s["name"]: s["id"] for s in students}

            st_name = st.selectbox("Student", list(student_map.keys()))
            activity = st.selectbox("Activity", ["Meal","Sleep","Play","Toilet"])

            if st.button("Add Log"):
                run_query(
                    "INSERT INTO care_logs VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()),student_map[st_name],st_name,activity,"",str(datetime.now()),sid)
                )
                st.success("Log added")

        # -------- GALLERY --------
        elif menu == "Gallery":
            student_map = {s["name"]: s["id"] for s in students}

            st_name = st.selectbox("Student", list(student_map.keys()))
            img = st.file_uploader("Upload Image")

            if st.button("Upload"):
                if img:
                    run_query(
                        "INSERT INTO gallery VALUES (?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()),student_map[st_name],st_name,"",img.read(),sid)
                    )
                    st.success("Uploaded")

    # ================= PARENT =================
    elif st.session_state.auth["role"] == "parent":

        student_id = st.session_state.auth["student_id"]

        student = run_query("SELECT * FROM students WHERE id=?", (student_id,), True)[0]

        st.title(student["name"])
        st.write("Blood:", student["blood"])

        logs = run_query("SELECT * FROM care_logs WHERE student_id=?", (student_id,), True) or []
        for l in logs:
            st.write(l["activity"], l["time"])

        fees = run_query("SELECT * FROM fees WHERE student_id=?", (student_id,), True) or []
        for f in fees:
            st.write(f["month"], f["status"])

        imgs = run_query("SELECT * FROM gallery WHERE student_id=?", (student_id,), True) or []
        for i in imgs:
            st.image(i["image"])
