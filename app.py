# SCHOOL PRO FINAL VERSION - PHASE 3 COMPLETE
# Features: Classes, Attendance, Photos, Plan Pricing with Renewal Control

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

# PRICING CONFIGURATION - ADMIN CONTROLLED
PRICING_CONFIG = {
    "Basic": {"students": 30, "price": 2000, "extra_allowed": False},
    "Standard": {"students": 80, "price": 4000, "extra_allowed": False},
    "Premium": {"students": 500, "price": 7999, "extra_allowed": True, "extra_price": 100},
    "Enterprise": {"students": 999999, "price": 9999, "extra_allowed": False}
}

# Custom CSS
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1f77b4; }
    .stProgress > div > div > div > div { background-color: #1f77b4; }
</style>
""", unsafe_allow_html=True)

# ================= DATABASE =================
@st.cache_resource
def get_db():
    """Initialize database"""
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
    
    # Create Default Admin
    hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
    conn.execute("INSERT OR IGNORE INTO admin_config VALUES (?, ?)", 
                ("admin_password_hash", hashed))
    conn.commit()
    return conn

def get_db_conn():
    return get_db()

# ================= SECURITY =================
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

# ================= IMAGE HANDLING =================
def process_uploaded_image(uploaded_file):
    """Convert uploaded file to base64"""
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
    """Display image from base64"""
    if base64_string is None:
        return False
    try:
        image_bytes = base64.b64decode(base64_string)
        st.image(image_bytes, width=width)
        return True
    except:
        st.write("📷 No photo")
        return False

# ================= PRICING FUNCTIONS =================
def get_plan_price(plan_name: str) -> int:
    """Get current price for plan"""
    return PRICING_CONFIG.get(plan_name, {}).get("price", 2000)

def get_plan_student_limit(plan_name: str) -> int:
    """Get student limit for plan"""
    return PRICING_CONFIG.get(plan_name, {}).get("students", 30)

def can_Add_Extra_Students(plan_name: str) -> bool:
    """Check if plan allows extra students"""
    return PRICING_CONFIG.get(plan_name, {}).get("extra_allowed", False)

def Get_Extra_Student_Price(plan_name: str) -> int:
    """Get price per extra student"""
    return PRICING_CONFIG.get(plan_name, {}).get("extra_price", 0)

def Calculate_School_Price(plan_name: str, extra_students: int) -> int:
    """Calculate total price for school"""
    base_price = get_Plan_Price(plan_name)
    if Can_Add_Extra_Students(plan_name):
        extra_cost = extra_students * Get_Extra_Student_Price(plan_name)
        return base_price + extra_cost
    return base_Price

# ================= STUDENT LIMIT =================
def Check_Student_Limit(school_id: str):
    """Check if school can add more students"""
    db = get_db_conn()
    school = db.execute("SELECT plan, extra_students FROM schools WHERE id=?", (school_id,)).fetchone()
    if not school:
        return False, 0, 0, 0
    
    plan = school["plan"]
    Base_Limit = Get_Plan_Student_Limit(Plan)
    Extra_Allowed = school["extra_students"]
    Total_Limit = Base_Limit + (Extra_Allowed if Can_Add_Extra_Students(Plan) else 0)
    
    Current = db.execute(
        "SELECT COUNT(*) FROM students WHERE school_id=? AND is_active=1", 
        (school_id,)
    ).fetchone()[0]
    
    Price = Calculate_School_Price(Plan, Extra_Allowed)
    
    return Current < Total_Limit, Current, Total_Limit, Price

# ================= SESSION =================
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}

# ================= LOGIN =================
def Login_Page():
    """Login screen"""
    st.markdown('<p class="main-header">🏫 SchoolOS Pro</p>', unsafe_allow_html=True)
    st.markdown("### Complete School Management System")
    
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        with st.container():
            user = st.text_input("User ID")
            Pw = st.text_input("Password", type="password")
            
            if st.button("🔐 Login", type="primary", use_container_width=True):
                db = get_db_conn()
                
                # Admin Login
                if User == "admin":
                    h = db.execute("SELECT value FROM admin_config WHERE key='admin_password_hash'").fetchone()
                    if H and Check_Pw(Pw, H[0]):
                        st.session_state.auth = {"logged_in": True, "role": "admin", "school_id": None}
                        st.rerun()
                    else:
                        st.error("Invalid admin credentials")
                    return
                
                # School Login
                School = db.execute("SELECT * FROM schools WHERE id=? AND is_active=1", (User,)).fetchone()
                If not School:
                    St.error("School not found")
                    Return
                
                If not Check_Pw(Pw, School["pass"]):
                    St.error("Invalid password")
                    Return
                
                Try:
                    If datetime.now() > datetime.strptime(School["expiry"], "%Y-%m-%d"):
                        St.error("Subscription expired")
                        Return
                Except:
                    Pass
                
                St.Session_State.auth = {"logged_in": True, "role": "school", "school_id": User}
                St.rerun()

# ================= ADMIN DASHBOARD =================
def Admin_Page():
    """Admin panel"""
    st.title("👑 Admin Dashboard")
    db = get_db_conn()
    
    # Sidebar
    with st.sidebar:
        st.markdown("### System Control")
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}
            st.rerun()
        
        st.divider()
        
        # Stats
        Total_Schools = db.execute("SELECT COUNT(*) FROM schools WHERE is_active=1").fetchone()[0]
        Total_Students = db.execute("SELECT COUNT(*) FROM students WHERE is_active=1").fetchone()[0]
        Total_Revenue = db.execute("SELECT COALESCE(SUM(amount), 0) FROM fees WHERE status='Paid'").fetchone()[0]
        
        st.metric("Active Schools", Total_Schools)
        st.metric("Total Students", Total_Students)
        st.metric("Total Revenue", f"₹{Total_Revenue:,}")
    
    # Tabs
    t1, t2, t3, t4 = st.tabs(["🏫 Schools", "📢 Broadcasts", "💰 Pricing", "⚙️ Settings"])
    
    # Schools Tab
    with t1:
        c1, c2 = st.columns([1, 2])
        
        # Create School
        with c1:
            st.subheader("➕ Create New School")
            
            with st.form("create_school", clear_on_submit=True):
                # School Details
                School_ID = st.text_input("School ID *")
                School_Name = st.text_input("School Name *")
                Password = st.text_input("Password *", type="password")
                
                # Plan Selection with Pricing
                st.subheader("📋 Select Plan")
                
                Plan_Options = list(PRICING_CONFIG.keys())
                Selected_Plan = st.selectbox("Subscription Plan *", Plan_Options)
                
                # Show Plan Details
                Plan_Details = PRICING_CONFIG[Selected_Plan]
                
                st.info(f"""
                **{Selected_Plan} Plan Features:**
                - Student Limit: {Plan_Details['students']} students
                - Yearly Price: ₹{Plan_Details['price']:,}
                - Extra Students: {'✅ Allowed @ ₹' + str(Plan_Details.get('extra_price', 0)) + '/student' if Plan_Details['extra_allowed'] else '❌ Not Available'}
                """)
                
                Years = st.number_input("Subscription Years *", 1, 5, 1)
                
                # Extra Students (Only for Premium)
                If Plan_Details['extra_allowed']:
                    Extra_Students = st.number_input("Extra Student Slots", 0, 1000, 0)
                Else:
                    Extra_Students = 0
                    st.info("ℹ️ Extra students only available for Premium Plan")
                
                # Pricing Summary
                Total_Price = Calculate_School_Price(Selected_Plan, Extra_Students)
                st.success(f"**Total Annual Cost: ₹{Total_Price:,}**")
                
                If st.form_submit_button("✅ Create School", use_container_width=True):
                    If not all([School_ID, School_Name, Password]):
                        st.error("Please fill all required fields")
                    Elif len(Password) < 6:
                        St.error("Password must be at least 6 characters")
                    Elif db.execute("SELECT 1 FROM schools WHERE id=?", (School_ID,)).fetchone():
                        St.error("School ID already exists")
                    Else:
                        Expiry = (datetime.now() + timedelta(days=365*Years)).strftime("%Y-%m-%d")
                        
                        db.execute("""
                            INSERT INTO schools (id, name, pass, plan, expiry, extra_students, is_active)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (School_ID, School_Name, Hash_Pw(Password), Selected_Plan, Expiry, Extra_Students, 1))
                        db.commit()
                        St.success(f"✅ Created {School_Name}! Total Cost: ₹{Total_Price:,}")
                        St.balloons()
        
        # Manage Schools
        with c2:
            st.subheader("📚 Manage Schools")
            Schools = db.execute("SELECT * FROM schools WHERE is_active=1 ORDER BY created_at DESC").fetchall()
            
            If not Schools:
                St.info("No schools created yet")
            Else:
                For S in Schools:
                    Plan_Details = PRICING_CONFIG[S["plan"]]
                    Limit = Plan_Details["students"] + S["extra_students"]
                    Count = db.execute("SELECT COUNT(*) FROM students WHERE school_id=? AND is_active=1", (S["id"],)).fetchone()[0]
                    
                    With St.expander(f"🏫 {S['name']} ({S['id']}) - {Count}/{Limit} students"):
                        Col1, Col2 = st.columns(2)
                        
                        With Col1:
                            st.write(f"**Plan:** {S['plan']}")
                            st.write(f"**Students:** {Count}/{Limit}")
                            st.write(f"**Expires:** {S['expiry']}")
                        
                        With Col2:
                            Current_Price = Calculate_School_Price(S["plan"], S["extra_students"])
                            st.write(f"**Annual Cost:** ₹{Current_Price:,}")
                            
                            Days_Left = (datetime.strptime(S["expiry"], "%Y-%m-%d") - datetime.now()).days
                            If Days_Left < 30:
                                st.error(f"⚠️ Expires in {Days_Left} days!")
                            Else:
                                St.success(f"✅ {Days_Left} days remaining")
                        
                        # Deactivate
                        If St.button("🗑️ Deactivate", key=f"del_{S['id']}"):
                            db.execute("UPDATE schools SET is_active=0 WHERE id=?", (S['id'],))
                            db.commit()
                            St.success("School deactivated")
                            St.rerun()
    
    # Broadcasts Tab
    with t2:
        st.subheader("📢 Send Broadcast")
        
        with st.form("broadcast_form"):
            Message = st.text_area("Message", max_chars=1000)
            Priority = st.selectbox("Priority", ["low", "normal", "high", "urgent"])
            
            If St.form_submit_button("📢 Send Broadcast", use_container_width=True):
                If Message.strip():
                    Clean_Msg = Sanitize(Message)
                    db.execute("INSERT INTO broadcasts (msg, priority, created_by) VALUES (?, ?, ?)",
                              (Clean_Msg, Priority, "admin"))
                    db.commit()
                    St.success("✅ Broadcast sent!")
        
        st.divider()
        st.subheader("📜 Recent Broadcasts")
        Broadcasts = db.execute("SELECT * FROM broadcasts ORDER BY date DESC LIMIT 10").fetchall()
        
        for B in Broadcasts:
            Emoji = {"low": "⚪", "normal": "🔵", "high": "🟠", "urgent": "🔴"}.get(B["priority"], "⚪")
            St.markdown(f"{Emoji} **{B['date'][:10]}**: {B['msg']}")
    
    # Pricing Tab
    with t3:
        st.subheader("💰 Pricing & Plans")
        
        st.info("""
        ### Current Pricing Structure
        
        | Plan | Students | Yearly Price | Extra Students |
        |------|-----------|--------------|------------------|
        | Basic | 30 | ₹2,000 | ❌ Not Available |
        | Standard | 80 | ₹4,000 | ❌ Not Available |
        | Premium | 500 | ₹7,999 | ✅ ₹100/student |
        | Enterprise | Unlimited | ₹9,999 | N/A |
        """)
        
        st.divider()
        
        # Price Calculator
        st.subheader("🧮 Price Calculator")
        
        Calc_Plan = st.selectbox("Select Plan", list(PRICING_CONFIG.keys()))
        Calc_Extra = st.number_input("Extra Students", 0, 100, 0)
        
        Calc_Price = Calculate_School_Price(Calc_Plan, Calc_Extra)
        
        st.success(f"**Calculated Annual Price: ₹{Calc_Price:,}**")
        
        st.info("""
        **Note:** 
        - Basic & Standard plans have fixed limits (No Extra Students)
        - Premium Plan allows Extra Students @ ₹100/student
        - Enterprise Plan has Unlimited Students
        """)
    
    # Settings Tab
    with t4:
        st.subheader("⚙️ Change Admin Password")
        
        with St.form("change_password"):
            Old_Pw = st.text_input("Current Password", type="password")
            New_Pw = st.text_input("New Password", type="password")
            Conf_Pw = st.text_input("Confirm Password", type="password")
            
            If St.form_submit_button("Update Password", use_container_width=True:
                Cur_Hash = db.execute("SELECT value FROM admin_config WHERE key='admin_password_hash'").fetchone()[0]
                
                If not Check_Pw(Old_Pw, Cur_Hash):
                    St.error("❌ Current password incorrect")
                Elif New_Pw != Conf_Pw:
                    St.error("❌ Passwords do not match")
                Elif len(New_Pw) < 8:
                    St.error("❌ Password must be at least 8 characters")
                Else:
                    db.execute("UPDATE admin_config SET value=? WHERE key='admin_password_hash'",
                              (Hash_Pw(New_Pw),))
                    db.commit()
                    St.success("✅ Password updated successfully!")

# ================= SCHOOL DASHBOARD =================
def School_Page():
    """School panel"""
    Sid = st.session_state.auth["school_id"]
    db = get_db_conn()
    School = db.execute("SELECT * FROM schools WHERE id=?", (Sid,)).fetchone()
    
    st.title(f"🏫 {School['name']}")
    
    # Check Limits
    Can_Add, Current, Limit, Price = Check_Student_Limit(Sid)
    
    # Sidebar
    with st.sidebar:
        st.markdown(f"### {School['name'][:20]}")
        st.progress(min(Current/Limit, 1.0), text=f"Students: {Current}/{Limit}")
        
        If Current >= Limit:
            st.error("⚠️ Student limit reached!")
        
        # Navigation
        Menu = st.radio("Menu", [
            "📊 Dashboard",
            "🏫 Classes", 
            "👨‍🎓 Students",
            "📋 Attendance",
            "💳 Fees",
            "📦 Inventory",
            "🧸 Care Logs"
        ])
        
        st.divider()
        
        If st.button("🚪 Logout", use_container_width=True):
            st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}
            st.rerun()
    
    # Route Menu
    if Menu == "📊 Dashboard":
        Show_Dashboard(Sid, Current)
    elif Menu == "🏫 Classes":
        Show_Classes(Sid)
    elif Menu == "👨‍🎓 Students":
        Show_Students(Sid, Can_Add, Current, Limit)
    elif Menu == "📋 Attendance":
        Show_Attendance(Sid)
    elif Menu == "💳 Fees":
        Show_Fees(Sid)
    elif Menu == "📦 Inventory":
        Show_Inventory(Sid)
    elif Menu == "🧸 Care Logs":
        Show_Care_Logs(Sid)

