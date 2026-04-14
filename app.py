import streamlit as st
import sqlite3
import uuid
from datetime import datetime, timedelta

st.set_page_config(page_title="SchoolOS SaaS Pro", layout="wide", page_icon="🚀")

# ---------------- DATABASE ----------------
def run_query(q, p=(), fetch=False):
    conn = sqlite3.connect("schoolos.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(q, p)
    if fetch:
        data = cur.fetchall()
        conn.close()
        return data
    conn.commit()
    conn.close()

# ---------------- INIT ----------------
def init_db():
    run_query("""CREATE TABLE IF NOT EXISTS schools(
        id TEXT PRIMARY KEY, name TEXT, pass TEXT, plan TEXT, 
        expiry TEXT, extra_students INTEGER, revenue INTEGER
    )""")
    run_query("""CREATE TABLE IF NOT EXISTS students(
        id TEXT PRIMARY KEY, name TEXT, school_id TEXT
    )""")
    run_query("""CREATE TABLE IF NOT EXISTS fees(
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT, 
        amount INTEGER, status TEXT, date TEXT, school_id TEXT
    )""")
    run_query("""CREATE TABLE IF NOT EXISTS broadcasts(
        id TEXT PRIMARY KEY, msg TEXT, date TEXT
    )""")

if "db" not in st.session_state:
    init_db()
    st.session_state.db = True

# ---------------- LOGIN SESSION ----------------
if "auth" not in st.session_state:
    st.session_state.auth = {"login": False, "role": None, "sid": None}

if not st.session_state.auth["login"]:
    st.title("🏫 SchoolOS SaaS")
    col1, col2 = st.columns([1, 1])
    with col1:
        role = st.selectbox("Login As", ["Admin", "School"])
        user = st.text_input("ID / Username")
        pw = st.text_input("Password", type="password")

        if st.button("Login", use_container_width=True):
            if role == "Admin" and user == "admin" and pw == "admin123":
                st.session_state.auth = {"login": True, "role": "admin", "sid": "ADMIN"}
                st.rerun()

            school_data = run_query("SELECT * FROM schools WHERE id=? AND pass=?", (user, pw), True)
            if role == "School" and school_data:
                school = school_data[0]
                if datetime.now() > datetime.strptime(school["expiry"], "%Y-%m-%d"):
                    st.error("🚨 Subscription expired. Please contact Admin.")
                else:
                    st.session_state.auth = {"login": True, "role": "school", "sid": user}
                    st.rerun()
            else:
                st.error("Invalid credentials")

# ---------------- MAIN ----------------
else:
    if st.sidebar.button("Logout"):
        st.session_state.auth = {"login": False, "role": None, "sid": None}
        st.rerun()

    # ================= ADMIN DASHBOARD =================
    if st.session_state.auth["role"] == "admin":
        st.title("👑 SaaS Admin Dashboard")
        tabs = st.tabs(["Create School", "Revenue & Analytics", "Global Broadcast"])

        with tabs[0]:
            c1, c2 = st.columns(2)
            sid = c1.text_input("Unique School ID")
            name = c1.text_input("School Name")
            pw = c2.text_input("Initial Password")
            plan = c2.selectbox("SaaS Plan", ["Basic", "Standard", "Premium"])
            prices = {"Basic": 2000, "Standard": 4000, "Premium": 7999}

            if st.button("Deploy School Instance"):
                expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
                try:
                    run_query("INSERT INTO schools VALUES (?,?,?,?,?,?,?)", 
                              (sid, name, pw, plan, expiry, 0, prices[plan]))
                    st.success(f"Instance {sid} is live!")
                except:
                    st.warning("School ID already registered.")

        with tabs[1]:
            schools = run_query("SELECT * FROM schools", fetch=True)
            total_rev = sum(s["revenue"] for s in schools) if schools else 0
            st.metric("Annual Recurring Revenue (ARR)", f"₹{total_rev}")
            st.table(schools)

        with tabs[2]:
            msg = st.text_area("Announcement to all Schools")
            if st.button("Send Broadcast"):
                run_query("INSERT INTO broadcasts VALUES (?,?,?)", 
                          (str(uuid.uuid4()), msg, datetime.now().strftime("%Y-%m-%d %H:%M")))
                st.success("Message pushed to all dashboards.")

    # ================= SCHOOL DASHBOARD =================
    elif st.session_state.auth["role"] == "school":
        sid = st.session_state.auth["sid"]
        st.title(f"🏫 Dashboard: {sid}")

        # --- BROADCAST NEWS ---
        news = run_query("SELECT * FROM broadcasts ORDER BY date DESC LIMIT 1", fetch=True)
        if news:
            st.info(f"📣 **Admin Message:** {news[0]['msg']} ({news[0]['date']})")

        menu = st.sidebar.radio("Navigation", ["Students", "Fees & Billing"])

        if menu == "Students":
            with st.expander("➕ Add New Student"):
                s_name = st.text_input("Full Name")
                if st.button("Register Student"):
                    run_query("INSERT INTO students VALUES (?,?,?)", (str(uuid.uuid4()), s_name, sid))
                    st.success("Student added.")
                    st.rerun()

            st.subheader("Student Directory")
            students = run_query("SELECT * FROM students WHERE school_id=?", (sid,), True)
            if students:
                for s in students:
                    st.text(f"👤 {s['name']}")
            else:
                st.info("No students registered yet.")

        elif menu == "Fees & Billing":
            students = run_query("SELECT * FROM students WHERE school_id=?", (sid,), True)
            
            if not students:
                st.warning("Please add students first.")
            else:
                st_map = {s["name"]: s["id"] for s in students}
                col1, col2 = st.columns(2)
                st_name = col1.selectbox("Select Student", list(st_map.keys()))
                amt = col2.number_input("Amount (₹)", min_value=0)

                if st.button("Generate Invoice"):
                    run_query("INSERT INTO fees VALUES (?,?,?,?,?,?,?)",
                              (str(uuid.uuid4()), st_map[st_name], st_name, amt, "Pending", "", sid))
                    st.rerun()

            st.divider()
            fees = run_query("SELECT * FROM fees WHERE school_id=?", (sid,), True)
            for f in fees:
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.write(f"**{f['student_name']}**")
                c2.write(f"₹{f['amount']}")
                if f["status"] == "Pending":
                    if c3.button("Collect Payment", key=f["id"]):
                        run_query("UPDATE fees SET status=?, date=? WHERE id=?", 
                                  ("Paid", datetime.now().strftime("%Y-%m-%d"), f["id"]))
                        st.rerun()
                else:
                    c3.success("Paid")
