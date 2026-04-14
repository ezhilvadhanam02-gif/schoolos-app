import streamlit as st
import sqlite3
import uuid
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="SchoolOS Pro", layout="wide", page_icon="🏫")

# ---------------- RESET DB ----------------
if st.sidebar.button("⚠️ Reset Database (Demo only)"):
    if os.path.exists("schoolos.db"):
        os.remove("schoolos.db")
    st.success("Database reset! Refresh the app.")
    st.stop()

# ---------------- SAFE DATABASE CONNECTION ----------------
# We open and close the connection for every query to prevent thread locking
def run_query(query, params=(), fetch=False):
    conn = sqlite3.connect("schoolos.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, params)
    
    if fetch:
        result = cur.fetchall()
        conn.close()
        return result
    
    conn.commit()
    conn.close()
    return None

# ---------------- INIT DB ----------------
def init_db():
    run_query("""CREATE TABLE IF NOT EXISTS schools (
        id TEXT PRIMARY KEY, name TEXT, pass TEXT, plan TEXT, expiry TEXT, extra_students INTEGER DEFAULT 0
    )""")
    run_query("""CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY, name TEXT, blood TEXT, allergy TEXT, parent_name TEXT, parent_phone TEXT, 
        parent_pass TEXT, likes TEXT, dislikes TEXT, siblings TEXT, class TEXT, school_id TEXT
    )""")
    run_query("""CREATE TABLE IF NOT EXISTS fees (
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT, amount INTEGER, month TEXT, 
        status TEXT, payment_date TEXT, school_id TEXT
    )""")
    run_query("""CREATE TABLE IF NOT EXISTS inventory (
        id TEXT PRIMARY KEY, item_name TEXT, category TEXT, quantity INTEGER, min_quantity INTEGER, school_id TEXT
    )""")
    run_query("""CREATE TABLE IF NOT EXISTS care_logs (
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT, activity TEXT, notes TEXT, time TEXT, school_id TEXT
    )""")
    run_query("""CREATE TABLE IF NOT EXISTS gallery (
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT, caption TEXT, image BLOB, school_id TEXT
    )""")
init_db()

# ---------------- SESSION ----------------
# Added fallback keys to prevent KeyErrors during logout
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None, "student_id": None}

# ---------------- LOGIN ----------------
if not st.session_state.auth["logged_in"]:
    st.title("🏫 SchoolOS Pro")
    st.markdown("### Login to continue")
    role = st.selectbox("Login As", ["School/Admin", "Parent"])
    user = st.text_input("User ID / Phone Number")
    pw = st.text_input("Password", type="password")
    
    if st.button("🔑 Login", use_container_width=True):
        if role == "School/Admin" and user == "admin" and pw == "admin123":
            st.session_state.auth = {"logged_in": True, "role": "admin", "school_id": None, "student_id": None}
            st.rerun()
        
        if role == "School/Admin":
            school_res = run_query("SELECT * FROM schools WHERE id=? AND pass=?", (user, pw), True)
            if school_res:
                school = school_res[0]
                if datetime.now() < datetime.strptime(school["expiry"], "%Y-%m-%d"):
                    st.session_state.auth = {"logged_in": True, "role": "school", "school_id": user, "student_id": None}
                    st.rerun()
                else:
                    st.error("Your school subscription has expired!")
            else:
                st.error("Invalid Admin/School credentials.")
                
        if role == "Parent":
            parent_res = run_query("SELECT * FROM students WHERE parent_phone=? AND parent_pass=?", (user, pw), True)
            if parent_res:
                parent = parent_res[0]
                st.session_state.auth = {
                    "logged_in": True,
                    "role": "parent",
                    "school_id": parent["school_id"],
                    "student_id": parent["id"]
                }
                st.rerun()
            else:
                st.error("Invalid Parent credentials.")