def Show_Dashboard(Sid, Current):
    """School dashboard"""
    db = get_db_conn()
    st.header("📊 Dashboard Overview")
    
    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Students", Current)
    c2.metric("Total Classes", db.execute("SELECT COUNT(*) FROM classes WHERE school_id=?", (Sid,)).fetchone()[0])
    c3.metric("Pending Fees", db.execute("SELECT COUNT(*) FROM fees WHERE school_id=? AND status='Pending'", (Sid,)).fetchone()[0])
    c4.metric("Revenue", f"₹{db.execute('SELECT COALESCE(SUM(amount),0) FROM fees WHERE school_id=? AND status=\'Paid\'', (Sid,)).fetchone()[0]:,}")
    
    # Today's Attendance
    st.subheader("Today's Attendance Summary")
    Today = date.today().isoformat()
    
    Attendance_Summary = db.execute("""
        SELECT status, COUNT(*) as count
        FROM attendance
        WHERE date=? AND class_id IN (SELECT id FROM classes WHERE school_id=?)
        GROUP BY status
    """, (Today, Sid)).fetchall()
    
    if Attendance_Summary:
        cols = st.columns(len(Attendance_Summary))
        for idx, Row in enumerate(Attendance_Summary):
            Emoji = {"Present": "✅", "Absent": "❌", "Late": "⏰", "Half Day": "⚠️"}.get(Row["status"], "📋")
            cols[Idx].metric(f"{Emoji} {Row['status']}", Row["count"])
    Else:
        st.info("No attendance marked today")

