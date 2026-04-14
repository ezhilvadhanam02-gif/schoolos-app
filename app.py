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
    return None

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
        parent_pass TEXT,
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
    run_query("""CREATE TABLE IF NOT EXISTS gallery (
        id TEXT PRIMARY KEY,
        student_id TEXT,
        student_name TEXT,
        caption TEXT,
        image BLOB,
        school_id TEXT
    )""")
init_db()

# ---------------- SESSION ----------------
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
            st.session_state.auth = {"logged_in": True, "role": "admin"}
            st.rerun()
        
        school = run_query("SELECT * FROM schools WHERE id=? AND pass=?", (user, pw), True)
        if role == "School/Admin" and school:
            school = school[0]
            if datetime.now() < datetime.strptime(school["expiry"], "%Y-%m-%d"):
                st.session_state.auth = {"logged_in": True, "role": "school", "school_id": user}
                st.rerun()
            else:
                st.error("Your school subscription has expired!")
        
        parent = run_query("SELECT * FROM students WHERE parent_phone=? AND parent_pass=?", (user, pw), True)
        if role == "Parent" and parent:
            parent = parent[0]
            st.session_state.auth = {
                "logged_in": True,
                "role": "parent",
                "school_id": parent["school_id"],
                "student_id": parent["id"]
            }
            st.rerun()
        
        st.error("Invalid credentials. Try again.")

