import streamlit as st
import sqlite3
import uuid
import os
from datetime import datetime, timedelta

# ====================== CONFIG ======================
st.set_page_config(
    page_title="SchoolOS Pro",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================== DATABASE ======================
def get_db_connection():
    conn = sqlite3.connect('schoolos.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Schools Table
    c.execute('''CREATE TABLE IF NOT EXISTS schools (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    pass TEXT,
                    plan TEXT,
                    expiry TEXT,
                    extra_students INTEGER DEFAULT 0
                 )''')
    
    # Students Table
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    blood TEXT,
                    allergy TEXT,
                    school_id TEXT,
                    FOREIGN KEY(school_id) REFERENCES schools(id)
                 )''')
    
    # Broadcasts Table
    c.execute('''CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    msg TEXT,
                    date TEXT
                 )''')
    
    conn.commit()
    conn.close()

init_db()

# ====================== SESSION STATE ======================
if "auth" not in st.session_state:
    st.session_state.auth = {
        "logged_in": False,
        "role": None,
        "school_id": None
    }

# Safe alias
auth = st.session_state.auth

# ====================== HELPER FUNCTIONS ======================
def run_query(query, params=(), fetch=False):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(query, params)
    
    if fetch:
        result = c.fetchall()
        conn.close()
        return result
    else:
        conn.commit()
        conn.close()
        return None

# ====================== ONE-TIME JSON MIGRATION ======================
def migrate_from_json():
    if not os.path.exists('schools.json') and not os.path.exists('students.json'):
        st.warning("No JSON files found for migration.")
        return
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Migrate Schools
    if os.path.exists('schools.json'):
        try:
            with open('schools.json', 'r') as f:
                schools_data = json.load(f)  # Note: import json at top if needed
            for sid, data in schools_data.items():
                c.execute("""INSERT OR IGNORE INTO schools 
                            (id, name, pass, plan, expiry, extra_students) 
                            VALUES (?, ?, ?, ?, ?, ?)""",
                          (sid, data.get('name'), data.get('pass'), 
                           data.get('plan', 'Basic'), data.get('expiry'), 
                           data.get('extra_students', 0)))
        except Exception as e:
            st.error(f"School migration error: {e}")

    # Migrate Students
    if os.path.exists('students.json'):
        try:
            with open('students.json', 'r') as f:
                students_data = json.load(f)
            for stu in students_data:
                student_id = stu.get('id') or str(uuid.uuid4())
                school_id = stu.get('school') or stu.get('school_id')
                if school_id:
                    c.execute("""INSERT OR IGNORE INTO students 
                                (id, name, blood, allergy, school_id) 
                                VALUES (?, ?, ?, ?, ?)""",
                              (student_id, stu.get('name'), 
                               stu.get('blood') or stu.get('bg', 'O+'),
                               stu.get('allergies') or stu.get('allergy', ''),
                               school_id))
        except Exception as e:
            st.error(f"Student migration error: {e}")

    conn.commit()
    conn.close()
    st.success("✅ Data migration completed successfully!")

# ====================== LOGIN PAGE ======================
if not auth.get("logged_in", False):
    st.title("🏫 SchoolOS Pro")
    st.markdown("### Login to your School Workspace")
    
    user = st.text_input("User ID")
    pw = st.text_input("Password", type="password")
    
    if st.button("🔑 Secure Login", type="primary", use_container_width=True):
        if user == "admin" and pw == "admin123":
            st.session_state.auth = {"logged_in": True, "role": "admin", "school_id": None}
            st.rerun()
        
        # School Login
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM schools WHERE id = ? AND pass = ?", (user, pw))
        school = c.fetchone()
        conn.close()
        
        if school:
            expiry = datetime.strptime(school["expiry"], "%Y-%m-%d")
            if datetime.now() < expiry:
                st.session_state.auth = {
                    "logged_in": True,
                    "role": "school",
                    "school_id": user
                }
                st.rerun()
            else:
                st.error("❌ Subscription expired. Contact admin.")
        else:
            st.error("❌ Invalid credentials.")

# ====================== MAIN APP ======================
else:
    if st.sidebar.button("🚪 Logout"):
        st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}
        st.rerun()

    # ---------------- ADMIN DASHBOARD ----------------
    if auth["role"] == "admin":
        st.title("👑 Admin Command Center")
        tab1, tab2, tab3 = st.tabs(["Onboard School", "Broadcast", "Migration"])

        with tab1:
            st.subheader("Create New School")
            col1, col2 = st.columns(2)
            with col1:
                sid = st.text_input("School ID (e.g. TN001)")
                name = st.text_input("School Name")
            with col2:
                pw = st.text_input("Password", type="password")
                plan = st.selectbox("Plan", ["Basic", "Standard", "Premium", "Enterprise"])
            
            if st.button("✅ Create School", type="primary"):
                if sid and name and pw:
                    expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
                    run_query("INSERT OR IGNORE INTO schools VALUES (?, ?, ?, ?, ?, ?)",
                              (sid, name, pw, plan, expiry, 0))
                    st.success(f"School **{name}** created successfully!")
                    st.rerun()
                else:
                    st.error("All fields are required.")

        with tab2:
            st.subheader("Global Broadcast")
            msg = st.text_area("Message to all schools")
            if st.button("📢 Send Broadcast"):
                run_query("INSERT INTO broadcasts (msg, date) VALUES (?, ?)",
                          (msg, str(datetime.now())))
                st.success("Broadcast sent to all schools!")

        with tab3:
            st.subheader("Data Migration")
            st.info("Use this only once to import data from old JSON files.")
            if st.button("🚀 Migrate Old JSON Data"):
                migrate_from_json()

    # ---------------- SCHOOL DASHBOARD ----------------
    elif auth["role"] == "school":
        sid = auth["school_id"]
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM schools WHERE id = ?", (sid,))
        school = c.fetchone()
        conn.close()

        st.title(f"🏫 {school['name']}")

        PLAN_LIMITS = {"Basic": 30, "Standard": 80, "Premium": 500, "Enterprise": float('inf')}
        base = PLAN_LIMITS.get(school["plan"], 30)
        max_students = base if base == float('inf') else base + (school["extra_students"] * 50)

        # Student count
        student_count = run_query("SELECT COUNT(*) as cnt FROM students WHERE school_id = ?", 
                                  (sid,), fetch=True)[0]["cnt"]

        st.sidebar.info(f"Plan: **{school['plan']}**\n\nStudents: **{student_count} / {max_students}**")

        menu = st.sidebar.selectbox("Menu", ["📊 Dashboard", "👦 Students", "💎 Upgrade Plan"])

        if menu == "📊 Dashboard":
            col1, col2 = st.columns(2)
            col1.metric("Total Students", student_count)
            col2.metric("Current Plan", school["plan"])
            
            latest = run_query("SELECT msg FROM broadcasts ORDER BY id DESC LIMIT 1", fetch=True)
            if latest:
                st.warning(f"📢 {latest[0]['msg']}")

        elif menu == "👦 Students":
            st.subheader("Add New Student")
            with st.form("add_student"):
                name = st.text_input("Full Name")
                blood = st.selectbox("Blood Group", ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"])
                allergy = st.text_input("Allergies / Medical Notes")
                submitted = st.form_submit_button("Add Student")
                
                if submitted:
                    if student_count >= max_students:
                        st.error("Student limit reached! Please upgrade your plan.")
                    else:
                        exists = run_query("SELECT 1 FROM students WHERE name = ? AND school_id = ?", 
                                           (name, sid), fetch=True)
                        if exists:
                            st.warning("Student with this name already exists!")
                        else:
                            student_id = str(uuid.uuid4())
                            run_query("INSERT INTO students VALUES (?, ?, ?, ?, ?)",
                                      (student_id, name, blood, allergy, sid))
                            st.success("Student added successfully!")
                            st.rerun()

            st.subheader("Student List")
            students = run_query("SELECT * FROM students WHERE school_id = ?", (sid,), fetch=True)
            for s in students:
                col1, col2 = st.columns([5, 1])
                col1.write(f"**{s['name']}** ({s['blood']}) — Allergy: {s['allergy'] or 'None'}")
                if col2.button("Delete", key=s['id']):
                    run_query("DELETE FROM students WHERE id = ?", (s['id'],))
                    st.rerun()

        elif menu == "💎 Upgrade Plan":
            st.subheader("Upgrade Your Plan")
            PLAN_PRICES = {"Basic": 2000, "Standard": 4000, "Premium": 7999, "Enterprise": 9999}
            for p, price in PLAN_PRICES.items():
                st.write(f"**{p}** → ₹{price}/year")
            
            new_plan = st.selectbox("Select New Plan", list(PLAN_PRICES.keys()))
            if st.button("Upgrade Plan"):
                run_query("UPDATE schools SET plan = ? WHERE id = ?", (new_plan, sid))
                st.success("Plan upgraded successfully!")
                st.rerun()

            st.divider()
            add_option = st.selectbox("Add Extra Capacity", ["+50 students", "+100 students"])
            if st.button("Add Extra Capacity"):
                extra_add = 1 if "+50" in add_option else 2
                run_query("UPDATE schools SET extra_students = extra_students + ? WHERE id = ?", 
                          (extra_add, sid))
                st.success("Capacity increased!")
                st.rerun()

# Footer
st.caption("SchoolOS Pro • Built for Indian Preschools & Daycares")
