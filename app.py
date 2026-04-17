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
st.set_page_config(page_title="SchoolOS Pro — SaaS Platform", layout="wide", page_icon="🏫")

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
    .revenue-box { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 12px; text-align: center; }
    @media (max-width: 768px) { .main-header { font-size: 1.6rem; } }
</style>
""", unsafe_allow_html=True)

# =================== DATABASE ===================
@st.cache_resource
def get_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS admin_config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            max_students INTEGER DEFAULT 30,
            yearly_price INTEGER DEFAULT 0,
            extra_student_price INTEGER DEFAULT 0,
            features TEXT DEFAULT '{}',
            is_active INTEGER DEFAULT 1,
            is_popular INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS schools (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            pass TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            plan_id TEXT,
            max_students INTEGER DEFAULT 30,
            expiry TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY,
            school_id TEXT,
            plan_id TEXT,
            amount_paid INTEGER,
            payment_status TEXT DEFAULT 'Pending',
            payment_id TEXT,
            razorpay_order_id TEXT,
            start_date TEXT,
            end_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS teachers (
            id TEXT PRIMARY KEY,
            school_id TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            pass TEXT NOT NULL,
            role TEXT DEFAULT 'teacher',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS teacher_sessions (
            id TEXT PRIMARY KEY,
            teacher_id TEXT NOT NULL,
            school_id TEXT NOT NULL,
            login_time TEXT DEFAULT CURRENT_TIMESTAMP,
            last_active TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS classes (
            id TEXT PRIMARY KEY,
            class_name TEXT NOT NULL,
            section TEXT,
            school_id TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS programs (
            id TEXT PRIMARY KEY,
            program_name TEXT NOT NULL,
            class_id TEXT NOT NULL,
            school_id TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            mother_name TEXT,
            father_name TEXT,
            dob TEXT,
            age TEXT,
            blood_group TEXT,
            program_id TEXT,
            class_id TEXT,
            phone TEXT,
            email TEXT,
            guardian_name TEXT,
            likes TEXT,
            dislikes TEXT,
            school_id TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            profile_photo TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            class_id TEXT NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Present','Absent','Late','Half Day')),
            in_time TEXT,
            out_time TEXT,
            notes TEXT,
            marked_by TEXT,
            marked_at TEXT DEFAULT CURRENT_TIMESTAMP
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
    """)
    
    h = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
    conn.execute("INSERT OR IGNORE INTO admin_config VALUES (?,?)", ("admin_password_hash", h))
    
    # Seed default plans if none exist
    if conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0] == 0:
        default_plans = [
            ("plan_basic", "Basic", 30, 2999, 0, json.dumps({
                "students": True, "attendance": True, "care_logs": True,
                "reports": False, "photos": False, "whatsapp": False,
                "multi_teacher": False, "max_teachers": 1
            }), 1, 0, 1),
            ("plan_std", "Standard", 80, 4999, 0, json.dumps({
                "students": True, "attendance": True, "care_logs": True,
                "reports": True, "photos": False, "whatsapp": False,
                "multi_teacher": True, "max_teachers": 2
            }), 1, 0, 2),
            ("plan_prem", "Premium", 500, 7999, 100, json.dumps({
                "students": True, "attendance": True, "care_logs": True,
                "reports": True, "photos": True, "whatsapp": True,
                "multi_teacher": True, "max_teachers": 10
            }), 1, 1, 3),
            ("plan_ent", "Enterprise", 9999, 11999, 0, json.dumps({
                "students": True, "attendance": True, "care_logs": True,
                "reports": True, "photos": True, "whatsapp": True,
                "multi_teacher": True, "max_teachers": 50
            }), 1, 0, 4),
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
        st.error(f"Image processing error: {e}")
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
    if not row:
        return {}
    return json.loads(row["features"] or '{}')

def get_school_plan(school_id):
    db = get_db_conn()
    s = db.execute("SELECT plan_id, max_students FROM schools WHERE id=?", (school_id,)).fetchone()
    if not s:
        return None, 0, {}
    p = db.execute("SELECT * FROM plans WHERE id=?", (s["plan_id"],)).fetchone()
    if not p:
        return None, 0, {}
    return p, s["max_students"], json.loads(p["features"] or '{}')

# =================== SESSION ===================
if "auth" not in st.session_state:
    st.session_state.auth = {
        "logged_in": False, "role": None, "school_id": None,
        "user_id": None, "name": None, "session_id": None
    }
if "show_teacher_reg" not in st.session_state:
    st.session_state.show_teacher_reg = False
if "show_school_reg" not in st.session_state:
    st.session_state.show_school_reg = False
if "payment_success" not in st.session_state:
    st.session_state.payment_success = None

def require_auth(allowed_roles):
    if not st.session_state.auth["logged_in"]:
        st.warning("Please log in first.")
        st.stop()
    if st.session_state.auth["role"] not in allowed_roles:
        st.error("Unauthorized access.")
        st.stop()
    if st.session_state.auth["role"] == "teacher" and st.session_state.auth.get("session_id"):
        if not is_session_active(st.session_state.auth["session_id"]):
            st.error("Your session was logged out from another device.")
            st.session_state.auth = {
                "logged_in": False, "role": None, "school_id": None,
                "user_id": None, "name": None, "session_id": None
            }
            st.rerun()

# =================== PUBLIC LANDING ===================
def landing_page():
    st.markdown('<p class="main-header">🏫 SchoolOS Pro</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">The Complete Daycare & Preschool Management Platform</p>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        tab_login, tab_reg = st.tabs(["🔐 School Login", "📝 New School Registration"])
        
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
                school_id = st.text_input("School ID")
                pw = st.text_input("Password", type="password")
                if st.button("Login", type="primary", use_container_width=True):
                    db = get_db_conn()
                    s = db.execute("SELECT * FROM schools WHERE id=? AND is_active=1", (school_id,)).fetchone()
                    if not s:
                        st.error("School not found")
                    elif not check_pw(pw, s["pass"]):
                        st.error("Invalid password")
                    else:
                        try:
                            if datetime.now() > datetime.strptime(s["expiry"], "%Y-%m-%d"):
                                st.error("Subscription expired. Renew now.")
                                return
                        except:
                            pass
                        st.session_state.auth = {
                            "logged_in": True, "role": "head", "school_id": school_id,
                            "user_id": school_id, "name": s["name"], "session_id": None
                        }
                        st.rerun()
            
            elif role == "Teacher":
                school_id = st.text_input("School ID", key="t_school")
                phone = st.text_input("Phone Number", key="t_phone")
                pw = st.text_input("Password", type="password", key="t_pw")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Login", type="primary", use_container_width=True):
                        db = get_db_conn()
                        t = db.execute("SELECT * FROM teachers WHERE school_id=? AND phone=? AND is_active=1",
                                       (school_id, phone)).fetchone()
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
                        reg_school = st.text_input("School ID (from invite)")
                        reg_name = st.text_input("Full Name")
                        reg_phone = st.text_input("Phone Number")
                        reg_pw = st.text_input("Create Password", type="password")
                        reg_pw2 = st.text_input("Confirm Password", type="password")
                        if st.form_submit_button("✅ Register"):
                            if not all([reg_school, reg_name, reg_phone, reg_pw]):
                                st.error("Fill all fields")
                            elif reg_pw != reg_pw2:
                                st.error("Passwords don't match")
                            elif len(reg_pw) < 6:
                                st.error("Password too short")
                            else:
                                db = get_db_conn()
                                if not db.execute("SELECT 1 FROM schools WHERE id=? AND is_active=1", (reg_school,)).fetchone():
                                    st.error("Invalid School ID")
                                elif db.execute("SELECT 1 FROM teachers WHERE phone=?", (reg_phone,)).fetchone():
                                    st.error("Phone already registered")
                                else:
                                    db.execute("INSERT INTO teachers (id, school_id, name, phone, pass) VALUES (?,?,?,?,?)",
                                               (gen_id(), reg_school, sanitize(reg_name), sanitize(reg_phone), hash_pw(reg_pw)))
                                    db.commit()
                                    st.success("✅ Registered! You can now log in.")
                                    st.session_state.show_teacher_reg = False
                                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        
        with tab_reg:
            school_registration_flow()

# =================== SCHOOL SELF-REGISTRATION ===================
def school_registration_flow():
    db = get_db_conn()
    plans = db.execute("SELECT * FROM plans WHERE is_active=1 ORDER BY sort_order").fetchall()
    
    st.subheader("Choose Your Plan")
    st.caption("Select a plan that fits your school. Pay securely via Razorpay.")
    
    # Display plan cards
    cols = st.columns(len(plans))
    selected_plan = None
    for idx, p in enumerate(plans):
        features = json.loads(p["features"] or '{}')
        with cols[idx]:
            popular_class = "plan-card plan-popular" if p["is_popular"] else "plan-card"
            st.markdown(f'<div class="{popular_class}">', unsafe_allow_html=True)
            if p["is_popular"]:
                st.markdown("🔥 **MOST POPULAR**")
            st.markdown(f"### {p['name']}")
            st.markdown(f"<h2>₹{p['yearly_price']:,}<small>/year</small></h2>", unsafe_allow_html=True)
            st.markdown(f"**{p['max_students']}** Students Included")
            if p["extra_student_price"] > 0:
                st.caption(f"+₹{p['extra_student_price']} per extra student")
            
            st.divider()
            for feat, enabled in features.items():
                icon = "✅" if enabled else "❌"
                label = feat.replace("_", " ").title()
                if enabled:
                    st.markdown(f"<span class='feature-yes'>{icon} {label}</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span class='feature-no'>{icon} {label}</span>", unsafe_allow_html=True)
            
            if st.button(f"Select {p['name']}", key=f"sel_plan_{p['id']}", use_container_width=True):
                st.session_state.selected_plan_id = p["id"]
            st.markdown('</div>', unsafe_allow_html=True)
    
    if "selected_plan_id" in st.session_state:
        selected_plan_id = st.session_state.selected_plan_id
        plan = db.execute("SELECT * FROM plans WHERE id=?", (selected_plan_id,)).fetchone()
        if plan:
            st.divider()
            st.subheader(f"📝 Register for {plan['name']} Plan")
            
            with st.form("school_reg"):
                c1, c2 = st.columns(2)
                with c1:
                    s_name = st.text_input("School Name *", placeholder="Little Angels School")
                    s_email = st.text_input("Email *", placeholder="school@email.com")
                with c2:
                    s_phone = st.text_input("Phone *", placeholder="9876543210")
                    s_pass = st.text_input("Create Password *", type="password")
                    s_pass2 = st.text_input("Confirm Password *", type="password")
                
                st.info(f"""
                **Subscription Summary:**
                - Plan: {plan['name']}
                - Students: Up to {plan['max_students']}
                - Amount: ₹{plan['yearly_price']:,} / year
                """)
                
                # Razorpay integration placeholder
                st.markdown("---")
                st.markdown("💳 **Payment via Razorpay** (Test Mode)")
                st.caption("In production, this opens Razorpay checkout. For demo, simulate payment below.")
                
                pay_method = st.radio("Payment Method", ["Razorpay (Recommended)", "UPI / Bank Transfer (Manual)"], horizontal=True)
                
                if st.form_submit_button("✅ Complete Registration & Pay", use_container_width=True):
                    if not all([s_name, s_email, s_phone, s_pass]):
                        st.error("Please fill all required fields")
                    elif s_pass != s_pass2:
                        st.error("Passwords do not match")
                    elif len(s_pass) < 6:
                        st.error("Password must be at least 6 characters")
                    elif db.execute("SELECT 1 FROM schools WHERE id=?", (sanitize(s_name).lower().replace(" ", "_"),)).fetchone():
                        st.error("A school with similar ID exists. Try a different name.")
                    else:
                        # Generate school ID from name
                        school_id = sanitize(s_name).lower().replace(" ", "_") + "_" + secrets.token_hex(3)
                        expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
                        
                        # Create school (inactive until payment confirmed)
                        db.execute("""
                            INSERT INTO schools (id, name, pass, email, phone, plan_id, max_students, expiry, is_active)
                            VALUES (?,?,?,?,?,?,?,?,0)
                        """, (school_id, sanitize(s_name), hash_pw(s_pass), sanitize(s_email), sanitize(s_phone),
                              plan['id'], plan['max_students'], expiry))
                        
                        # Record subscription
                        sub_id = gen_id()
                        db.execute("""
                            INSERT INTO subscriptions (id, school_id, plan_id, amount_paid, payment_status, start_date, end_date)
                            VALUES (?,?,?,?,?,?,?)
                        """, (sub_id, school_id, plan['id'], plan['yearly_price'], 
                              'Paid' if pay_method == "Razorpay (Recommended)" else 'Pending',
                              datetime.now().isoformat(), expiry))
                        db.commit()
                        
                        if pay_method == "Razorpay (Recommended)":
                            # Simulate Razorpay success
                            db.execute("UPDATE schools SET is_active=1 WHERE id=?", (school_id,))
                            db.execute("UPDATE subscriptions SET payment_status='Paid', payment_id=? WHERE id=?",
                                       ("pay_demo_" + secrets.token_hex(4), sub_id))
                            db.commit()
                            
                            st.session_state.payment_success = {
                                "school_id": school_id,
                                "name": s_name,
                                "plan": plan['name'],
                                "amount": plan['yearly_price']
                            }
                        else:
                            st.warning("⏳ Your registration is pending manual payment verification. You will receive access after confirmation.")
                        st.rerun()
    
    if st.session_state.payment_success:
        success = st.session_state.payment_success
        st.balloons()
        st.success(f"""
        🎉 Registration Successful!
        
        **School:** {success['name']}
        **School ID:** `{success['school_id']}`
        **Plan:** {success['plan']}
        **Amount Paid:** ₹{success['amount']:,}
        
        You can now log in using your School ID and Password.
        """)
        if st.button("Go to Login"):
            del st.session_state.payment_success
            if "selected_plan_id" in st.session_state:
                del st.session_state.selected_plan_id
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
        total_schools = db.execute("SELECT COUNT(*) FROM schools").fetchone()[0]
        active_schools = db.execute("SELECT COUNT(*) FROM schools WHERE is_active=1").fetchone()[0]
        total_revenue = db.execute("SELECT COALESCE(SUM(amount_paid),0) FROM subscriptions WHERE payment_status='Paid'").fetchone()[0]
        st.metric("Total Schools", total_schools)
        st.metric("Active", active_schools)
        st.metric("Total Revenue", f"₹{total_revenue:,}")
    
    tab1, tab2, tab3 = st.tabs(["💰 Revenue & Subscriptions", "📋 Plan Management", "⚙️ Settings"])
    
    # REVENUE TAB
    with tab1:
        st.header("💰 Revenue Dashboard")
        
        # Top stats
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Revenue", f"₹{total_revenue:,}")
        c2.metric("This Month", f"₹{db.execute('''SELECT COALESCE(SUM(amount_paid),0) FROM subscriptions 
                      WHERE payment_status='Paid' AND strftime('%Y-%m',created_at)=?''', 
                      (datetime.now().strftime('%Y-%m'),)).fetchone()[0]:,}")
        c3.metric("Active Subscriptions", db.execute("SELECT COUNT(*) FROM subscriptions WHERE payment_status='Paid'").fetchone()[0])
        c4.metric("Pending Payments", db.execute("SELECT COUNT(*) FROM subscriptions WHERE payment_status='Pending'").fetchone()[0])
        
        st.divider()
        st.subheader("📚 All Subscriptions")
        subs = db.execute("""
            SELECT s.name, s.email, s.phone, s.is_active, s.created_at,
                   p.name as plan_name, p.yearly_price,
                   sub.amount_paid, sub.payment_status, sub.payment_id, sub.start_date, sub.end_date
            FROM subscriptions sub
            JOIN schools s ON sub.school_id = s.id
            JOIN plans p ON sub.plan_id = p.id
            ORDER BY sub.created_at DESC
        """).fetchall()
        
        if not subs:
            st.info("No subscriptions yet")
        else:
            data = []
            for sub in subs:
                data.append({
                    "School": sub['name'],
                    "Email": sub['email'],
                    "Phone": sub['phone'],
                    "Plan": sub['plan_name'],
                    "Amount": f"₹{sub['amount_paid']:,}",
                    "Status": sub['payment_status'],
                    "Payment ID": sub['payment_id'] or "-",
                    "Start": sub['start_date'][:10] if sub['start_date'] else "-",
                    "End": sub['end_date'][:10] if sub['end_date'] else "-",
                    "Active": "✅" if sub['is_active'] else "⏳"
                })
            st.dataframe(data, use_container_width=True, hide_index=True)
    
    # PLANS TAB
    with tab2:
        st.header("📋 Plan Configuration")
        st.caption("Control what each plan includes, pricing, and student limits. Changes apply to NEW subscriptions only.")
        
        with st.expander("➕ Create New Plan"):
            with st.form("create_plan"):
                pname = st.text_input("Plan Name *")
                pstudents = st.number_input("Max Students", min_value=1, value=30)
                pprice = st.number_input("Yearly Price (₹)", min_value=0, value=2999, step=500)
                pextra = st.number_input("Extra Student Price (₹)", min_value=0, value=0)
                
                st.subheader("Features Included")
                f_attendance = st.checkbox("Attendance System", value=True)
                f_care = st.checkbox("Care Logs", value=True)
                f_reports = st.checkbox("Reports & Analytics")
                f_photos = st.checkbox("Photo Gallery (Premium)")
                f_whatsapp = st.checkbox("WhatsApp Integration")
                f_multiteacher = st.checkbox("Multi-Teacher Login")
                f_max_teachers = st.number_input("Max Teachers Allowed", min_value=1, value=1)
                f_broadcast = st.checkbox("Broadcast Messages", value=True)
                
                is_popular = st.checkbox("Mark as Popular", value=False)
                
                if st.form_submit_button("✅ Save Plan"):
                    features = json.dumps({
                        "attendance": f_attendance,
                        "care_logs": f_care,
                        "reports": f_reports,
                        "photos": f_photos,
                        "whatsapp": f_whatsapp,
                        "multi_teacher": f_multiteacher,
                        "max_teachers": f_max_teachers,
                        "broadcast": f_broadcast
                    })
                    db.execute("""
                        INSERT INTO plans (id, name, max_students, yearly_price, extra_student_price, features, is_active, is_popular)
                        VALUES (?,?,?,?,?,?,1,?)
                    """, (gen_id(), sanitize(pname), pstudents, pprice, pextra, features, 1 if is_popular else 0))
                    db.commit()
                    st.success(f"✅ Plan '{pname}' created!")
                    st.rerun()
        
        st.divider()
        st.subheader("✏️ Manage Existing Plans")
        plans = db.execute("SELECT * FROM plans ORDER BY sort_order").fetchall()
        for p in plans:
            features = json.loads(p["features"] or '{}')
            with st.expander(f"{'🔥 ' if p['is_popular'] else ''}{p['name']} — ₹{p['yearly_price']:,} ({p['max_students']} students)"):
                c1, c2 = st.columns([3,1])
                with c1:
                    st.write(f"**Students:** {p['max_students']} | **Extra:** ₹{p['extra_student_price']} | **Active:** {'Yes' if p['is_active'] else 'No'}")
                    st.write("**Features:** " + ", ".join([k.replace("_"," ").title() for k,v in features.items() if v and isinstance(v, bool)]))
                with c2:
                    if st.button("🗑️ Deactivate", key=f"del_plan_{p['id']}"):
                        db.execute("UPDATE plans SET is_active=0 WHERE id=?", (p['id'],))
                        db.commit()
                        st.rerun()
    
    # SETTINGS TAB
    with tab3:
        st.subheader("⚙️ Admin Password")
        with st.form("admin_pw"):
            old = st.text_input("Current Password", type="password")
            new = st.text_input("New Password", type="password")
            conf = st.text_input("Confirm", type="password")
            if st.form_submit_button("Update"):
                cur = db.execute("SELECT value FROM admin_config WHERE key='admin_password_hash'").fetchone()[0]
                if not check_pw(old, cur):
                    st.error("Wrong password")
                elif new != conf:
                    st.error("Mismatch")
                elif len(new) < 8:
                    st.error("Too short")
                else:
                    db.execute("UPDATE admin_config SET value=? WHERE key='admin_password_hash'", (hash_pw(new),))
                    db.commit()
                    st.success("✅ Updated")

# =================== SCHOOL SHARED ===================
def school_sidebar():
    auth = st.session_state.auth
    sid = auth["school_id"]
    plan, max_students, features = get_school_plan(sid)
    
    with st.sidebar:
        st.markdown(f"### {auth['name']}")
        st.caption(f"Role: {auth['role'].upper()}")
        if plan:
            st.caption(f"Plan: {plan['name']}")
        st.divider()
        
        menu_items = ["📊 Dashboard"]
        if auth["role"] == "head":
            menu_items.append("👨‍🏫 Teachers")
        menu_items.extend(["🏫 Classes & Programs", "👶 Students", "📋 Attendance"])
        if features.get("reports"):
            menu_items.append("📊 Reports")
        menu_items.append("🧸 Care Logs")
        if features.get("photos"):
            menu_items.append("🖼️ Photo Gallery")
        
        menu = st.radio("Menu", menu_items)
        st.divider()
        st.progress(0.3, text="Subscription Active")
        st.caption(f"Renewal: Check with admin")
        if st.button("🚪 Logout", use_container_width=True):
            if auth.get("session_id"):
                logout_teacher_session(auth["session_id"])
            st.session_state.auth = {
                "logged_in": False, "role": None, "school_id": None,
                "user_id": None, "name": None, "session_id": None
            }
            st.rerun()
    return menu, features

# =================== DASHBOARD ===================
def show_dashboard(sid, features):
    db = get_db_conn()
    st.header("📊 Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Students", db.execute("SELECT COUNT(*) FROM students WHERE school_id=? AND is_active=1", (sid,)).fetchone()[0])
    c2.metric("Teachers", db.execute("SELECT COUNT(*) FROM teachers WHERE school_id=? AND is_active=1", (sid,)).fetchone()[0])
    c3.metric("Classes", db.execute("SELECT COUNT(*) FROM classes WHERE school_id=?", (sid,)).fetchone()[0])
    c4.metric("Today's Attendance", db.execute("""
        SELECT COUNT(*) FROM attendance 
        WHERE date=? AND class_id IN (SELECT id FROM classes WHERE school_id=?)
    """, (date.today().isoformat(), sid)).fetchone()[0])

# =================== TEACHERS ===================
def show_teachers(sid, features):
    require_auth(["head"])
    db = get_db_conn()
    st.header("👨‍🏫 Teacher Management")
    
    max_teachers = features.get("max_teachers", 1)
    current_teachers = db.execute("SELECT COUNT(*) FROM teachers WHERE school_id=? AND is_active=1", (sid,)).fetchone()[0]
    
    st.caption(f"Plan Limit: {current_teachers}/{max_teachers} teachers")
    
    if current_teachers < max_teachers:
        with st.expander("➕ Add Teacher"):
            with st.form("add_teacher"):
                tname = st.text_input("Name *")
                tphone = st.text_input("Phone *")
                tpw = st.text_input("Password *", type="password")
                if st.form_submit_button("✅ Add"):
                    if not all([tname, tphone, tpw]):
                        st.error("Fill all fields")
                    elif db.execute("SELECT 1 FROM teachers WHERE phone=?", (tphone,)).fetchone():
                        st.error("Phone exists")
                    else:
                        db.execute("INSERT INTO teachers (id, school_id, name, phone, pass) VALUES (?,?,?,?,?)",
                                   (gen_id(), sid, sanitize(tname), sanitize(tphone), hash_pw(tpw)))
                        db.commit()
                        st.success("✅ Added!")
                        st.rerun()
    else:
        st.warning("⚠️ Teacher limit reached for your plan. Upgrade to add more.")
    
    teachers = db.execute("SELECT * FROM teachers WHERE school_id=? AND is_active=1", (sid,)).fetchall()
    for t in teachers:
        cols = st.columns([3,2,2,1])
        cols[0].write(f"**{t['name']}**")
        cols[1].write(f"📞 {t['phone']}")
        cols[2].write(f"Role: {t['role']}")
        if cols[3].button("🗑️", key=f"rmt_{t['id']}"):
            db.execute("UPDATE teachers SET is_active=0 WHERE id=?", (t['id'],))
            db.commit()
            st.rerun()

# =================== CLASSES & PROGRAMS ===================
def show_classes_programs(sid):
    db = get_db_conn()
    st.header("🏫 Classes & Programs")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📚 Classes")
        with st.form("add_class"):
            cname = st.text_input("Class Name *", placeholder="Nursery...")
            csec = st.text_input("Section", placeholder="A, B...")
            if st.form_submit_button("➕ Add Class"):
                if cname:
                    db.execute("INSERT INTO classes (id, class_name, section, school_id) VALUES (?,?,?,?)",
                               (gen_id(), sanitize(cname), sanitize(csec), sid))
                    db.commit()
                    st.success(f"✅ Added {cname}!")
                else:
                    st.error("Name required")
        
        classes = db.execute("SELECT * FROM classes WHERE school_id=? AND is_active=1", (sid,)).fetchall()
        for c in classes:
            sc = db.execute("SELECT COUNT(*) FROM students WHERE class_id=? AND is_active=1", (c['id'],)).fetchone()[0]
            cols = st.columns([3,1,1])
            cols[0].write(f"**{c['class_name']} {c['section'] or ''}** ({sc} students)")
            if cols[2].button("🗑️", key=f"delc_{c['id']}"):
                if sc == 0:
                    db.execute("DELETE FROM classes WHERE id=?", (c['id'],))
                    db.commit()
                    st.rerun()
                else:
                    st.error("Has students!")
    
    with c2:
        st.subheader("📋 Programs (Auto-Class)")
        classes = db.execute("SELECT * FROM classes WHERE school_id=? AND is_active=1", (sid,)).fetchall()
        if classes:
            class_opts = {f"{c['class_name']} {c['section'] or ''}".strip(): c['id'] for c in classes}
            with st.form("add_program"):
                pname = st.text_input("Program Name *")
                pcls = st.selectbox("Assign to Class *", list(class_opts.keys()))
                if st.form_submit_button("➕ Add Program"):
                    if pname:
                        db.execute("INSERT INTO programs (id, program_name, class_id, school_id) VALUES (?,?,?,?)",
                                   (gen_id(), sanitize(pname), class_opts[pcls], sid))
                        db.commit()
                        st.success("✅ Added!")
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
    
    plan, max_students, _ = get_school_plan(sid)
    current_count = db.execute("SELECT COUNT(*) FROM students WHERE school_id=? AND is_active=1", (sid,)).fetchone()[0]
    
    programs = db.execute("""
        SELECT p.*, c.class_name, c.section 
        FROM programs p JOIN classes c ON p.class_id=c.id 
        WHERE p.school_id=?
    """, (sid,)).fetchall()
    prog_dict = {f"{p['program_name']} → {p['class_name']} {p['section'] or ''}": p for p in programs}
    
    st.caption(f"Students: {current_count}/{max_students}")
    
    t1, t2 = st.tabs(["➕ Add", "📋 List"])
    with t1:
        if current_count >= max_students:
            st.error(f"❌ Student limit reached ({max_students}). Upgrade plan to add more.")
        elif not programs:
            st.warning("Create programs first")
        else:
            with st.form("add_student", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Name *")
                    mother = st.text_input("Mother's Name")
                    father = st.text_input("Father's Name")
                    dob = st.date_input("DOB", value=date(2020,1,1))
                    blood = st.selectbox("Blood", ["A+","A-","B+","B-","AB+","AB-","O+","O-","Unknown"])
                with c2:
                    prog = st.selectbox("Program *", list(prog_dict.keys()))
                    phone = st.text_input("Phone")
                    email = st.text_input("Email")
                    guardian = st.text_input("Guardian")
                    likes = st.text_area("Likes")
                    dislikes = st.text_area("Dislikes")
                
                photo = st.file_uploader("Profile Photo", type=["jpg","jpeg","png"])
                if photo:
                    st.image(photo, width=150)
                
                if st.form_submit_button("✅ Register"):
                    if not name or not prog:
                        st.error("Name and Program required")
                    else:
                        p = prog_dict[prog]
                        age = calc_age(dob.isoformat())
                        ph = compress_image(photo)
                        db.execute("""
                            INSERT INTO students (id, name, mother_name, father_name, dob, age, blood_group, program_id, class_id,
                             phone, email, guardian_name, likes, dislikes, school_id, is_active, profile_photo)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (gen_id(), sanitize(name), sanitize(mother), sanitize(father), dob.isoformat(), age, blood,
                              p['id'], p['class_id'], sanitize(phone), sanitize(email), sanitize(guardian),
                              sanitize(likes), sanitize(dislikes), sid, 1, ph))
                        db.commit()
                        st.success(f"✅ {name} registered!")
                        st.balloons()
    
    with t2:
        students = db.execute("""
            SELECT s.*, p.program_name, c.class_name, c.section
            FROM students s LEFT JOIN programs p ON s.program_id=p.id LEFT JOIN classes c ON s.class_id=c.id
            WHERE s.school_id=? AND s.is_active=1 ORDER BY s.name
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
                    st.write(f"**DOB:** {s['dob'] or '-'} | **Phone:** {s['phone'] or '-'} | **Email:** {s['email'] or '-'}")
                    st.write(f"**Guardian:** {s['guardian_name'] or '-'}")
                    st.write(f"**Class:** {s['class_name'] or '-'} {s['section'] or ''}")
                    st.write(f"**Likes:** {s['likes'] or '-'} | **Dislikes:** {s['dislikes'] or '-'}")
                    if st.button("🗑️ Remove", key=f"rms_{s['id']}"):
                        db.execute("UPDATE students SET is_active=0 WHERE id=?", (s['id'],))
                        db.commit()
                        st.rerun()

# =================== ATTENDANCE ===================
def show_attendance(sid):
    db = get_db_conn()
    st.header("📋 Attendance (In/Out Time)")
    classes = db.execute("SELECT * FROM classes WHERE school_id=? AND is_active=1", (sid,)).fetchall()
    if not classes:
        st.warning("Create classes first")
        return
    class_opts = {f"{c['class_name']} {c['section'] or ''}".strip(): c['id'] for c in classes}
    
    t1, t2 = st.tabs(["📝 Mark", "📅 View"])
    with t1:
        cls = st.selectbox("Class", list(class_opts.keys()), key="acls")
        dt = st.date_input("Date", value=date.today(), key="adt")
        students = db.execute("SELECT id, name FROM students WHERE class_id=? AND school_id=? AND is_active=1 ORDER BY name",
                              (class_opts[cls], sid)).fetchall()
        if not students:
            st.info("No students")
            return
        
        existing = {r['student_id']: r for r in db.execute("SELECT * FROM attendance WHERE date=? AND class_id=?",
                                                            (dt.isoformat(), class_opts[cls])).fetchall()}
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
            
            if st.form_submit_button("💾 Save Attendance", use_container_width=True):
                db.execute("DELETE FROM attendance WHERE date=? AND class_id=?", (dt.isoformat(), class_opts[cls]))
                for rid, stt, it, ot, nt in records:
                    db.execute("""
                        INSERT INTO attendance (student_id, class_id, date, status, in_time, out_time, notes, marked_by)
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (rid, class_opts[cls], dt.isoformat(), stt, str(it) if it else None, str(ot) if ot else None, nt, sid))
                db.commit()
                st.success(f"✅ Saved {len(records)} records!")
                st.balloons()
    
    with t2:
        vdt = st.date_input("Select Date", value=date.today(), key="vdt")
        vcls = st.selectbox("Class", list(class_opts.keys()), key="vcls")
        recs = db.execute("""
            SELECT a.*, s.name FROM attendance a JOIN students s ON a.student_id=s.id
            WHERE a.date=? AND a.class_id=? ORDER BY s.name
        """, (vdt.isoformat(), class_opts[vcls])).fetchall()
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
    st.header("📊 Attendance Reports")
    classes = db.execute("SELECT * FROM classes WHERE school_id=? AND is_active=1", (sid,)).fetchall()
    if not classes:
        st.warning("No classes")
        return
    class_opts = {f"{c['class_name']} {c['section'] or ''}".strip(): c['id'] for c in classes}
    
    t1, t2 = st.tabs(["📅 Monthly", "📆 Yearly"])
    with t1:
        c1,c2,c3 = st.columns([2,2,2])
        with c1:
            rcls = st.selectbox("Class", list(class_opts.keys()), key="rcls")
        with c2:
            rmon = st.selectbox("Month", list(calendar.month_name)[1:], key="rmon")
        with c3:
            ryr = st.selectbox("Year", list(range(datetime.now().year, datetime.now().year-5, -1)), key="ryr")
        
        mn = list(calendar.month_name).index(rmon)
        sd = f"{ryr}-{mn:02d}-01"
        ld = calendar.monthrange(ryr, mn)[1]
        ed = f"{ryr}-{mn:02d}-{ld}"
        
        wd = db.execute("SELECT COUNT(DISTINCT date) FROM attendance WHERE class_id=? AND date BETWEEN ? AND ?",
                        (class_opts[rcls], sd, ed)).fetchone()[0]
        stu = db.execute("SELECT id, name FROM students WHERE class_id=? AND school_id=? AND is_active=1 ORDER BY name",
                         (class_opts[rcls], sid)).fetchall()
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
        else:
            st.info("No students")
    
    with t2:
        c1,c2 = st.columns([2,2])
        with c1:
            ycls = st.selectbox("Class", list(class_opts.keys()), key="ycls")
        with c2:
            yyr = st.selectbox("Year", list(range(datetime.now().year, datetime.now().year-5, -1)), key="yyr")
        
        ys = f"{yyr}-01-01"
        ye = f"{yyr}-12-31"
        ywd = db.execute("SELECT COUNT(DISTINCT date) FROM attendance WHERE class_id=? AND date BETWEEN ? AND ?",
                         (class_opts[ycls], ys, ye)).fetchone()[0]
        ystu = db.execute("SELECT id, name FROM students WHERE class_id=? AND school_id=? AND is_active=1 ORDER BY name",
                          (class_opts[ycls], sid)).fetchall()
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
        else:
            st.info("No students")

# =================== CARE LOGS ===================
def show_care_logs(sid):
    db = get_db_conn()
    st.header("🧸 Care Logs")
    stu = db.execute("SELECT id, name FROM students WHERE school_id=? AND is_active=1 ORDER BY name", (sid,)).fetchall()
    if not stu:
        st.warning("No students")
        return
    sd = {s['name']: s['id'] for s in stu}
    
    t1, t2 = st.tabs(["➕ New Log", "📋 Today"])
    with t1:
        ss = st.selectbox("Student", list(sd.keys()))
        lt = st.selectbox("Type", ["Breakfast","Lunch","Diaper Change","Pee","Potty","Naptime","Daycare","Activity"])
        
        if lt in ["Breakfast","Lunch"]:
            with st.form(f"log_{lt}"):
                portion = st.selectbox("Portion", ["Full","Half","Little","Refused"])
                notes = st.text_area("Notes")
                if st.form_submit_button("💾 Save"):
                    db.execute("""INSERT INTO care_logs (id, student_id, student_name, activity, notes, school_id, type, sub_type, status)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (gen_id(), sd[ss], ss, lt, notes, sid, "food", lt.lower(), portion))
                    db.commit()
                    st.success("Saved!")
        elif lt in ["Diaper Change","Pee","Potty"]:
            with st.form(f"log_{lt}"):
                notes = st.text_area("Notes")
                if st.form_submit_button("💾 Save"):
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
                if st.form_submit_button("💾 Save"):
                    db.execute("""INSERT INTO care_logs (id, student_id, student_name, activity, notes, school_id, type, start_time, end_time)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (gen_id(), sd[ss], ss, lt, notes, sid, "nap", str(start), str(end)))
                    db.commit()
                    st.success("Saved!")
        else:
            with st.form(f"log_{lt}"):
                notes = st.text_area("Details")
                if st.form_submit_button("💾 Save"):
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

# =================== PHOTO GALLERY (PREMIUM) ===================
def show_photo_gallery(sid):
    st.header("🖼️ Photo Gallery")
    st.info("Premium Feature: Batch upload with student tagging coming in Phase 3.")
    st.image("https://via.placeholder.com/800x400?text=Photo+Gallery+-+Premium+Only", use_column_width=True)

# =================== MAIN ROUTER ===================
def school_page():
    require_auth(["head", "teacher"])
    sid = st.session_state.auth["school_id"]
    menu, features = school_sidebar()
    
    if menu == "📊 Dashboard":
        show_dashboard(sid, features)
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
    elif menu == "🖼️ Photo Gallery":
        show_photo_gallery(sid)

def main():
    if not st.session_state.auth["logged_in"]:
        landing_page()
    elif st.session_state.auth["role"] == "admin":
        admin_page()
    else:
        school_page()
    
    st.divider()
    st.caption("SchoolOS Pro SaaS | Self-Service Plans | Revenue Control")

if __name__ == "__main__":
    main()
