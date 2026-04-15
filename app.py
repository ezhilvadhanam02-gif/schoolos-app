import streamlit as st
import sqlite3
import uuid
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="SchoolOS Pro", layout="wide")

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect("schoolos.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def run_query(query, params=(), fetch=False):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        if fetch:
            return [dict(row) for row in cur.fetchall()]
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Database Error: {e}")
        return None

# ---------------- INIT DB ----------------
def init_db():
    run_query("""CREATE TABLE IF NOT EXISTS schools (
        id TEXT PRIMARY KEY, name TEXT, pass TEXT, plan TEXT, 
        expiry TEXT, extra_students INTEGER DEFAULT 0
    )""")
    
    # Fixed Schema: Added parent details to student table
    run_query("""CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY, name TEXT, blood TEXT, dob TEXT, 
        class TEXT, parent_name TEXT, parent_phone TEXT, 
        parent_pass TEXT, school_id TEXT
    )""")
    
    run_query("""CREATE TABLE IF NOT EXISTS fees (
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT, 
        amount INTEGER, month TEXT, status TEXT, 
        payment_date TEXT, school_id TEXT
    )""")
    
    run_query("""CREATE TABLE IF NOT EXISTS care_logs (
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT, 
        activity TEXT, notes TEXT, time TEXT, school_id TEXT
    )""")
    
    run_query("""CREATE TABLE IF NOT EXISTS gallery (
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT, 
        caption TEXT, image BLOB, school_id TEXT
    )""")

# Initialize database on startup
init_db()

# ---------------- RESET DB ----------------
if st.sidebar.button("⚠️ Reset Database"):
    if os.path.exists("schoolos.db"):
        os.remove("schoolos.db")
        st.rerun()

# ---------------- SESSION ----------------
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None, "student_id": None}

# ---------------- LOGIN ----------------
if not st.session_state.auth["logged_in"]:
    st.title("🏫 SchoolOS Pro")
    role = st.selectbox("Login As", ["School/Admin", "Parent"])
    user = st.text_input("User ID / Phone")
    pw = st.text_input("Password", type="password")

    if st.button("Login"):
        # Super Admin Login
        if role == "School/Admin" and user == "admin" and pw == "admin123":
            st.session_state.auth = {"logged_in": True, "role": "admin"}
            st.rerun()

        # School Login
        school = run_query("SELECT * FROM schools WHERE id=? AND pass=?", (user, pw), True)
        if role == "School/Admin" and school:
            s_data = school[0]
            if datetime.now() < datetime.strptime(s_data["expiry"], "%Y-%m-%d"):
                st.session_state.auth = {"logged_in": True, "role": "school", "school_id": user}
                st.rerun()
            else:
                st.error("Subscription expired")

        # Parent Login
        parent = run_query("SELECT * FROM students WHERE parent_phone=? AND parent_pass=?", (user, pw), True)
        if role == "Parent" and parent:
            p_data = parent[0]
            st.session_state.auth = {
                "logged_in": True, "role": "parent", 
                "school_id": p_data["school_id"], "student_id": p_data["id"]
            }
            st.rerun()
        st.error("Invalid credentials")

