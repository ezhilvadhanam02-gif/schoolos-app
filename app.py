# SCHOOL PRO FINAL VERSION - PHASE 3
# Complete School Management System with Classes, Attendance & Profile Photos
# Browser-only, no external dependencies except streamlit and bcrypt

import streamlit as st
import sqlite3
import re
import secrets
import base64
from datetime import datetime, timedelta, date
import bcrypt

# ================= CONFIGURATION =================
st.set_page_config(
    page_title="SchoolOS Pro",
    layout="wide",
    page_icon="🏫",
    initial_sidebar_state="expanded"
)

# Plan limits for student enrollment
PLAN_LIMITS = {
    "Basic": 30,
    "Standard": 80, 
    "Premium": 500,
    "Enterprise": 999999
}

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1f77b4; }
    .metric-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; color: white; }
    .stProgress > div > div > div > div { background-color: #1f77b4; }
</style>
""", unsafe_allow_html=True)

# ================= DATABASE =================
@st.cache_resource
def get_db():
    """Initialize database with all tables"""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS schools (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        pass TEXT NOT NULL,
        plan TEXT DEFAULT 'Basic',
        expiry TEXT,
        extra_students INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS classes (
        id TEXT PRIMARY KEY,
        class_name TEXT NOT NULL,
        section TEXT,
        school_id TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
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
        class_id TEXT,
        school_id TEXT,
        is_active INTEGER DEFAULT 1,
        profile_photo TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
        id TEXT PRIMARY KEY,
        student_id TEXT,
        student_name TEXT,
        amount INTEGER,
        month TEXT,
        status TEXT,
        payment_date TEXT,
        school_id TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS inventory (
        id TEXT PRIMARY KEY,
        item_name TEXT,
        category TEXT,
        quantity INTEGER,
        min_quantity INTEGER,
        school_id TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS care_logs (
        id TEXT PRIMARY KEY,
        student_id TEXT,
        student_name TEXT,
        activity TEXT,
        notes TEXT,
        time TEXT DEFAULT CURRENT_TIMESTAMP,
        school_id TEXT,
        type TEXT,
        sub_type TEXT,
        status TEXT,
        start_time TEXT,
        end_time TEXT
    );
    
    CREATE TABLE IF NOT EXISTS broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        msg TEXT,
        date TEXT DEFAULT CURRENT_TIMESTAMP,
        priority TEXT DEFAULT 'normal'
    );
    
    CREATE TABLE IF NOT EXISTS admin_config (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    
    # Create default admin
    hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
    conn.execute("INSERT OR IGNORE INTO admin_config VALUES (?, ?)", 
                ("admin_password_hash", hashed))
    conn.commit()
    return conn

def get_db_conn():
    """Get database connection"""
    return get_db()

# ================= SECURITY =================
def sanitize(text):
    """Clean user input"""
    if not isinstance(text, str):
        return ""
    return re.sub(r'[<>\"\'%;()&+]', '', text)[:255].strip()

def hash_pw(pw):
    """Hash password"""
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def check_pw(pw, hashed):
    """Verify password"""
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except:
        return False

def gen_id():
    """Generate unique ID"""
    return secrets.token_urlsafe(16)

# ================= IMAGE HANDLING (BROWSER ONLY) =================
def process_uploaded_image(uploaded_file):
    """Convert uploaded file to base64 - NO PILLOW NEEDED"""
    if uploaded_file is None:
        return None
    try:
        bytes_data = uploaded_file.getvalue()
        base64_string = base64.b64encode(bytes_data).decode('utf-8')
        return base64_string
    except Exception as e:
        st.error(f"Image processing error: {e}")
        return None

def display_image_from_base64(base64_string, width=150):
    """Display image from base64 string"""
    if base64_string is None:
        return False
    try:
        image_bytes = base64.b64decode(base64_string)
        st.image(image_bytes, width=width)
        return True
    except:
        st.write("📷 No photo")
        return False

# ================= STUDENT LIMIT CHECK =================
def check_student_limit(school_id):
    """Check if school can add more students"""
    db = get_db_conn()
    school = db.execute("SELECT plan, extra_students FROM schools WHERE id=?", (school_id,)).fetchone()
    if not school:
        return False, 0, 0
    
    limit = PLAN_LIMITS.get(school["plan"], 30) + school["extra_students"]
    current = db.execute("SELECT COUNT(*) FROM students WHERE school_id=? AND is_active=1", (school_id,)).fetchone()[0]
    
    return current < limit, current, limit

# ================= SESSION =================
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}

# ================= LOGIN =================
def login_page():
    """Login screen"""
    st.markdown('<p class="main-header">🏫 SchoolOS Pro</p>', unsafe_allow_html=True)
    st.markdown("### Complete School Management System")
    
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        with st.container():
            user = st.text_input("User ID", key="login_user")
            pw = st.text_input("Password", type="password", key="login_pw")
            
            if st.button("🔐 Login", type="primary", use_container_width=True):
                db = get_db_conn()
                
                # Admin login
                if user == "admin":
                    h = db.execute("SELECT value FROM admin_config WHERE key='admin_password_hash'").fetchone()
                    if h and check_pw(pw, h[0]):
                        st.session_state.auth = {"logged_in": True, "role": "admin", "school_id": None}
                        st.rerun()
                    else:
                        st.error("Invalid admin credentials")
                    return
                
                # School login
                school = db.execute("SELECT * FROM schools WHERE id=? AND is_active=1", (user,)).fetchone()
                if not school:
                    st.error("School not found")
                    return
                if not check_pw(pw, school["pass"]):
                    st.error("Invalid password")
                    return
                
                # Check expiry
                try:
                    if datetime.now() > datetime.strptime(school["expiry"], "%Y-%m-%d"):
                        st.error("Subscription expired")
                        return
                except:
                    pass
                
                st.session_state.auth = {"logged_in": True, "role": "school", "school_id": user}
                st.rerun()

# ================= ADMIN DASHBOARD =================
def admin_page():
    """Admin panel"""
    st.title("👑 Admin Dashboard")
    db = get_db_conn()
    
    # Sidebar
    with st.sidebar:
        st.markdown("### System")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}
            st.rerun()
        
        st.divider()
        
        # Stats
        total_schools = db.execute("SELECT COUNT(*) FROM schools WHERE is_active=1").fetchone()[0]
        total_students = db.execute("SELECT COUNT(*) FROM students WHERE is_active=1").fetchone()[0]
        total_revenue = db.execute("SELECT COALESCE(SUM(amount), 0) FROM fees WHERE status='Paid'").fetchone()[0]
        
        st.metric("Active Schools", total_schools)
        st.metric("Total Students", total_students)
        st.metric("Total Revenue", f"₹{total_revenue:,}")
    
    # Tabs
    t1, t2, t3, t4 = st.tabs(["🏫 Schools", "📢 Broadcasts", "💰 Revenue", "⚙️ Settings"])
    
    # Schools Tab
    with t1:
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.subheader("Create School")
            with st.form("add_school", clear_on_submit=True):
                sid = st.text_input("School ID *")
                name = st.text_input("School Name *")
                pw = st.text_input("Password *", type="password")
                plan = st.selectbox("Plan *", list(PLAN_LIMITS.keys()))
                years = st.number_input("Subscription Years", 1, 5, 1)
                extra = st.number_input("Extra Student Slots", 0, 1000, 0)
                
                if st.form_submit_button("➕ Create School", use_container_width=True):
                    if not all([sid, name, pw]):
                        st.error("Please fill all required fields")
                    elif len(pw) < 6:
                        st.error("Password must be at least 6 characters")
                    elif db.execute("SELECT 1 FROM schools WHERE id=?", (sid,)).fetchone():
                        st.error("School ID already exists")
                    else:
                        exp = (datetime.now() + timedelta(days=365*years)).strftime("%Y-%m-%d")
                        db.execute("""
                            INSERT INTO schools (id, name, pass, plan, expiry, extra_students, is_active)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (sid, name, hash_pw(pw), plan, exp, extra, 1))
                        db.commit()
                        total_limit = PLAN_LIMITS[plan] + extra
                        st.success(f"✅ Created {name}! Plan: {plan} (Limit: {total_limit} students)")
                        st.balloons()
        
        with c2:
            st.subheader("Manage Schools")
            schools = db.execute("SELECT * FROM schools WHERE is_active=1 ORDER BY created_at DESC").fetchall()
            
            if not schools:
                st.info("No schools created yet")
            else:
                for s in schools:
                    limit = PLAN_LIMITS.get(s["plan"], 30) + s["extra_students"]
                    count = db.execute("SELECT COUNT(*) FROM students WHERE school_id=? AND is_active=1", (s["id"],)).fetchone()[0]
                    
                    with st.expander(f"🏫 {s['name']} ({s['id']}) - {count}/{limit} students"):
                        col1, col2 = st.columns(2)
                        col1.write(f"**Plan:** {s['plan']}")
                        col1.write(f"**Students:** {count}/{limit}")
                        col2.write(f"**Expires:** {s['expiry']}")
                        
                        days_left = (datetime.strptime(s['expiry'], "%Y-%m-%d") - datetime.now()).days
                        if days_left < 30:
                            col2.error(f"⚠️ {days_left} days left")
                        else:
                            col2.success(f"✅ {days_left} days left")
                        
                        if st.button("🗑️ Deactivate", key=f"del_{s['id']}"):
                            db.execute("UPDATE schools SET is_active=0 WHERE id=?", (s['id'],))
                            db.commit()
                            st.success("School deactivated")
                            st.rerun()
    
    # Broadcasts Tab
    with t2:
        st.subheader("Send Broadcast")
        with st.form("broadcast"):
            msg = st.text_area("Message", max_chars=1000)
            priority = st.selectbox("Priority", ["low", "normal", "high", "urgent"])
            
            if st.form_submit_button("📢 Send Broadcast", use_container_width=True):
                if msg.strip():
                    clean_msg = sanitize(msg)
                    db.execute("INSERT INTO broadcasts (msg, priority, created_by) VALUES (?, ?, ?)",
                              (clean_msg, priority, "admin"))
                    db.commit()
                    st.success("✅ Broadcast sent to all schools!")
        
        st.divider()
        st.subheader("Recent Broadcasts")
        broadcasts = db.execute("SELECT * FROM broadcasts ORDER BY date DESC LIMIT 10").fetchall()
        
        for b in broadcasts:
            emoji = {"low": "⚪", "normal": "🔵", "high": "🟠", "urgent": "🔴"}.get(b["priority"], "⚪")
            with st.container():
                st.markdown(f"{emoji} **{b['date'][:10]}**")
                st.markdown(b["msg"])
                st.divider()
    
    # Revenue Tab
    with t3:
        st.subheader("💰 Revenue Analytics")
        
        # Summary metrics
        c1, c2, c3 = st.columns(3)
        total_paid = db.execute("SELECT COALESCE(SUM(amount), 0) FROM fees WHERE status='Paid'").fetchone()[0]
        total_pending = db.execute("SELECT COALESCE(SUM(amount), 0) FROM fees WHERE status='Pending'").fetchone()[0]
        total_records = db.execute("SELECT COUNT(*) FROM fees").fetchone()[0]
        
        c1.metric("Total Collected", f"₹{total_paid:,}")
        c2.metric("Pending Amount", f"₹{total_pending:,}")
        c3.metric("Total Fee Records", total_records)
        
        st.divider()
        
        # Revenue by plan
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
            st.info("No revenue data available")
        
        st.divider()
        
        # Recent payments
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
    
    # Settings Tab
    with t4:
        st.subheader("🔐 Change Admin Password")
        with st.form("chg_pw"):
            old_pw = st.text_input("Current Password", type="password")
            new_pw = st.text_input("New Password", type="password")
            conf_pw = st.text_input("Confirm New Password", type="password")
            
            if st.form_submit_button("Update Password", use_container_width=True):
                cur_hash = db.execute("SELECT value FROM admin_config WHERE key='admin_password_hash'").fetchone()[0]
                
                if not check_pw(old_pw, cur_hash):
                    st.error("❌ Current password is incorrect")
                elif new_pw != conf_pw:
                    st.error("❌ Passwords do not match")
                elif len(new_pw) < 8:
                    st.error("❌ Password must be at least 8 characters")
                else:
                    db.execute("UPDATE admin_config SET value=? WHERE key='admin_password_hash'",
                              (hash_pw(new_pw),))
                    db.commit()
                    st.success("✅ Password updated successfully!")

