import streamlit as st
import sqlite3
import uuid
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
st.set_page_config(
    page_title="SchoolOS Pro",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------- DATABASE ----------------
@st.cache_resource
def get_db_connection():
    conn = sqlite3.connect('schoolos.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS schools (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    pass TEXT,
                    plan TEXT,
                    expiry TEXT,
                    extra_students INTEGER DEFAULT 0
                 )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    blood TEXT,
                    allergy TEXT,
                    school_id TEXT,
                    FOREIGN KEY(school_id) REFERENCES schools(id)
                 )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    msg TEXT,
                    date TEXT
                 )''')
    
    conn.commit()
    conn.close()

init_db()  # Run once when app starts

# ---------------- SESSION STATE ----------------
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}

# ---------------- LOGIN PAGE ----------------
if not st.session_state.auth["logged_in"]:
    st.title("🏫 SchoolOS Pro")
    st.markdown("### Login to your School Dashboard")
    
    user = st.text_input("User ID (School ID or admin)")
    pw = st.text_input("Password", type="password")
    
    if st.button("🔑 Login", type="primary"):
        conn = get_db_connection()
        c = conn.cursor()
        
        if user == "admin" and pw == "admin123":
            st.session_state.auth = {"logged_in": True, "role": "admin"}
            st.rerun()
        
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
            st.error("❌ Invalid User ID or Password")

# ---------------- MAIN APP (After Login) ----------------
else:
    if st.sidebar.button("🚪 Logout"):
        st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}
        st.rerun()

    # ADMIN DASHBOARD
    if st.session_state.auth["role"] == "admin":
        st.title("👑 Admin Command Center")
        tab1, tab2 = st.tabs(["➕ Add New School", "📢 Broadcast Message"])
        
        with tab1:
            st.subheader("Onboard New School")
            sid = st.text_input("School ID (example: school_01)")
            name = st.text_input("School Name")
            pw = st.text_input("Password for school")
            plan = st.selectbox("Choose Plan", ["Basic", "Standard", "Premium", "Enterprise"])
            
            if st.button("✅ Create School Account"):
                conn = get_db_connection()
                c = conn.cursor()
                expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
                c.execute("INSERT OR REPLACE INTO schools VALUES (?, ?, ?, ?, ?, ?)",
                          (sid, name, pw, plan, expiry, 0))
                conn.commit()
                conn.close()
                st.success(f"🎉 School '{name}' created successfully!")

        with tab2:
            st.subheader("Send Broadcast to All Schools")
            msg = st.text_area("Message content")
            if st.button("📡 Send to All Schools"):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT INTO broadcasts (msg, date) VALUES (?, ?)",
                          (msg, str(datetime.now())))
                conn.commit()
                conn.close()
                st.success("Broadcast sent successfully!")

    # SCHOOL DASHBOARD
    elif st.session_state.auth["role"] == "school":
        sid = st.session_state.auth["school_id"]
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM schools WHERE id = ?", (sid,))
        school = c.fetchone()
        conn.close()

        st.title(f"🏫 {school['name']}")

        PLAN_LIMITS = {"Basic": 30, "Standard": 80, "Premium": 500, "Enterprise": float('inf')}
        base = PLAN_LIMITS[school["plan"]]
        max_students = base if base == float('inf') else base + (school["extra_students"] * 50)

        # Student count
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM students WHERE school_id = ?", (sid,))
        student_count = c.fetchone()["cnt"]
        conn.close()

        st.sidebar.success(f"Plan: {school['plan']}")
        st.sidebar.info(f"Students: {student_count} / {max_students}")

        menu = st.sidebar.selectbox("Menu", ["📊 Dashboard", "👦 Students", "💎 Upgrade Plan"])

        if menu == "📊 Dashboard":
            st.metric("Total Students", student_count)
            st.metric("Current Plan", school["plan"])
            
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM broadcasts ORDER BY id DESC LIMIT 1")
            latest = c.fetchone()
            conn.close()
            if latest:
                st.warning(f"📢 Latest Broadcast: {latest['msg']}")

        elif menu == "👦 Students":
            st.subheader("Manage Students")
            
            with st.form("add_student"):
                name = st.text_input("Student Full Name")
                blood = st.selectbox("Blood Group", ["O+", "A+", "B+", "AB+"])
                allergy = st.text_input("Allergies (if any)")
                submitted = st.form_submit_button("Add Student")
                
                if submitted:
                    if student_count >= max_students:
                        st.error("Student limit reached! Please upgrade your plan.")
                    else:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("SELECT 1 FROM students WHERE name = ? AND school_id = ?", (name, sid))
                        if c.fetchone():
                            st.warning("Student already exists!")
                        else:
                            student_id = str(uuid.uuid4())
                            c.execute("INSERT INTO students VALUES (?, ?, ?, ?, ?)",
                                      (student_id, name, blood, allergy, sid))
                            conn.commit()
                            conn.close()
                            st.success("Student added successfully!")
                            st.rerun()

            st.write("### Current Students")
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM students WHERE school_id = ?", (sid,))
            students = c.fetchall()
            conn.close()

            for s in students:
                col1, col2 = st.columns([4, 1])
                col1.write(f"**{s['name']}** ({s['blood']}) — Allergies: {s['allergy'] or 'None'}")
                if col2.button("🗑️ Delete", key=s['id']):
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("DELETE FROM students WHERE id = ?", (s['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()

        elif menu == "💎 Upgrade Plan":
            st.subheader("Upgrade Your Plan")
            PLAN_PRICES = {"Basic": 2000, "Standard": 4000, "Premium": 7999, "Enterprise": 9999}
            
            for p, price in PLAN_PRICES.items():
                st.write(f"**{p}** → ₹{price}/year")
            
            new_plan = st.selectbox("Select New Plan", list(PLAN_PRICES.keys()))
            if st.button("Upgrade Plan Now"):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("UPDATE schools SET plan = ? WHERE id = ?", (new_plan, sid))
                conn.commit()
                conn.close()
                st.success("Plan upgraded successfully!")
                st.rerun()

            st.divider()
            add_option = st.selectbox("Add Extra Capacity", ["+50 students", "+100 students"])
            if st.button("Add Extra Capacity"):
                extra_add = 1 if "+50" in add_option else 2
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("UPDATE schools SET extra_students = extra_students + ? WHERE id = ?", (extra_add, sid))
                conn.commit()
                conn.close()
                st.success("Capacity increased!")
                st.rerun()