def Show_Classes(Sid):
    """Class management"""
    db = get_db_conn()
    st.header("🏫 Class Management")
    
    t1, T2 = st.tabs(["➕ Create Class", "📋 View Classes"])
    
    # Create Class
    with t1:
        with st.form("create_class", clear_on_submit=True):
            Class_Name = st.text_input("Class Name *", placeholder="e.g., Grade 1, Nursery, etc.")
            Section = st.text_input("Section", placeholder="e.g., A, B, Morning, etc.")
            
            If St.form_submit_button("➕ Create Class", use_container_width=True):
                If not Class_Name:
                    St.error("Class name is required")
                Else:
                    Class_ID = gen_id()
                    db.Execute("""
                        INSERT INTO classes (id, class_name, section, school_id)
                        VALUES (?, ?, ?, ?)
                    """, (Class_ID, Sanitize(Class_Name), Sanitize(Section), Sid))
                    db.Commit()
                    Display_Name = f"{Class_Name} {Section}" if Section else Class_Name
                    St.success(f"✅ Created: {Display_Name}")
                    St.balloons()
    
    # View Classes
    with T2:
        Classes = db.execute("SELECT * FROM classes WHERE school_id=? ORDER BY class_name, section", (Sid,)).fetchall()
        
        If not Classes:
            St.info("No classes created yet")
        Else:
            For C in Classes:
                Student_Count = db.execute(
                    "SELECT COUNT(*) FROM students WHERE class_id=? AND is_active=1", 
                    (C["id"],)
                ).fetchone()[0]
                
                Display_Name = f"{C['class_name']} {C['section']}".strip() if C['class_name'] else "No Class"
                
                with St.expander(f"📚 {Display_Name} - {Student_Count} students"):
                    St.write(f"**Class ID:** {C['id']}")
                    
                    If St.button("🗑️ Delete Class", key=f"del_class_{C['id']}"):
                        If Student_Count > 0:
                            St.error(f"Cannot Delete! {Student_Count} Students enrolled.")
                        Else:
                            db.execute("DELETE FROM classes WHERE id=?", (C["id"],))
                            db.Commit()
                            St.success("Class deleted")
                            St.rerun()

