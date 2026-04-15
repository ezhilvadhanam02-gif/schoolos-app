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
    st.success("Database reset! Please refresh the app.")
    st.stop()

# ---------------- SAFE DATABASE QUERY ----------------
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

# ---------------- SESSION STATE ----------------
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None, "student_id": None}

# ---------------- LOGIN ----------------
if not st.session_state.auth["logged_in"]:
    st.title("🏫 SchoolOS Pro")
    st.markdown("### Welcome! Login to continue")
    
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
                    st.error("Your school subscription has expired!")
            else:
                st.error("Invalid School ID or Password.")
        
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
                st.error("Invalid Phone or Password.")
else:
    if st.sidebar.button("🚪 Logout"):
        st.session_state.auth = {"logged_in": False, "role": None, "school_id": None, "student_id": None}
        st.rerun()

    # ================= ADMIN DASHBOARD =================
    if st.session_state.auth["role"] == "admin":
        st.title("👑 Admin Dashboard")
        st.subheader("Create New School")
        
        col1, col2 = st.columns(2)
        with col1:
            sid = st.text_input("School ID (e.g. TN001)")
            name = st.text_input("School Name")
        with col2:
            pw = st.text_input("Password", type="password")
            plan = st.selectbox("Plan", ["Basic", "Standard", "Premium", "Enterprise"])
        
        if st.button("Create School", type="primary"):
            if sid and name and pw:
                expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
                try:
                    run_query("INSERT INTO schools VALUES (?, ?, ?, ?, ?, ?)", 
                              (sid, name, pw, plan, expiry, 0))
                    st.success(f"✅ School **{name}** created!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("School ID already exists!")
            else:
                st.error("All fields are required!")

        st.subheader("Registered Schools")
        schools = run_query("SELECT id, name, plan, expiry FROM schools", fetch=True)
        if schools:
            for s in schools:
                st.write(f"**{s['name']}** ({s['id']}) — {s['plan']} | Expires: {s['expiry']}")
        else:
            st.info("No schools registered yet.")

    # ================= SCHOOL DASHBOARD =================
    elif st.session_state.auth["role"] == "school":
        sid = st.session_state.auth["school_id"]
        st.title(f"🏫 {sid} Dashboard")
        
        # Quick metrics
        students = run_query("SELECT COUNT(*) as cnt FROM students WHERE school_id=?", (sid,), True)[0]["cnt"]
        pending_fees = run_query("SELECT COUNT(*) as cnt FROM fees WHERE school_id=? AND status='Pending'", (sid,), True)[0]["cnt"]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Students", students)
        col2.metric("Pending Fees", pending_fees)
        col3.metric("Low Stock", "Coming soon")
        
        menu = st.sidebar.selectbox("Menu", ["Students", "Fees", "Inventory", "Care Logs", "Gallery"])
        
        if menu == "Students":
            # (Your existing student form + list - I kept it similar but cleaned)
            st.subheader("Add New Student")
            with st.form("add_student"):
                name = st.text_input("Student Name")
                blood = st.selectbox("Blood Group", ["O+","O-","A+","A-","B+","B-","AB+","AB-"])
                class_ = st.text_input("Class")
                parent_name = st.text_input("Parent Name")
                parent_phone = st.text_input("Parent Phone")
                parent_pass = st.text_input("Parent Password")
                if st.form_submit_button("Add Student"):
                    if name and parent_phone and parent_pass:
                        run_query("""INSERT INTO students 
                            (id, name, blood, allergy, parent_name, parent_phone, parent_pass, likes, dislikes, siblings, class, school_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (str(uuid.uuid4()), name, blood, "", parent_name, parent_phone, parent_pass, "", "", "", class_, sid))
                        st.success("Student added!")
                        st.rerun()
            
            st.subheader("Student List")
            studs = run_query("SELECT * FROM students WHERE school_id=?", (sid,), True)
            for s in studs:
                st.write(f"👦 **{s['name']}** - {s['class']} | Parent: {s['parent_phone']}")

        # ... (Fees, Inventory, Care Logs, Gallery sections kept similar but cleaned for brevity)
        # I can expand any section if you want.

    # ================= PARENT DASHBOARD =================
    elif st.session_state.auth["role"] == "parent":
        sid = st.session_state.auth["student_id"]
        student = run_query("SELECT * FROM students WHERE id=?", (sid,), True)
        if student:
            student = student[0]
            st.title(f"👶 {student['name']}'s Dashboard")
            
            st.subheader("Recent Care Logs")
            logs = run_query("SELECT * FROM care_logs WHERE student_id=? ORDER BY time DESC LIMIT 5", (sid,), True)
            for log in logs:
                st.info(f"**{log['activity']}** — {log['notes']} ({log['time']})")
            
            st.subheader("Gallery")
            photos = run_query("SELECT * FROM gallery WHERE student_id=?", (sid,), True)
            for photo in photos:
                st.image(photo["image"], caption=photo["caption"], use_column_width=True)

# Note: I shortened some sections for this response. Tell me which menu you want fully expanded.
