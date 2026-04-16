# ================= SCHOOLOS PRO - FINAL STABLE VERSION =================
import streamlit as st
import sqlite3
import uuid
from datetime import datetime, timedelta
import os
import bcrypt

# ---------------- CONFIG ----------------
st.set_page_config(page_title="SchoolOS Pro", layout="wide", page_icon="🏫")
DB_NAME = "schoolos.db"

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def run_query(query, params=(), fetch=False):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(query, params)

        if fetch:
            result = cur.fetchall()
            return result

        conn.commit()
        return True

    except Exception as e:
        st.error(f"Database error: {e}")
        return [] if fetch else False

    finally:
        conn.close()

# ---------------- PASSWORD ----------------
def hash_pw(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_pw(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

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
        likes TEXT,
        dislikes TEXT,
        siblings TEXT,
        class TEXT,
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

    run_query("""CREATE TABLE IF NOT EXISTS broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        msg TEXT,
        date TEXT
    )""")

    run_query("""CREATE TABLE IF NOT EXISTS inventory (
        id TEXT PRIMARY KEY,
        item_name TEXT,
        category TEXT,
        quantity INTEGER,
        min_quantity INTEGER,
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

init_db()

# ---------------- RESET DB SAFE ----------------
def reset_database():
    try:
        if os.path.exists(DB_NAME):
            os.remove(DB_NAME)
        init_db()
        st.success("✅ Database reset successfully!")
        st.rerun()
    except Exception as e:
        st.error(f"Reset failed: {e}")

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

        # ADMIN LOGIN
        if user == "admin":
            if pw == "admin123":
                st.session_state.auth = {"logged_in": True, "role": "admin", "school_id": None}
                st.rerun()
            else:
                st.error("Invalid admin credentials")
            st.stop()

        # SCHOOL LOGIN
        school = run_query("SELECT * FROM schools WHERE id=?", (user,), fetch=True)

        if school:
            school = school[0]

            if not check_pw(pw, school["pass"]):
                st.error("Invalid password")
                st.stop()

            expiry = datetime.strptime(school["expiry"], "%Y-%m-%d")

            if datetime.now() > expiry:
                st.error("Subscription expired")
                st.stop()

            st.session_state.auth = {
                "logged_in": True,
                "role": "school",
                "school_id": user
            }
            st.rerun()

        else:
            st.error("School not found")

# ---------------- MAIN APP ----------------
else:
    if st.sidebar.button("Logout"):
        st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}
        st.rerun()

    # ================= ADMIN =================
    if st.session_state.auth["role"] == "admin":
        st.title("👑 Admin Dashboard")

        tab1, tab2, tab3, tab4 = st.tabs([
            "Add School", "Broadcast", "Revenue", "Database"
        ])

        # CREATE SCHOOL
        with tab1:
            with st.form("create_school"):
                sid = st.text_input("School ID")
                name = st.text_input("School Name")
                pw = st.text_input("Password")
                plan = st.selectbox("Plan", list(PLAN_LIMITS.keys()))

                if st.form_submit_button("Create"):
                    exists = run_query("SELECT * FROM schools WHERE id=?", (sid,), fetch=True)

                    if exists:
                        st.warning("ID exists")
                    else:
                        expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

                        run_query(
                            "INSERT INTO schools VALUES (?, ?, ?, ?, ?, ?)",
                            (sid, name, hash_pw(pw), plan, expiry, 0)
                        )

                        st.success("School created")

        # BROADCAST
        with tab2:
            msg = st.text_area("Message")
            if st.button("Send"):
                run_query("INSERT INTO broadcasts (msg, date) VALUES (?, ?)", (msg, str(datetime.now())))
                st.success("Sent")

        # REVENUE
        with tab3:
            schools = run_query("SELECT * FROM schools", fetch=True)

            st.metric("Schools", len(schools))
            st.metric("Revenue", f"₹{sum(PLAN_PRICES.get(s['plan'], 0) for s in schools)}")

        # DATABASE
        with tab4:
            if st.button("Reset Database"):
                reset_database()
# ================= SCHOOL ===============          
else:
      sid = st.session_state.auth["school_id"]

        school = run_query(
            "SELECT * FROM schools WHERE id=?",
            (sid,),
            fetch=True
        )[0]

        st.title(f"🏫 {school['name']}")

        students = run_query(
            "SELECT * FROM students WHERE school_id=?",
            (sid,),
            fetch=True
        )

        menu = st.sidebar.selectbox(
            "Menu",
            ["Dashboard", "Students", "Fees", "Inventory", "Care Logs"]
        )

        # ================= DASHBOARD =================
        if menu == "Dashboard":
            st.metric("Total Students", len(students))

        # ================= STUDENTS =================
        elif menu == "Students":
            st.subheader("Add Student")

            with st.form("add_student"):
                name = st.text_input("Name")
                blood = st.text_input("Blood Group")
                allergy = st.text_input("Allergy")
                parent = st.text_input("Parent Name")
                phone = st.text_input("Parent Phone")
                student_class = st.text_input("Class")

                if st.form_submit_button("Add Student"):
                    run_query(
                        "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            str(uuid.uuid4()), name, blood, allergy,
                            parent, phone, "", "", "", student_class, sid
                        )
                    )
                    st.success("Student added")
                    st.rerun()

            st.subheader("Student List")
            for s in students:
                st.write(f"{s['name']} | {s['class']} | Parent: {s['parent_name']}")

        # ================= FEES =================
        elif menu == "Fees":
            st.subheader("Add Fee Record")

            if students:
                student_names = [s["name"] for s in students]
                selected = st.selectbox("Student", student_names)

                amount = st.number_input("Amount", min_value=0)
                month = st.text_input("Month")

                if st.button("Add Fee"):
                    run_query(
                        "INSERT INTO fees VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            str(uuid.uuid4()),
                            "",
                            selected,
                            amount,
                            month,
                            "Paid",
                            str(datetime.now()),
                            sid
                        )
                    )
                    st.success("Fee recorded")
                    st.rerun()

            st.subheader("Fee Records")
            fees = run_query(
                "SELECT * FROM fees WHERE school_id=?",
                (sid,),
                fetch=True
            )

            for f in fees:
                st.write(f"{f['student_name']} | ₹{f['amount']} | {f['month']}")

        # ================= INVENTORY =================
        elif menu == "Inventory":
            st.subheader("Add Item")

            with st.form("add_item"):
                name = st.text_input("Item Name")
                category = st.text_input("Category")
                qty = st.number_input("Quantity", min_value=0)
                min_qty = st.number_input("Min Quantity", min_value=0)

                if st.form_submit_button("Add Item"):
                    run_query(
                        "INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            str(uuid.uuid4()),
                            name,
                            category,
                            qty,
                            min_qty,
                            sid
                        )
                    )
                    st.success("Item added")
                    st.rerun()

            st.subheader("Inventory List")
            items = run_query(
                "SELECT * FROM inventory WHERE school_id=?",
                (sid,),
                fetch=True
            )

            for i in items:
                alert = "⚠️ Low Stock" if i["quantity"] <= i["min_quantity"] else ""
                st.write(f"{i['item_name']} | Qty: {i['quantity']} {alert}")

        # ================= CARE LOGS =================
        elif menu == "Care Logs":
            st.subheader("Add Care Log")

            if students:
                student_names = [s["name"] for s in students]
                selected = st.selectbox("Student", student_names)

                activity = st.text_input("Activity")
                notes = st.text_area("Notes")

                if st.button("Save Log"):
                    run_query(
                        "INSERT INTO care_logs VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            str(uuid.uuid4()),
                            "",
                            selected,
                            activity,
                            notes,
                            str(datetime.now()),
                            sid
                        )
                    )
                    st.success("Log saved")
                    st.rerun()

            st.subheader("Logs")
            logs = run_query(
                "SELECT * FROM care_logs WHERE school_id=?",
                (sid,),
                fetch=True
            )

            for l in logs:
                st.write(f"{l['student_name']} | {l['activity']} | {l['time']}")
