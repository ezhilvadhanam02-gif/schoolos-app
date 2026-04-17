# SCHOOL PRO PHASE 3 - ATTENDANCE, CLASSES & PROFILE PHOTOS
import streamlit as st
import sqlite3
import re
import secrets
import base64
import io
from datetime import datetime, timedelta, date
import bcrypt
from PIL import Image

st.set_page_config(page_title="SchoolOS Pro Phase 3", layout="wide", page_icon="🏫")

# PLAN LIMITS
PLAN_LIMITS = {"Basic": 30, "Standard": 80, "Premium": 500, "Enterprise": 999999}

# Database
@st.cache_resource
def get_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS schools (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, pass TEXT NOT NULL,
        plan TEXT DEFAULT 'Basic', expiry TEXT, extra_students INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS classes (
        id TEXT PRIMARY KEY,
        class_name TEXT NOT NULL,
        section TEXT,
        school_id TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY, name TEXT, blood TEXT, allergy TEXT,
        parent_name TEXT, parent_phone TEXT, likes TEXT, dislikes TEXT,
        siblings TEXT, class_id TEXT, school_id TEXT, is_active INTEGER DEFAULT 1,
        profile_photo TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        class_id TEXT NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Present', 'Absent', 'Late', 'Half Day')),
        notes TEXT,
        marked_by TEXT,
        marked_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS fees (
        id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT,
        amount INTEGER, month TEXT, status TEXT, payment_date TEXT, school_id TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS inventory (
        id TEXT PRIMARY KEY, item_name TEXT, category TEXT,
        quantity INTEGER, min_quantity INTEGER, school_id TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
    
    hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
    conn.execute("INSERT OR IGNORE INTO admin_config VALUES (?, ?)", 
                ("admin_password_hash", hashed))
    conn.commit()
    return conn

def get_db_conn():
    return get_db()

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

# Student limit check
def check_student_limit(school_id):
    db = get_db_conn()
    school = db.execute("SELECT plan, extra_students FROM schools WHERE id=?", (school_id,)).fetchone()
    if not school:
        return False, 0, 0
    
    limit = PLAN_LIMITS.get(school["plan"], 30) + school["extra_students"]
    current = db.execute("SELECT COUNT(*) FROM students WHERE school_id=? AND is_active=1", (school_id,)).fetchone()[0]
    
    return current < limit, current, limit

# Session
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}

# Login
def login_page():
    st.title("🏫 SchoolOS Pro Phase 3")
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        user = st.text_input("User ID")
        pw = st.text_input("Password", type="password")
        
        if st.button("🔐 Login", type="primary", use_container_width=True):
            db = get_db_conn()
            
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
    db = get_db_conn()
    
    with st.sidebar:
        if st.button("🚪 Logout"):
            st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}
            st.rerun()
        
        total_schools = db.execute("SELECT COUNT(*) FROM schools WHERE is_active=1").fetchone()[0]
        total_students = db.execute("SELECT COUNT(*) FROM students WHERE is_active=1").fetchone()[0]
        total_revenue = db.execute("SELECT COALESCE(SUM(amount), 0) FROM fees WHERE status='Paid'").fetchone()[0]
        
        st.metric("Schools", total_schools)
        st.metric("Students", total_students)
        st.metric("Revenue", f"₹{total_revenue:,}")
    
    t1, t2, t3, t4 = st.tabs(["🏫 Schools", "📢 Broadcasts", "💰 Revenue", "⚙️ Settings"])
    
    with t1:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("Create School")
            with st.form("add_school", clear_on_submit=True):
                sid = st.text_input("School ID")
                name = st.text_input("Name")
                pw = st.text_input("Password", type="password")
                plan = st.selectbox("Plan", list(PLAN_LIMITS.keys()))
                years = st.number_input("Years", 1, 5, 1)
                extra = st.number_input("Extra Student Slots", 0, 1000, 0)
                
                if st.form_submit_button("➕ Create"):
                    if not all([sid, name, pw]):
                        st.error("Fill all fields")
                    elif db.execute("SELECT 1 FROM schools WHERE id=?", (sid,)).fetchone():
                        st.error("ID exists")
                    else:
                        exp = (datetime.now() + timedelta(days=365*years)).strftime("%Y-%m-%d")
                        db.execute("""
                            INSERT INTO schools (id, name, pass, plan, expiry, extra_students, is_active) 
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (sid, name, hash_pw(pw), plan, exp, extra, 1))
                        db.commit()
                        st.success(f"Created {name}! Plan: {plan} (Limit: {PLAN_LIMITS[plan] + extra} students)")
        
        with c2:
            st.subheader("All Schools")
            for s in db.execute("SELECT * FROM schools WHERE is_active=1").fetchall():
                limit = PLAN_LIMITS.get(s["plan"], 30) + s["extra_students"]
                count = db.execute("SELECT COUNT(*) FROM students WHERE school_id=? AND is_active=1", (s["id"],)).fetchone()[0]
                with st.expander(f"{s['name']} ({s['id']}) - {count}/{limit} students"):
                    st.write(f"Plan: {s['plan']} | Limit: {limit} | Expires: {s['expiry']}")
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
        st.subheader("💰 Revenue Analytics")
        
        c1, c2, c3 = st.columns(3)
        total_paid = db.execute("SELECT COALESCE(SUM(amount), 0) FROM fees WHERE status='Paid'").fetchone()[0]
        total_pending = db.execute("SELECT COALESCE(SUM(amount), 0) FROM fees WHERE status='Pending'").fetchone()[0]
        total_fees = db.execute("SELECT COUNT(*) FROM fees").fetchone()[0]
        
        c1.metric("Total Collected", f"₹{total_paid:,}")
        c2.metric("Pending Amount", f"₹{total_pending:,}")
        c3.metric("Total Records", total_fees)
        
        st.divider()
        
        st.subheader("Revenue by Plan")
        plan_revenue = db.execute("""
            SELECT s.plan, COUNT(DISTINCT s.id) as schools, COALESCE(SUM(f.amount), 0) as revenue
            FROM schools s
            LEFT JOIN fees f ON s.id = f.school_id AND f.status='Paid'
            WHERE s.is_active=1
            GROUP BY s.plan
        """).fetchall()
        
        if plan_revenue:
            cols = st.columns(len(plan_revenue))
            for idx, row in enumerate(plan_revenue):
                with cols[idx]:
                    st.metric(f"{row['plan']}", f"₹{row['revenue']:,}", f"{row['schools']} schools")
        else:
            st.info("No revenue data yet")
        
        st.divider()
        
        st.subheader("Recent Payments")
        recent = db.execute("""
            SELECT f.*, s.name as school_name 
            FROM fees f
            JOIN schools s ON f.school_id = s.id
            WHERE f.status='Paid'
            ORDER BY f.payment_date DESC
            LIMIT 20
        """).fetchall()
        
        for r in recent:
            st.markdown(f"**{r['student_name']}** | ₹{r['amount']:,} | {r['month']} | *{r['school_name']}*")
    
    with t4:
        st.subheader("Change Admin Password")
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
    db = get_db_conn()
    school = db.execute("SELECT * FROM schools WHERE id=?", (sid,)).fetchone()
    st.title(f"🏫 {school['name']}")
    
    can_add, current, limit = check_student_limit(sid)
    
    with st.sidebar:
        st.progress(min(current/limit, 1.0), text=f"Students: {current}/{limit}")
        if current >= limit:
            st.error("⚠️ Student limit reached!")
        
        menu = st.radio("Menu", ["📊 Dashboard", "🏫 Classes", "👨‍🎓 Students", "📋 Attendance", "💳 Fees", "📦 Inventory", "🧸 Care Logs"])
        if st.button("🚪 Logout"):
            st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}
            st.rerun()
    
    if menu == "📊 Dashboard":
        show_dashboard(sid, current)
    elif menu == "🏫 Classes":
        show_classes(sid)
    elif menu == "👨‍🎓 Students":
        show_students(sid, can_add, current, limit)
    elif menu == "📋 Attendance":
        show_attendance(sid)
    elif menu == "💳 Fees":
        show_fees(sid)
    elif menu == "📦 Inventory":
        show_inventory(sid)
    elif menu == "🧸 Care Logs":
        show_care_logs(sid)

def show_dashboard(sid, current):
    db = get_db_conn()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Students", current)
    c2.metric("Classes", db.execute("SELECT COUNT(*) FROM classes WHERE school_id=?", (sid,)).fetchone()[0])
    c3.metric("Pending Fees", db.execute("SELECT COUNT(*) FROM fees WHERE school_id=? AND status='Pending'", (sid,)).fetchone()[0])
    c4.metric("Revenue", f"₹{db.execute('SELECT COALESCE(SUM(amount),0) FROM fees WHERE school_id=? AND status=\'Paid\'', (sid,)).fetchone()[0]:,}")
    
    # Today's attendance summary
    st.subheader("Today's Attendance")
    today = date.today().isoformat()
    attendance_summary = db.execute("""
        SELECT status, COUNT(*) as count 
        FROM attendance 
        WHERE date=? AND class_id IN (SELECT id FROM classes WHERE school_id=?)
        GROUP BY status
    """, (today, sid)).fetchall()
    
    if attendance_summary:
        cols = st.columns(len(attendance_summary))
        for idx, row in enumerate(attendance_summary):
            emoji = {"Present": "✅", "Absent": "❌", "Late": "⏰", "Half Day": "⚠️"}.get(row["status"], "📋")
            cols[idx].metric(f"{emoji} {row['status']}", row["count"])
    else:
        st.info("No attendance marked today")

def show_classes(sid):
    db = get_db_conn()
    st.header("🏫 Class Management")
    
    t1, t2 = st.tabs(["➕ Create Class", "📋 View Classes"])
    
    with t1:
        with st.form("add_class", clear_on_submit=True):
            class_name = st.text_input("Class Name (e.g., Grade 1, Nursery, etc.)*")
            section = st.text_input("Section (e.g., A, B, Morning, etc.)")
            
            if st.form_submit_button("➕ Create Class"):
                if not class_name:
                    st.error("Class name is required")
                else:
                    class_id = gen_id()
                    db.execute("""
                        INSERT INTO classes (id, class_name, section, school_id)
                        VALUES (?, ?, ?, ?)
                    """, (class_id, sanitize(class_name), sanitize(section), sid))
                    db.commit()
                    st.success(f"Created: {class_name} {section}")
                    st.balloons()
    
    with t2:
        classes = db.execute("SELECT * FROM classes WHERE school_id=? ORDER BY class_name", (sid,)).fetchall()
        if not classes:
            st.info("No classes created yet")
        else:
            for c in classes:
                student_count = db.execute("SELECT COUNT(*) FROM students WHERE class_id=? AND is_active=1", (c["id"],)).fetchone()[0]
                with st.expander(f"📚 {c['class_name']} {c['section']} - {student_count} students"):
                    st.write(f"Class ID: {c['id']}")
                    if st.button("🗑️ Delete Class", key=f"del_class_{c['id']}"):
                        # Check if students exist
                        if student_count > 0:
                            st.error(f"Cannot delete! {student_count} students enrolled. Move them first.")
                        else:
                            db.execute("DELETE FROM classes WHERE id=?", (c["id"],))
                            db.commit()
                            st.success("Class deleted")
                            st.rerun()

def show_students(sid, can_add, current, limit):
    db = get_db_conn()
    st.header("👨‍🎓 Student Management")
    
    # Get available classes
    classes = db.execute("SELECT id, class_name, section FROM classes WHERE school_id=?", (sid,)).fetchall()
    class_dict = {f"{c['class_name']} {c['section']}": c["id"] for c in classes}
    
    t1, t2 = st.tabs(["➕ Add Student", "📋 Student List"])
    
    with t1:
        if not can_add:
            st.error(f"❌ Student limit reached! ({current}/{limit})")
            st.info("Contact admin to upgrade your plan or add extra slots.")
        elif not classes:
            st.warning("⚠️ No classes available! Create a class first in 'Classes' section.")
        else:
            st.info(f"Student slots: {current}/{limit} used")
            
            with st.form("add_student", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Full Name*")
                    blood = st.selectbox("Blood Group", ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"])
                    allergy = st.text_area("Allergies/Medical Notes")
                    selected_class = st.selectbox("Assign to Class*", list(class_dict.keys()))
                
                with c2:
                    parent = st.text_input("Parent/Guardian Name*")
                    phone = st.text_input("Parent Phone")
                    likes = st.text_area("Likes/Interests")
                    dislikes = st.text_area("Dislikes")
                
                # Profile photo upload
                st.subheader("📸 Profile Photo")
                photo_file = st.file_uploader("Upload photo (optional)", type=["jpg", "jpeg", "png"])
                
                if st.form_submit_button("✅ Register Student"):
                    if not all([name, parent, selected_class]):
                        st.error("Fill required fields (*)")
                    else:
                        can_still_add, _, _ = check_student_limit(sid)
                        if not can_still_add:
                            st.error("Limit reached! Cannot add more students.")
                        else:
                            # Process photo
                            photo_base64 = None
                            if photo_file:
                                try:
                                    image = Image.open(photo_file)
                                    image = image.resize((200, 200))
                                    buffered = io.BytesIO()
                                    image.save(buffered, format="JPEG")
                                    photo_base64 = base64.b64encode(buffered.getvalue()).decode()
                                except Exception as e:
                                    st.warning(f"Photo processing failed: {e}")
                            
                            db.execute("""
                                INSERT INTO students (id, name, blood, allergy, parent_name, parent_phone, 
                                                    likes, dislikes, class_id, school_id, is_active, profile_photo)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (gen_id(), sanitize(name), blood, sanitize(allergy), sanitize(parent), 
                                  sanitize(phone), sanitize(likes), sanitize(dislikes), 
                                  class_dict[selected_class], sid, 1, photo_base64))
                            db.commit()
                            st.success(f"✅ {name} registered in {selected_class}!")
                            st.balloons()
    
    with t2:
        # Filter by class
        filter_class = st.selectbox("Filter by Class", ["All Classes"] + list(class_dict.keys()))
        
        query = """
            SELECT s.*, c.class_name, c.section 
            FROM students s
            LEFT JOIN classes c ON s.class_id = c.id
            WHERE s.school_id=? AND s.is_active=1
        """
        params = [sid]
        
        if filter_class != "All Classes":
            query += " AND s.class_id=?"
            params.append(class_dict[filter_class])
        
        query += " ORDER BY c.class_name, s.name"
        
        students = db.execute(query, tuple(params)).fetchall()
        
        if not students:
            st.info("No students found")
        else:
            st.write(f"**Total: {len(students)} students**")
            
            for s in students:
                class_display = f"{s['class_name']} {s['section']}" if s['class_name'] else "No Class"
                
                with st.expander(f"👤 {s['name']} ({class_display})"):
                    c1, c2 = st.columns([1, 3])
                    
                    with c1:
                        # Show profile photo
                        if s["profile_photo"]:
                            try:
                                st.image(base64.b64decode(s["profile_photo"]), width=150)
                            except:
                                st.write("📷 Photo unavailable")
                        else:
                            st.write("📷 No photo")
                    
                    with c2:
                        st.write(f"**Blood:** {s['blood']}")
                        st.write(f"**Allergies:** {s['allergy'] or 'None'}")
                        st.write(f"**Parent:** {s['parent_name']} ({s['parent_phone'] or 'N/A'})")
                        st.write(f"**Likes:** {s['likes'] or 'Not specified'}")
                        st.write(f"**Class:** {class_display}")
                        
                        # Change class option
                        new_class = st.selectbox("Move to Class", list(class_dict.keys()), 
                                                key=f"move_{s['id']}")
                        if st.button("Move Class", key=f"btn_move_{s['id']}"):
                            db.execute("UPDATE students SET class_id=? WHERE id=?", 
                                      (class_dict[new_class], s["id"]))
                            db.commit()
                            st.success(f"Moved to {new_class}")
                            st.rerun()
                        
                        if st.button("🗑️ Remove Student", key=f"rm_{s['id']}"):
                            db.execute("UPDATE students SET is_active=0 WHERE id=?", (s['id'],))
                            db.commit()
                            st.rerun()

def show_attendance(sid):
    db = get_db_conn()
    st.header("📋 Attendance")
    
    # Get classes
    classes = db.execute("SELECT id, class_name, section FROM classes WHERE school_id=?", (sid,)).fetchall()
    if not classes:
        st.warning("Create classes first!")
        return
    
    class_dict = {f"{c['class_name']} {c['section']}": c["id"] for c in classes}
    
    t1, t2, t3 = st.tabs(["📝 Mark Attendance", "📊 View Report", "📅 Date View"])
    
    with t1:
        selected_class = st.selectbox("Select Class", list(class_dict.keys()), key="att_class")
        att_date = st.date_input("Date", value=date.today())
        
        # Get students in class
        students = db.execute("""
            SELECT id, name, profile_photo FROM students 
            WHERE class_id=? AND school_id=? AND is_active=1
            ORDER BY name
        """, (class_dict[selected_class], sid)).fetchall()
        
        if not students:
            st.info("No students in this class")
        else:
            st.write(f"**{len(students)} students**")
            
            # Check if attendance already marked
            existing = db.execute("""
                SELECT student_id, status FROM attendance 
                WHERE date=? AND class_id=?
            """, (att_date.isoformat(), class_dict[selected_class])).fetchall()
            existing_dict = {row["student_id"]: row["status"] for row in existing}
            
            with st.form("mark_attendance"):
                attendance_data = []
                
                for s in students:
                    cols = st.columns([1, 3, 4])
                    
                    with cols[0]:
                        # Show small photo
                        if s["profile_photo"]:
                            try:
                                st.image(base64.b64decode(s["profile_photo"]), width=50)
                            except:
                                st.write("📷")
                        else:
                            st.write("👤")
                    
                    with cols[1]:
                        st.write(f"**{s['name']}**")
                    
                    with cols[2]:
                        status = st.radio(
                            f"Status_{s['id']}", 
                            ["Present", "Absent", "Late", "Half Day"],
                            index=0 if s["id"] not in existing_dict else ["Present", "Absent", "Late", "Half Day"].index(existing_dict[s["id"]]),
                            horizontal=True,
                            label_visibility="collapsed"
                        )
                        attendance_data.append((s["id"], status))
                    
                    st.divider()
                
                notes = st.text_area("General Notes (optional)")
                
                if st.form_submit_button("💾 Save Attendance"):
                    # Delete existing records for this date/class
                    db.execute("DELETE FROM attendance WHERE date=? AND class_id=?", 
                              (att_date.isoformat(), class_dict[selected_class]))
                    
                    # Insert new records
                    for student_id, status in attendance_data:
                        db.execute("""
                            INSERT INTO attendance (student_id, class_id, date, status, notes, marked_by)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (student_id, class_dict[selected_class], att_date.isoformat(), 
                              status, notes, sid))
                    
                    db.commit()
                    st.success(f"✅ Attendance saved for {len(attendance_data)} students!")
                    st.balloons()
    
    with t2:
        # Attendance report
        report_class = st.selectbox("Select Class", list(class_dict.keys()), key="rep_class")
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("From", value=date.today() - timedelta(days=7))
        with col2:
            end_date = st.date_input("To", value=date.today())
        
        # Get attendance summary
        report = db.execute("""
            SELECT s.name, 
                   COUNT(CASE WHEN a.status='Present' THEN 1 END) as present,
                   COUNT(CASE WHEN a.status='Absent' THEN 1 END) as absent,
                   COUNT(CASE WHEN a.status='Late' THEN 1 END) as late,
                   COUNT(CASE WHEN a.status='Half Day' THEN 1 END) as half_day,
                   COUNT(a.id) as total
            FROM students s
            LEFT JOIN attendance a ON s.id = a.student_id 
                AND a.date BETWEEN ? AND ? AND a.class_id=?
            WHERE s.class_id=? AND s.school_id=? AND s.is_active=1
            GROUP BY s.id
            ORDER BY s.name
        """, (start_date.isoformat(), end_date.isoformat(), class_dict[report_class],
              class_dict[report_class], sid)).fetchall()
        
        if report:
            st.write("**Attendance Summary**")
            for r in report:
                percentage = (r["present"] / r["total"] * 100) if r["total"] > 0 else 0
                with st.expander(f"{r['name']} - {percentage:.1f}%"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Present", r["present"])
                    c2.metric("Absent", r["absent"])
                    c3.metric("Late", r["late"])
                    c4.metric("Half Day", r["half_day"])
        else:
            st.info("No attendance data for selected period")
    
    with t3:
        # View by date
        view_date = st.date_input("Select Date", value=date.today(), key="view_date")
        view_class = st.selectbox("Select Class", list(class_dict.keys()), key="view_class")
        
        attendance_records = db.execute("""
            SELECT a.*, s.name, s.profile_photo 
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.date=? AND a.class_id=?
            ORDER BY s.name
        """, (view_date.isoformat(), class_dict[view_class])).fetchall()
        
        if attendance_records:
            st.write(f"**Attendance for {view_date}**")
            for a in attendance_records:
                emoji = {"Present": "✅", "Absent": "❌", "Late": "⏰", "Half Day": "⚠️"}.get(a["status"], "📋")
                
                cols = st.columns([1, 4, 2])
                with cols[0]:
                    if a["profile_photo"]:
                        try:
                            st.image(base64.b64decode(a["profile_photo"]), width=40)
                        except:
                            st.write("👤")
                    else:
                        st.write("👤")
                with cols[1]:
                    st.write(f"**{a['name']}**")
                with cols[2]:
                    st.write(f"{emoji} {a['status']}")
        else:
            st.info("No attendance marked for this date")

def show_fees(sid):
    db = get_db_conn()
    st.header("💳 Fees")
    
    t1, t2 = st.tabs(["➕ Add", "📊 View"])
    
    with t1:
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
                    db.execute("""
                        INSERT INTO fees (id, student_id, student_name, amount, month, status, payment_date, school_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (gen_id(), stu_dict[sel], sel, amt, month, status,
                          datetime.now().isoformat() if status=="Paid" else None, sid))
                    db.commit()
                    st.success("Saved!")
    
    with t2:
        for f in db.execute("SELECT * FROM fees WHERE school_id=?", (sid,)).fetchall():
            color = "green" if f["status"]=="Paid" else "orange"
            st.markdown(f"**{f['student_name']}** | ₹{f['amount']} | {f['month']} | :{color}[{f['status']}]")

def show_inventory(sid):
    db = get_db_conn()
    st.header("📦 Inventory")
    
    t1, t2 = st.tabs(["➕ Add", "📦 Stock"])
    
    with t1:
        with st.form("add_item"):
            name = st.text_input("Item*")
            cat = st.selectbox("Category", ["Stationery", "Books", "Sports", "Lab", "Furniture", "Electronics", "Other"])
            qty = st.number_input("Qty", min_value=0)
            min_qty = st.number_input("Min", min_value=0, value=10)
            if st.form_submit_button("➕ Add") and name:
                db.execute("""
                    INSERT INTO inventory (id, item_name, category, quantity, min_quantity, school_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (gen_id(), sanitize(name), cat, qty, min_qty, sid))
                db.commit()
                st.success(f"Added {name}!")
    
    with t2:
        for i in db.execute("SELECT * FROM inventory WHERE school_id=?", (sid,)).fetchall():
            emoji = "🔴" if i["quantity"] <= i["min_quantity"] else "🟢"
            st.write(f"{emoji} **{i['item_name']}** - {i['quantity']} (min: {i['min_quantity']})")

def show_care_logs(sid):
    db = get_db_conn()
    st.header("🧸 Care Logs")
    
    students = db.execute("SELECT id, name FROM students WHERE school_id=? AND is_active=1", (sid,)).fetchall()
    if not students:
        st.warning("No students")
        return
    stu_dict = {s["name"]: s["id"] for s in students}
    
    t1, t2 = st.tabs(["➕ New", "📋 Today"])
    
    with t1:
        sel = st.selectbox("Student", list(stu_dict.keys()))
        log_type = st.selectbox("Type", ["Bathroom", "Food", "Nap"])
        if log_type == "Bathroom":
            with st.form("log_bath"):
                sub = st.selectbox("Type", ["Pee", "Potty", "Diaper"])
                if st.form_submit_button("Save"):
                    db.execute("""
                        INSERT INTO care_logs (id, student_id, student_name, activity, school_id, type, sub_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (gen_id(), stu_dict[sel], sel, "Bathroom", sid, "bathroom", sub.lower()))
                    db.commit()
                    st.success("Saved!")
        elif log_type == "Food":
            with st.form("log_food"):
                meal = st.selectbox("Meal", ["Breakfast", "Lunch", "Snack"])
                status = st.selectbox("Status", ["Full", "Half", "Little", "Refused"])
                if st.form_submit_button("Save"):
                    db.execute("""
                        INSERT INTO care_logs (id, student_id, student_name, activity, school_id, type, sub_type, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (gen_id(), stu_dict[sel], sel, "Food", sid, "food", meal, status))
                    db.commit()
                    st.success("Saved!")
        elif log_type == "Nap":
            with st.form("log_nap"):
                start = st.time_input("Start")
                end = st.time_input("End")
                if st.form_submit_button("Save"):
                    db.execute("""
                        INSERT INTO care_logs (id, student_id, student_name, activity, school_id, type, start_time, end_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (gen_id(), stu_dict[sel], sel, "Nap", sid, "nap", str(start), str(end)))
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
    st.caption("SchoolOS Pro Phase 3 | Attendance, Classes & Photos")

if __name__ == "__main__":
    main()