else:
    if st.sidebar.button("🚪 Logout"):
        st.session_state.auth = {"logged_in": False, "role": None}
        st.rerun()

    sid = st.session_state.auth.get("school_id")

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
                    run_query(
                        "INSERT INTO schools VALUES (?, ?, ?, ?, ?, ?)",
                        (sid_input, name, pw, plan, expiry, 0)
                    )
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
        st.title(f"🏫 {sid.upper()} Dashboard")
        
        total_students = len(run_query("SELECT id FROM students WHERE school_id=?", (sid,), True))
        pending_fees = len(run_query("SELECT id FROM fees WHERE school_id=? AND status='Pending'", (sid,), True))
        low_stock = len(run_query("SELECT id FROM inventory WHERE school_id=? AND quantity <= min_quantity", (sid,), True))
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Students", total_students)
        col2.metric("Pending Fees", pending_fees)
        col3.metric("Low Stock Items", low_stock)
        
        menu = st.sidebar.selectbox(
            "Menu",
            ["📋 Students", "💰 Fees", "📦 Inventory", "🧸 Care Logs", "📸 Gallery"]
        )

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
                phone = st.text_input("Parent Phone")
                ppass = st.text_input("Parent Password (for login)")
                
                if st.form_submit_button("Add Student"):
                    if not name or not parent or not phone:
                        st.error("Name, Parent & Phone are required")
                    else:
                        run_query(
                            "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (str(uuid.uuid4()), name, blood, allergy, parent, phone, ppass, likes, dislikes, "", class_, sid)
                        )
                        st.success("Student added successfully!")
                        st.rerun()

            st.subheader("All Students")
            students = run_query("SELECT * FROM students WHERE school_id=?", (sid,), True)
            if students:
                for s in students:
                    with st.expander(f"👦 {s['name']} • {s['class']}"):
                        st.write(f"**Blood:** {s['blood']} | **Allergy:** {s['allergy'] or 'None'}")
                        st.write(f"**Parent:** {s['parent_name']} | **Phone:** {s['parent_phone']}")
                        st.write(f"**Likes:** {s['likes']} | **Dislikes:** {s['dislikes']}")
            else:
                st.info("No students yet.")

        # (Fees, Inventory, Care Logs, Gallery sections are included below - full code continues)

        elif menu == "💰 Fees":
            st.subheader("Fee Management")
            students = run_query("SELECT * FROM students WHERE school_id=?", (sid,), True)
            student_map = {s["name"]: s["id"] for s in students}
            with st.form("fee_form"):
                student_name = st.selectbox("Student", list(student_map.keys()))
                amount = st.number_input("Amount (₹)", min_value=0)
                month = st.selectbox("Month", ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])
                if st.form_submit_button("Add Fee Record"):
                    run_query("INSERT INTO fees VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), student_map[student_name], student_name, amount, month, "Pending", "", sid))
                    st.success("Fee record added!")
                    st.rerun()
            st.subheader("All Fees")
            fees = run_query("SELECT * FROM fees WHERE school_id=? ORDER BY month", (sid,), True)
            if fees:
                for f in fees:
                    status = "✅ Paid" if f["status"] == "Paid" else "⏳ Pending"
                    col1, col2, col3, col4 = st.columns([2,1,1,2])
                    col1.write(f["student_name"])
                    col2.write(f["month"])
                    col3.write(f"₹{f['amount']}")
                    col4.write(status)
                    if f["status"] == "Pending":
                        if st.button(f"Mark {f['student_name']} - {f['month']} as PAID", key=f["id"]):
                            run_query("UPDATE fees SET status='Paid', payment_date=? WHERE id=?", (str(datetime.now()), f["id"]))
                            st.rerun()
            else:
                st.info("No fee records yet.")

        elif menu == "📦 Inventory":
            st.subheader("Inventory Management")
            col1, col2, col3 = st.columns([3,2,2])
            with col1: item = st.text_input("Item Name")
            with col2: category = st.selectbox("Category", ["General", "Stationery", "Food", "Uniform", "Medicine"])
            with col3: qty = st.number_input("Current Quantity", min_value=0, value=10)
            if st.button("Add / Update Item"):
                existing = run_query("SELECT id FROM inventory WHERE item_name=? AND school_id=?", (item, sid), True)
                if existing:
                    run_query("UPDATE inventory SET quantity=? WHERE id=?", (qty, existing[0]["id"]))
                    st.success("Quantity updated!")
                else:
                    run_query("INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), item, category, qty, 5, sid))
                    st.success("Item added!")
                st.rerun()
            st.subheader("Current Stock")
            inventory = run_query("SELECT * FROM inventory WHERE school_id=?", (sid,), True)
            if inventory:
                for item in inventory:
                    color = "🔴 Low Stock" if item["quantity"] <= item["min_quantity"] else "🟢 OK"
                    st.write(f"{color} **{item['item_name']}** ({item['category']}) — Qty: **{item['quantity']}**")
            else:
                st.info("No items in inventory yet.")

        elif menu == "🧸 Care Logs":
            st.subheader("Add Care Log")
            students = run_query("SELECT * FROM students WHERE school_id=?", (sid,), True)
            student_map = {s["name"]: s["id"] for s in students}
            st_name = st.selectbox("Student", list(student_map.keys()))
            activity = st.selectbox("Activity", ["Meal", "Sleep", "Play", "Toilet", "Activity"])
            notes = st.text_input("Notes / Observation")
            if st.button("Save Log"):
                run_query("INSERT INTO care_logs VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), student_map[st_name], st_name, activity, notes, str(datetime.now()), sid))
                st.success("Care log added!")
                st.rerun()
            st.subheader("Recent Care Logs")
            logs = run_query("SELECT * FROM care_logs WHERE school_id=? ORDER BY time DESC LIMIT 30", (sid,), True)
            for l in logs:
                st.caption(f"{l['time'][:16]} • {l['student_name']}")
                st.write(f"**{l['activity']}** — {l['notes']}")

        elif menu == "📸 Gallery":
            st.subheader("Upload Photo")
            students = run_query("SELECT * FROM students WHERE school_id=?", (sid,), True)
            student_map = {s["name"]: s["id"] for s in students}
            st_name = st.selectbox("Student", list(student_map.keys()))
            img = st.file_uploader("Choose image", type=["jpg", "png", "jpeg"])
            caption = st.text_input("Caption / Description")
            if st.button("Upload to Gallery") and img:
                run_query("INSERT INTO gallery VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), student_map[st_name], st_name, caption, img.read(), sid))
                st.success("Photo uploaded!")
                st.rerun()
            st.subheader("School Gallery")
            imgs = run_query("SELECT * FROM gallery WHERE school_id=? ORDER BY id DESC", (sid,), True)
            if imgs:
                cols = st.columns(3)
                for idx, i in enumerate(imgs):
                    with cols[idx % 3]:
                        st.image(i["image"], caption=f"{i['student_name']} — {i['caption']}", use_column_width=True)
            else:
                st.info("No photos yet.")

    # ================= PARENT DASHBOARD =================
    elif st.session_state.auth["role"] == "parent":
        student_id = st.session_state.auth["student_id"]
        student = run_query("SELECT * FROM students WHERE id=?", (student_id,), True)[0]
        st.title(f"👶 {student['name']}'s Dashboard")
        st.write(f"**Class:** {student['class']} | **Blood:** {student['blood']}")
        if student.get('allergy'):
            st.warning(f"⚠️ Allergy: {student['allergy']}")
        st.subheader("🧸 Recent Care Logs")
        logs = run_query("SELECT * FROM care_logs WHERE student_id=? ORDER BY time DESC LIMIT 10", (student_id,), True)
        for l in logs:
            st.write(f"**{l['activity']}** — {l['notes']} • {l['time'][:16]}")
        st.subheader("💰 Fees")
        fees = run_query("SELECT * FROM fees WHERE student_id=? ORDER BY month", (student_id,), True)
        for f in fees:
            status = "✅ Paid" if f["status"] == "Paid" else "⏳ Pending"
            st.write(f"{f['month']} — ₹{f['amount']} — {status}")
        st.subheader("📸 Gallery")
        imgs = run_query("SELECT * FROM gallery WHERE student_id=? ORDER BY id DESC", (student_id,), True)
        if imgs:
            for i in imgs:
                st.image(i["image"], caption=i["caption"])
        else:
            st.info("No photos yet.")
