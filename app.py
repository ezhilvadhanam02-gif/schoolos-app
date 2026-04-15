import streamlit as st
import sqlite3
import uuid
from datetime import datetime, timedelta

---------------- CONFIG ----------------

st.set_page_config(page_title="SchoolOS Pro", layout="wide")

---------------- DATABASE ----------------

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

---------------- INIT DB ----------------

def init_db():
    run_query("CREATE TABLE IF NOT EXISTS schools (id TEXT PRIMARY KEY, name TEXT, pass TEXT, plan TEXT, expiry TEXT, extra_students INTEGER DEFAULT 0)")
    run_query("CREATE TABLE IF NOT EXISTS students (id TEXT PRIMARY KEY, name TEXT, blood TEXT, allergy TEXT, parent_name TEXT, parent_phone TEXT, likes TEXT, dislikes TEXT, siblings TEXT, class TEXT, school_id TEXT)")
    run_query("CREATE TABLE IF NOT EXISTS fees (id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT, amount INTEGER, month TEXT, status TEXT, payment_date TEXT, school_id TEXT)")
    run_query("CREATE TABLE IF NOT EXISTS broadcasts (id INTEGER PRIMARY KEY AUTOINCREMENT, msg TEXT, date TEXT)")
    # PHASE 2 TABLES
    run_query("CREATE TABLE IF NOT EXISTS inventory (id TEXT PRIMARY KEY, item_name TEXT, category TEXT, quantity INTEGER, min_quantity INTEGER, school_id TEXT)")
    run_query("CREATE TABLE IF NOT EXISTS care_logs (id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT, activity TEXT, notes TEXT, time TEXT, school_id TEXT)")

init_db()

---------------- PRICING ----------------

PLAN_LIMITS = {"Basic": 30, "Standard": 80, "Premium": 500, "Enterprise": float("inf")}
PLAN_PRICES = {"Basic": 2000, "Standard": 4000, "Premium": 7999, "Enterprise": 9999}

---------------- SESSION ----------------

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}

---------------- LOGIN ----------------

if not st.session_state.auth["logged_in"]:
    st.title("🏫 SchoolOS Pro")
    user = st.text_input("User ID")
    pw = st.text_input("Password", type="password")
    if st.button("Login"):
        if user == "admin" and pw == "admin123":
            st.session_state.auth = {"logged_in": True, "role": "admin"}
            st.rerun()
        school = run_query("SELECT * FROM schools WHERE id=? AND pass=?", (user, pw), fetch=True)
        if school:
            school = school[0]
            expiry = datetime.strptime(school["expiry"], "%Y-%m-%d")
            if datetime.now() < expiry:
                st.session_state.auth = {"logged_in": True, "role": "school", "school_id": user}
                st.rerun()
            else: st.error("Subscription expired")
        else: st.error("Invalid credentials")