else:
    # Safe Logout
    if st.sidebar.button("🚪 Logout"):
        st.session_state.auth = {"logged_in": False, "role": None, "school_id": None, "student_id": None}
        st.rerun()

    # ================= ADMIN DASHBOARD =================
    if st.session_state.auth["role"] == "admin":
        st.title("👑 Admin Dashboard")
        st.subheader("Create New School")
        
        col1, col2 = st.columns(2)
        with col1:
            sid_input = st.text_input("School ID (e.g. DELHI001)")
            name = st.text_input("School Name")
        with col2:
            pw = st.text_input("Password", type="password")
            plan = st.selectbox("Plan", ["Basic", "Standard", "Premium", "Enterprise"])
        
        if st.button("Create School", type="primary"):
            if not sid_input or not name or not pw:
                st.error("All fields are required!")
            else:
                expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
                try:
                    run_query("INSERT INTO schools VALUES (?, ?, ?, ?, ?, ?)", (sid_input, name, pw, plan, expiry, 0))
                    st.success(f"✅ School **{name}** created successfully!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("School ID already exists!")

        st.subheader("All Registered Schools")
        schools = run_query("SELECT id, name, plan, expiry FROM schools ORDER BY name", fetch=True)
        if schools:
            for s in schools:
                st.write(f"**{s['name']}** ({s['id']}) — Plan: {s['plan']} | Expires: {s['expiry']}")
        else:
            st.info("No schools yet. Create one above.")

    # ================= SCHOOL DASHBOARD =================
    elif st.session_state.auth["role"] == "school":
        sid = st.session_state.auth.get("school_id")
        st.title(f"🏫 {sid.upper()} Dashboard")
        
        students_db = run_query("SELECT * FROM students WHERE school_id=?", (sid,), True)
        total_students = len(students_db) if students_db else 0
        pending_fees_db = run_query("SELECT id FROM fees WHERE school_id=? AND status='Pending'", (sid,), True)
        pending_fees = len(pending_fees_db) if pending_fees_db else 0
        low_stock_db = run_query("SELECT id FROM inventory WHERE school_id=? AND quantity <= min_quantity", (sid,), True)
        low_stock = len(low_stock_db) if low_stock_db else 0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Students", total_students)
        col2.metric("Pending Fees", pending_fees)
        col3.metric("Low Stock Items", low_stock)
        
        menu = st.sidebar.selectbox("Menu", ["📋 Students", "💰 Fees", "📦 Inventory", "🧸 Care Logs", "📸 Gallery"])

        if menu == "📋 Students":
            st.subheader("Add New Student")
            with st.form("add_student"):
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input("Student Name*")
                    blood = st.selectbox("Blood Group", ["O+","O-","A+","A-","B+","B-","AB+","AB-"])
                    class_ = st.text_input("Class / Section")
                with col2:
                    allergy = st.text_input("Allergies / Medical notes")
                    likes = st.text_input("Likes")
                    dislikes = st.text_input("Dislikes")
                parent = st.text_input("Parent Name")
                phone = st.text_input("Parent Phone*")
                ppass = st.text_input("Parent Password* (for login)")
                
                if st.form_submit_button("Add Student"):import streamlit as st
import sqlite3
import uuid
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="SchoolOS Pro", layout="wide", page_icon="🏫")

