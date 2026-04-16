# ================= SCHOOLOS PRO - PHASE 2 (FINAL PRODUCTION READY) =================
import streamlit as st
import sqlite3
import uuid
from datetime import datetime, timedelta
import bcrypt
from fpdf import FPDF
from io import BytesIO

# ---------------- CONFIG ----------------
st.set_page_config(page_title="SchoolOS Pro", layout="wide", page_icon="🏫")

# ---------------- SECURITY ----------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

# ---------------- DATABASE ----------------
@st.cache_resource
def get_db():
    conn = sqlite3.connect("schoolos.db", check_same_thread=False, timeout=15)
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
        return False if not fetch else []

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
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            school_id TEXT,
            username TEXT UNIQUE,
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

    # Performance indexes
    run_query("CREATE INDEX IF NOT EXISTS idx_students_school ON students(school_id)")
    run_query("CREATE INDEX IF NOT EXISTS idx_fees_school ON fees(school_id)")
    run_query("CREATE INDEX IF NOT EXISTS idx_logs_school ON care_logs(school_id)")

    # Create default super-admin if not exists
    if not run_query("SELECT * FROM users WHERE username=?", ("admin",), True):
        run_query("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                  (str(uuid.uuid4()), "global", "admin", hash_password("admin123"), "admin"))

init_db()

# ---------------- RECEIPT (IN-MEMORY) ----------------
def generate_receipt(name: str, amount: int) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, "SchoolOS Pro Receipt", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, f"Student: {name}", ln=True)
    pdf.cell(200, 10, f"Amount Paid: ₹{amount}", ln=True)
    pdf.cell(200, 10, f"Date: {datetime.now().strftime('%d %b %Y')}", ln=True)
    pdf.cell(200, 10, "Thank you for your payment!", ln=True)
    
    pdf_bytes = pdf.output(dest='S')
    return pdf_bytes.encode('latin-1')

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
    
    if st.button("Login", type="primary"):
        # Check DB (admin is now also in DB)
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
    st.caption("Default admin: **admin** / **admin123**")