# ================= SCHOOL DASHBOARD =================
def school_page():
    """School panel"""
    sid = st.session_state.auth["school_id"]
    db = get_db_conn()
    school = db.execute("SELECT * FROM schools WHERE id=?", (sid,)).fetchone()
    
    st.title(f"🏫 {school['name']}")
    
    # Check student limit
    can_add, current, limit = check_student_limit(sid)
    
    # Sidebar
    with st.sidebar:
        st.markdown(f"### {school['name'][:20]}")
        
        # Progress bar
        progress = min(current / limit, 1.0) if limit > 0 else 0
        st.progress(progress, text=f"Students: {current}/{limit}")
        
        if current >= limit:
            st.error("⚠️ Student limit reached!")
        
        st.divider()
        
        # Navigation
        menu = st.radio("Menu", [
            "📊 Dashboard",
            "🏫 Classes",
            "👨‍🎓 Students",
            "📋 Attendance",
            "💳 Fees",
            "📦 Inventory",
            "🧸 Care Logs"
        ])
        
        st.divider()
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}
            st.rerun()
    
    # Route to selected menu
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
    """School dashboard"""
    db = get_db_conn()
    
    st.header("📊 Dashboard Overview")
    
    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Students", current)
    c2.metric("Total Classes", db.execute("SELECT COUNT(*) FROM classes WHERE school_id=?", (sid,)).fetchone()[0])
    c3.metric("Pending Fees", db.execute("SELECT COUNT(*) FROM fees WHERE school_id=? AND status='Pending'", (sid,)).fetchone()[0])
    c4.metric("Revenue", f"₹{db.execute('SELECT COALESCE(SUM(amount),0) FROM fees WHERE school_id=? AND status=\'Paid\'', (sid,)).fetchone()[0]:,}")
    
    # Today's attendance
    st.subheader("Today's Attendance Summary")
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
    """Class management"""
    db = get_db_conn()
    st.header("🏫 Class Management")
    
    t1, t2 = st.tabs(["➕ Create Class", "📋 View Classes"])
    
    # Create Class
    with t1:
        with st.form("add_class", clear_on_submit=True):
            class_name = st.text_input("Class Name *", placeholder="e.g., Grade 1, Nursery, etc.")
            section = st.text_input("Section", placeholder="e.g., A, B, Morning, etc.")
            
            if st.form_submit_button("➕ Create Class", use_container_width=True):
                if not class_name:
                    st.error("Class name is required")
                else:
                    class_id = gen_id()
                    db.execute("""
                        INSERT INTO classes (id, class_name, section, school_id)
                        VALUES (?, ?, ?, ?)
                    """, (class_id, sanitize(class_name), sanitize(section), sid))
                    db.commit()
                    display_name = f"{class_name} {section}" if section else class_name
                    st.success(f"✅ Created: {display_name}")
                    st.balloons()
    
    # View Classes
    with t2:
        classes = db.execute("SELECT * FROM classes WHERE school_id=? ORDER BY class_name, section", (sid,)).fetchall()
        
        if not classes:
            st.info("No classes created yet")
        else:
            for c in classes:
                student_count = db.execute(
                    "SELECT COUNT(*) FROM students WHERE class_id=? AND is_active=1", 
                    (c["id"],)
                ).fetchone()[0]
                
                display_name = f"{c['class_name']} {c['section']}" if c["section"] else c["class_name"]
                
                with st.expander(f"📚 {display_name} - {student_count} students"):
                    st.write(f"**Class ID:** {c['id']}")
                    
                    if st.button("🗑️ Delete Class", key=f"del_class_{c['id']}"):
                        if student_count > 0:
                            st.error(f"Cannot delete! {student_count} students enrolled. Move them first.")
                        else:
                            db.execute("DELETE FROM classes WHERE id=?", (c["id"],))
                            db.commit()
                            st.success("Class deleted")
                            st.rerun()

