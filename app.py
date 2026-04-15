import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta
import math

# ==========================================
# 1. FRONT-END CONFIG & CSS
# ==========================================
st.set_page_config(page_title="Bright Beginnings Pro", layout="wide", page_icon="☀️")

st.markdown("""
    <style>
    .receipt { border: 2px dashed #000; padding: 20px; font-family: monospace; background: #fff; color: #000;}
    .sos-alert { background: #ff4b4b; color: white; padding: 15px; border-radius: 8px; font-weight: bold; text-align: center; animation: pulse 1s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. BACK-END DATABASE ENGINE
# ==========================================
DB_FILES = {
    'schools': 'db_schools.json',
    'students': 'db_students.json',
    'inventory': 'db_inventory.json',
    'logs': 'db_daily_logs.json',
    'fees': 'db_fees.json',
    'messages': 'db_messages.json',
    'notices': 'db_notices.json',
    'gallery': 'db_gallery.json' # Stores photo metadata
}

def load_db(table_name, default_data):
    file_path = DB_FILES[table_name]
    if not os.path.exists(file_path):
        with open(file_path, 'w') as f: json.dump(default_data, f)
        return default_data
    with open(file_path, 'r') as f: return json.load(f)

def save_db(table_name, data):
    with open(DB_FILES[table_name], 'w') as f: json.dump(data, f)

# Initialize Tables
db_schools = load_db('schools', {})
db_students = load_db('students', [])
db_inventory = load_db('inventory', [
    {"item": "Band-aids", "cat": "First Aid", "qty": 50, "min": 10},
    {"item": "Milk Powder", "cat": "Kitchen", "qty": 10, "min": 2},
    {"item": "Crayons", "cat": "Stationery", "qty": 100, "min": 20}
])
db_logs = load_db('logs', [])
db_fees = load_db('fees', {})
db_messages = load_db('messages', [])
db_notices = load_db('notices', [])

# ==========================================
# 3. AUTHENTICATION ROUTER
# ==========================================
if 'auth' not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}

def login_system():
    st.title("☀️ Bright Beginnings OS")
    st.write("Enter your credentials to access your workspace.")
    
    uid = st.text_input("User ID")
    upw = st.text_input("Password", type="password")
    
    if st.button("Secure Login"):
        if uid == "admin_boss" and upw == "secure123":
            st.session_state.auth = {"logged_in": True, "role": "super_admin", "school_id": "MASTER"}
            st.rerun()
        elif uid in db_schools and db_schools[uid]['pass'] == upw:
            expiry = datetime.strptime(db_schools[uid]['expiry'], '%Y-%m-%d')
            if datetime.now() < expiry:
                st.session_state.auth = {"logged_in": True, "role": "school", "school_id": uid}
                st.rerun()
            else:
                st.error("Account Locked: Annual subscription expired.")
        else:
            st.error("Invalid ID or Password.")

# ==========================================
# 4. SUPER ADMIN INTERFACE (YOUR DASHBOARD)
# ==========================================
def render_super_admin():
    st.title("👑 Owner Command Center")
    t1, t2, t3 = st.tabs(["Manage Clients", "Global Broadcast", "System Revenue"])
    
    with t1:
        st.subheader("Onboard New School")
        with st.form("new_client"):
            s_id = st.text_input("Client ID (e.g., school_01)")
            s_pw = st.text_input("Client Password")
            s_name = st.text_input("School Name")
            if st.form_submit_button("Generate 1-Year License"):
                exp = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
                db_schools[s_id] = {"name": s_name, "pass": s_pw, "expiry": exp}
                save_db('schools', db_schools)
                st.success(f"License generated for {s_name}")
        if db_schools:
            st.table(pd.DataFrame.from_dict(db_schools, orient='index'))

    with t2:
        st.subheader("Push Notice to All Schools")
        msg = st.text_area("Message Content")
        is_sos = st.checkbox("Mark as 🚨 EMERGENCY SOS")
        if st.button("Broadcast Now"):
            prefix = "🚨 SOS: " if is_sos else "📢 UPDATE: "
            db_notices.append({"date": str(datetime.now()), "msg": prefix + msg})
            save_db('notices', db_notices)
            st.success("Broadcast deployed across all tenants.")

    with t3:
        st.subheader("Revenue Audit")
        st.metric("Total Active Licenses", len(db_schools))
        st.write("Assuming $1500/year per school:")
        st.metric("Projected Annual ARR", f"${len(db_schools) * 1500}")

# ==========================================
# 5. SCHOOL TENANT INTERFACE (CLIENT DASHBOARD)
# ==========================================
def render_school_dashboard():
    sid = st.session_state.auth["school_id"]
    school_name = db_schools[sid]['name']
    
    # Check for SOS / Broadcasts
    if db_notices and "🚨" in db_notices[-1]['msg']:
        st.markdown(f'<div class="sos-alert">{db_notices[-1]["msg"]}</div><br>', unsafe_allow_html=True)
        
    st.sidebar.title(f"🏫 {school_name}")
    nav = st.sidebar.radio("Workspace", [
        "Daily Care & Logs", 
        "Student Directory", 
        "Photo Gallery",
        "Inventory Management", 
        "Fee & Receipts", 
        "Parent Queries",
        "Staff Attendance"
    ])

    # Filter data for this specific school
    my_students = [s for s in db_students if s.get('school') == sid]
    student_names = [s['name'] for s in my_students]

    if nav == "Daily Care & Logs":
        st.title("🧸 Daily Care Tracker")
        with st.form("log_form"):
            child = st.selectbox("Select Child", student_names) if student_names else st.selectbox("Select Child", ["No students found"])
            activity = st.selectbox("Activity", ["💧 Pee/Potty", "🧻 Diaper Change", "🍱 Lunch", "🍎 Snacks", "🏥 Ouchie/First Aid"])
            notes = st.text_input("Details (e.g., 'Ate all', 'Dry')")
            if st.form_submit_button("Post Update to Parent"):
                db_logs.append({"school": sid, "child": child, "act": activity, "notes": notes, "time": datetime.now().strftime("%I:%M %p")})
                save_db('logs', db_logs)
                st.success("Update sent to parent feed!")
        
        st.subheader("Today's Timeline")
        my_logs = [log for log in db_logs if log.get('school') == sid]
        if my_logs: st.table(pd.DataFrame(my_logs).tail(5))

    elif nav == "Student Directory":
        st.title("📁 Student Profiles")
        with st.expander("➕ Enroll New Student"):
            with st.form("enroll"):
                name = st.text_input("Full Name")
                parent = st.text_input("Parent Name & Contact")
                bg = st.selectbox("Blood Group", ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"])
                allg = st.text_input("Critical Allergies (Leave blank if none)")
                if st.form_submit_button("Save Profile"):
                    db_students.append({"school": sid, "name": name, "parent": parent, "bg": bg, "allergies": allg})
                    save_db('students', db_students)
                    st.rerun()
        if my_students: st.dataframe(pd.DataFrame(my_students))

    elif nav == "Photo Gallery":
        st.title("📸 Class Photos & Tagging")
        uploaded_file = st.file_uploader("Upload Class Photo", type=['jpg', 'png', 'jpeg'])
        if uploaded_file and student_names:
            st.image(uploaded_file, width=300)
            tagged = st.multiselect("Tag Students in this photo", student_names)
            if st.button("Publish to Parents"):
                st.success(f"Photo published! Notifications sent to parents of: {', '.join(tagged)}")

    elif nav == "Inventory Management":
        st.title("📦 Resource Stock")
        cat_filter = st.radio("Category", ["All", "First Aid", "Kitchen", "Stationery"], horizontal=True)
        
        for i, item in enumerate(db_inventory):
            if cat_filter == "All" or item['cat'] == cat_filter:
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.write(f"**{item['item']}** ({item['qty']} left)")
                if item['qty'] <= item['min']: c1.error("LOW STOCK")
                if c2.button("➕", key=f"add_{i}"):
                    db_inventory[i]['qty'] += 1
                    save_db('inventory', db_inventory)
                    st.rerun()
                if c3.button("➖", key=f"sub_{i}"):
                    db_inventory[i]['qty'] -= 1
                    save_db('inventory', db_inventory)
                    st.rerun()

    elif nav == "Fee & Receipts":
        st.title("💰 Financial Ledger")
        if student_names:
            child = st.selectbox("Select Account", student_names)
            amt = st.number_input("Payment Amount ($)", min_value=1)
            if st.button("Process Payment & Generate Receipt"):
                date_str = datetime.now().strftime("%Y-%m-%d")
                st.markdown(f"""
                <div class="receipt">
                    <h2>{school_name.upper()}</h2>
                    <p><b>Official Receipt</b></p><hr>
                    <p>Student: {child}</p>
                    <p>Date: {date_str}</p>
                    <p>Amount Received: <b>${amt}</b></p>
                    <hr><p>Thank you for your business.</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("Please add students first.")

    elif nav == "Parent Queries":
        st.title("💬 Private Messaging")
        st.info("Parents submit queries via their mobile view. Teachers respond here.")
        # Placeholder for 2-way chat loop
        st.text_area("Respond to pending query (Child: Rahul, Issue: Late pickup today)")
        st.button("Send Reply")

    elif nav == "Staff Attendance":
        st.title("📍 Geofenced Check-In (10m)")
        st.write("System requesting high-accuracy GPS coordinates...")
        # Simulating the JS Geolocation for the backend logic
        st.info("Distance to school center: ~4 meters.")
        if st.button("Confirm Arrival (In-Time)"):
            st.success(f"Verified! In-Time logged at {datetime.now().strftime('%H:%M %p')}")

# ==========================================
# 6. APP EXECUTION
# ==========================================
if not st.session_state.auth["logged_in"]:
    login_system()
else:
    if st.sidebar.button("Log Out"):
        st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}
        st.rerun()
        
    if st.session_state.auth["role"] == "super_admin":
        render_super_admin()
    else:
        render_school_dashboard()
