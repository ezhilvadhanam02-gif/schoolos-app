import streamlit as st
import sqlite3
import uuid
from datetime import datetime, timedelta
import bcrypt
from fpdf import FPDF

st.set_page_config(page_title="SchoolOS Pro", layout="wide")

# ---------------- SECURITY ----------------
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

# ---------------- DATABASE ----------------
def run_query(query, params=(), fetch=False):
    conn = sqlite3.connect("schoolos.db", timeout=10)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(query, params)

    if fetch:
        data = cur.fetchall()
        conn.close()
        return data

    conn.commit()
    conn.close()

# ---------------- INIT DB ----------------
def init_db():
    run_query("""
    CREATE TABLE IF NOT EXISTS schools (
        id TEXT PRIMARY KEY,
        name TEXT,
        plan TEXT,
        expiry TEXT,
        extra_students INTEGER DEFAULT 0
    )
    """)

    run_query("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        school_id TEXT,
        username TEXT,
        password TEXT,
        role TEXT
    )
    """)

    run_query("""
    CREATE TABLE IF NOT EXISTS students (
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

    run_query("""
    CREATE TABLE IF NOT EXISTS inventory (
        id TEXT PRIMARY KEY,
        item_name TEXT,
        category TEXT,
        quantity INTEGER,
        min_quantity INTEGER,
        school_id TEXT
    )
    """)

    run_query("""
    CREATE TABLE IF NOT EXISTS care_logs (
        id TEXT PRIMARY KEY,
        student_id TEXT,
        student_name TEXT,
        activity TEXT,
        notes TEXT,
        time TEXT,
        school_id TEXT
    )
    """)

    run_query("""
    CREATE TABLE IF NOT EXISTS broadcasts (
        id TEXT PRIMARY KEY,
        message TEXT,
        time TEXT
    )
    """)

init_db()

# ---------------- RECEIPT ----------------
def generate_receipt(name, amount):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, "SchoolOS Receipt", ln=True)
    pdf.cell(200, 10, f"Student: {name}", ln=True)
    pdf.cell(200, 10, f"Amount Paid: ₹{amount}", ln=True)

    file = f"receipt_{uuid.uuid4().hex}.pdf"
    pdf.output(file)
    return file

# ---------------- PLANS ----------------
PLAN_LIMITS = {"Basic": 30, "Standard": 80, "Premium": 500, "Enterprise": float("inf")}
PLAN_PRICES = {"Basic": 2000, "Standard": 4000, "Premium": 7999, "Enterprise": 9999}

# ---------------- SESSION ----------------
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False}

# ---------------- LOGIN ----------------
if not st.session_state.auth.get("logged_in"):
    st.title("🏫 SchoolOS Pro Login")

    user = st.text_input("Username")
    pw = st.text_input("Password", type="password")

    if st.button("Login"):

        # SUPER ADMIN
        if user == "admin" and pw == "admin123":
            st.session_state.auth = {"logged_in": True, "role": "super_admin"}
            st.rerun()

        user_data = run_query("SELECT * FROM users WHERE username=?", (user,), True)

        if user_data and verify_password(pw, user_data[0]["password"]):
            st.session_state.auth = {
                "logged_in": True,
                "role": user_data[0]["role"],
                "school_id": user_data[0]["school_id"]
            }
            st.rerun()
        else:
            st.error("Invalid credentials")