def show_students(sid, can_add, current, limit):
    """Student management"""
    db = get_db_conn()
    st.header("👨‍🎓 Student Management")
    
    # Get classes for dropdown
    classes = db.execute("SELECT id, class_name, section FROM classes WHERE school_id=?", (sid,)).fetchall()
    class_dict = {f"{c['class_name']} {c['section']}".strip(): c["id"] for c in classes}
    
    t1, t2 = st.tabs(["➕ Add Student", "📋 Student List"])
    
    # Add Student
    with t1:
        if not can_add:
            st.error(f"❌ Student limit reached! ({current}/{limit})")
            st.info("Contact admin to upgrade your plan or add extra slots.")
        elif not classes:
            st.warning("⚠️ No classes available! Create a class first.")
        else:
            st.info(f"Student slots available: {current}/{limit}")
            
            with st.form("add_student", clear_on_submit=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    name = st.text_input("Full Name *")
                    blood = st.selectbox("Blood Group", 
                                        ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"])
                    allergy = st.text_area("Allergies/Medical Notes")
                    selected_class = st.selectbox("Assign to Class *", list(class_dict.keys()))
                
                with col2:
                    parent = st.text_input("Parent/Guardian Name *")
                    phone = st.text_input("Parent Phone")
                    likes = st.text_area("Likes/Interests")
                    dislikes = st.text_area("Dislikes")
                
                # Photo upload - BROWSER ONLY
                st.subheader("📸 Profile Photo (Optional)")
                photo_file = st.file_uploader(
                    "Upload student photo",
                    type=["jpg", "jpeg", "png", "gif"],
                    help="Supported formats: JPG, PNG, GIF"
                )
                
                if photo_file:
                    st.write("Preview:")
                    st.image(photo_file, width=150)
                
                if st.form_submit_button("✅ Register Student", use_container_width=True):
                    if not all([name, parent, selected_class]):
                        st.error("Please fill all required fields (*)")
                    else:
                        # Double-check limit
                        can_still_add, _, _ = check_student_limit(sid)
                        if not can_still_add:
                            st.error("Student limit reached! Cannot add more.")
                        else:
                            # Process photo
                            photo_base64 = process_uploaded_image(photo_file)
                            
                            db.execute("""
                                INSERT INTO students 
                                (id, name, blood, allergy, parent_name, parent_phone, likes, dislikes,
                                 class_id, school_id, is_active, profile_photo)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (gen_id(), sanitize(name), blood, sanitize(allergy),
                                  sanitize(parent), sanitize(phone), sanitize(likes), 
                                  sanitize(dislikes), class_dict[selected_class], sid, 1, photo_base64))
                            db.commit()
                            
                            success_msg = f"✅ {name} registered in {selected_class}!"
                            if photo_file:
                                success_msg += " (with photo)"
                            st.success(success_msg)
                            st.balloons()
    
    # Student List
    with t2:
        # Filter
        filter_options = ["All Classes"] + list(class_dict.keys())
        filter_class = st.selectbox("Filter by Class", filter_options)
        
        # Build query
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
                class_display = f"{s['class_name']} {s['section']}".strip() if s['class_name'] else "No Class"
                
                with st.expander(f"👤 {s['name']} ({class_display})"):
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        # Display photo
                        if s["profile_photo"]:
                            display_image_from_base64(s["profile_photo"], width=150)
                        else:
                            st.write("📷 No photo")
                    
                    with col2:
                        st.write(f"**Blood Group:** {s['blood']}")
                        st.write(f"**Allergies:** {s['allergy'] or 'None'}")
                        st.write(f"**Parent:** {s['parent_name']}")
                        st.write(f"**Phone:** {s['parent_phone'] or 'N/A'}")
                        st.write(f"**Likes:** {s['likes'] or 'Not specified'}")
                        st.write(f"**Class:** {class_display}")
                        
                        # Move class
                        new_class = st.selectbox("Move to Class", list(class_dict.keys()),
                                                key=f"move_{s['id']}")
                        if st.button("Move Class", key=f"btn_move_{s['id']}"):
                            db.execute("UPDATE students SET class_id=? WHERE id=?",
                                      (class_dict[new_class], s["id"]))
                            db.commit()
                            st.success(f"Moved to {new_class}")
                            st.rerun()
                        
                        # Remove
                        if st.button("🗑️ Remove Student", key=f"rm_{s['id']}"):
                            db.execute("UPDATE students SET is_active=0 WHERE id=?", (s['id'],))
                            db.commit()
                            st.rerun()

def show_attendance(sid):
    """Attendance management"""
    db = get_db_conn()
    st.header("📋 Attendance")
    
    # Get classes
    classes = db.execute("SELECT id, class_name, section FROM classes WHERE school_id=?", (sid,)).fetchall()
    if not classes:
        st.warning("Create classes first!")
        return
    
    class_dict = {f"{c['class_name']} {c['section']}".strip(): c["id"] for c in classes}
    
    t1, t2, t3 = st.tabs(["📝 Mark Attendance", "📊 View Report", "📅 Date View"])
    
    # Mark Attendance
    with t1:
        selected_class = st.selectbox("Select Class", list(class_dict.keys()), key="att_class")
        att_date = st.date_input("Date", value=date.today())
        
        # Get students with photos
        students = db.execute("""
            SELECT id, name, profile_photo
            FROM students
            WHERE class_id=? AND school_id=? AND is_active=1
            ORDER BY name
        """, (class_dict[selected_class], sid)).fetchall()
        
        if not students:
            st.info("No students in this class")
        else:
            st.write(f"**{len(students)} students**")
            
            # Check existing attendance
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
                        if s["profile_photo"]:
                            display_image_from_base64(s["profile_photo"], width=50)
                        else:
                            st.write("👤")
                    
                    with cols[1]:
                        st.write(f"**{s['name']}**")
                    
                    with cols[2]:
                        default_idx = 0
                        if s["id"] in existing_dict:
                            default_idx = ["Present", "Absent", "Late", "Half Day"].index(existing_dict[s["id"]])
                        
                        status = st.radio(
                            f"status_{s['id']}",
                            ["Present", "Absent", "Late", "Half Day"],
                            index=default_idx,
                            horizontal=True,
                            label_visibility="collapsed"
                        )
                        attendance_data.append((s["id"], status))
                    
                    st.divider()
                
                notes = st.text_area("General Notes (optional)")
                
                if st.form_submit_button("💾 Save Attendance", use_container_width=True):
                    # Clear existing
                    db.execute("DELETE FROM attendance WHERE date=? AND class_id=?",
                              (att_date.isoformat(), class_dict[selected_class]))
                    
                    # Insert new
                    for student_id, status in attendance_data:
                        db.execute("""
                            INSERT INTO attendance (student_id, class_id, date, status, notes, marked_by)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (student_id, class_dict[selected_class], att_date.isoformat(),
                              status, notes, sid))
                    
                    db.commit()
                    st.success(f"✅ Attendance saved for {len(attendance_data)} students!")
                    st.balloons()
    
    # View Report
    with t2:
        report_class = st.selectbox("Select Class", list(class_dict.keys()), key="rep_class")
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("From", value=date.today() - timedelta(days=7))
        with col2:
            end_date = st.date_input("To", value=date.today())
        
        report = db.execute("""
            SELECT s.name, s.profile_photo,
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
            st.subheader("Attendance Summary")
            for r in report:
                percentage = (r["present"] / r["total"] * 100) if r["total"] > 0 else 0
                
                with st.expander(f"{r['name']} - {percentage:.1f}%"):
                    cols = st.columns([1, 4])
                    with cols[0]:
                        if r["profile_photo"]:
                            display_image_from_base64(r["profile_photo"], width=80)
                        else:
                            st.write("👤")
                    with cols[1]:
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Present", r["present"])
                        c2.metric("Absent", r["absent"])
                        c3.metric("Late", r["late"])
                        c4.metric("Half Day", r["half_day"])
        else:
            st.info("No attendance data for selected period")
    
    # Date View
    with t3:
        view_date = st.date_input("Select Date", value=date.today(), key="view_date")
        view_class = st.selectbox("Select Class", list(class_dict.keys()), key="view_class")
        
        records = db.execute("""
            SELECT a.*, s.name, s.profile_photo
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.date=? AND a.class_id=?
            ORDER BY s.name
        """, (view_date.isoformat(), class_dict[view_class])).fetchall()
        
        if records:
            st.subheader(f"Attendance for {view_date}")
            for r in records:
                emoji = {"Present": "✅", "Absent": "❌", "Late": "⏰", "Half Day": "⚠️"}.get(r["status"], "📋")
                
                cols = st.columns([1, 4, 2])
                with cols[0]:
                    if r["profile_photo"]:
                        display_image_from_base64(r["profile_photo"], width=50)
                    else:
                        st.write("👤")
                with cols[1]:
                    st.write(f"**{r['name']}**")
                with cols[2]:
                    st.write(f"{emoji} {r['status']}")
        else:
            st.info("No attendance marked for this date")

def show_fees(sid):
    """Fee management"""
    db = get_db_conn()
    st.header("💳 Fee Management")
    
    t1, t2 = st.tabs(["➕ Record Payment", "📊 View Fees"])
    
    # Record Payment
    with t1:
        students = db.execute("SELECT id, name FROM students WHERE school_id=? AND is_active=1", (sid,)).fetchall()
        if not students:
            st.warning("No active students")
            return
        
        stu_dict = {s["name"]: s["id"] for s in students}
        
        with st.form("add_fee"):
            selected = st.selectbox("Student", list(stu_dict.keys()))
            amount = st.number_input("Amount (₹)", min_value=0, step=100)
            month = st.text_input("For Month (e.g., January 2025)")
            status = st.selectbox("Status", ["Paid", "Pending"])
            
            if st.form_submit_button("💾 Save Record", use_container_width=True):
                db.execute("""
                    INSERT INTO fees (id, student_id, student_name, amount, month, status, payment_date, school_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (gen_id(), stu_dict[selected], selected, amount, month, status,
                      datetime.now().isoformat() if status == "Paid" else None, sid))
                db.commit()
                st.success("✅ Fee record saved!")
    
    # View Fees
    with t2:
        fees = db.execute("""
            SELECT * FROM fees WHERE school_id=? ORDER BY payment_date DESC, created_at DESC
        """, (sid,)).fetchall()
        
        if not fees:
            st.info("No fee records")
        else:
            for f in fees:
                color = "green" if f["status"] == "Paid" else "orange"
                st.markdown(f"**{f['student_name']}** | ₹{f['amount']:,} | {f['month']} | :{color}[{f['status']}]")

def show_inventory(sid):
    """Inventory management"""
    db = get_db_conn()
    st.header("📦 Inventory")
    
    t1, t2 = st.tabs(["➕ Add Item", "📦 Stock Levels"])
    
    # Add Item
    with t1:
        with st.form("add_item"):
            name = st.text_input("Item Name *")
            category = st.selectbox("Category", [
                "Stationery", "Books", "Sports", "Lab Equipment",
                "Furniture", "Electronics", "Cleaning Supplies", "Other"
            ])
            qty = st.number_input("Quantity *", min_value=0)
            min_qty = st.number_input("Minimum Stock Level *", min_value=0, value=10)
            
            if st.form_submit_button("➕ Add Item", use_container_width=True):
                if not name:
                    st.error("Item name is required")
                else:
                    db.execute("""
                        INSERT INTO inventory (id, item_name, category, quantity, min_quantity, school_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (gen_id(), sanitize(name), category, qty, min_qty, sid))
                    db.commit()
                    st.success(f"✅ Added: {name}")
    
    # Stock Levels
    with t2:
        items = db.execute("""
            SELECT * FROM inventory WHERE school_id=? ORDER BY category, item_name
        """, (sid,)).fetchall()
        
        if not items:
            st.info("No inventory items")
        else:
            for i in items:
                is_low = i["quantity"] <= i["min_quantity"]
                emoji = "🔴" if is_low else "🟢"
                status = "LOW STOCK!" if is_low else "OK"
                
                with st.container():
                    cols = st.columns([3, 2, 1])
                    cols[0].write(f"{emoji} **{i['item_name']}** ({i['category']})")
                    cols[1].write(f"Qty: {i['quantity']} (Min: {i['min_quantity']})")
                    cols[2].write(f"**{status}**")

def show_care_logs(sid):
    """Care logs"""
    db = get_db_conn()
    st.header("🧸 Care Logs")
    
    students = db.execute("SELECT id, name FROM students WHERE school_id=? AND is_active=1", (sid,)).fetchall()
    if not students:
        st.warning("No active students")
        return
    
    stu_dict = {s["name"]: s["id"] for s in students}
    
    t1, t2 = st.tabs(["➕ New Log", "📋 Today's Logs"])
    
    # New Log
    with t1:
        selected = st.selectbox("Select Student", list(stu_dict.keys()))
        log_type = st.selectbox("Log Type", ["Bathroom", "Food", "Nap"])
        
        if log_type == "Bathroom":
            with st.form("log_bathroom"):
                subtype = st.selectbox("Type", ["Pee", "Potty", "Diaper Change"])
                notes = st.text_area("Notes")
                
                if st.form_submit_button("💾 Save"):
                    db.execute("""
                        INSERT INTO care_logs (id, student_id, student_name, activity, notes, school_id, type, sub_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (gen_id(), stu_dict[selected], selected, "Bathroom", notes, sid, "bathroom", subtype))
                    db.commit()
                    st.success("✅ Saved!")
        
        elif log_type == "Food":
            with st.form("log_food"):
                meal = st.selectbox("Meal", ["Breakfast", "Lunch", "Snack"])
                status = st.selectbox("Consumption", ["Full", "Half", "Little", "Refused", "Vomited"])
                
                if st.form_submit_button("💾 Save"):
                    db.execute("""
                        INSERT INTO care_logs (id, student_id, student_name, activity, school_id, type, sub_type, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (gen_id(), stu_dict[selected], selected, "Food", sid, "food", meal, status))
                    db.commit()
                    st.success("✅ Saved!")
        
        elif log_type == "Nap":
            with st.form("log_nap"):
                start = st.time_input("Nap Start")
                end = st.time_input("Nap End")
                
                if st.form_submit_button("💾 Save"):
                    db.execute("""
                        INSERT INTO care_logs (id, student_id, student_name, activity, school_id, type, start_time, end_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (gen_id(), stu_dict[selected], selected, "Nap", sid, "nap", str(start), str(end)))
                    db.commit()
                    st.success("✅ Saved!")
    
    # Today's Logs
    with t2:
        logs = db.execute("""
            SELECT * FROM care_logs
            WHERE school_id=? AND date(time)=date('now')
            ORDER BY time DESC
        """, (sid,)).fetchall()
        
        if not logs:
            st.info("No logs today")
        else:
            for l in logs:
                emoji = {"bathroom": "🚽", "food": "🍽️", "nap": "😴"}.get(l["type"], "📝")
                st.markdown(f"{emoji} **{l['student_name']}** - {l['activity']} at {l['time'][11:16]}")

# ================= MAIN =================
def main():
    """Main application entry"""
    if not st.session_state.auth["logged_in"]:
        login_page()
    elif st.session_state.auth["role"] == "admin":
        admin_page()
    else:
        school_page()
    
    st.divider()
    st.caption("SchoolOS Pro Final Version | Phase 3 Complete | Browser-Only Technology")

if __name__ == "__main__":
    main()