# ---------------- MAIN ----------------
else:
    if st.sidebar.button("Logout"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

    # ================= ADMIN =================
    if st.session_state.auth["role"] == "admin":
        st.title("👑 Admin Dashboard")
        sid = st.text_input("School ID")
        sname = st.text_input("School Name")
        spw = st.text_input("Password")
        plan = st.selectbox("Plan", ["Basic","Standard","Premium","Enterprise"])

        if st.button("Create School"):
            if not sid or not sname or not spw:
                st.error("All fields required")
            else:
                expiry = (datetime.now()+timedelta(days=365)).strftime("%Y-%m-%d")
                success = run_query("INSERT INTO schools VALUES (?, ?, ?, ?, ?, ?)", (sid, sname, spw, plan, expiry, 0))
                if success: st.success("School created")

    # ================= SCHOOL =================
    elif st.session_state.auth["role"] == "school":
        sid = st.session_state.auth["school_id"]
        menu = st.sidebar.selectbox("Menu", ["Students","Fees","Care Logs","Gallery"])
        
        students = run_query("SELECT * FROM students WHERE school_id=?", (sid,), True) or []

        if menu == "Students":
            with st.form("student_form"):
                st.subheader("Add New Student")
                name = st.text_input("Student Name")
                s_class = st.text_input("Class")
                blood = st.selectbox("Blood Group", ["O+","O-","A+","A-","B+","B-","AB+","AB-"])
                dob = st.date_input("Date of Birth")
                p_name = st.text_input("Parent Name")
                phone = st.text_input("Parent Phone")
                ppass = st.text_input("Parent Password")

                if st.form_submit_button("Add Student"):
                    if name and phone:
                        run_query(
                            "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (str(uuid.uuid4()), name, blood, str(dob), s_class, p_name, phone, ppass, sid)
                        )
                        st.success("Student added")
                        st.rerun()

            st.write("### Registered Students")
            for s in students:
                st.write(f"👤 {s['name']} (Class {s['class']}) | Parent: {s['parent_name']}")

        elif menu == "Fees":
            if not students:
                st.warning("Add students first")
            else:
                student_map = {s["name"]: s["id"] for s in students}
                with st.form("fee_form"):
                    st_name = st.selectbox("Student", list(student_map.keys()))
                    amount = st.number_input("Amount", min_value=0)
                    month = st.selectbox("Month", ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])
                    if st.form_submit_button("Add Fee Record"):
                        run_query("INSERT INTO fees VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                                 (str(uuid.uuid4()), student_map[st_name], st_name, amount, month, "Pending", "", sid))
                        st.success("Fee record added")
                        st.rerun()

        elif menu == "Care Logs":
            if not students:
                st.warning("Add students first")
            else:
                student_map = {s["name"]: s["id"] for s in students}
                st_name = st.selectbox("Student", list(student_map.keys()))
                activity = st.selectbox("Activity", ["Meal","Sleep","Play","Toilet"])
                notes = st.text_area("Notes")
                if st.button("Add Log"):
                    run_query("INSERT INTO care_logs VALUES (?, ?, ?, ?, ?, ?, ?)", 
                             (str(uuid.uuid4()), student_map[st_name], st_name, activity, notes, str(datetime.now()), sid))
                    st.success("Log added")

        elif menu == "Gallery":
            if not students:
                st.warning("Add students first")
            else:
                student_map = {s["name"]: s["id"] for s in students}
                st_name = st.selectbox("Select Student", list(student_map.keys()))
                caption = st.text_input("Caption (e.g., Playing with blocks)")
                img_file = st.file_uploader("Upload Image", type=['jpg', 'png', 'jpeg'])
                
                if st.button("Upload to Gallery"):
                    if img_file and caption:
                        run_query("INSERT INTO gallery VALUES (?, ?, ?, ?, ?, ?)", 
                                 (str(uuid.uuid4()), student_map[st_name], st_name, caption, img_file.read(), sid))
                        st.success("Photo uploaded!")
                    else:
                        st.error("Image and caption required")

    # ================= PARENT =================
    elif st.session_state.auth["role"] == "parent":
        student_id = st.session_state.auth["student_id"]
        res = run_query("SELECT * FROM students WHERE id=?", (student_id,), True)
        if res:
            student = res[0]
            st.title(f"👋 Welcome, Parent of {student['name']}!")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Class", student["class"])
            col2.metric("DOB", student["dob"])
            col3.metric("Blood Group", student["blood"])

            # Fees
            st.subheader("💰 Fee History")
            fees = run_query("SELECT * FROM fees WHERE student_id=? ORDER BY month DESC", (student_id,), True)
            if fees:
                for f in fees:
                    status = "✅ Paid" if f["status"] == "Paid" else "⏳ Pending"
                    st.write(f"**{f['month']}** — ₹{f['amount']} — {status}")
            else: st.info("No fee records.")

            # Logs
            st.subheader("🧸 Recent Care Logs")
            logs = run_query("SELECT * FROM care_logs WHERE student_id=? ORDER BY time DESC LIMIT 5", (student_id,), True)
            for l in logs:
                with st.expander(f"{l['time'][:16]} • {l['activity']}"):
                    st.write(l["notes"])

            # Gallery
            st.subheader("📸 Your Child's Photos")
            imgs = run_query("SELECT * FROM gallery WHERE student_id=? ORDER BY id DESC", (student_id,), True)
            if imgs:
                cols = st.columns(3)
                for idx, i in enumerate(imgs):
                    with cols[idx % 3]:
                        st.image(i["image"], caption=i["caption"], use_container_width=True)
            else: st.info("No photos yet.")
