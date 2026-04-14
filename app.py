import streamlit as st
import sqlite3
import uuid
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
st.set_page_config(page_title="SchoolOS Pro", layout="wide")

# ---------------- DATABASE ----------------
@st.cache_resource
def get_db():
    conn = sqlite3.connect("schoolos.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def run_query(query, params=(), fetch=False):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(query, params)
    if fetch:
        return cur.fetchall()
    conn.commit()

# ---------------- INIT DB ----------------
def init_db():
    run_query("""
    CREATE TABLE IF NOT EXISTS schools (
        id TEXT PRIMARY KEY,
        name TEXT,
        pass TEXT,
        plan TEXT,
        expiry TEXT,
        extra_students INTEGER DEFAULT 0
    )
    """)

    run_query("""
    CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY,
        name TEXT,
        blood TEXT,
        allergy TEXT,
        school_id TEXT
    )
    """)

    run_query("""
    CREATE TABLE IF NOT EXISTS broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        msg TEXT,
        date TEXT
    )
    """)

    run_query("""
    CREATE TABLE IF NOT EXISTS fees (
        id TEXT PRIMARY KEY,
        student_id TEXT,
        student_name TEXT,
        amount INTEGER,
        month TEXT,
        status TEXT,
        payment_date TEXT,
        school_id TEXT
    )
    """)

init_db()

# ---------------- PRICING ----------------
PLAN_LIMITS = {
    "Basic": 30,
    "Standard": 80,
    "Premium": 500,
    "Enterprise": float("inf")
}

PLAN_PRICES = {
    "Basic": 2000,
    "Standard": 4000,
    "Premium": 7999,
    "Enterprise": 9999
}

# ---------------- SESSION ----------------
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}

# ---------------- LOGIN ----------------
if not st.session_state.auth["logged_in"]:
    st.title("🏫 SchoolOS Pro")

    user = st.text_input("User ID")
    pw = st.text_input("Password", type="password")

    if st.button("Login"):
        if user == "admin" and pw == "admin123":
            st.session_state.auth = {"logged_in": True, "role": "admin"}
            st.rerun()

        school = run_query(
            "SELECT * FROM schools WHERE id=? AND pass=?",
            (user, pw),
            fetch=True
        )

        if school:
            school = school[0]
            expiry = datetime.strptime(school["expiry"], "%Y-%m-%d")

            if datetime.now() < expiry:
                st.session_state.auth = {
                    "logged_in": True,
                    "role": "school",
                    "school_id": user
                }
                st.rerun()
            else:
                st.error("Subscription expired")
        else:
            st.error("Invalid credentials")