---------------- MAIN ----------------

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
                exists = run_query("SELECT * FROM schools WHERE id=?", (sid,), fetch=True)
                if exists: st.warning("School ID already exists!")
                else:
                    expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
                    run_query("INSERT INTO schools VALUES (?, ?, ?, ?, ?, ?)", (sid, name, pw, plan, expiry, 0))
                    st.success("School created!")
        with tab2:
            msg = st.text_area("Message")
            if st.button("Send Broadcast"):
                run_query("INSERT INTO broadcasts (msg, date) VALUES (?, ?)", (msg, str(datetime.now())))
                st.success("Broadcast sent!")
        with tab3:
            schools = run_query("SELECT * FROM schools", fetch=True)
            active = sum(1 for s in schools if datetime.now() < datetime.strptime(s["expiry"], "%Y-%m-%d"))
            revenue = sum(PLAN_PRICES[s["plan"]] for s in schools)
            st.metric("Total Schools", len(schools))
            st.metric("Active Schools", active)
            st.metric("Revenue", f"₹{revenue}")

    # ================= SCHOOL =================
    else:
        sid = st.session_state.auth["school_id"]
        school = run_query("SELECT * FROM schools WHERE id=?", (sid,), fetch=True)[0]
        st.title(f"🏫 {school['name']}")
        
        base = PLAN_LIMITS[school["plan"]]
        max_students = base if base == float("inf") else base + (school["extra_students"] * 50)
        students = run_query("SELECT * FROM students WHERE school_id=?", (sid,), fetch=True)
        student_map = {s["name"]: s["id"] for s in students}
        
        st.sidebar.info(f"Plan: {school['plan']}\nStudents: {len(students)} / {max_students}")
        menu = st.sidebar.selectbox("Menu", ["Dashboard", "Students", "Fees", "Inventory", "Care Logs", "Upgrade"])

        # -------- DASHBOARD --------
        if menu == "Dashboard":
            st.metric("Total Students", len(students))
            # Show active broadcasts
            bc = run_query("SELECT * FROM broadcasts ORDER BY id DESC LIMIT 1", fetch=True)
            if bc: st.warning(f"📢 {bc[0]['msg']}")

        # -------- STUDENTS --------
        elif menu == "Students":
            st.subheader("Student Profiles")
            with st.form("add_student"):
                name = st.text_input("Name")
                blood = st.selectbox("Blood Group", ["O+","O-","A+","A-","B+","B-","AB+","AB-"])
                allergy = st.text_input("Allergies")
                parent_name = st.text_input("Parent Name")
                parent_phone = st.text_input("Parent Phone")
                likes = st.text_input("Likes")
                dislikes = st.text_input("Dislikes")
                siblings = st.text_input("Siblings")
                student_class = st.text_input("Class")
                if st.form_submit_button("Add Student"):
                    run_query("INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), name, blood, allergy, parent_name, parent_phone, likes, dislikes, siblings, student_class, sid))
                    st.success("Added!")
                    st.rerun()
            for s in students:
                with st.expander(f"👶 {s['name']} - {s['class']}"):
                    st.write(f"**Parent:** {s['parent_name']} ({s['parent_phone']})")
                    st.write(f"**Health:** Blood {s['blood']} | Allergies: {s['allergy']}")

        # -------- FEES --------
        elif menu == "Fees":
            st.subheader("Fee Management")
            if not student_map: st.info("Add students first")
            else:
                with st.form("fee_form"):
                    student_name = st.selectbox("Student", list(student_map.keys()))
                    amount = st.number_input("Amount", min_value=0)
                    month = st.selectbox("Month", ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])
                    if st.form_submit_button("Add Fee"):
                        run_query("INSERT INTO fees VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), student_map[student_name], student_name, amount, month, "Pending", "", sid))
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
                        run_query("UPDATE fees SET status=?, payment_date=? WHERE id=?", ("Paid", str(datetime.now().date()), f["id"]))
                        st.rerun()
                else: col4.success("Paid")

        # -------- INVENTORY (UPGRADED) --------
        elif menu == "Inventory":
            st.subheader("📦 Inventory Management")
            with st.form("add_item"):
                item_input = st.text_input("Item Name").strip()
                cat = st.selectbox("Category", ["First Aid", "Kitchen", "Stationery", "Cleaning"])
                qty = st.number_input("Add Quantity", min_value=1)
                min_q = st.number_input("Min Level for Alert", min_value=1)
                if st.form_submit_button("Update Stock"):
                    existing = run_query("SELECT id, quantity FROM inventory WHERE item_name=? AND school_id=?", (item_input, sid), True)
                    if existing:
                        run_query("UPDATE inventory SET quantity=quantity+? WHERE id=?", (qty, existing[0]['id']))
                    else:
                        run_query("INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), item_input, cat, qty, min_q, sid))
                    st.success("Stock Updated!")
                    st.rerun()
            
            items = run_query("SELECT * FROM inventory WHERE school_id=?", (sid,), True)
            for i in items:
                col1, col2 = st.columns([3, 1])
                col1.write(f"**{i['item_name']}** ({i['category']}) - Qty: {i['quantity']}")
                if i["quantity"] <= i["min_quantity"]: col2.error("Low Stock!")

        # -------- CARE LOGS (UPGRADED) --------
        elif menu == "Care Logs":
            st.subheader("👶 Daily Care Activity")
            if not student_map: st.info("Add students first")
            else:
                with st.form("log"):
                    st_name = st.selectbox("Student", list(student_map.keys()))
                    activity = st.selectbox("Activity", ["Meal","Sleep","Potty","Play","Medicine"])
                    notes = st.text_input("Notes")
                    if st.form_submit_button("Log Activity"):
                        # Uses formatted time for readability
                        t = datetime.now().strftime("%I:%M %p")
                        run_query("INSERT INTO care_logs VALUES (?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), student_map[st_name], st_name, activity, notes, t, sid))
                        st.success("Logged!")
                        st.rerun()
                
                logs = run_query("SELECT * FROM care_logs WHERE school_id=? ORDER BY time DESC LIMIT 20", (sid,), True)
                for l in logs:
                    st.text(f"[{l['time']}] {l['student_name']}: {l['activity']} - {l['notes']}")

        # -------- UPGRADE --------
        elif menu == "Upgrade":
            st.subheader("Plan Upgrades")
            for p, price in PLAN_PRICES.items():
                st.write(f"**{p}**: ₹{price}/year (Limit: {PLAN_LIMITS[p]})")
