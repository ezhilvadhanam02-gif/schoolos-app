import streamlit as st
import sqlite3
import uuid
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="SchoolOS Pro", layout="wide", page_icon="🏫")

# ---------------- RESET DB (Demo only) ----------------
if st.sidebar.button("⚠️ Reset Database (Demo only)"):
    if os.path.exists("schoolos.db"):
        os.remove("schoolos.db")
    st.success("Database reset! Refresh the app.")
    st.stop()

# ---------------- SAFE QUERY FUNCTION ----------------
def run_query(query, params=(), fetch=False):
    conn = sqlite3.connect("schoolos.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, params)
    
    if fetch:
        result = cur.fetchall()
        conn.close()
        return result
    
    conn.commit()
    conn.close()
    return None

# ---------------- INIT DATABASE ----------------
def init_db():
    run_query("""CREATE TABLE IF NOT EXISTS schools (
        id TEXT PRIMARY KEY, name TEXT, pass TEXT, plan TEXT, expiry TEXT, extra_students INTEGER DEFAULT 0
    )""")
    
    run_query("""CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY, name TEXT, blood TEXT, allergy TEXT, parent_name TEXT, 
        parent_phone TEXT, parent_pass TEXT, likes TEXT, dislikes TEXT, siblings TEXT, 
        class TEXT, school_id TEXT
    )""")
    
    run_query("""CREATE TABLE IF NOT EXISTS fees (
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT, amount INTEGER, 
        month TEXT, status TEXT, payment_date TEXT, school_id TEXT
    )""")
    
    run_query("""CREATE TABLE IF NOT EXISTS inventory (
        id TEXT PRIMARY KEY, item_name TEXT, category TEXT, quantity INTEGER, 
        min_quantity INTEGER, school_id TEXT
    )""")
    
    run_query("""CREATE TABLE IF NOT EXISTS care_logs (
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT, activity TEXT, 
        notes TEXT, time TEXT, school_id TEXT
    )""")
    
    run_query("""CREATE TABLE IF NOT EXISTS gallery (
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT, caption TEXT, 
        image BLOB, school_id TEXT
    )""")

init_db()

# ---------------- SESSION ----------------
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None, "student_id": None}

# ---------------- LOGIN ----------------
if not st.session_state.auth["logged_in"]:
    st.title("🏫 SchoolOS Pro")
    st.markdown("### Login to your workspace")
    
    role = st.selectbox("Login As", ["School/Admin", "Parent"])
    user = st.text_input("User ID / Phone Number")
    pw = st.text_input("Password", type="password")
    
    if st.button("🔑 Login", type="primary", use_container_width=True):
        if role == "School/Admin":
            if user == "admin" and pw == "admin123":
                st.session_state.auth = {"logged_in": True, "role": "admin"}
                st.rerun()
            
            school_res = run_query("SELECT * FROM schools WHERE id=? AND pass=?", (user, pw), True)
            if school_res:
                school = school_res[0]
                if datetime.now() < datetime.strptime(school["expiry"], "%Y-%m-%d"):
                    st.session_state.auth = {"logged_in": True, "role": "school", "school_id": user}
                    st.rerun()
                else:
                    st.error("Subscription expired!")
            else:
                st.error("Invalid credentials.")
        
        elif role == "Parent":
            parent_res = run_query("SELECT * FROM students WHERE parent_phone=? AND parent_pass=?", (user, pw), True)
            if parent_res:
                parent = parent_res[0]
                st.session_state.auth = {
                    "logged_in": True,
                    "role": "parent",
                    "school_id": parent["school_id"],
                    "student_id": parent["id"]
                }
                st.rerun()
            else:
                st.error("Invalid phone or password.")
else:
    if st.sidebar.button("🚪 Logout"):
        st.session_state.auth = {"logged_in": False, "role": None, "school_id": None, "student_id": None}
        st.rerun()

    # ADMIN SECTION
    if st.session_state.auth["role"] == "admin":
        st.title("👑 Admin Dashboard")
        # ... (your admin code - keep as is or tell me if you want improvements)

    # SCHOOL SECTION
    elif st.session_state.auth["role"] == "school":
        sid = st.session_state.auth["school_id"]
        st.title(f"🏫 {sid} Dashboard")
        menu = st.sidebar.selectbox("Menu", ["Students", "Fees", "Inventory", "Care Logs", "Gallery"])
        # Your existing menu logic goes here...

    # PARENT SECTION
    elif st.session_state.auth["role"] == "parent":
        student_id = st.session_state.auth["student_id"]
        student = run_query("SELECT * FROM students WHERE id=?", (student_id,), True)
        if student:
            student = student[0]
            st.title(f"👶 {student['name']}'s Dashboard")
            # Your parent view code...

# Note: I kept the structure but you can paste your full sections back in.