# ---------------- MAIN ----------------
else:

    if st.sidebar.button("Logout"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

    # ================= ADMIN =================
    if st.session_state.auth["role"] == "admin":
        st.title("👑 Admin Dashboard")

        tab1, tab2, tab3 = st.tabs(["Add School", "Broadcast", "Revenue"])

        # ---- ADD SCHOOL ----
        with tab1:
            sid = st.text_input("School ID")
            name = st.text_input("School Name")
            pw = st.text_input("Password")
            plan = st.selectbox("Plan", list(PLAN_LIMITS.keys()))

            if st.button("Create School"):
                exists = run_query(
                    "SELECT * FROM schools WHERE id=?",
                    (sid,),
                    fetch=True
                )

                if exists:
                    st.warning("School ID already exists!")
                else:
                    expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

                    run_query(
                        "INSERT INTO schools VALUES (?, ?, ?, ?, ?, ?)",
                        (sid, name, pw, plan, expiry, 0)
                    )

                    st.success("School created!")

        # ---- BROADCAST ----
        with tab2:
            msg = st.text_area("Message")

            if st.button("Send"):
                run_query(
                    "INSERT INTO broadcasts (msg, date) VALUES (?, ?)",
                    (msg, str(datetime.now()))
                )
                st.success("Broadcast sent!")

        # ---- REVENUE ----
        with tab3:
            schools = run_query("SELECT * FROM schools", fetch=True)

            total = len(schools)

            active = sum(
                1 for s in schools
                if datetime.now() < datetime.strptime(s["expiry"], "%Y-%m-%d")
            )

            revenue = sum(PLAN_PRICES[s["plan"]] for s in schools)

            st.metric("Total Schools", total)
            st.metric("Active Schools", active)
            st.metric("Projected Revenue", f"₹{revenue}")

    # ================= SCHOOL =================
    elif st.session_state.auth["role"] == "school":

        sid = st.session_state.auth["school_id"]

        school = run_query(
            "SELECT * FROM schools WHERE id=?",
            (sid,),
            fetch=True
        )[0]

        st.title(f"🏫 {school['name']}")

        base = PLAN_LIMITS[school["plan"]]
        max_students = base if base == float("inf") else base + (school["extra_students"] * 50)

        students = run_query(
            "SELECT * FROM students WHERE school_id=?",
            (sid,),
            fetch=True
        )

        st.sidebar.info(f"""
Plan: {school['plan']}
Students: {len(students)} / {max_students}
        """)

        menu = st.sidebar.selectbox("Menu", ["Dashboard", "Students", "Fees", "Upgrade"])

        # -------- DASHBOARD --------
        if menu == "Dashboard":
            st.metric("Students", len(students))
            st.metric("Plan", school["plan"])

            latest = run_query(
                "SELECT * FROM broadcasts ORDER BY id DESC LIMIT 1",
                fetch=True
            )

            if latest:
                msg = latest[0]["msg"]
                if "🚨" in msg:
                    st.error(msg)
                else:
                    st.warning(msg)

        # -------- STUDENTS --------
        elif menu == "Students":

            with st.form("add_student"):
                name = st.text_input("Name")
                blood = st.selectbox("Blood", ["O+", "A+", "B+", "AB+"])
                allergy = st.text_input("Allergy")

                if st.form_submit_button("Add"):

                    if len(students) >= max_students:
                        st.error("Limit reached!")
                    else:
                        exists = run_query(
                            "SELECT * FROM students WHERE name=? AND school_id=?",
                            (name, sid),
                            fetch=True
                        )

                        if exists:
                            st.warning("Student exists!")
                        else:
                            run_query(
                                "INSERT INTO students VALUES (?, ?, ?, ?, ?)",
                                (str(uuid.uuid4()), name, blood, allergy, sid)
                            )
                            st.success("Added!")
                            st.rerun()

            st.write("### Student List")

            for s in students:
                col1, col2 = st.columns([4,1])
                col1.write(f"{s['name']} ({s['blood']})")

                if col2.button("Delete", key=s["id"]):
                    run_query("DELETE FROM students WHERE id=?", (s["id"],))
                    st.rerun()

        # -------- FEES --------
        elif menu == "Fees":
            st.subheader("💰 Fee Management")

            student_map = {s["name"]: s["id"] for s in students}

            with st.form("fee_form"):
                student_name = st.selectbox("Student", list(student_map.keys()))
                amount = st.number_input("Amount", min_value=0)
                month = st.selectbox("Month", ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])

                if st.form_submit_button("Add Fee"):
                    run_query(
                        "INSERT INTO fees VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            str(uuid.uuid4()),
                            student_map[student_name],
                            student_name,
                            amount,
                            month,
                            "Pending",
                            "",
                            sid
                        )
                    )
                    st.success("Fee added!")
                    st.rerun()

            fees = run_query(
                "SELECT * FROM fees WHERE school_id=?",
                (sid,),
                fetch=True
            )

            total = 0
            pending = 0

            for f in fees:
                col1, col2, col3, col4 = st.columns([2,2,2,1])

                col1.write(f["student_name"])
                col2.write(f"₹{f['amount']}")
                col3.write(f["month"])

                if f["status"] == "Pending":
                    if col4.button("Mark Paid", key=f["id"]):
                        run_query(
                            "UPDATE fees SET status=?, payment_date=? WHERE id=?",
                            ("Paid", str(datetime.now()), f["id"])
                        )
                        st.rerun()
                else:
                    col4.success("Paid")

                total += f["amount"]
                if f["status"] == "Pending":
                    pending += f["amount"]

            st.divider()
            st.metric("Total Fees", f"₹{total}")
            st.metric("Pending Fees", f"₹{pending}")

        # -------- UPGRADE --------
        elif menu == "Upgrade":

            for p, price in PLAN_PRICES.items():
                st.write(f"{p} - ₹{price}")

            new_plan = st.selectbox("Plan", list(PLAN_LIMITS.keys()))

            if st.button("Upgrade"):
                run_query(
                    "UPDATE schools SET plan=? WHERE id=?",
                    (new_plan, sid)
                )
                st.success("Updated!")
                st.rerun()

            st.write("### Add Capacity")

            add = st.selectbox("Add", ["+50", "+100"])

            if st.button("Add Students"):
                extra = 1 if add == "+50" else 2

                run_query(
                    "UPDATE schools SET extra_students = extra_students + ? WHERE id=?",
                    (extra, sid)
                )
                st.success("Added!")
                st.rerun()
