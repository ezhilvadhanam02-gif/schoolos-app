# ================= SCHOOLOS PRO - PHASE 2 (FIXED + DATABASE HEALTH) =================
import streamlit as st
import sqlite3
import uuid
from datetime import datetime, timedelta
import os

# ---------------- CONFIG ----------------
st.set_page_config(page_title="SchoolOS Pro", layout="wide", page_icon="🏫")

# ---------------- DATABASE ----------------
@st.cache_resource
def get_db():
    conn = sqlite3.connect("schoolos.db", check_same_thread=False, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

def run_query(query: str, params=(), fetch=False):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(query, params)
        if fetch:
            return cur.fetchall()
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Database error: {e}")
        return [] if fetch else False

# ---------------- INIT DB ----------------
def init_db():
    run_query("""CREATE TABLE IF NOT EXISTS schools (
        id TEXT PRIMARY KEY, name TEXT, pass TEXT, plan TEXT, 
        expiry TEXT, extra_students INTEGER DEFAULT 0
    )""")
    run_query("""CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY, name TEXT, blood TEXT, allergy TEXT,
        parent_name TEXT, parent_phone TEXT, likes TEXT, dislikes TEXT,
        siblings TEXT, class TEXT, school_id TEXT
    )""")
    run_query("""CREATE TABLE IF NOT EXISTS fees (
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT,
        amount INTEGER, month TEXT, status TEXT, payment_date TEXT, school_id TEXT
    )""")
    run_query("""CREATE TABLE IF NOT EXISTS broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, msg TEXT, date TEXT
    )""")
    run_query("""CREATE TABLE IF NOT EXISTS inventory (
        id TEXT PRIMARY KEY, item_name TEXT, category TEXT,
        quantity INTEGER, min_quantity INTEGER, school_id TEXT
    )""")
    run_query("""CREATE TABLE IF NOT EXISTS care_logs (
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT,
        activity TEXT, notes TEXT, time TEXT, school_id TEXT
    )""")

init_db()

# ---------------- PRICING ----------------
PLAN_LIMITS = {"Basic": 30, "Standard": 80, "Premium": 500, "Enterprise": float("inf")}
PLAN_PRICES = {"Basic": 2000, "Standard": 4000, "Premium": 7999, "Enterprise": 9999}

# ---------------- SESSION ----------------
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}

# ---------------- LOGIN ----------------
if not st.session_state.auth["logged_in"]:
    st.title("🏫 SchoolOS Pro")
    user = st.text_input("User ID")
    pw = st.text_input("Password", type="password")
    
    if st.button("Login", type="primary"):
        if user == "admin" and pw == "admin123":
            st.session_state.auth = {"logged_in": True, "role": "admin"}
            st.rerun()
        
        school = run_query("SELECT * FROM schools WHERE id=? AND pass=?", (user, pw), fetch=True)
        if school:
            school = school[0]
            expiry = datetime.strptime(school["expiry"], "%Y-%m-%d")
            if datetime.now() < expiry:
                st.session_state.auth = {"logged_in": True, "role": "school", "school_id": user}
                st.rerun()
            else:
                st.error("Subscription expired")
        else:
            st.error("Invalid User ID or Password")

# ---------------- MAIN APP ----------------
else:
    if st.sidebar.button("Logout"):
        st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}
        st.rerun()

    # ================= ADMIN =================
    if st.session_state.auth["role"] == "admin":
        st.title("👑 Admin Dashboard")
        tab1, tab2, tab3, tab4 = st.tabs(["Add School", "Broadcast", "Revenue", "🔍 Database Health"])

        with tab1:
            st.subheader("Create New School")
            with st.form("create_school_form"):
                sid = st.text_input("School ID")
                name = st.text_input("School Name")
                pw = st.text_input("Password (plain text)")
                plan = st.selectbox("Plan", list(PLAN_LIMITS.keys()))
                
                if st.form_submit_button("Create School", type="primary"):
                    exists = run_query("SELECT * FROM schools WHERE id=?", (sid,), fetch=True)
                    if exists:
                        st.warning("School ID already exists!")
                    else:
                        expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
                        success = run_query(
                            "INSERT INTO schools VALUES (?, ?, ?, ?, ?, ?)",
                            (sid, name, pw, plan, expiry, 0)
                        )
                        if success:
                            st.success(f"✅ School Created!")
                            st.info(f"**Login Credentials:**\nUser ID: `{sid}`\nPassword: `{pw}`")
                            st.rerun()

        with tab2:
            msg = st.text_area("Message")
            if st.button("Send Broadcast", type="primary"):
                run_query("INSERT INTO broadcasts (msg, date) VALUES (?, ?)", (msg, str(datetime.now())))
                st.success("Broadcast sent!")

        with tab3:
            schools = run_query("SELECT * FROM schools", fetch=True)
            total = len(schools)
            active = sum(1 for s in schools if datetime.now() < datetime.strptime(s["expiry"], "%Y-%m-%d"))
            revenue = sum(PLAN_PRICES.get(s["plan"], 0) for s in schools)
            st.metric("Total Schools", total)
            st.metric("Active Schools", active)
            st.metric("Revenue", f"₹{revenue}")

        # ====================== NEW: DATABASE HEALTH ======================
        with tab4:
            st.subheader("🔍 Database Health Check")
            if st.button("Check Database Now"):
                st.write(f"**Database file exists:** {'✅ Yes' if os.path.exists('schoolos.db') else '❌ No'}")
                
                conn = get_db()
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cur.fetchall()]
                st.write(f"**Tables found:** {tables}")
                
                for t in tables:
                    cur.execute(f"SELECT COUNT(*) FROM {t}")
                    count = cur.fetchone()[0]
                    st.write(f"Table `{t}` → **{count}** rows")
                
                st.success("Database check completed!")
                conn.close()

            if st.button("🗑️ Reset Database (Delete & Recreate)", type="secondary"):
                if os.path.exists("schoolos.db"):
                    os.remove("schoolos.db")
                    st.success("Database deleted!")
                    init_db()
                    st.success("Fresh database created!")
                    st.rerun()

    # ================= SCHOOL =================
    else:
        # (Your original school code - unchanged)
        sid = st.session_state.auth["school_id"]
        school_data = run_query("SELECT * FROM schools WHERE id=?", (sid,), fetch=True)
        if not school_data:
            st.error("School not found")
            st.stop()
        school = school_data[0]
        st.title(f"🏫 {school['name']}")
        # ... (rest of your school menus remain exactly as before)

st.caption("SchoolOS Pro • Phase 2 Fixed + Database Health")