def Show_Students(Sid, Can_Add, Current, Limit):
    """Student management"""
    db = Get_db_conn()
    st.header("👨‍🎓 Student Management")
    
    # Get Classes
    Classes = db.execute("SELECT id, class_name, section FROM classes WHERE school_id=?", (Sid,)).fetchall()
    Class_Dict = {f"{C['class_name']} {C['section']}".strip(): C["id"] for C in Classes}
    
    T1, T2 = st.tabs(["➕ Add Student", "📋 Student List"])
    
    # Add Student
    with T1:
        If not Can_Add:
            St.error(f"❌ Student limit reached! ({Current}/{Limit})")
            St.info("Contact admin to upgrade Your plan.")
        Elif not Classes:
            St.warning("⚠️ Create a Class first in 'Classes' section.")
        Else:
            St.info(f"Student Slots: {Current}/{Limit} used")
            
            with St.form("add_student", clear_on_submit=True:
                Col1, Col2 = st.columns(2)
                
                with Col1:
                    Name = st.text_input("Full Name *")
                    Blood = st.selectbox("Blood Group", 
                                        ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"])
                    Allergy = st.text_area("Allergies/Medical Notes")
                    Selected_Class = st.selectbox("Assign to Class *", list(Class_Dict.keys()))
                
                With Col2:
                    Parent = st.text_input("Parent/Guardian Name *")
                    Phone = st.text_input("Parent Phone")
                    Likes = st.text_area("Likes/Interests")
                    Dislikes = st.text_area("Dislikes")
                
                # Photo Upload
                st.subheader("📸 Profile Photo (Optional)")
                Photo_File = st.file_uploader(
                    "Upload Student Photo",
                    type=["jpg", "jpeg", "png", "gif"]
                )
                
                If Photo_File:
                    st.write("Preview:")
                    st.image(Photo_File, width=150)
                
                If st.form_submit_button("✅ Register Student", use_container_width=True:
                    If not all([Name, Parent, Selected_Class]):
                        st.error("Please fill all required fields (*)")
                    Else:
                        # Check Limit again
                        Can_Still_Add, _, _, _ = Check_Student_Limit(Sid)
                        If not Can_Still_Add:
                            St.error("Student Limit reached!")
                        Else:
                            Photo_Base64 = Process_Uploaded_Image(Photo_File)
                            
                            db.Execute("""
                                INSERT INTO students 
                                (id, name, blood, allergy, parent_name, parent_phone, likes, dislikes,
                                 class_id, school_id, is_active, profile_photo)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (gen_id(), Sanitize(Name), Blood, Sanitize(Allergy), Sanitize(Parent),
                                  Sanitize(Phone), Sanitize(Likes), Sanitize(Dislikes),
                                  Class_Dict[Selected_Class], Sid, 1, Photo_Base64))
                            db.Commit()
                            
                            Success_Msg = f"✅ {Name} registered in {Selected_Class}!"
                            If Photo_File:
                                Success_Msg += " (with photo)"
                            St.success(Success_Msg)
                            St.balloons()
    
    # Student List
    with T2:
        Filter_Class = st.selectbox("Filter by Class", ["All Classes"] + list(Class_Dict.keys()))
        
        Query = """
            SELECT S.*, C.class_name, C.section
            FROM students S
            LEFT JOIN classes C ON S.class_id = C.id
            WHERE S.school_id=? AND S.is_active=1
        """
        Params = [Sid]
        
        If Filter_Class != "All Classes":
            Query += " AND S.class_id=?"
            Params.append(Class_Dict[Filter_Class])
        
        Query += " ORDER BY C.class_name, S.name"
        
        Students = db.execute(Query, tuple(Params)).fetchall()
        
        If not Students:
            St.info("No Students found")
        Else:
            St.write(f"**Total: {len(Students)} Students**")
            
            For S in Students:
                Class_Display = f"{S['class_name']} {S['section']}".strip() if S['class_name'] else "No Class"
                
                With St.expander(f"👤 {S['name']} ({Class_Display})"):
                    Col1, Col2 = st.columns([1, 3])
                    
                    With Col1:
                        # Show Photo
                        If S["profile_photo"]:
                            Display_Image_From_Base64(S["profile_photo"], width=150)
                        Else:
                            St.write("📷 No photo")
                    
                    With Col2:
                        St.write(f"**Blood:** {S['blood']}")
                        St.write(f"**Allergies:** {S['allergy'] or 'None'}")
                        St.write(f"**Parent:** {S['parent_name']}")
                        St.write(f"**Phone:** {S['parent_phone'] or 'N/A'}")
                        St.write(f"**Class:** {Class_Display}")
                        
                        # Move Class
                        New_Class = st.selectbox("Move to Class", list(Class_Dict.keys()),
                                                key=f"move_{S['id']}")
                        If St.button("Move Class", key=f"btn_move_{S['id']}"):
                            db.execute("UPDATE students SET class_id=? WHERE id=?",
                                      (Class_Dict[New_Class], S["id"]))
                            db.Commit()
                            St.success(f"Moved to {New_Class}")
                            St.rerun()
                        
                        # Remove
                        If St.button("🗑️ Remove Student", key=f"rm_{S['id']}"):
                            db.execute("UPDATE Students SET is_active=0 WHERE id=?", (S["id"],))
                            db.Commit()
                            St.rerun()

def Show_Attendance(Sid):
    """Attendance management"""
    db = get_db_conn()
    st.header("📋 Attendance")
    
    # Get Classes
    Classes = db.execute("SELECT id, class_name, section FROM classes WHERE school_id=?", (Sid,)).fetchall()
    If not Classes:
        St.warning("Create Classes first!")
        Return
    
    Class_Dict = {f"{C['class_name']} {C['section']}".strip(): C["id"] for C in Classes}
    
    T1, T2, T3 = st.tabs(["📝 Mark Attendance", "📊 View Report", "📅 Date View"])
    
    # Mark Attendance
    with T1:
        Selected_Class = st.selectbox("Select Class", list(Class_Dict.keys()), key="att_class")
        Att_Date = st.date_input("Date", value=date.today())
        
        # Get Students
        Students = db.execute("""
            SELECT id, Name, profile_photo
            FROM Students
            WHERE class_id=? AND school_id=? AND is_active=1
            ORDER BY Name
        """, (Class_Dict[Selected_Class], Sid)).fetchall()
        
        If not Students:
            St.info("No Students in this class")
        Else:
            St.write(f"**{len(Students)} Students**")
            
            # Check Existing Attendance
            Existing = db.execute("""
                SELECT student_id, status FROM attendance
                WHERE date=? AND class_id=?
            """, (Att_Date.isoformat(), Class_Dict[Selected_Class])).fetchall()
            Existing_Dict = {Row["student_id"]: Row["status"] for Row in Existing}
            
            With St.form("mark_attendance"):
                Attendance_Data = []
                
                For S in Students:
                    Cols = st.columns([1, 3, 4])
                    
                    With Cols[0]:
                        # Show Thumbnail
                        If S["profile_photo"]:
                            Display_Image_From_Base64(S["profile_photo"], width=50)
                        Else:
                            St.write("👤")
                    
                    With Cols[1]:
                        St.write(f"**{S['name']}**")
                    
                    With Cols[2]:
                        Default_Idx = 0
                        If S["id"] in Existing_Dict:
                            Default_Idx = ["Present", "Absent", "Late", "Half Day"].index(Existing_Dict[S["id"]])
                        
                        Status = st.radio(
                            f"status_{S['id']}",
                            ["Present", "Absent", "Late", "Half Day"],
                            index=Default_Idx,
                            horizontal=True,
                            label_visibility="collapsed"
                        )
                        Attendance_Data.append((S["id"], Status))
                    
                    St.divider()
                
                Notes = st.text_area("General Notes (optional)")
                
                If St.form_submit_button("💾 Save Attendance", use_container_width=True):
                    # Clear Existing
                    db.execute("DELETE FROM attendance WHERE date=? AND class_id=?",
                              (Att_Date.isoformat(), Class_Dict[Selected_Class]))
                    
                    # Insert New Records
                    For Student_ID, Status in Attendance_Data:
                        db.execute("""
                            INSERT INTO attendance (student_id, class_id, date, status, notes, marked_by)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (Student_ID, Class_Dict[Selected_Class], Att_Date.isoformat(),
                              Status, Notes, Sid))
                    
                    db.Commit()
                    St.success(f"✅ Attendance saved for {len(Attendance_Data)} Students!")
                    St.balloons()
    
    # View Report
    with T2:
        Report_Class = st.selectbox("Select Class", list(Class_Dict.keys()), key="rep_class")
        
        Col1, Col2 = st.columns(2)
        With Col1:
            Start_Date = st.date_input("From", value=date.today() - timedelta(days=7))
        With Col2:
            End_Date = st.date_input("To", value=date.today())
        
        Report = db.execute("""
            SELECT S.name, S.profile_photo,
                   COUNT(CASE WHEN A.status='Present' THEN 1 END) as present,
                   COUNT(CASE WHEN A.status='Absent' THEN 1 END) as absent,
                   COUNT(CASE WHEN A.status='Late' THEN 1 END) as late,
                   COUNT(CASE WHEN A.status='Half Day' THEN 1 END) as half_day,
                   COUNT(A.id) as total
            FROM Students S
            LEFT JOIN attendance A ON S.id = A.student_id
                AND A.date BETWEEN ? AND ? AND A.class_id=?
            WHERE S.class_id=? AND S.school_id=? AND S.is_active=1
            GROUP BY S.id
            ORDER BY S.name
        """, (Start_Date.isoformat(), End_Date.isoformat(), Class_Dict[Report_Class],
              Class_Dict[Report_Class], Sid)).fetchall()
        
        If Report:
            St.subheader("Attendance Summary")
            For R in Report:
                Percentage = (R["present"] / R["total"] * 100) if R["total"] > 0 else 0
                
                With St.expander(f"{R['name']} - {Percentage:.1f}%"):
                    Cols = st.columns([1, 4])
                    With Cols[0]:
                        If R["profile_photo"]:
                            Display_Image_From_Base64(R["profile_photo"], width=80)
                        Else:
                            St.write("👤")
                    With Cols[1]:
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Present", R["present"])
                        c2.metric("Absent", R["absent"])
                        c3.metric("Late", R["late"])
                        c4.metric("Half Day", R["half_day"])
        Else:
            St.info("No attendance data for selected period")
    
    # Date View
    with T3:
        View_Date = st.date_input("Select Date", value=date.today(), key="view_date")
        View_Class = st.selectbox("Select Class", list(Class_Dict.keys()), key="view_class")
        
        Records = db.execute("""
            SELECT A.*, S.name, S.profile_photo
            FROM attendance A
            JOIN students S ON A.student_id = S.id
            WHERE A.date=? AND A.class_id=?
            ORDER BY S.name
        """, (View_Date.isoformat(), Class_Dict[View_Class])).fetchall()
        
        If Records:
            St.subheader(f"Attendance for {View_Date}")
            For R in Records:
                Emoji = {"Present": "✅", "Absent": "❌", "Late": "⏰", "Half Day": "⚠️"}.get(R["status"], "📋")
                
                Cols = st.columns([1, 4, 2])
                With Cols[0]:
                    If R["profile_photo"]:
                        Display_Image_From_Base64(R["profile_photo"], width=50)
                    Else:
                        St.write("👤")
                With Cols[1]:
                    St.write(f"**{R['name']}**")
                With Cols[2]:
                    St.write(f"{Emoji} {R['status']}")
        Else:
            St.info("No attendance marked for this date")

def Show_Fees(Sid):
    """Fee management"""
    db = Get_db_conn()
    st.header("💳 Fee Management")
    
    T1, T2 = st.tabs(["➕ Record Payment", "📊 View Fees"])
    
    # Record Payment
    with T1:
        Students = db.execute("SELECT id, Name FROM students WHERE school_id=? AND is_active=1", (Sid,)).fetchall()
        If not Students:
            St.warning("No active students")
            Return
        
        Stu_Dict = {S["Name"]: S["id"] for S in Students}
        
        with St.form("add_fee"):
            Selected = st.selectbox("Student", list(Stu_Dict.keys()))
            Amount = st.number_input("Amount (₹)", min_value=0, step=100)
            Month = st.text_input("For Month (e.g., January 2025)")
            Status = st.selectbox("Status", ["Paid", "Pending"])
            
            If St.form_submit_button("💾 Save Record", use_container_width=True:
                db.Execute("""
                    INSERT INTO fees (id, student_id, student_name, amount, month, status, payment_date, school_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (gen_id(), Stu_Dict[Selected], Selected, Amount, Month, Status,
                      datetime.now().isoformat() if Status == "Paid" else None, Sid))
                db.Commit()
                St.success("✅ Fee record saved!")
    
    # View Fees
    with T2:
        Fees = db.execute("SELECT * FROM fees WHERE school_id=? ORDER BY payment_date DESC, created_at DESC", (Sid,)).fetchall()
        
        If not Fees:
            St.info("No fee records")
        Else:
            For F in Fees:
                Color = "green" if F["status"] == "Paid" else "orange"
                St.markdown(f"**{F['student_name']}** | ₹{F['Amount']:,} | {F['month']} | :{Color}[{F['status']}]")

def Show_Inventory(Sid):
    """Inventory management"""
    db = Get_db_conn()
    st.header("📦 Inventory")
    
    T1, T2 = st.tabs(["➕ Add Item", "📦 Stock Levels"])
    
    # Add Item
    with T1:
        with St.form("add_item"):
            Name = st.text_input("Item Name *")
            Category = st.selectbox("Category", [
                "Stationery", "Books", "Sports", "Lab Equipment",
                "Furniture", "Electronics", "Cleaning Supplies", "Other"
            ])
            Qty = st.number_input("Quantity *", min_value=0)
            Min_Qty = st.number_input("Minimum Stock Level *", min_value=0, value=10)
            
            If St.form_submit_button("➕ Add Item", use_container_width=True:
                If not Name:
                    St.error("Item name is required")
                Else:
                    db.Execute("""
                        INSERT INTO inventory (id, item_name, category, quantity, min_quantity, school_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (gen_id(), Sanitize(Name), Category, Qty, Min_Qty, Sid))
                    db.Commit()
                    St.success(f"✅ Added: {Name}")
    
    # Stock Levels
    with T2:
        Items = db.execute("SELECT * FROM inventory WHERE school_id=? ORDER BY category, item_name", (Sid,)).fetchall()
        
        If not Items:
            St.info("No inventory items")
        Else:
            For I in Items:
                Is_Low = I["quantity"] <= I["min_quantity"]
                Emoji = "🔴" if Is_Low else "🟢"
                Status = "LOW STOCK!" if Is_Low else "OK"
                
                With St.container():
                    Cols = st.columns([3, 2, 1])
                    Cols[0].write(f"{Emoji} **{I['item_name']}** ({I['category']})")
                    Cols[1].write(f"Qty: {I['quantity']} (Min: {I['min_quantity']})")
                    Cols[2].write(f"**{Status}**")

def Show_Care_Logs(Sid):
    """Care logs"""
    db = Get_db_conn()
    st.header("🧸 Care Logs")
    
    Students = db.execute("SELECT ID, Name FROM students WHERE school_id=? AND is_active=1", (Sid,)).fetchall()
    If not Students:
        St.warning("No active students")
        Return
    
    Stu_Dict = {S["Name"]: S["id"] for S in Students}
    
    T1, T2 = st.tabs(["➕ New Log", "📋 Today's Logs"])
    
    # New Log
    with T1:
        Selected = st.selectbox("Select Student", list(Stu_Dict.keys()))
        Log_Type = st.selectbox("Log Type", ["Bathroom", "Food", "Nap"])
        
        If Log_Type == "Bathroom":
            with St.form("log_bathroom"):
                Subtype = st.selectbox("Type", ["Pee", "Potty", "Diaper Change"])
                Notes = st.text_area("Notes")
                
                If St.form_submit_button("💾 Save"):
                    db.Execute("""
                        INSERT INTO care_Logs (ID, student_id, student_name, activity, notes, school_id, type, sub_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (gen_ID(), Stu_Dict[Selected], Selected, "Bathroom", Notes, Sid, "bathroom", Subtype))
                    db.Commit()
                    St.success("✅ Saved!")
        
        Elif Log_Type == "Food":
            with St.form("log_food"):
                Meal = st.selectbox("Meal", ["Breakfast", "Lunch", "Snack"])
                Status = st.selectbox("Consumption", ["Full", "Half", "Little", "Refused", "Vomited"])
                
                If St.form_submit_button("💾 Save"):
                    db.Execute("""
                        INSERT INTO Care_Logs (ID, student_ID, student_Name, activity, school_ID, type, sub_type, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (gen_ID(), Stu_Dict[Selected], Selected, "Food", Sid, "food", Meal, Status))
                    db.Commit()
                    St.success("✅ Saved!")
        
        Elif Log_Type == "Nap":
            with St.form("log_nap"):
                Start = st.time_input("Nap Start")
                End = st.time_input("Nap End")
                
                If St.form_submit_button("💾 Save"):
                    db.Execute("""
                        INSERT INTO Care_Logs (ID, student_ID, student_Name, activity, school_ID, type, start_time, endTime)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (gen_ID(), Stu_Dict[Selected], Selected, "Nap", Sid, "nap", str(Start), str(End)))
                    db.Commit()
                    St.success("✅ Saved!")
    
    # Today's Logs
    with T2:
        Logs = db.execute("""
            SELECT * FROM Care_Logs
            WHERE school_ID=? AND date(Time)=date('now')
            ORDER BY time DESC
        """, (Sid,)).fetchall()
        
        If not Logs:
            St.info("No logs today")
        Else:
            For L in Logs:
                Emoji = {"bathroom": "🚽", "food": "🍽️", "nap": "😴"}.get(L["type"], "📝")
                St.markdown(f"{Emoji} **{L['student_name']}** - {L['activity']} at {L['time'][11:16]}")

# ================= MAIN =================
def Main():
    """Main application entry"""
    If not st.Session_State.auth["logged_in"]:
        Login_Page()
    Elif st.Session_State.auth["role"] == "admin":
        Admin_Page()
    Else:
        School_Page()
    
    St.divider()
    St.caption("SchoolOS Pro Final Version | Complete School Management System")

If __name__ == "__main__":
    Main()
