# SCHOOL PRO CLOUD v2.0 - COMPLETE
import streamlit as st
import sqlite3
import uuid
import re
import secrets
from datetime import datetime, timedelta
import bcrypt

# Page config
st.set_page_config(page_title="SchoolOS Pro", layout="wide", page_icon="🏫")

# Database
@st.cache_resource
def get_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS schools (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, pass TEXT NOT NULL,
        plan TEXT DEFAULT 'Basic', expiry TEXT, extra_students INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY, name TEXT, blood TEXT, allergy TEXT,
        parent_name TEXT, parent_phone TEXT, likes TEXT, dislikes TEXT,
        siblings TEXT, class TEXT, school_id TEXT, is_active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS fees (
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT,
        amount INTEGER, month TEXT, status TEXT, payment_date TEXT, school_id TEXT
    );
    CREATE TABLE IF NOT EXISTS inventory (
        id TEXT PRIMARY KEY, item_name TEXT, category TEXT,
        quantity INTEGER, min_quantity INTEGER, school_id TEXT
    );
    CREATE TABLE IF NOT EXISTS care_logs (
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT,
        activity TEXT, notes TEXT, time TEXT DEFAULT CURRENT_TIMESTAMP,
        school_id TEXT, type TEXT, sub_type TEXT, status TEXT,
        start_time TEXT, end_time TEXT
    );
    CREATE TABLE IF NOT EXISTS broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, msg TEXT,
        date TEXT DEFAULT CURRENT_TIMESTAMP, priority TEXT DEFAULT 'normal'
    );
    CREATE TABLE IF NOT EXISTS admin_config (
        key TEXT PRIMARY KEY, value TEXT
    );
    """)
    
    # Default admin
    hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
    conn.execute("INSERT OR IGNORE INTO admin_config VALUES (?, ?)", 
                ("admin_password_hash", hashed))
    conn.commit()
    return conn

# Security
def sanitize(text):
    if not isinstance(text, str):
        return ""
    return re.sub(r'[<>\"\'%;()&+]', '', text)[:255].strip()

def hash_pw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def check_pw(pw, hashed):
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except:
        return False

def gen_id():
    return secrets.token_urlsafe(16)

# Session
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}

# Login
def login_page():
    st.title("🏫 SchoolOS Pro")
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        user = st.text_input("User ID")
        pw = st.text_input("Password", type="password")
        
        if st.button("🔐 Login", type="primary", use_container_width=True):
            db = get_db()
            
            if user == "admin":
                h = db.execute("SELECT value FROM admin_config WHERE key='admin_password_hash'").fetchone()
                if h and check_pw(pw, h[0]):
                    st.session_state.auth = {"logged_in": True, "role": "admin", "school_id": None}
                    st.rerun()
                else:
                    st.error("Invalid credentials")
                return
            
            school = db.execute("SELECT * FROM schools WHERE id=? AND is_active=1", (user,)).fetchone()
            if not school:
                st.error("School not found")
                return
            if not check_pw(pw, school["pass"]):
                st.error("Wrong password")
                return
            
            try:
                if datetime.now() > datetime.strptime(school["expiry"], "%Y-%m-%d"):
                    st.error("Subscription expired")
                    return
            except:
                pass
            
            st.session_state.auth = {"logged_in": True, "role": "school", "school_id": user}
            st.rerun()

# Admin
def admin_page():
    st.title("👑 Admin")
    db = get_db()
    
    with st.sidebar:
        if st.button("🚪 Logout"):
            st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}
            st.rerun()
        st.metric("Schools", db.execute("SELECT COUNT(*) FROM schools WHERE is_active=1").fetchone()[0])
    
    t1, t2, t3 = st.tabs(["🏫 Schools", "📢 Broadcasts", "⚙️ Settings"])
    
    with t1:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("Create School")
            with st.form("add_school", clear_on_submit=True):
                sid = st.text_input("School ID")
                name = st.text_input("Name")
                pw = st.text_input("Password", type="password")
                plan = st.selectbox("Plan", ["Basic", "Standard", "Premium", "Enterprise"])
                years = st.number_input("Years", 1, 5, 1)
                
                if st.form_submit_button("➕ Create"):
                    if not all([sid, name, pw]):
                        st.error("Fill all fields")
                    elif db.execute("SELECT 1 FROM schools WHERE id=?", (sid,)).fetchone():
                        st.error("ID exists")
                    else:
                        exp = (datetime.now() + timedelta(days=365*years)).strftime("%Y-%m-%d")
                        db.execute("INSERT INTO schools VALUES (?,?,?,?,?,?)",
                                  (sid, name, hash_pw(pw), plan, exp, 0))
                        db.commit()
                        st.success(f"Created {name}!")
        
        with c2:
            st.subheader("All Schools")
            for s in db.execute("SELECT * FROM schools WHERE is_active=1").fetchall():
                with st.expander(f"{s['name']} ({s['id']})"):
                    st.write(f"Plan: {s['plan']} | Expires: {s['expiry']}")
                    if st.button("🗑️ Delete", key=f"del_{s['id']}"):
                        db.execute("UPDATE schools SET is_active=0 WHERE id=?", (s['id'],))
                        db.commit()
                        st.rerun()
    
    with t2:
        with st.form("broadcast"):
            msg = st.text_area("Message")
            priority = st.selectbox("Priority", ["low", "normal", "high", "urgent"])
            if st.form_submit_button("📢 Send") and msg.strip():
                db.execute("INSERT INTO broadcasts (msg, priority) VALUES (?, ?)",
                          (sanitize(msg), priority))
                db.commit()
                st.success("Sent!")
        
        for b in db.execute("SELECT * FROM broadcasts ORDER BY date DESC LIMIT 10").fetchall():
            emoji = {"low": "⚪", "normal": "🔵", "high": "🟠", "urgent": "🔴"}.get(b["priority"], "⚪")
            st.markdown(f"{emoji} **{b['date'][:10]}**: {b['msg']}")
    
    with t3:
        with st.form("chg_pw"):
            old = st.text_input("Current", type="password")
            new = st.text_input("New", type="password")
            conf = st.text_input("Confirm", type="password")
            if st.form_submit_button("Update"):
                cur = db.execute("SELECT value FROM admin_config WHERE key='admin_password_hash'").fetchone()[0]
                if not check_pw(old, cur):
                    st.error("Wrong password")
                elif new != conf:
                    st.error("Don't match")
                else:
                    db.execute("UPDATE admin_config SET value=? WHERE key='admin_password_hash'", (hash_pw(new),))
                    db.commit()
                    st.success("Updated!")

# School
def school_page():
    sid = st.session_state.auth["school_id"]
    db = get_db()
    school = db.execute("SELECT * FROM schools WHERE id=?", (sid,)).fetchone()
    st.title(f"🏫 {school['name']}")
    
    with st.sidebar:
        menu = st.radio("Menu", ["📊 Dashboard", "👨‍🎓 Students", "💳 Fees", "📦 Inventory", "🧸 Care Logs"])
        if st.button("🚪 Logout"):
            st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}
            st.rerun()
    
    if menu == "📊 Dashboard":
        c1, c2, c3 = st.columns(3)
        c1.metric("Students", db.execute("SELECT COUNT(*) FROM students WHERE school_id=? AND is_active=1", (sid,)).fetchone()[0])
        c2.metric("Pending", db.execute("SELECT COUNT(*) FROM fees WHERE school_id=? AND status='Pending'", (sid,)).fetchone()[0])
        c3.metric("Revenue", f"₹{db.execute('SELECT COALESCE(SUM(amount),0) FROM fees WHERE school_id=? AND status=\'Paid\'', (sid,)).fetchone()[0]:,}")
    
    elif menu == "👨‍🎓 Students":
        t1, t2 = st.tabs(["➕ Add", "📋 List"])
        with t1:
            with st.form("add_student"):
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Name*")
                    blood = st.selectbox("Blood", ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"])
                    allergy = st.text_area("Allergies")
                    s_class = st.text_input("Class*")
                with c2:
                    parent = st.text_input("Parent*")
                    phone = st.text_input("Phone")
                    likes = st.text_area("Likes")
                if st.form_submit_button("✅ Add") and name and s_class and parent:
                    db.execute("INSERT INTO students VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                              (gen_id(), sanitize(name), blood, sanitize(allergy), sanitize(parent), sanitize(phone),
                               sanitize(likes), "", "", sanitize(s_class), sid, 1))
                    db.commit()
                    st.success(f"Added {name}!")
        with t2:
            for s in db.execute("SELECT * FROM students WHERE school_id=? AND is_active=1", (sid,)).fetchall():
                with st.expander(f"{s['name']} ({s['class']})"):
                    st.write(f"Blood: {s['blood']} | Parent: {s['parent_name']}")
                    if st.button("Remove", key=f"rm_{s['id']}"):
                        db.execute("UPDATE students SET is_active=0 WHERE id=?", (s['id'],))
                        db.commit()
                        st.rerun()
    
    elif menu == "💳 Fees":
        t1, t2 = st.tabs(["➕ Add", "📊 View"])
        students = db.execute("SELECT id, name FROM students WHERE school_id=? AND is_active=1", (sid,)).fetchall()
        if not students:
            st.warning("No students")
            return
        stu_dict = {s["name"]: s["id"] for s in students}
        with t1:
            with st.form("add_fee"):
                sel = st.selectbox("Student", list(stu_dict.keys()))
                amt = st.number_input("Amount", min_value=0, step=100)
                month = st.text_input("Month (e.g., Jan 2025)")
                status = st.selectbox("Status", ["Paid", "Pending"])
                if st.form_submit_button("💾 Save"):
                    db.execute("INSERT INTO fees VALUES (?,?,?,?,?,?,?,?)",
                              (gen_id(), stu_dict[sel], sel, amt, month, status,
                               datetime.now().isoformat() if status=="Paid" else None, sid))
                    db.commit()
                    st.success("Saved!")
        with t2:
            for f in db.execute("SELECT * FROM fees WHERE school_id=?", (sid,)).fetchall():
                color = "green" if f["status"]=="Paid" else "orange"
                st.markdown(f"**{f['student_name']}** | ₹{f['amount']} | {f['month']} | :{color}[{f['status']}]")
    
    elif menu == "📦 Inventory":
        t1, t2 = st.tabs(["➕ Add", "📦 Stock"])
        with t1:
            with st.form("add_item"):
                name = st.text_input("Item*")
                cat = st.selectbox("Category", ["Stationery", "Books", "Sports", "Lab", "Furniture", "Electronics", "Other"])
                qty = st.number_input("Qty", min_value=0)
                min_qty = st.number_input("Min", min_value=0, value=10)
                if st.form_submit_button("➕ Add") and name:
                    db.execute("INSERT INTO inventory VALUES (?,?,?,?,?,?)",
                              (gen_id(), sanitize(name), cat, qty, min_qty, sid))
                    db.commit()
                    st.success(f"Added {name}!")
        with t2:
            for i in db.execute("SELECT * FROM inventory WHERE school_id=?", (sid,)).fetchall():
                emoji = "🔴" if i["quantity"] <= i["min_quantity"] else "🟢"
                st.write(f"{emoji} **{i['item_name']}** - {i['quantity']} (min: {i['min_quantity']})")
    
    elif menu == "🧸 Care Logs":
        t1, t2 = st.tabs(["➕ New", "📋 Today"])
        students = db.execute("SELECT id, name FROM students WHERE school_id=? AND is_active=1", (sid,)).fetchall()
        if not students:
            st.warning("No students")
            return
        stu_dict = {s["name"]: s["id"] for s in students}
        with t1:
            sel = st.selectbox("Student", list(stu_dict.keys()))
            log_type = st.selectbox("Type", ["Bathroom", "Food", "Nap"])
            if log_type == "Bathroom":
                with st.form("log_bath"):
                    sub = st.selectbox("Type", ["Pee", "Potty", "Diaper"])
                    if st.form_submit_button("Save"):
                        db.execute("INSERT INTO care_logs (id, student_id, student_name, activity, school_id, type, sub_type) VALUES (?,?,?,?,?,?,?)",
                                  (gen_id(), stu_dict[sel], sel, "Bathroom", sid, "bathroom", sub.lower()))
                        db.commit()
                        st.success("Saved!")
            elif log_type == "Food":
                with st.form("log_food"):
                    meal = st.selectbox("Meal", ["Breakfast", "Lunch", "Snack"])
                    status = st.selectbox("Status", ["Full", "Half", "Little", "Refused"])
                    if st.form_submit_button("Save"):
                        db.execute("INSERT INTO care_logs (id, student_id, student_name, activity, school_id, type, sub_type, status) VALUES (?,?,?,?,?,?,?,?)",
                                  (gen_id(), stu_dict[sel], sel, "Food", sid, "food", meal, status))
                        db.commit()
                        st.success("Saved!")
            elif log_type == "Nap":
                with st.form("log_nap"):
                    start = st.time_input("Start")
                    end = st.time_input("End")
                    if st.form_submit_button("Save"):
                        db.execute("INSERT INTO care_logs (id, student_id, student_name, activity, school_id, type, start_time, end_time) VALUES (?,?,?,?,?,?,?,?)",
                                  (gen_id(), stu_dict[sel], sel, "Nap", sid, "nap", str(start), str(end)))
                        db.commit()
                        st.success("Saved!")
        with t2:
            for l in db.execute("SELECT * FROM care_logs WHERE school_id=? AND date(time)=date('now') ORDER BY time DESC", (sid,)).fetchall():
                emoji = {"bathroom": "🚽", "food": "🍽️", "nap": "😴"}.get(l["type"], "📝")
                st.markdown(f"{emoji} **{l['student_name']}** - {l['activity']} at {l['time'][11:16]}")

# Main
def main():
    if not st.session_state.auth["logged_in"]:
        login_page()
    elif st.session_state.auth["role"] == "admin":
        admin_page()
    else:
        school_page()
    st.divider()
    st.caption("SchoolOS Pro v2.0 | Cloud")

if __name__ == "__main__":
    main()