# ---------------- MAIN APP ----------------
else:
    if st.sidebar.button("Logout"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

    # ====================== ADMIN PANEL ======================
    if st.session_state.auth["role"] == "admin":
        st.title("👑 Admin Panel - Create School")
        col1, col2 = st.columns(2)
        with col1:
            sid = st.text_input("School ID (unique)")
            name = st.text_input("School Name")
        with col2:
            pw = st.text_input("School Admin Password", type="password")
            plan = st.selectbox("Plan", list(PLAN_LIMITS.keys()))
        
        if st.button("Create School", type="primary"):
            if not sid or not name or not pw:
                st.error("All fields required")
            else:
                exists = run_query("SELECT * FROM schools WHERE id=?", (sid,), True)
                if exists:
                    st.error("School ID already exists")
                else:
                    expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
                    run_query("INSERT INTO schools VALUES (?, ?, ?, ?, ?, ?)",
                              (sid, name, hash_password(pw), plan, expiry, 0))
                    run_query("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                              (str(uuid.uuid4()), sid, sid, hash_password(pw), "admin"))
                    st.success(f"✅ School '{name}' created successfully!")
                    st.rerun()

    # ====================== SCHOOL DASHBOARD ======================
    else:
        sid = st.session_state.auth["school_id"]
        school_data = run_query("SELECT * FROM schools WHERE id=?", (sid,), True)
        
        if not school_data:
            st.error("School not found")
            st.stop()

        school = school_data[0]
        expiry = datetime.strptime(school["expiry"], "%Y-%m-%d")
        
        if datetime.now() > expiry:
            st.error("❌ Your subscription has expired. Please contact admin.")
            st.stop()

        st.title(f"🏫 {school['name']}")

        # Plan info
        students = run_query("SELECT * FROM students WHERE school_id=?", (sid,), True)
        max_students = PLAN_LIMITS[school["plan"]]
        st.sidebar.info(f"**Plan**: {school['plan']}\n**Students**: {len(students)}/{max_students}")

        menu = st.sidebar.selectbox(
            "Menu",
            ["Dashboard", "Students", "Fees", "Inventory", "Care Logs", "Upgrade"]
        )

        # ---------------- DASHBOARD ----------------
        if menu == "Dashboard":
            fees = run_query("SELECT * FROM fees WHERE school_id=?", (sid,), True)
            paid = sum(f["amount"] for f in fees if f["status"] == "Paid")
            pending = sum(f["amount"] for f in fees if f["status"] == "Pending")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Students", len(students))
            col2.metric("Fees Collected", f"₹{paid}")
            col3.metric("Pending Fees", f"₹{pending}")
            st.caption(f"Plan Limit: **{max_students}** students")

        # ---------------- STUDENTS ----------------
        elif menu == "Students":
            st.subheader("Student Profiles")
            
            with st.form("add_student"):
                name = st.text_input("Name *")
                blood = st.selectbox("Blood Group", ["O+","O-","A+","A-","B+","B-","AB+","AB-"])
                allergy = st.text_input("Allergies")
                parent_name = st.text_input("Parent Name *")
                parent_phone = st.text_input("Parent Phone *")
                likes = st.text_input("Likes")
                dislikes = st.text_input("Dislikes")
                siblings = st.text_input("Siblings")
                student_class = st.text_input("Class *")
                
                if st.form_submit_button("Add Student"):
                    if not name or not parent_name or not parent_phone or not student_class:
                        st.error("Required fields missing (*)")
                    elif not parent_phone.isdigit() or len(parent_phone) < 10:
                        st.error("Invalid phone number")
                    elif len(students) >= max_students:
                        st.error("Student limit reached for current plan")
                    else:
                        run_query(
                            "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (str(uuid.uuid4()), name, blood, allergy,
                             parent_name, parent_phone, likes, dislikes,
                             siblings, student_class, sid)
                        )
                        st.success("Student added successfully!")
                        st.rerun()

            # Display students
            for s in students:
                with st.expander(f"👶 {s['name']} | {s['class']}"):
                    st.write(f"**Blood**: {s['blood']} | **Allergy**: {s['allergy']}")
                    st.write(f"**Parent**: {s['parent_name']} | **Phone**: {s['parent_phone']}")
                    st.write(f"Likes: {s['likes']} | Dislikes: {s['dislikes']} | Siblings: {s['siblings']}")

        # ---------------- FEES ----------------
        elif menu == "Fees":
            st.subheader("Fee Management")
            student_map = {f"{s['name']} ({s['id'][:6]})": s["id"] for s in students}
            
            with st.form("fee_form"):
                student_name = st.selectbox("Student", list(student_map.keys()))
                amount = st.number_input("Amount (₹)", min_value=0)
                month = st.selectbox("Month", ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])
                if st.form_submit_button("Add Fee"):
                    run_query(
                        "INSERT INTO fees VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), student_map[student_name], student_name.split(' (')[0],
                         amount, month, "Pending", "", sid)
                    )
                    st.success("Fee record added!")
                    st.rerun()

            fees = run_query("SELECT * FROM fees WHERE school_id=?", (sid,), True)
            for f in fees:
                col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
                col1.write(f["student_name"])
                col2.write(f["month"])
                col3.write(f"₹{f['amount']}")
                
                if f["status"] == "Pending":
                    if col4.button("Mark Paid ✅", key=f"id_{f['id']}"):
                        run_query(
                            "UPDATE fees SET status=?, payment_date=? WHERE id=?",
                            ("Paid", str(datetime.now()), f["id"])
                        )
                        receipt_data = generate_receipt(f["student_name"], f["amount"])
                        st.download_button(
                            label="📥 Download Receipt",
                            data=receipt_data,
                            file_name=f"{f['student_name']}_receipt.pdf",
                            mime="application/pdf"
                        )
                        st.success("Payment marked & receipt generated!")
                        st.rerun()
                else:
                    col4.success("✅ Paid")

        # ---------------- INVENTORY ----------------
        elif menu == "Inventory":
            st.subheader("📦 Inventory Management")
            with st.form("add_item"):
                item = st.text_input("Item Name")
                category = st.selectbox("Category", ["First Aid", "Kitchen", "Stationery"])
                qty = st.number_input("Current Quantity", min_value=0)
                min_qty = st.number_input("Minimum Alert Level", min_value=0)
                if st.form_submit_button("Add Item"):
                    run_query(
                        "INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), item, category, qty, min_qty, sid)
                    )
                    st.success("Item added!")
                    st.rerun()

            items = run_query("SELECT * FROM inventory WHERE school_id=?", (sid,), True)
            for i in items:
                status = "🔴 Low Stock!" if i["quantity"] <= i["min_quantity"] else "✅ OK"
                st.write(f"{i['item_name']} | {i['category']} | Qty: **{i['quantity']}** | {status}")

        # ---------------- CARE LOGS ----------------
        elif menu == "Care Logs":
            st.subheader("👶 Care Logs")
            student_map = {f"{s['name']} ({s['id'][:6]})": s["id"] for s in students}
            
            with st.form("log_form"):
                st_name = st.selectbox("Student", list(student_map.keys()))
                activity = st.selectbox("Activity", ["Meal", "Sleep", "Potty", "Play", "Medicine"])
                notes = st.text_input("Notes")
                if st.form_submit_button("Add Log"):
                    run_query(
                        "INSERT INTO care_logs VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), student_map[st_name], st_name.split(' (')[0],
                         activity, notes, str(datetime.now()), sid)
                    )
                    st.success("Care log added!")
                    st.rerun()

            logs = run_query("SELECT * FROM care_logs WHERE school_id=? ORDER BY time DESC", (sid,), True)
            for l in logs:
                st.write(f"**{l['student_name']}** | {l['activity']} | {l['notes']} | {l['time'][:16]}")

        # ---------------- UPGRADE ----------------
        elif menu == "Upgrade":
            st.subheader("Upgrade Your Plan")
            for p, price in PLAN_PRICES.items():
                if st.button(f"Upgrade to **{p}** — ₹{price}", key=p):
                    run_query("UPDATE schools SET plan=? WHERE id=?", (p, sid))
                    st.success(f"✅ Successfully upgraded to {p} plan!")
                    st.rerun()

st.caption("SchoolOS Pro • Phase 2 Production Ready • Built clean for Phase 3")