# ---------------- RESET DB ----------------
if st.sidebar.button("⚠️ Reset Database (Demo only)"):
    if os.path.exists("schoolos.db"):
        os.remove("schoolos.db")
    st.success("Database reset! Refresh the app.")
    st.stop()
                    if not name or not phone or not ppass:
                        st.error("Name, Phone & Password are required")
                    else:
                        run_query("INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                  (str(uuid.uuid4()), name, blood, allergy, parent, phone, ppass, likes, dislikes, "", class_, sid))
                        st.success("Student added successfully!")
                        st.rerun()

            st.subheader("All Students")
            if students_db:
                for s in students_db:
                    with st.expander(f"👦 {s['name']} • {s['class']}"):
                        st.write(f"**Blood:** {s['blood']} | **Allergy:** {s['allergy'] or 'None'}")
                        st.write(f"**Parent:** {s['parent_name']} | **Phone:** {s['parent_phone']} | **Pass:** {s['parent_pass']}")
            else:
                st.info("No students yet.")

        elif menu == "💰 Fees":
            st.subheader("Manage Fee Ledgers")
            if students_db:
                with st.form("add_fee"):
                    st_dict = {s["name"]: s["id"] for s in students_db}
                    sel_name = st.selectbox("Select Student", list(st_dict.keys()))
                    amt = st.number_input("Amount (₹)", min_value=0)
                    month = st.selectbox("Billing Month", ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
                    status = st.selectbox("Payment Status", ["Paid", "Pending"])
                    if st.form_submit_button("Record Transaction"):
                        run_query("INSERT INTO fees VALUES (?,?,?,?,?,?,?,?)",
                                  (str(uuid.uuid4()), st_dict[sel_name], sel_name, amt, month, status, str(datetime.now().date()), sid))
                        st.success("Fee ledger updated!")
                        st.rerun()
                
                fees_db = run_query("SELECT * FROM fees WHERE school_id=?", (sid,), True)
                if fees_db:
                    for f in fees_db:
                        icon = "✅" if f['status'] == "Paid" else "⏳"
                        st.write(f"{icon} **{f['student_name']}** — {f['month']} — ₹{f['amount']} ({f['status']})")
            else:
                st.warning("Please add students before managing fees.")

        elif menu == "📦 Inventory":
            st.subheader("Inventory & Stock")
            with st.form("add_inv"):
                item = st.text_input("Item Name")
                cat = st.selectbox("Category", ["First Aid", "Kitchen", "Stationery"])
                qty = st.number_input("Current Quantity", min_value=0)
                min_qty = st.number_input("Minimum Alert Threshold", min_value=0)
                if st.form_submit_button("Add Item"):
                    run_query("INSERT INTO inventory VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), item, cat, qty, min_qty, sid))
                    st.success("Item added to inventory!")
                    st.rerun()
            
            inv_db = run_query("SELECT * FROM inventory WHERE school_id=?", (sid,), True)
            if inv_db:
                for i in inv_db:
                    alert = "🚨 LOW STOCK" if i['quantity'] <= i['min_quantity'] else "✅"
                    st.write(f"{alert} **{i['item_name']}** ({i['category']}) - {i['quantity']} remaining")

        elif menu == "🧸 Care Logs":
            st.subheader("Daily Care & Activity Tracking")
            if students_db:
                with st.form("add_log"):
                    st_dict = {s["name"]: s["id"] for s in students_db}
                    sel_name = st.selectbox("Child", list(st_dict.keys()))
                    act = st.selectbox("Activity", ["💧 Restroom/Diaper", "🍱 Meal/Snack", "🏥 First Aid/Ouchie", "😴 Nap Time"])
                    notes = st.text_input("Details / Notes")
                    if st.form_submit_button("Post Update to Parent"):
                        time_str = datetime.now().strftime("%Y-%m-%d %I:%M %p")
                        run_query("INSERT INTO care_logs VALUES (?,?,?,?,?,?,?)",
                                  (str(uuid.uuid4()), st_dict[sel_name], sel_name, act, notes, time_str, sid))
                        st.success("Activity logged securely!")
                        st.rerun()
            else:
                st.warning("Add students to start logging activities.")

        elif menu == "📸 Gallery":
            st.subheader("Photo Gallery (Parent Viewable)")
            if students_db:
                with st.form("add_photo"):
                    st_dict = {s["name"]: s["id"] for s in students_db}
                    sel_name = st.selectbox("Tag Child", list(st_dict.keys()))
                    caption = st.text_input("Photo Caption")
                    file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
                    if st.form_submit_button("Publish to Parent Dashboard"):
                        if file:
                            run_query("INSERT INTO gallery VALUES (?,?,?,?,?,?)",
                                      (str(uuid.uuid4()), st_dict[sel_name], sel_name, caption, file.read(), sid))
                            st.success("Photo published!")
                            st.rerun()
                        else:
                            st.error("Please upload an image file.")
            else:
                st.warning("Add students to upload photos.")

    # ================= PARENT DASHBOARD =================
    elif st.session_state.auth["role"] == "parent":
        student_id = st.session_state.auth["student_id"]
        student_res = run_query("SELECT * FROM students WHERE id=?", (student_id,), True)
        
        if student_res:
            student = student_res[0]
            st.title(f"👶 {student['name']}'s Dashboard")
            st.write(f"**Class:** {student['class']} | **Blood:** {student['blood']}")
            
            if student.get('allergy'):
                st.warning(f"⚠️ **Known Allergies:** {student['allergy']}")
                
            st.subheader("🧸 Recent Care Logs")
            logs = run_query("SELECT * FROM care_logs WHERE student_id=? ORDER BY time DESC LIMIT 10", (student_id,), True)
            if logs:
                for l in logs:
                    st.write(f"**{l['activity']}** — {l['notes']} • *{l['time']}*")
            else:
                st.info("No logs yet today.")
                
            st.subheader("💰 Fees")
            fees = run_query("SELECT * FROM fees WHERE student_id=? ORDER BY month", (student_id,), True)
            if fees:
                for f in fees:
                    status = "✅ Paid" if f["status"] == "Paid" else "⏳ Pending"
                    st.write(f"{f['month']} — ₹{f['amount']} — {status}")
            else:
                st.info("No fee records found.")
                
            st.subheader("📸 Gallery")
            imgs = run_query("SELECT * FROM gallery WHERE student_id=? ORDER BY id DESC", (student_id,), True)
            if imgs:
                for i in imgs:
                    st.image(i["image"], caption=i["caption"], use_container_width=True)
            else:
                st.info("No photos shared yet.")