# ---------------- MAIN ----------------
else:
    if st.sidebar.button("Logout"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

    role = st.session_state.auth["role"]

    # =====================================================
    # 👑 SUPER ADMIN
    # =====================================================
    if role == "super_admin":
        st.title("👑 Super Admin Panel")

        menu = st.sidebar.selectbox("Admin Menu",
                                   ["Create School", "Revenue", "Schools", "Broadcast"])

        # CREATE SCHOOL
        if menu == "Create School":
            sid = st.text_input("School ID")
            name = st.text_input("School Name")
            pw = st.text_input("Password")
            plan = st.selectbox("Plan", list(PLAN_LIMITS.keys()))

            if st.button("Create School"):
                expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

                run_query("INSERT INTO schools VALUES (?, ?, ?, ?, ?)",
                          (sid, name, plan, expiry, 0))

                run_query("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                          (str(uuid.uuid4()), sid, sid, hash_password(pw), "school"))

                st.success("School Created")

        # REVENUE
        elif menu == "Revenue":
            schools = run_query("SELECT * FROM schools", fetch=True)

            total = sum(PLAN_PRICES[s["plan"]] for s in schools)
            st.metric("Total Revenue", f"₹{total}")

            plan_count = {}
            for s in schools:
                plan_count[s["plan"]] = plan_count.get(s["plan"], 0) + 1

            for p, c in plan_count.items():
                st.write(f"{p}: {c} schools")

        # SCHOOLS
        elif menu == "Schools":
            schools = run_query("SELECT * FROM schools", fetch=True)

            for s in schools:
                expiry = datetime.strptime(s["expiry"], "%Y-%m-%d")
                status = "Active" if datetime.now() < expiry else "Expired"

                st.write(f"{s['name']} | {s['plan']} | {status}")

        # BROADCAST
        elif menu == "Broadcast":
            msg = st.text_area("Message")

            if st.button("Send"):
                run_query("INSERT INTO broadcasts VALUES (?, ?, ?)",
                          (str(uuid.uuid4()), msg, str(datetime.now())))
                st.success("Sent")

            logs = run_query("SELECT * FROM broadcasts ORDER BY time DESC", fetch=True)
            for l in logs:
                st.write(f"{l['time']} - {l['message']}")

    # =====================================================
    # 🏫 SCHOOL PANEL (FULL FEATURES)
    # =====================================================
    elif role == "school":
        sid = st.session_state.auth["school_id"]

        school = run_query("SELECT * FROM schools WHERE id=?", (sid,), True)[0]

        if datetime.now() > datetime.strptime(school["expiry"], "%Y-%m-%d"):
            st.error("Subscription expired")
            st.stop()

        st.title(f"🏫 {school['name']}")

        # Broadcasts
        broadcasts = run_query("SELECT * FROM broadcasts ORDER BY time DESC LIMIT 3", fetch=True)
        for b in broadcasts:
            st.info(f"📢 {b['message']}")

        students = run_query("SELECT * FROM students WHERE school_id=?", (sid,), True)
        max_students = PLAN_LIMITS[school["plan"]] + school["extra_students"]

        st.sidebar.info(f"{school['plan']} | {len(students)}/{max_students}")

        menu = st.sidebar.selectbox(
            "Menu",
            ["Dashboard", "Students", "Fees", "Inventory", "Care Logs", "Upgrade"]
        )

        # DASHBOARD
        if menu == "Dashboard":
            fees = run_query("SELECT * FROM fees WHERE school_id=?", (sid,), True)

            paid = sum(f["amount"] for f in fees if f["status"] == "Paid")
            pending = sum(f["amount"] for f in fees if f["status"] == "Pending")

            col1, col2, col3 = st.columns(3)
            col1.metric("Students", len(students))
            col2.metric("Collected", f"₹{paid}")
            col3.metric("Pending", f"₹{pending}")

        # STUDENTS
        elif menu == "Students":
            with st.form("add_student"):
                name = st.text_input("Name")
                blood = st.selectbox("Blood Group", ["O+","O-","A+","A-","B+","B-","AB+","AB-"])
                allergy = st.text_input("Allergy")
                parent_name = st.text_input("Parent Name")
                parent_phone = st.text_input("Phone")
                likes = st.text_input("Likes")
                dislikes = st.text_input("Dislikes")
                siblings = st.text_input("Siblings")
                student_class = st.text_input("Class")

                if st.form_submit_button("Add"):
                    if len(students) >= max_students:
                        st.error("Limit reached")
                    elif not parent_phone.isdigit() or len(parent_phone) != 10:
                        st.error("Invalid phone")
                    else:
                        run_query(
                            "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (str(uuid.uuid4()), name, blood, allergy,
                             parent_name, parent_phone,
                             likes, dislikes, siblings,
                             student_class, sid)
                        )
                        st.rerun()

            for s in students:
                st.write(f"{s['name']} | {s['parent_name']}")

        # FEES
        elif menu == "Fees":
            student_map = {f"{s['name']} ({s['id'][:4]})": s["id"] for s in students}

            with st.form("fee"):
                sn = st.selectbox("Student", list(student_map.keys()))
                amt = st.number_input("Amount", 0)
                month = st.selectbox("Month", ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])

                if st.form_submit_button("Add"):
                    run_query(
                        "INSERT INTO fees VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), student_map[sn], sn, amt, month, "Pending", "", sid)
                    )
                    st.rerun()

            fees = run_query("SELECT * FROM fees WHERE school_id=?", (sid,), True)

            for f in fees:
                col1, col2, col3, col4 = st.columns(4)
                col1.write(f["student_name"])
                col2.write(f["month"])
                col3.write(f"₹{f['amount']}")

                if f["status"] == "Pending":
                    if col4.button("Mark Paid", key=f["id"]):
                        run_query(
                            "UPDATE fees SET status=?, payment_date=? WHERE id=?",
                            ("Paid", str(datetime.now()), f["id"])
                        )

                        file = generate_receipt(f["student_name"], f["amount"])
                        with open(file, "rb") as fobj:
                            st.download_button("Download Receipt", fobj, file_name=file)

                        st.rerun()
                else:
                    col4.success("Paid")

        # INVENTORY
        elif menu == "Inventory":
            with st.form("inv"):
                item = st.text_input("Item")
                cat = st.text_input("Category")
                qty = st.number_input("Qty", 0)
                minq = st.number_input("Min", 0)

                if st.form_submit_button("Add"):
                    run_query(
                        "INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), item, cat, qty, minq, sid)
                    )
                    st.rerun()

            items = run_query("SELECT * FROM inventory WHERE school_id=?", (sid,), True)
            for i in items:
                st.write(f"{i['item_name']} | Qty: {i['quantity']}")
                if i["quantity"] <= i["min_quantity"]:
                    st.error("Low stock")

        # CARE LOGS
        elif menu == "Care Logs":
            student_map = {s["name"]: s["id"] for s in students}

            with st.form("log"):
                sn = st.selectbox("Student", list(student_map.keys()))
                act = st.selectbox("Activity", ["Meal","Sleep","Potty","Play","Medicine"])
                notes = st.text_input("Notes")

                if st.form_submit_button("Add"):
                    run_query(
                        "INSERT INTO care_logs VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), student_map[sn], sn, act, notes, str(datetime.now()), sid)
                    )
                    st.rerun()

            logs = run_query("SELECT * FROM care_logs WHERE school_id=? ORDER BY time DESC", (sid,), True)
            for l in logs:
                st.write(f"{l['student_name']} | {l['activity']} | {l['notes']}")

        # UPGRADE
        elif menu == "Upgrade":
            for p, price in PLAN_PRICES.items():
                if st.button(f"{p} ₹{price}"):
                    new_expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
                    run_query("UPDATE schools SET plan=?, expiry=? WHERE id=?",
                              (p, new_expiry, sid))
                    st.success("Upgraded")
                    st.rerun()
