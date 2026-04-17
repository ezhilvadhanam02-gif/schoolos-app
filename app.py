import streamlit as st
import sqlite3
import bcrypt
import secrets
import base64
from datetime import datetime, timedelta, date
import calendar
import io
from PIL import Image
import json

# =================== CONFIG ===================
st.set_page_config(page_title="SchoolOS Pro", layout="wide", page_icon="🏫")

st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: bold; color: #1f77b4; text-align: center; margin-bottom: 0.5rem; }
    .sub-header { font-size: 1.1rem; color: #555; text-align: center; margin-bottom: 2rem; }
    .plan-card { border: 2px solid #e0e0e0; border-radius: 12px; padding: 1.5rem; text-align: center; background: #fafafa; height: 100%; }
    .plan-card:hover { border-color: #1f77b4; transform: translateY(-2px); transition: all 0.2s; }
    .plan-popular { border-color: #ff9800; background: #fff8e1; }
    .login-box { max-width: 480px; margin: auto; padding: 2rem; border: 1px solid #ddd; border-radius: 12px; background: #fff; }
    .feature-yes { color: #2e7d32; font-weight: bold; }
    .feature-no { color: #c62828; text-decoration: line-through; opacity: 0.6; }
    .school-id-box { background: #e3f2fd; border-left: 4px solid #1f77b4; padding: 10px; border-radius: 6px; margin: 10px 0; font-family: monospace; font-size: 1.1rem; }
    .trial-box { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; margin: 10px 0; text-align: center; }
    .trial-expired { background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%); }
    .upgrade-banner { background: #fff3e0; border: 2px solid #ff9800; padding: 15px; border-radius: 10px; margin: 10px 0; text-align: center; }
    @media (max-width: 768px) { .main-header { font-size: 1.6rem; } }
</style>
""", unsafe_allow_html=True)

# =================== DATABASE ===================
@st.cache_resource
def get_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS admin_config (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, max_students INTEGER DEFAULT 30,
            yearly_price INTEGER DEFAULT 0, extra_student_price INTEGER DEFAULT 0,
            features TEXT DEFAULT '{}', is_active INTEGER DEFAULT 1,
            is_popular INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS schools (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, pass TEXT NOT NULL,
            email TEXT, phone TEXT, plan_id TEXT, max_students INTEGER DEFAULT 10,
            expiry TEXT, is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            trial_start TEXT, trial_end TEXT, is_trial INTEGER DEFAULT 1,
            is_upgraded INTEGER DEFAULT 0, hard_limit_hit INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY, school_id TEXT, plan_id TEXT,
            amount_paid INTEGER, payment_status TEXT DEFAULT 'Pending',
            payment_id TEXT, razorpay_order_id TEXT,
            start_date TEXT, end_date TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS teachers (
            id TEXT PRIMARY KEY, school_id TEXT NOT NULL, name TEXT NOT NULL,
            phone TEXT NOT NULL, pass TEXT NOT NULL, role TEXT DEFAULT 'teacher',
            is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS teacher_sessions (
            id TEXT PRIMARY KEY, teacher_id TEXT NOT NULL, school_id TEXT NOT NULL,
            login_time TEXT DEFAULT CURRENT_TIMESTAMP, last_active TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS classes (
            id TEXT PRIMARY KEY, class_name TEXT NOT NULL, section TEXT,
            school_id TEXT NOT NULL, is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS programs (
            id TEXT PRIMARY KEY, program_name TEXT NOT NULL, class_id TEXT NOT NULL,
            school_id TEXT NOT NULL, is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, mother_name TEXT,
            father_name TEXT, dob TEXT, age TEXT, blood_group TEXT,
            allergy TEXT, program_id TEXT, class_id TEXT, phone TEXT, email TEXT,
            guardian_name TEXT, likes TEXT, dislikes TEXT,
            school_id TEXT NOT NULL, is_active INTEGER DEFAULT 1,
            profile_photo TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
            class_id TEXT NOT NULL, date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Present','Absent','Late','Half Day')),
            in_time TEXT, out_time TEXT, notes TEXT,
            marked_by TEXT, marked_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS care_logs (
            id TEXT PRIMARY KEY, student_id TEXT, student_name TEXT,
            activity TEXT, notes TEXT, time TEXT DEFAULT CURRENT_TIMESTAMP,
            school_id TEXT, type TEXT, sub_type TEXT, status TEXT,
            start_time TEXT, end_time TEXT
        );
    """)
    
    h = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
    conn.execute("INSERT OR IGNORE INTO admin_config VALUES (?,?)", ("admin_password_hash", h))
    
    if conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0] == 0:
        default_plans = [
            ("plan_basic", "Basic", 30, 2999, 0,
             json.dumps({"students":True,"attendance":True,"care_logs":True,"reports":False,"photos":False,"whatsapp":False,"multi_teacher":False,"max_teachers":1,"broadcast":True}), 1, 0, 1),
            ("plan_std", "Standard", 80, 4999, 0,
             json.dumps({"students":True,"attendance":True,"care_logs":True,"reports":True,"photos":False,"whatsapp":False,"multi_teacher":True,"max_teachers":2,"broadcast":True}), 1, 0, 2),
            ("plan_prem", "Premium", 500, 7999, 100,
             json.dumps({"students":True,"attendance":True,"care_logs":True,"reports":True,"photos":True,"whatsapp":True,"multi_teacher":True,"max_teachers":10,"broadcast":True}), 1, 1, 3),
            ("plan_ent", "Enterprise", 9999, 11999, 0,
             json.dumps({"students":True,"attendance":True,"care_logs":True,"reports":True,"photos":True,"whatsapp":True,"multi_teacher":True,"max_teachers":50,"broadcast":True}), 1, 0, 4),
        ]
        conn.executemany("""
            INSERT INTO plans (id, name, max_students, yearly_price, extra_student_price, features, is_active, is_popular, sort_order)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, default_plans)
    conn.commit()
    return conn

def get_db_conn():
    return get_db()

# =================== HELPERS ===================
def sanitize(text):
    if not isinstance(text, str):
        return ""
    return text.strip()[:255]

def hash_pw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def check_pw(pw, hashed):
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

def gen_id():
    return secrets.token_urlsafe(12)

def gen_school_id():
    """Generate unique 8-character school ID"""
    return secrets.token_urlsafe(6)[:8].upper()

def compress_image(uploaded_file, max_size=(600, 600), quality=60):
    if uploaded_file is None:
        return None
    try:
        img = Image.open(io.BytesIO(uploaded_file.getvalue()))
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            if img.mode in ('RGBA', 'LA'):
                bg.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = bg
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=quality, optimize=True)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        st.error(f"Image error: {e}")
        return None

def calc_age(dob_str):
    try:
        dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
        today = date.today()
        years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return str(years)
    except Exception:
        return ""

def manage_teacher_session(teacher_id, school_id):
    db = get_db_conn()
    rows = db.execute("""
        SELECT ts.id FROM teacher_sessions ts
        JOIN teachers t ON ts.teacher_id = t.id
        WHERE ts.school_id=? AND ts.is_active=1 AND t.role='teacher'
        ORDER BY ts.login_time ASC
    """, (school_id,)).fetchall()
    if len(rows) >= 2:
        db.execute("UPDATE teacher_sessions SET is_active=0 WHERE id=?", (rows[0]["id"],))
    sid = gen_id()
    now = datetime.now().isoformat()
    db.execute("""
        INSERT INTO teacher_sessions (id, teacher_id, school_id, login_time, last_active, is_active)
        VALUES (?,?,?,?,?,1)
    """, (sid, teacher_id, school_id, now, now))
    db.commit()
    return sid

def is_session_active(session_id):
    if not session_id:
        return False
    db = get_db_conn()
    r = db.execute("SELECT is_active FROM teacher_sessions WHERE id=?", (session_id,)).fetchone()
    return r is not None and r["is_active"] == 1

def logout_teacher_session(session_id):
    db = get_db_conn()
    db.execute("UPDATE teacher_sessions SET is_active=0 WHERE id=?", (session_id,))
    db.commit()

def get_plan_features(plan_id):
    db = get_db_conn()
    row = db.execute("SELECT features FROM plans WHERE id=?", (plan_id,)).fetchone()
    return json.loads(row["features"] or '{}') if row else {}

def get_school_plan(school_id):
    db = get_db_conn()
    s = db.execute("SELECT * FROM schools WHERE id=?", (school_id,)).fetchone()
    if not s:
        return None, 0, {}, True  # expired default
    
    # Check trial status
    is_expired = False
    is_hard_limited = s["hard_limit_hit"] == 1
    
    if s["is_trial"] == 1 and s["trial_end"]:
        try:
            trial_end = datetime.strptime(s["trial_end"], "%Y-%m-%d")
            if datetime.now() > trial_end:
                is_expired = True
        except:
            pass
    
    # If upgraded, use plan features
    if s["is_upgraded"] == 1 and s["plan_id"]:
        p = db.execute("SELECT * FROM plans WHERE id=?", (s["plan_id"],)).fetchone()
        if p:
            features = json.loads(p["features"] or '{}')
            # Force disable photos if not explicitly in paid plan
            if s["plan_id"] == "plan_basic":
                features["photos"] = False
            return p, s["max_students"], features, is_expired
    
    # Trial mode - limited features
    trial_features = {
        "students": True,
        "attendance": True,
        "care_logs": True,
        "reports": False,
        "photos": False,  # Locked during trial
        "whatsapp": False,
        "multi_teacher": False,
        "max_teachers": 1,
        "broadcast": True
    }
    
    # Post-trial expired with 8/10 rule
    if is_expired and not is_hard_limited:
        # Count active students
        active_count = db.execute("SELECT COUNT(*) FROM students WHERE school_id=? AND is_active=1", (school_id,)).fetchone()[0]
        if active_count >= 8:
            is_hard_limited = True
    
    return None, s["max_students"], trial_features, is_expired or is_hard_limited

def check_trial_limits(school_id):
    """Check if school has hit trial limits (11 students or 14 days)"""
    db = get_db_conn()
    s = db.execute("SELECT * FROM schools WHERE id=?", (school_id,)).fetchone()
    if not s or s["is_upgraded"] == 1:
        return {"can_add": True, "reason": None, "students": 0, "max": 9999}
    
    student_count = db.execute("SELECT COUNT(*) FROM students WHERE school_id=? AND is_active=1", (school_id,)).fetchone()[0]
    max_students = s["max_students"]
    
    # Check hard limit (11 students during trial)
    if student_count >= 11 and s["is_trial"] == 1:
        db.execute("UPDATE schools SET hard_limit_hit=1 WHERE id=?", (school_id,))
        db.commit()
        return {"can_add": False, "reason": "trial_student_limit", "students": student_count, "max": 11}
    
    # Check trial expiration
    if s["trial_end"]:
        try:
            trial_end = datetime.strptime(s["trial_end"], "%Y-%m-%d")
            if datetime.now() > trial_end:
                # Post-trial: 8/10 rule
                if student_count >= 8:
                    db.execute("UPDATE schools SET hard_limit_hit=1 WHERE id=?", (school_id,))
                    db.commit()
                    return {"can_add": False, "reason": "post_trial_limit", "students": student_count, "max": 10}
                max_students = 10  # Allow up to 10 post-trial but lock at 8
        except:
            pass
    
    return {"can_add": student_count < max_students, "reason": None, "students": student_count, "max": max_students}

# =================== SESSION ===================
if "auth" not in st.session_state:
    st.session_state.auth = {
        "logged_in": False, "role": None, "school_id": None,
        "user_id": None, "name": None, "session_id": None
    }
if "show_teacher_reg" not in st.session_state:
    st.session_state.show_teacher_reg = False
if "payment_success" not in st.session_state:
    st.session_state.payment_success = None
if "reg_success" not in st.session_state:
    st.session_state.reg_success = None

def require_auth(allowed_roles):
    if not st.session_state.auth["logged_in"]:
        st.warning("Please log in first.")
        st.stop()
    if st.session_state.auth["role"] not in allowed_roles:
        st.error("Unauthorized access.")
        st.stop()
    if st.session_state.auth["role"] == "teacher" and st.session_state.auth.get("session_id"):
        if not is_session_active(st.session_state.auth["session_id"]):
            st.error("Session logged out from another device.")
            st.session_state.auth = {
                "logged_in": False, "role": None, "school_id": None,
                "user_id": None, "name": None, "session_id": None
            }
            st.rerun()

# =================== LANDING ===================
def landing_page():
    st.markdown('<p class="main-header">🏫 SchoolOS Pro</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Complete Daycare & Preschool Management</p>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        tab_login, tab_reg = st.tabs(["🔐 Login", "📝 Register School"])
        
        with tab_login:
            st.markdown('<div class="login-box">', unsafe_allow_html=True)
            role = st.radio("Login as", ["School Head", "Teacher", "Admin"], horizontal=True)
            
            if role == "Admin":
                user = st.text_input("Admin ID", value="admin")
                pw = st.text_input("Password", type="password")
                if st.button("Login", type="primary", use_container_width=True):
                    db = get_db_conn()
                    h = db.execute("SELECT value FROM admin_config WHERE key='admin_password_hash'").fetchone()
                    if h and check_pw(pw, h[0]):
                        st.session_state.auth = {
                            "logged_in": True, "role": "admin", "school_id": None,
                            "user_id": "admin", "name": "Admin", "session_id": None
                        }
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
            
            elif role == "School Head":
                school_id = st.text_input("School ID", placeholder="e.g., ABC12345")
                pw = st.text_input("Password", type="password")
                if st.button("Login", type="primary", use_container_width=True):
                    db = get_db_conn()
                    s = db.execute("SELECT * FROM schools WHERE id=? AND is_active=1", (school_id,)).fetchone()
                    if not s:
                        st.error("School not found")
                    elif not check_pw(pw, s["pass"]):
                        st.error("Invalid password")
                    else:
                        # Check if trial expired and needs upgrade
                        limits = check_trial_limits(school_id)
                        st.session_state.auth = {
                            "logged_in": True, "role": "head", "school_id": school_id,
                            "user_id": school_id, "name": s["name"], "session_id": None
                        }
                        st.rerun()
            
            elif role == "Teacher":
                school_id = st.text_input("School ID", key="t_school", placeholder="e.g., ABC12345")
                phone = st.text_input("Your Phone", key="t_phone")
                pw = st.text_input("Password", type="password", key="t_pw")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Login", type="primary", use_container_width=True):
                        db = get_db_conn()
                        t = db.execute("""
                            SELECT * FROM teachers WHERE school_id=? AND phone=? AND is_active=1
                        """, (school_id, phone)).fetchone()
                        if not t:
                            st.error("Teacher not found")
                        elif not check_pw(pw, t["pass"]):
                            st.error("Invalid password")
                        else:
                            sess = manage_teacher_session(t["id"], school_id)
                            st.session_state.auth = {
                                "logged_in": True, "role": t["role"], "school_id": school_id,
                                "user_id": t["id"], "name": t["name"], "session_id": sess
                            }
                            st.rerun()
                with c2:
                    if st.button("📝 New Teacher? Register", use_container_width=True):
                        st.session_state.show_teacher_reg = True
                        st.rerun()
                
                if st.session_state.show_teacher_reg:
                    st.divider()
                    with st.form("teacher_reg"):
                        reg_school = st.text_input("School ID")
                        reg_name = st.text_input("Full Name")
                        reg_phone = st.text_input("Your Phone")
                        reg_pw = st.text_input("Password", type="password")
                        reg_pw2 = st.text_input("Confirm Password", type="password")
                        if st.form_submit_button("Register"):
                            if not all([reg_school, reg_name, reg_phone, reg_pw]):
                                st.error("Fill all fields")
                            elif reg_pw != reg_pw2:
                                st.error("Passwords don't match")
                            elif len(reg_pw) < 6:
                                st.error("Too short")
                            else:
                                db = get_db_conn()
                                if not db.execute("SELECT 1 FROM schools WHERE id=? AND is_active=1", (reg_school,)).fetchone():
                                    st.error("Invalid School ID")
                                elif db.execute("SELECT 1 FROM teachers WHERE phone=?", (reg_phone,)).fetchone():
                                    st.error("Phone exists")
                                else:
                                    db.execute("""
                                        INSERT INTO teachers (id, school_id, name, phone, pass)
                                        VALUES (?,?,?,?,?)
                                    """, (gen_id(), reg_school, sanitize(reg_name), sanitize(reg_phone), hash_pw(reg_pw)))
                                    db.commit()
                                    st.success("Registered! You can log in now.")
                                    st.session_state.show_teacher_reg = False
                                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        
        with tab_reg:
            school_registration_flow()

# =================== SCHOOL REGISTRATION ===================
def school_registration_flow():
    st.subheader("🎉 Start Your 14-Day Free Trial")
    st.markdown("""
    <div style="background: #e8f5e9; padding: 15px; border-radius: 10px; margin: 15px 0;">
        <h4>✨ Trial Includes:</h4>
        <ul>
            <li>Up to <strong>10 students</strong> completely FREE</li>
            <li><strong>14 days</strong> full access to core features</li>
            <li>Attendance, Care Logs, Classes & Programs</li>
            <li>Basic reporting</li>
        </ul>
        <p><small>📸 Photo Gallery unlocks after upgrade | 🚫 Hard limit at 11 students during trial</small></p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("trial_reg"):
        c1, c2 = st.columns(2)
        with c1:
            s_name = st.text_input("School Name *", placeholder="Little Angels Preschool")
            s_email = st.text_input("Email *", placeholder="school@email.com")
        with c2:
            s_phone = st.text_input("Phone Number *", placeholder="9876543210")
            s_pass = st.text_input("Create Password *", type="password")
            s_pass2 = st.text_input("Confirm Password *", type="password")
        
        st.info("""
        **Trial Terms:**
        - 14 days from registration date
        - Maximum 10 students (11th student triggers upgrade requirement)
        - After trial: Can keep 8 students active, need upgrade for more
        - Photo Gallery available only in paid plans
        """)
        
        if st.form_submit_button("🚀 Start Free Trial", use_container_width=True):
            if not all([s_name, s_email, s_phone, s_pass]):
                st.error("Fill all required fields")
            elif s_pass != s_pass2:
                st.error("Passwords don't match")
            elif len(s_pass) < 6:
                st.error("Password too short")
            elif not s_phone.isdigit() or len(s_phone) < 10:
                st.error("Enter valid phone number")
            else:
                db = get_db_conn()
                
                # Generate unique school ID
                school_id = gen_school_id()
                while db.execute("SELECT 1 FROM schools WHERE id=?", (school_id,)).fetchone():
                    school_id = gen_school_id()
                
                trial_start = datetime.now()
                trial_end = trial_start + timedelta(days=14)
                
                db.execute("""
                    INSERT INTO schools (id, name, pass, email, phone, plan_id, max_students, 
                                       trial_start, trial_end, is_trial, is_active, is_upgraded)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (school_id, sanitize(s_name), hash_pw(s_pass), sanitize(s_email), 
                      sanitize(s_phone), None, 10,
                      trial_start.isoformat(), trial_end.strftime("%Y-%m-%d"), 1, 1, 0))
                db.commit()
                
                st.session_state.reg_success = {
                    "school_id": school_id,
                    "name": s_name,
                    "trial_end": trial_end.strftime("%Y-%m-%d"),
                    "phone": s_phone
                }
                st.rerun()
    
    if st.session_state.reg_success:
        s = st.session_state.reg_success
        st.balloons()
        st.success(f"""
        🎉 Trial Started Successfully!
        
        **School Name:** {s['name']}
        **Your School ID:** `{s['school_id']}`
        **Trial Ends:** {s['trial_end']}
        **Phone:** {s['phone']}
        
        **Important:** 
        - Save your School ID: `{s['school_id']}`
        - You can add up to 10 students
        - 11th student will require upgrade
        - Photo Gallery unlocks after upgrade
        
        Login with School ID and your password to get started!
        """)
        if st.button("Go to Login"):
            del st.session_state.reg_success
            st.rerun()

# =================== UPGRADE FLOW ===================
def show_upgrade_prompt(sid, reason="trial_expired"):
    db = get_db_conn()
    plans = db.execute("SELECT * FROM plans WHERE is_active=1 ORDER BY sort_order").fetchall()
    
    st.markdown(f"""
    <div class="{'trial-expired' if reason == 'trial_expired' else 'upgrade-banner'}">
        <h3>⚡ Upgrade Required</h3>
        <p>{'Your 14-day trial has ended.' if reason == 'trial_expired' else 'You have reached the maximum limit.'}</p>
        <p>{'To continue using SchoolOS Pro with all features, please choose a plan below.' if reason == 'trial_expired' else 'Please upgrade to add more students and unlock all features.'}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.subheader("Choose a Plan")
    cols = st.columns(len(plans))
    
    for idx, p in enumerate(plans):
        features = json.loads(p["features"] or '{}')
        with cols[idx]:
            popular_class = "plan-card plan-popular" if p["is_popular"] else "plan-card"
            st.markdown(f'<div class="{popular_class}">', unsafe_allow_html=True)
            if p["is_popular"]:
                st.markdown("🔥 **POPULAR**")
            st.markdown(f"### {p['name']}")
            st.markdown(f"<h2>₹{p['yearly_price']:,}<small>/yr</small></h2>", unsafe_allow_html=True)
            st.write(f"**{p['max_students']}** Students")
            if p["extra_student_price"] > 0:
                st.caption(f"+₹{p['extra_student_price']}/extra")
            st.divider()
            for feat, enabled in features.items():
                label = feat.replace("_", " ").title()
                if enabled:
                    st.markdown(f"<span class='feature-yes'>✅ {label}</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span class='feature-no'>❌ {label}</span>", unsafe_allow_html=True)
            
            if st.button(f"Upgrade to {p['name']}", key=f"upgrade_{p['id']}", use_container_width=True):
                process_upgrade(sid, p)
            st.markdown('</div>', unsafe_allow_html=True)

def process_upgrade(school_id, plan):
    db = get_db_conn()
    expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    
    # Update school to upgraded status
    db.execute("""
        UPDATE schools SET 
            plan_id=?, max_students=?, is_trial=0, is_upgraded=1, 
            hard_limit_hit=0, expiry=?
        WHERE id=?
    """, (plan['id'], plan['max_students'], expiry, school_id))
    
    # Create subscription record
    sub_id = gen_id()
    db.execute("""
        INSERT INTO subscriptions (id, school_id, plan_id, amount_paid, payment_status, start_date, end_date)
        VALUES (?,?,?,?,?,?,?)
    """, (sub_id, school_id, plan['id'], plan['yearly_price'], 'Paid',
          datetime.now().isoformat(), expiry))
    
    db.commit()
    
    st.success(f"🎉 Upgraded to {plan['name']}! You now have access to {plan['max_students']} students and all features including Photo Gallery.")
    st.balloons()
    st.rerun()

# =================== ADMIN ===================
def admin_page():
    require_auth(["admin"])
    db = get_db_conn()
    st.title("👑 Admin Command Center")
    
    with st.sidebar:
        st.markdown("### System")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.auth = {
                "logged_in": False, "role": None, "school_id": None,
                "user_id": None, "name": None, "session_id": None
            }
            st.rerun()
        st.divider()
        ts = db.execute("SELECT COUNT(*) FROM schools").fetchone()[0]
        active = db.execute("SELECT COUNT(*) FROM schools WHERE is_active=1").fetchone()[0]
        trial = db.execute("SELECT COUNT(*) FROM schools WHERE is_trial=1").fetchone()[0]
        upgraded = db.execute("SELECT COUNT(*) FROM schools WHERE is_upgraded=1").fetchone()[0]
        rev = db.execute("SELECT COALESCE(SUM(amount_paid),0) FROM subscriptions WHERE payment_status='Paid'").fetchone()[0]
        st.metric("Total Schools", ts)
        st.metric("Active", active)
        st.metric("In Trial", trial)
        st.metric("Upgraded", upgraded)
        st.metric("Revenue", f"₹{rev:,}")
    
    t1, t2, t3 = st.tabs(["💰 Revenue & Schools", "📋 Plans", "⚙️ Settings"])
    
    with t1:
        st.header("Revenue Dashboard")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Revenue", f"₹{rev:,}")
        c2.metric("This Month", f"₹{db.execute('SELECT COALESCE(SUM(amount_paid),0) FROM subscriptions WHERE payment_status=? AND strftime(?,created_at)=?', ('Paid','%Y-%m',datetime.now().strftime('%Y-%m'))).fetchone()[0]:,}")
        c3.metric("Paid Subs", db.execute("SELECT COUNT(*) FROM subscriptions WHERE payment_status='Paid'").fetchone()[0])
        c4.metric("Pending", db.execute("SELECT COUNT(*) FROM subscriptions WHERE payment_status='Pending'").fetchone()[0])
        
        st.divider()
        st.subheader("All Schools")
        schools = db.execute("""
            SELECT s.*, p.name as plan_name 
            FROM schools s 
            LEFT JOIN plans p ON s.plan_id = p.id
            ORDER BY s.created_at DESC
        """).fetchall()
        
        if schools:
            data = []
            for s in schools:
                status = "🟢 Active" if s['is_upgraded'] else ("🟡 Trial" if s['is_trial'] else "🔴 Expired")
                data.append({
                    "School": s['name'], "ID": s['id'], "Phone": s['phone'], "Email": s['email'],
                    "Status": status, "Plan": s['plan_name'] or "Trial",
                    "Students": s['max_students'], "Trial Ends": s['trial_end'] or "-",
                    "Created": s['created_at'][:10] if s['created_at'] else "-"
                })
            st.dataframe(data, use_container_width=True, hide_index=True)
        else:
            st.info("No schools yet")
        
        st.subheader("Subscriptions")
        subs = db.execute("""
            SELECT s.id as school_id, s.name, s.email, s.is_active, s.created_at,
                   p.name as plan_name, p.yearly_price,
                   sub.amount_paid, sub.payment_status, sub.payment_id, sub.start_date, sub.end_date
            FROM subscriptions sub
            JOIN schools s ON sub.school_id = s.id
            JOIN plans p ON sub.plan_id = p.id
            ORDER BY sub.created_at DESC
        """).fetchall()
        
        if subs:
            data = []
            for sub in subs:
                data.append({
                    "School": sub['name'], "School ID": sub['school_id'], "Email": sub['email'],
                    "Plan": sub['plan_name'], "Amount": f"₹{sub['amount_paid']:,}",
                    "Status": sub['payment_status'], "Payment ID": sub['payment_id'] or "-",
                    "Start": sub['start_date'][:10] if sub['start_date'] else "-",
                    "End": sub['end_date'][:10] if sub['end_date'] else "-"
                })
            st.dataframe(data, use_container_width=True, hide_index=True)
    
    with t2:
        st.header("Plan Configuration")
        with st.expander("➕ Create Plan"):
            with st.form("create_plan"):
                pname = st.text_input("Plan Name *")
                pstudents = st.number_input("Max Students", min_value=1, value=30)
                pprice = st.number_input("Yearly Price (₹)", min_value=0, value=2999, step=500)
                pextra = st.number_input("Extra Student Price", min_value=0, value=0)
                f_att = st.checkbox("Attendance", value=True)
                f_care = st.checkbox("Care Logs", value=True)
                f_rep = st.checkbox("Reports")
                f_photo = st.checkbox("Photo Gallery")
                f_wa = st.checkbox("WhatsApp")
                f_multi = st.checkbox("Multi-Teacher")
                f_maxt = st.number_input("Max Teachers", min_value=1, value=1)
                f_bc = st.checkbox("Broadcast", value=True)
                is_pop = st.checkbox("Popular")
                if st.form_submit_button("Save Plan"):
                    features = json.dumps({
                        "attendance": f_att, "care_logs": f_care, "reports": f_rep,
                        "photos": f_photo, "whatsapp": f_wa, "multi_teacher": f_multi,
                        "max_teachers": f_maxt, "broadcast": f_bc
                    })
                    db.execute("""
                        INSERT INTO plans (id, name, max_students, yearly_price, extra_student_price, features, is_active, is_popular)
                        VALUES (?,?,?,?,?,?,1,?)
                    """, (gen_id(), sanitize(pname), pstudents, pprice, pextra, features, 1 if is_pop else 0))
                    db.commit()
                    st.success("Plan created!")
                    st.rerun()
        
        st.subheader("Manage Plans")
        plans = db.execute("SELECT * FROM plans ORDER BY sort_order").fetchall()
        for p in plans:
            features = json.loads(p["features"] or '{}')
            with st.expander(f"{'🔥 ' if p['is_popular'] else ''}{p['name']} — ₹{p['yearly_price']:,}"):
                c1, c2 = st.columns([3,1])
                with c1:
                    st.write(f"Students: {p['max_students']} | Extra: ₹{p['extra_student_price']}")
                    st.write("Features: " + ", ".join([k.replace("_"," ").title() for k,v in features.items() if v and isinstance(v, bool)]))
                with c2:
                    if st.button("Deactivate", key=f"del_plan_{p['id']}"):
                        db.execute("UPDATE plans SET is_active=0 WHERE id=?", (p['id'],))
                        db.commit()
                        st.rerun()
    
    with t3:
        st.subheader("Admin Password")
        with st.form("admin_pw"):
            old = st.text_input("Current", type="password")
            new = st.text_input("New", type="password")
            conf = st.text_input("Confirm", type="password")
            if st.form_submit_button("Update"):
                cur = db.execute("SELECT value FROM admin_config WHERE key='admin_password_hash'").fetchone()[0]
                if not check_pw(old, cur):
                    st.error("Wrong")
                elif new != conf:
                    st.error("Mismatch")
                elif len(new) < 8:
                    st.error("Too short")
                else:
                    db.execute("UPDATE admin_config SET value=? WHERE key='admin_password_hash'", (hash_pw(new),))
                    db.commit()
                    st.success("Updated")

# =================== SCHOOL SHARED ===================
def school_sidebar():
    auth = st.session_state.auth
    sid = auth["school_id"]
    plan, max_students, features, is_expired = get_school_plan(sid)
    
    with st.sidebar:
        st.markdown(f"### {auth['name']}")
        st.caption(f"Role: {auth['role'].upper()}")
        
        # Show trial/upgrade status
        db = get_db_conn()
        s = db.execute("SELECT * FROM schools WHERE id=?", (sid,)).fetchone()
        
        if s["is_trial"] == 1 and not s["is_upgraded"]:
            try:
                trial_end = datetime.strptime(s["trial_end"], "%Y-%m-%d")
                days_left = (trial_end - datetime.now()).days
                if days_left > 0:
                    st.markdown(f"""
                    <div class="trial-box">
                        <strong>🎁 Free Trial</strong><br>
                        {days_left} days remaining<br>
                        Max 10 students (11th requires upgrade)
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div class="trial-box trial-expired">
                        <strong>⏰ Trial Expired</strong><br>
                        Upgrade to continue
                    </div>
                    """, unsafe_allow_html=True)
            except:
                pass
        elif s["is_upgraded"] == 1:
            st.caption(f"Plan: {plan['name'] if plan else 'Basic'}")
        
        st.divider()
        
        st.markdown("**Your School ID**")
        st.markdown(f"<div class='school-id-box'>{sid}</div>", unsafe_allow_html=True)
        st.caption("Share this ID with teachers to register")
        st.divider()
        
        menu_items = ["📊 Dashboard"]
        if auth["role"] == "head":
            menu_items.append("👨‍🏫 Teachers")
        menu_items.extend(["🏫 Classes & Programs", "👶 Students", "📋 Attendance"])
        if features.get("reports"):
            menu_items.append("📊 Reports")
        menu_items.append("🧸 Care Logs")
        if features.get("photos") and s["is_upgraded"] == 1:
            menu_items.append("🖼️ Photo Gallery")
        elif s["is_upgraded"] == 0:
            menu_items.append("🔒 Photo Gallery (Upgrade)")
        
        menu = st.radio("Menu", menu_items)
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            if auth.get("session_id"):
                logout_teacher_session(auth["session_id"])
            st.session_state.auth = {
                "logged_in": False, "role": None, "school_id": None,
                "user_id": None, "name": None, "session_id": None
            }
            st.rerun()
    return menu, features, is_expired

# =================== DASHBOARD ===================
def show_dashboard(sid, features, is_expired):
    db = get_db_conn()
    st.header("📊 Dashboard")
    
    # Check limits and show warnings
    limits = check_trial_limits(sid)
    s = db.execute("SELECT * FROM schools WHERE id=?", (sid,)).fetchone()
    
    # Show upgrade prompt if expired or limited
    if is_expired or not limits["can_add"]:
        if s["is_trial"] == 1 and limits.get("reason") == "trial_student_limit":
            show_upgrade_prompt(sid, "student_limit")
        elif s["is_trial"] == 1 and datetime.now() > datetime.strptime(s["trial_end"], "%Y-%m-%d"):
            show_upgrade_prompt(sid, "trial_expired")
        elif limits.get("reason") == "post_trial_limit":
            show_upgrade_prompt(sid, "post_trial_limit")
        return  # Stop showing dashboard if upgrade required
    
    # Show warning if approaching limits
    if limits["students"] >= 8 and s["is_trial"] == 1:
        st.warning(f"⚠️ You have {limits['students']}/10 students. Adding 2 more will require upgrade (11th student forces upgrade).")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Students", db.execute("SELECT COUNT(*) FROM students WHERE school_id=? AND is_active=1", (sid,)).fetchone()[0])
    c2.metric("Teachers", db.execute("SELECT COUNT(*) FROM teachers WHERE school_id=? AND is_active=1", (sid,)).fetchone()[0])
    c3.metric("Classes", db.execute("SELECT COUNT(*) FROM classes WHERE school_id=?", (sid,)).fetchone()[0])
    c4.metric("Today", db.execute("""
        SELECT COUNT(*) FROM attendance WHERE date=? AND class_id IN (SELECT id FROM classes WHERE school_id=?)
    """, (date.today().isoformat(), sid)).fetchone()[0])

# =================== TEACHERS ===================
def show_teachers(sid, features):
    require_auth(["head"])
    db = get_db_conn()
    st.header("👨‍🏫 Teachers")
    
    max_t = features.get("max_teachers", 1)
    curr = db.execute("SELECT COUNT(*) FROM teachers WHERE school_id=? AND is_active=1", (sid,)).fetchone()[0]
    st.caption(f"Limit: {curr}/{max_t}")
    
    if curr < max_t:
        with st.expander("➕ Add Teacher"):
            with st.form("add_teacher"):
                tname = st.text_input("Name *")
                tphone = st.text_input("Phone *")
                tpw = st.text_input("Password *", type="password")
                if st.form_submit_button("Add"):
                    if not all([tname, tphone, tpw]):
                        st.error("Fill all")
                    elif db.execute("SELECT 1 FROM teachers WHERE phone=?", (tphone,)).fetchone():
                        st.error("Phone exists")
                    else:
                        db.execute("INSERT INTO teachers (id, school_id, name, phone, pass) VALUES (?,?,?,?,?)",
                                   (gen_id(), sid, sanitize(tname), sanitize(tphone), hash_pw(tpw)))
                        db.commit()
                        st.success("Added!")
                        st.rerun()
    else:
        st.warning("Teacher limit reached. Upgrade plan.")
    
    teachers = db.execute("SELECT * FROM teachers WHERE school_id=? AND is_active=1", (sid,)).fetchall()
    for t in teachers:
        cols = st.columns([3,2,2,1])
        cols[0].write(f"**{t['name']}**")
        cols[1].write(f"📞 {t['phone']}")
        cols[2].write(t['role'])
        if cols[3].button("🗑️", key=f"rmt_{t['id']}"):
            db.execute("UPDATE teachers SET is_active=0 WHERE id=?", (t['id'],))
            db.commit()
            st.rerun()

# =================== CLASSES ===================
def show_classes_programs(sid):
    db = get_db_conn()
    st.header("🏫 Classes & Programs")
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("📚 Classes")
        with st.form("add_class"):
            cname = st.text_input("Class Name *", placeholder="Nursery...")
            csec = st.text_input("Section", placeholder="A...")
            if st.form_submit_button("Add"):
                if cname:
                    db.execute("INSERT INTO classes (id, class_name, section, school_id) VALUES (?,?,?,?)",
                               (gen_id(), sanitize(cname), sanitize(csec), sid))
                    db.commit()
                    st.success("Added!")
                else:
                    st.error("Name required")
        
        classes = db.execute("SELECT * FROM classes WHERE school_id=? AND is_active=1", (sid,)).fetchall()
        for c in classes:
            sc = db.execute("SELECT COUNT(*) FROM students WHERE class_id=? AND is_active=1", (c['id'],)).fetchone()[0]
            cols = st.columns([3,1,1])
            cols[0].write(f"**{c['class_name']} {c['section'] or ''}** ({sc})")
            if cols[2].button("🗑️", key=f"delc_{c['id']}"):
                if sc == 0:
                    db.execute("DELETE FROM classes WHERE id=?", (c['id'],))
                    db.commit()
                    st.rerun()
                else:
                    st.error("Has students!")
    
    with c2:
        st.subheader("📋 Programs")
        classes = db.execute("SELECT * FROM classes WHERE school_id=? AND is_active=1", (sid,)).fetchall()
        if classes:
            copts = {f"{c['class_name']} {c['section'] or ''}".strip(): c['id'] for c in classes}
            with st.form("add_program"):
                pname = st.text_input("Program Name *")
                pc = st.selectbox("Class *", list(copts.keys()))
                if st.form_submit_button("Add"):
                    if pname:
                        db.execute("INSERT INTO programs (id, program_name, class_id, school_id) VALUES (?,?,?,?)",
                                   (gen_id(), sanitize(pname), copts[pc], sid))
                        db.commit()
                        st.success("Added!")
                    else:
                        st.error("Name required")
            
            programs = db.execute("""
                SELECT p.*, c.class_name, c.section 
                FROM programs p JOIN classes c ON p.class_id=c.id 
                WHERE p.school_id=?
            """, (sid,)).fetchall()
            for p in programs:
                cols = st.columns([3,2,1])
                cols[0].write(f"**{p['program_name']}**")
                cols[1].write(f"→ {p['class_name']} {p['section'] or ''}")
                if cols[2].button("🗑️", key=f"delp_{p['id']}"):
                    db.execute("DELETE FROM programs WHERE id=?", (p['id'],))
                    db.commit()
                    st.rerun()
        else:
            st.info("Create classes first")

# =================== STUDENTS ===================
def show_students(sid):
    db = get_db_conn()
    st.header("👶 Students")
    
    # Check trial limits first
    limits = check_trial_limits(sid)
    s = db.execute("SELECT * FROM schools WHERE id=?", (sid,)).fetchone()
    
    # Show upgrade prompt if cannot add more
    if not limits["can_add"]:
        if limits["reason"] == "trial_student_limit":
            st.error("🚫 You have reached the 11 student hard limit during trial. Upgrade required to add more.")
            show_upgrade_prompt(sid, "student_limit")
        elif limits["reason"] == "post_trial_limit":
            st.error("🚫 Trial ended and you have 8+ active students. Upgrade required to add more.")
            show_upgrade_prompt(sid, "post_trial_limit")
        return
    
    # Show warnings
    if limits["students"] >= 10 and s["is_trial"] == 1:
        st.warning("⚠️ You have 10 students. The next student (11th) will require an upgrade!")
    elif limits["students"] >= 8 and s["is_trial"] == 1:
        st.info(f"ℹ️ You have {limits['students']}/10 students in trial mode.")
    
    programs = db.execute("""
        SELECT p.*, c.class_name, c.section 
        FROM programs p JOIN classes c ON p.class_id=c.id 
        WHERE p.school_id=?
    """, (sid,)).fetchall()
    prog_dict = {f"{p['program_name']} → {p['class_name']} {p['section'] or ''}": p for p in programs}
    
    st.caption(f"Students: {limits['students']}/{limits['max']}")
    
    t1, t2 = st.tabs(["➕ Add", "📋 List"])
    with t1:
        if not programs:
            st.warning("Create programs first")
        else:
            with st.form("add_student", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Student Name *")
                    mother = st.text_input("Mother's Name")
                    father = st.text_input("Father's Name")
                    dob = st.date_input("Date of Birth", value=date(2020,1,1))
                    blood = st.selectbox("Blood Group", ["A+","A-","B+","B-","AB+","AB-","O+","O-","Unknown"])
                    allergy = st.text_input("Allergy / Medical Notes", placeholder="Any allergies")
                with c2:
                    prog = st.selectbox("Program Enrolled *", list(prog_dict.keys()))
                    phone = st.text_input("Phone Number")
                    email = st.text_input("Email ID")
                    guardian = st.text_input("Guardian Name")
                    likes = st.text_area("Likes / Interests")
                    dislikes = st.text_area("Dislikes")
                photo = st.file_uploader("Profile Photo", type=["jpg","jpeg","png"])
                if photo:
                    st.image(photo, width=150)
                
                # Check limit again on submit
                current_limits = check_trial_limits(sid)
                if st.form_submit_button("Register Student"):
                    if not name or not prog:
                        st.error("Name and Program required")
                    elif not current_limits["can_add"]:
                        st.error("Student limit reached! Please upgrade your plan.")
                        st.rerun()
                    else:
                        p = prog_dict[prog]
                        age = calc_age(dob.isoformat())
                        ph = compress_image(photo)
                        db.execute("""
                            INSERT INTO students (id, name, mother_name, father_name, dob, age, blood_group,
                             allergy, program_id, class_id, phone, email, guardian_name, likes, dislikes,
                             school_id, is_active, profile_photo)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (gen_id(), sanitize(name), sanitize(mother), sanitize(father), dob.isoformat(), age, blood,
                              sanitize(allergy), p['id'], p['class_id'], sanitize(phone), sanitize(email), sanitize(guardian),
                              sanitize(likes), sanitize(dislikes), sid, 1, ph))
                        db.commit()
                        
                        # Check if this addition hit the limit
                        new_limits = check_trial_limits(sid)
                        if not new_limits["can_add"]:
                            st.warning("🎉 Student added! You've reached the limit. Upgrade now for unlimited access.")
                        else:
                            st.success(f"✅ {name} registered!")
                            st.balloons()
    
    with t2:
        students = db.execute("""
            SELECT s.*, p.program_name, c.class_name, c.section
            FROM students s
            LEFT JOIN programs p ON s.program_id=p.id
            LEFT JOIN classes c ON s.class_id=c.id
            WHERE s.school_id=? AND s.is_active=1
            ORDER BY s.name
        """, (sid,)).fetchall()
        for s in students:
            with st.expander(f"👤 {s['name']} | {s['program_name'] or '-'} | Age: {s['age'] or '?'} | {s['blood_group'] or '-'} "):
                c1, c2 = st.columns([1,3])
                with c1:
                    if s['profile_photo']:
                        try:
                            st.image(base64.b64decode(s['profile_photo']), width=140)
                        except:
                            st.write("📷")
                    else:
                        st.write("📷 No photo")
                with c2:
                    st.write(f"**Mother:** {s['mother_name'] or '-'} | **Father:** {s['father_name'] or '-'}")
                    st.write(f"**DOB:** {s['dob'] or '-'} | **Blood:** {s['blood_group'] or '-'}")
                    st.write(f"**Allergy:** {s['allergy'] or 'None'}")
                    st.write(f"**Phone:** {s['phone'] or '-'} | **Email:** {s['email'] or '-'}")
                    st.write(f"**Guardian:** {s['guardian_name'] or '-'} | **Class:** {s['class_name'] or '-'} {s['section'] or ''}")
                    st.write(f"**Likes:** {s['likes'] or '-'} | **Dislikes:** {s['dislikes'] or '-'}")
                    if st.button("Remove", key=f"rms_{s['id']}"):
                        db.execute("UPDATE students SET is_active=0 WHERE id=?", (s['id'],))
                        db.commit()
                        st.rerun()

# =================== ATTENDANCE ===================
def show_attendance(sid):
    db = get_db_conn()
    st.header("📋 Attendance")
    classes = db.execute("SELECT * FROM classes WHERE school_id=? AND is_active=1", (sid,)).fetchall()
    if not classes:
        st.warning("Create classes first")
        return
    copts = {f"{c['class_name']} {c['section'] or ''}".strip(): c['id'] for c in classes}
    
    t1, t2 = st.tabs(["Mark", "View"])
    with t1:
        cls = st.selectbox("Class", list(copts.keys()), key="acls")
        dt = st.date_input("Date", value=date.today(), key="adt")
        students = db.execute("""
            SELECT id, name FROM students WHERE class_id=? AND school_id=? AND is_active=1 ORDER BY name
        """, (copts[cls], sid)).fetchall()
        if not students:
            st.info("No students")
            return
        
        existing = {r['student_id']: r for r in db.execute("""
            SELECT * FROM attendance WHERE date=? AND class_id=?
        """, (dt.isoformat(), copts[cls])).fetchall()}
        
        with st.form("mark_att"):
            records = []
            for s in students:
                cols = st.columns([2,3,2,2,3])
                with cols[0]:
                    st.write(f"**{s['name']}**")
                with cols[1]:
                    sts = ["Present","Absent","Late","Half Day"]
                    d = 0
                    if s['id'] in existing:
                        try:
                            d = sts.index(existing[s['id']]['status'])
                        except:
                            pass
                    status = st.radio(f"st_{s['id']}", sts, index=d, horizontal=True, label_visibility="collapsed", key=f"st_{s['id']}_{dt}")
                with cols[2]:
                    di = None
                    if s['id'] in existing and existing[s['id']]['in_time']:
                        try:
                            h,m = map(int, existing[s['id']]['in_time'].split(":"))
                            di = datetime.strptime(f"{h}:{m}", "%H:%M").time()
                        except:
                            pass
                    in_t = st.time_input("In", value=di, key=f"in_{s['id']}_{dt}", label_visibility="collapsed")
                with cols[3]:
                    do = None
                    if s['id'] in existing and existing[s['id']]['out_time']:
                        try:
                            h,m = map(int, existing[s['id']]['out_time'].split(":"))
                            do = datetime.strptime(f"{h}:{m}", "%H:%M").time()
                        except:
                            pass
                    out_t = st.time_input("Out", value=do, key=f"out_{s['id']}_{dt}", label_visibility="collapsed")
                with cols[4]:
                    note = st.text_input("Note", value=existing[s['id']]['notes'] if s['id'] in existing else "",
                                       key=f"nt_{s['id']}_{dt}", label_visibility="collapsed")
                records.append((s['id'], status, in_t, out_t, note))
                st.divider()
            
            if st.form_submit_button("Save Attendance", use_container_width=True):
                db.execute("DELETE FROM attendance WHERE date=? AND class_id=?", (dt.isoformat(), copts[cls]))
                for rid, stt, it, ot, nt in records:
                    db.execute("""
                        INSERT INTO attendance (student_id, class_id, date, status, in_time, out_time, notes, marked_by)
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (rid, copts[cls], dt.isoformat(), stt, str(it) if it else None, str(ot) if ot else None, nt, sid))
                db.commit()
                st.success(f"Saved {len(records)} records!")
                st.balloons()
    
    with t2:
        vdt = st.date_input("Date", value=date.today(), key="vdt")
        vcls = st.selectbox("Class", list(copts.keys()), key="vcls")
        recs = db.execute("""
            SELECT a.*, s.name FROM attendance a
            JOIN students s ON a.student_id=s.id
            WHERE a.date=? AND a.class_id=? ORDER BY s.name
        """, (vdt.isoformat(), copts[vcls])).fetchall()
        if recs:
            for r in recs:
                em = {"Present":"✅","Absent":"❌","Late":"⏰","Half Day":"⚠️"}.get(r['status'],"⬜")
                c1,c2,c3,c4 = st.columns([3,2,2,3])
                c1.write(f"**{r['name']}**")
                c2.write(f"{em} {r['status']}")
                io = []
                if r['in_time']:
                    io.append(f"In: {r['in_time'][:5]}")
                if r['out_time']:
                    io.append(f"Out: {r['out_time'][:5]}")
                c3.write(" | ".join(io) if io else "-")
                c4.write(f"📝 {r['notes']}" if r['notes'] else "")
        else:
            st.info("No records")

# =================== REPORTS ===================
def show_reports(sid):
    db = get_db_conn()
    st.header("📊 Reports")
    classes = db.execute("SELECT * FROM classes WHERE school_id=? AND is_active=1", (sid,)).fetchall()
    if not classes:
        st.warning("No classes")
        return
    copts = {f"{c['class_name']} {c['section'] or ''}".strip(): c['id'] for c in classes}
    
    t1, t2 = st.tabs(["Monthly", "Yearly"])
    with t1:
        c1,c2,c3 = st.columns([2,2,2])
        with c1:
            rcls = st.selectbox("Class", list(copts.keys()), key="rcls")
        with c2:
            rmon = st.selectbox("Month", list(calendar.month_name)[1:], key="rmon")
        with c3:
            ryr = st.selectbox("Year", list(range(datetime.now().year, datetime.now().year-5, -1)), key="ryr")
        
        mn = list(calendar.month_name).index(rmon)
        sd = f"{ryr}-{mn:02d}-01"
        ld = calendar.monthrange(ryr, mn)[1]
        ed = f"{ryr}-{mn:02d}-{ld}"
        wd = db.execute("SELECT COUNT(DISTINCT date) FROM attendance WHERE class_id=? AND date BETWEEN ? AND ?",
                        (copts[rcls], sd, ed)).fetchone()[0]
        stu = db.execute("SELECT id, name FROM students WHERE class_id=? AND school_id=? AND is_active=1 ORDER BY name",
                         (copts[rcls], sid)).fetchall()
        st.subheader(f"{rcls} — {rmon} {ryr}")
        st.caption(f"Working Days: {wd}")
        
        if stu:
            data = []
            for s in stu:
                stt = db.execute("""
                    SELECT SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as present,
                           SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) as absent,
                           SUM(CASE WHEN status='Late' THEN 1 ELSE 0 END) as late,
                           SUM(CASE WHEN status='Half Day' THEN 1 ELSE 0 END) as half,
                           COUNT(*) as total FROM attendance WHERE student_id=? AND date BETWEEN ? AND ?
                """, (s['id'], sd, ed)).fetchone()
                data.append({
                    "Name": s['name'], "Working Days": wd, "Present": stt['present'] or 0,
                    "Absent": stt['absent'] or 0, "Late": stt['late'] or 0,
                    "Half Day": stt['half'] or 0, "Total Marked": stt['total'] or 0
                })
            st.dataframe(data, use_container_width=True, hide_index=True)
    
    with t2:
        c1,c2 = st.columns([2,2])
        with c1:
            ycls = st.selectbox("Class", list(copts.keys()), key="ycls")
        with c2:
            yyr = st.selectbox("Year", list(range(datetime.now().year, datetime.now().year-5, -1)), key="yyr")
        
        ys = f"{yyr}-01-01"
        ye = f"{yyr}-12-31"
        ywd = db.execute("SELECT COUNT(DISTINCT date) FROM attendance WHERE class_id=? AND date BETWEEN ? AND ?",
                         (copts[ycls], ys, ye)).fetchone()[0]
        ystu = db.execute("SELECT id, name FROM students WHERE class_id=? AND school_id=? AND is_active=1 ORDER BY name",
                          (copts[ycls], sid)).fetchall()
        st.subheader(f"{ycls} — Year {yyr}")
        st.caption(f"Working Days: {ywd}")
        
        if ystu:
            ydata = []
            for s in ystu:
                stt = db.execute("""
                    SELECT SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as present,
                           SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) as absent,
                           SUM(CASE WHEN status='Late' THEN 1 ELSE 0 END) as late,
                           SUM(CASE WHEN status='Half Day' THEN 1 ELSE 0 END) as half,
                           COUNT(*) as total FROM attendance WHERE student_id=? AND date BETWEEN ? AND ?
                """, (s['id'], ys, ye)).fetchone()
                ydata.append({
                    "Name": s['name'], "Working Days": ywd, "Present": stt['present'] or 0,
                    "Absent": stt['absent'] or 0, "Late": stt['late'] or 0,
                    "Half Day": stt['half'] or 0, "Total Marked": stt['total'] or 0
                })
            st.dataframe(ydata, use_container_width=True, hide_index=True)

# =================== CARE LOGS ===================
def show_care_logs(sid):
    db = get_db_conn()
    st.header("🧸 Care Logs")
    stu = db.execute("SELECT id, name FROM students WHERE school_id=? AND is_active=1 ORDER BY name", (sid,)).fetchall()
    if not stu:
        st.warning("No students")
        return
    sd = {s['name']: s['id'] for s in stu}
    
    t1, t2 = st.tabs(["New Log", "Today"])
    with t1:
        ss = st.selectbox("Student", list(sd.keys()))
        lt = st.selectbox("Type", ["Breakfast","Lunch","Diaper Change","Pee","Potty","Naptime","Daycare","Activity"])
        
        if lt in ["Breakfast","Lunch"]:
            with st.form(f"log_{lt}"):
                portion = st.selectbox("Portion", ["Full","Half","Little","Refused"])
                notes = st.text_area("Notes")
                if st.form_submit_button("Save"):
                    db.execute("""INSERT INTO care_logs (id, student_id, student_name, activity, notes, school_id, type, sub_type, status)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (gen_id(), sd[ss], ss, lt, notes, sid, "food", lt.lower(), portion))
                    db.commit()
                    st.success("Saved!")
        elif lt in ["Diaper Change","Pee","Potty"]:
            with st.form(f"log_{lt}"):
                notes = st.text_area("Notes")
                if st.form_submit_button("Save"):
                    db.execute("""INSERT INTO care_logs (id, student_id, student_name, activity, notes, school_id, type, sub_type)
                        VALUES (?,?,?,?,?,?,?,?)""",
                        (gen_id(), sd[ss], ss, lt, notes, sid, "bathroom", lt.lower().replace(" ","_")))
                    db.commit()
                    st.success("Saved!")
        elif lt == "Naptime":
            with st.form("log_nap"):
                start = st.time_input("Start")
                end = st.time_input("End")
                notes = st.text_area("Notes")
                if st.form_submit_button("Save"):
                    db.execute("""INSERT INTO care_logs (id, student_id, student_name, activity, notes, school_id, type, start_time, end_time)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (gen_id(), sd[ss], ss, lt, notes, sid, "nap", str(start), str(end)))
                    db.commit()
                    st.success("Saved!")
        else:
            with st.form(f"log_{lt}"):
                notes = st.text_area("Details")
                if st.form_submit_button("Save"):
                    db.execute("""INSERT INTO care_logs (id, student_id, student_name, activity, notes, school_id, type)
                        VALUES (?,?,?,?,?,?,?)""",
                        (gen_id(), sd[ss], ss, lt, notes, sid, lt.lower()))
                    db.commit()
                    st.success("Saved!")
    with t2:
        logs = db.execute("SELECT * FROM care_logs WHERE school_id=? AND date(time)=date('now') ORDER BY time DESC", (sid,)).fetchall()
        if not logs:
            st.info("No logs today")
        else:
            for l in logs:
                em = {"food":"🍽️","bathroom":"🚽","nap":"😴","daycare":"🏠","activity":"🎨"}.get(l['type'],"📝")
                st.markdown(f"{em} **{l['student_name']}** — {l['activity']} at {l['time'][11:16]}")
                if l['status']:
                    st.caption(f"Status: {l['status']}")
                if l['notes']:
                    st.caption(f"Note: {l['notes']}")

# =================== PHOTO GALLERY ===================
def show_photo_gallery(sid):
    st.header("🖼️ Photo Gallery")
    st.info("📸 Upload and manage student photos with tagging. Batch upload coming soon!")

# =================== MAIN ===================
def school_page():
    require_auth(["head", "teacher"])
    sid = st.session_state.auth["school_id"]
    menu, features, is_expired = school_sidebar()
    
    # Check if upgrade is forced
    limits = check_trial_limits(sid)
    if is_expired or not limits["can_add"]:
        if menu == "👶 Students":
            show_students(sid)  # Will show upgrade prompt
        elif menu == "📊 Dashboard":
            show_dashboard(sid, features, is_expired)
        else:
            st.warning("⚠️ Please complete the upgrade to access all features.")
            show_upgrade_prompt(sid, "trial_expired" if is_expired else "student_limit")
        return
    
    if menu == "📊 Dashboard":
        show_dashboard(sid, features, is_expired)
    elif menu == "👨‍🏫 Teachers":
        show_teachers(sid, features)
    elif menu == "🏫 Classes & Programs":
        show_classes_programs(sid)
    elif menu == "👶 Students":
        show_students(sid)
    elif menu == "📋 Attendance":
        show_attendance(sid)
    elif menu == "📊 Reports":
        show_reports(sid)
    elif menu == "🧸 Care Logs":
        show_care_logs(sid)
    elif menu == "🖼️ Photo Gallery" or menu == "🔒 Photo Gallery (Upgrade)":
        if features.get("photos"):
            show_photo_gallery(sid)
        else:
            st.error("🔒 Photo Gallery is locked. Please upgrade to unlock this feature!")
            show_upgrade_prompt(sid, "feature_locked")

def main():
    if not st.session_state.auth["logged_in"]:
        landing_page()
    elif st.session_state.auth["role"] == "admin":
        admin_page()
    else:
        school_page()
    
    st.divider()
    st.caption("SchoolOS Pro SaaS | Free Trial: 10 students, 14 days")

if __name__ == "__main__":
    main()
