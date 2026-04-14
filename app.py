import streamlit as st
import sqlite3
import uuid
from datetime import datetime, timedelta
from fpdf import FPDF
import os

# ---------------- CONFIG ----------------
st.set_page_config(page_title="SchoolOS Pro", layout="wide")

# Create folders
os.makedirs("uploads", exist_ok=True)
os.makedirs("receipts", exist_ok=True)

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

# ---------------- PDF ----------------
def generate_receipt(student, amount, month, date):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "School Fee Receipt", ln=True, align="C")

    pdf.set_font("Arial", size=12)
    pdf.ln(10)

    pdf.cell(200, 10, f"Student: {student}", ln=True)
    pdf.cell(200, 10, f"Month: {month}", ln=True)
    pdf.cell(200, 10, f"Amount Paid: ₹{amount}", ln=True)
    pdf.cell(200, 10, f"Date: {date}", ln=True)

    filename = f"receipt_{uuid.uuid4().hex}.pdf"
    path = os.path.join("receipts", filename)
    pdf.output(path)

    return path

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
        parent_name TEXT,
        parent_phone TEXT,
        likes TEXT,
        dislikes TEXT,
        siblings TEXT,
        class TEXT,
        photo TEXT,
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
                    st.warning("School ID exists!")
                else:
                    expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

                    run_query(
                        "INSERT INTO schools VALUES (?, ?, ?, ?, ?, ?)",
                        (sid, name, pw, plan, expiry, 0)
                    )
                    st.success("School created!")

        with tab2:
            msg = st.text_area("Message")
            if st.button("Send"):
                run_query(
                    "INSERT INTO broadcasts (msg, date) VALUES (?, ?)",
                    (msg, str(datetime.now()))
                )
                st.success("Broadcast sent!")

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
            st.metric("Revenue", f"₹{revenue}")

    # ================= SCHOOL =================
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

        st.sidebar.info(f"Plan: {school['plan']} | Students: {len(students)}")

        menu = st.sidebar.selectbox("Menu", ["Dashboard", "Students", "Fees"])

        # DASHBOARD
        if menu == "Dashboard":
            st.metric("Students", len(students))

        # STUDENTS
        elif menu == "Students":
            st.subheader("Student Profiles")

            with st.form("add_student"):
                name = st.text_input("Name")
                blood = st.selectbox("Blood Group", ["O+","O-","A+","A-","B+","B-","AB+","AB-"])
                parent_name = st.text_input("Parent Name")
                parent_phone = st.text_input("Parent Phone")
                student_class = st.text_input("Class")
                photo = st.file_uploader("Upload Photo", type=["jpg","png"])

                if st.form_submit_button("Add"):
                    photo_path = ""
                    if photo:
                        path = f"uploads/{uuid.uuid4().hex}.png"
                        with open(path, "wb") as f:
                            f.write(photo.read())
                        photo_path = path

                    run_query(
                        "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            str(uuid.uuid4()), name, blood, "",
                            parent_name, parent_phone,
                            "", "", "",
                            student_class, photo_path, sid
                        )
                    )
                    st.success("Added!")
                    st.rerun()

            for s in students:
                col1, col2 = st.columns([1,4])

                if s["photo"]:
                    col1.image(s["photo"], width=60)
                else:
                    col1.write("👤")

                col2.write(f"{s['name']} | {s['class']} | Parent: {s['parent_name']}")

        # FEES
        elif menu == "Fees":
            st.subheader("Fee Management")

            names = [s["name"] for s in students]

            with st.form("fee"):
                st_name = st.selectbox("Student", names)
                amt = st.number_input("Amount", 0)
                month = st.selectbox("Month", ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])

                if st.form_submit_button("Add Fee"):
                    run_query(
                        "INSERT INTO fees VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), "", st_name, amt, month, "Pending", "", sid)
                    )
                    st.success("Added!")
                    st.rerun()

            fees = run_query("SELECT * FROM fees WHERE school_id=?", (sid,), True)

            for f in fees:
                col1, col2, col3, col4 = st.columns(4)

                col1.write(f["student_name"])
                col2.write(f["month"])
                col3.write(f"₹{f['amount']}")

                if f["status"] == "Pending":
                    if col4.button("Pay", key=f["id"]):
                        run_query(
                            "UPDATE fees SET status=?, payment_date=? WHERE id=?",
                            ("Paid", str(datetime.now()), f["id"])
                        )

                        receipt = generate_receipt(
                            f["student_name"],
                            f["amount"],
                            f["month"],
                            str(datetime.now())
                        )

                        with open(receipt, "rb") as file:
                            st.download_button(
                                "📄 Download Receipt",
                                file,
                                "receipt.pdf"
                            )

                        st.success("Payment done!")
                        st.rerun()
                else:
                    col4.success("Paid")
