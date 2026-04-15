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
        result = cur.fetchall()
        conn.close()
        return result

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

        # Super Admin Login
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

    # ================= SUPER ADMIN =================
    if role == "super_admin":
        st.title("👑 Super Admin Panel")

        sid = st.text_input("School ID")
        name = st.text_input("School Name")
        pw = st.text_input("Password")
        plan = st.selectbox("Plan", list(PLAN_LIMITS.keys()))

        if st.button("Create School"):
            exists = run_query("SELECT * FROM schools WHERE id=?", (sid,), True)

            if exists:
                st.error("School ID already exists")
            else:
                expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

                run_query(
                    "INSERT INTO schools VALUES (?, ?, ?, ?, ?)",
                    (sid, name, plan, expiry, 0)
                )

                run_query(
                    "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), sid, sid, hash_password(pw), "school")
                )

                st.success("School Created")

    # ================= SCHOOL =================
    elif role == "school":
        sid = st.session_state.auth["school_id"]

        school_data = run_query("SELECT * FROM schools WHERE id=?", (sid,), True)

        if not school_data:
            st.error("School not found")
            st.stop()

        school = school_data[0]

        expiry = datetime.strptime(school["expiry"], "%Y-%m-%d")
        if datetime.now() > expiry:
            st.error("Subscription expired")
            st.stop()

        st.title(f"🏫 {school['name']}")

        students = run_query("SELECT * FROM students WHERE school_id=?", (sid,), True)

        max_students = PLAN_LIMITS[school["plan"]] + school["extra_students"]

        st.sidebar.info(f"Plan: {school['plan']}\nStudents: {len(students)}/{max_students}")

        menu = st.sidebar.selectbox(
            "Menu",
            ["Dashboard", "Students", "Fees", "Inventory", "Care Logs", "Upgrade"]
        )

        # DASHBOARD
        if menu == "Dashboard":
            stats = run_query("""
            SELECT 
            SUM(CASE WHEN status='Paid' THEN amount ELSE 0 END) as paid,
            SUM(CASE WHEN status='Pending' THEN amount ELSE 0 END) as pending
            FROM fees WHERE school_id=?
            """, (sid,), True)[0]

            col1, col2, col3 = st.columns(3)
            col1.metric("Students", len(students))
            col2.metric("Collected", f"₹{stats['paid'] or 0}")
            col3.metric("Pending", f"₹{stats['pending'] or 0}")

        # STUDENTS
        elif menu == "Students":
            st.subheader("Student Profiles")

            with st.form("add_student"):
                name = st.text_input("Name")
                blood = st.selectbox("Blood Group", ["O+","O-","A+","A-","B+","B-","AB+","AB-"])
                parent_name = st.text_input("Parent Name")
                parent_phone = st.text_input("Parent Phone")

                if st.form_submit_button("Add Student"):
                    if not name or not parent_name or not parent_phone:
                        st.error("Required fields missing")
                    elif not parent_phone.isdigit() or len(parent_phone) != 10:
                        st.error("Invalid phone number")
                    elif len(students) >= max_students:
                        st.error("Student limit reached")
                    else:
                        run_query(
                            "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                str(uuid.uuid4()), name, blood, "",
                                parent_name, parent_phone,
                                "", "", "",
                                "", sid
                            )
                        )
                        st.success("Added!")
                        st.rerun()

            for s in students:
                st.write(f"👶 {s['name']} | Parent: {s['parent_name']}")

        # FEES
        elif menu == "Fees":
            st.subheader("Fee Management")

            student_map = {f"{s['name']}": s["id"] for s in students}

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

                        st.success("Payment done!")
                        st.rerun()
                else:
                    col4.success("Paid")

        # INVENTORY
        elif menu == "Inventory":
            st.subheader("📦 Inventory")

            with st.form("add_item"):
                item = st.text_input("Item Name")
                category = st.selectbox("Category", ["First Aid", "Kitchen", "Stationery"])
                qty = st.number_input("Quantity", 0)
                min_qty = st.number_input("Min Level", 0)

                if st.form_submit_button("Add"):
                    run_query(
                        "INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), item, category, qty, min_qty, sid)
                    )
                    st.success("Added!")
                    st.rerun()

            items = run_query("SELECT * FROM inventory WHERE school_id=?", (sid,), True)

            for i in items:
                st.write(f"{i['item_name']} | {i['category']} | Qty: {i['quantity']}")
                if i["quantity"] <= i["min_quantity"]:
                    st.error("Low Stock!")

        # CARE LOGS
        elif menu == "Care Logs":
            st.subheader("👶 Care Logs")

            student_map = {s["name"]: s["id"] for s in students}

            with st.form("log"):
                st_name = st.selectbox("Student", list(student_map.keys()))
                activity = st.selectbox("Activity", ["Meal","Sleep","Potty","Play","Medicine"])
                notes = st.text_input("Notes")

                if st.form_submit_button("Add Log"):
                    run_query(
                        "INSERT INTO care_logs VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            str(uuid.uuid4()),
                            student_map[st_name],
                            st_name,
                            activity,
                            notes,
                            str(datetime.now()),
                            sid
                        )
                    )
                    st.success("Logged!")
                    st.rerun()

            logs = run_query(
                "SELECT * FROM care_logs WHERE school_id=? ORDER BY time DESC",
                (sid,),
                True
            )

            for l in logs:
                st.write(f"{l['student_name']} | {l['activity']} | {l['notes']}")

        # UPGRADE
        elif menu == "Upgrade":
            for p, price in PLAN_PRICES.items():
                if st.button(f"Upgrade to {p} - ₹{price}"):
                    new_expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
                    run_query(
                        "UPDATE schools SET plan=?, expiry=? WHERE id=?",
                        (p, new_expiry, sid)
                    )
                    st.success("Upgraded")
                    st.rerun()
