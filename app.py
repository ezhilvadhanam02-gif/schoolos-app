import streamlit as st
import sqlite3
import bcrypt
import secrets
import base64
from datetime import datetime, timedelta, date
import calendar
import io
from PIL import Image

# =================== CONFIG ===================
st.set_page_config(page_title="SchoolOS Pro — Phase 2", layout="wide", page_icon="🏫")

st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: bold; color: #1f77b4; text-align: center; margin-bottom: 1rem; }
    .sub-header { font-size: 1.1rem; color: #555; text-align: center; margin-bottom: 2rem; }
    .login-box { max-width: 480px; margin: auto; padding: 2rem; border: 1px solid #ddd; border-radius: 12px; background: #fff; }
    .stProgress > div > div > div > div { background-color: #1f77b4; }
    @media (max-width: 768px) { .main-header { font-size: 1.6rem; } }
</style>
""", unsafe_allow_html=True)

# =================== DATABASE ===================
@st.cache_resource
def get_db():
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
        CREATE TABLE IF NOT EXISTS admin_config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    h = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
    conn.execute("INSERT OR IGNORE INTO admin_config VALUES (?,?)", ("admin_password_hash", h))
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

# =================== SESSION ===================
if "auth" not in st.session_state:
    st.session_state.auth = {
        "logged_in": False, "role": None, "school_id": None,
        "user_id": None, "name": None, "session_id": None
    }
if "show_teacher_reg" not in st.session_state:
    st.session_state.show_teacher_reg = False

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

# =================== LOGIN PAGE ===================
def login_page():
    st.markdown('<p class="main-header">🏫 SchoolOS Pro — Phase 2</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Complete Daycare & School Management</p>', unsafe_allow_html=True)

    role = st.radio("Login as", ["School Head", "Teacher", "Admin"], horizontal=True, key="login_role")

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.container():
            st.markdown('<div class="login-box">', unsafe_allow_html=True)

            if role == "Admin":
                user = st.text_input("Admin ID", value="admin")
                pw = st.text_input("Password", type="password")
                if st.button("🔐 Login", use_container_width=True):
                    db = get_db_conn()
                    h = db.execute("SELECT value FROM admin_config WHERE key='admin_password_hash'").fetchone()
                    if h and check_pw(pw, h[0]):
                        st.session_state.auth = {
                            "logged_in": True, "role": "admin", "school_id": None,
                            "user_id": "admin", "name": "Admin", "session_id": None
                        }
                        st.rerun()
                    else:
                        st.error("Invalid admin credentials")

            elif role == "School Head":
                school_id = st.text_input("School ID", key="head_id")
                pw = st.text_input("Password", type="password", key="head_pw")
                if st.button("🔐 Login", use_container_width=True):
                    db = get_db_conn()
                    s = db.execute("SELECT * FROM schools WHERE id=? AND is_active=1", (school_id,)).fetchone()
                    if not s:
                        st.error("School not found or inactive")
                    elif not check_pw(pw, s["pass"]):
                        st.error("Invalid password")
                    else:
                        try:
                            if datetime.now() > datetime.strptime(s["expiry"], "%Y-%m-%d"):
                                st.error("Subscription expired. Contact admin.")
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
                    if st.button("🔐 Login", use_container_width=True):
                        db = get_db_conn()
                        t = db.execute("""
                            SELECT * FROM teachers 
                            WHERE school_id=? AND phone=? AND is_active=1
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

            st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.show_teacher_reg:
            st.divider()
            st.subheader("👨‍🏫 Teacher Registration via School Invite")
            with st.form("teacher_reg"):
                reg_school = st.text_input("School ID (from invite)", key="reg_school")
                reg_name = st.text_input("Full Name")
                reg_phone = st.text_input("Phone Number")
                reg_pw = st.text_input("Create Password", type="password")
                reg_pw2 = st.text_input("Confirm Password", type="password")
                if st.form_submit_button("✅ Register", use_container_width=True):
                    if not all([reg_school, reg_name, reg_phone, reg_pw]):
                        st.error("Please fill all fields")
                    elif reg_pw != reg_pw2:
                        st.error("Passwords do not match")
                    elif len(reg_pw) < 6:
                        st.error("Password must be at least 6 characters")
                    else:
                        db = get_db_conn()
                        if not db.execute("SELECT 1 FROM schools WHERE id=? AND is_active=1", (reg_school,)).fetchone():
                            st.error("Invalid School ID")
                        elif db.execute("SELECT 1 FROM teachers WHERE phone=?", (reg_phone,)).fetchone():
                            st.error("Phone number already registered")
                        else:
                            db.execute("""
                                INSERT INTO teachers (id, school_id, name, phone, pass)
                                VALUES (?,?,?,?,?)
                            """, (gen_id(), reg_school, sanitize(reg_name), sanitize(reg_phone), hash_pw(reg_pw)))
                            db.commit()
                            st.success("✅ Registration successful! You can now log in.")
                            st.session_state.show_teacher_reg = False
                            st.rerun()

# =================== ADMIN ===================
def admin_page():
    require_auth(["admin"])
    st.title("👑 Admin Dashboard")
    db = get_db_conn()

    with st.sidebar:
        st.markdown("### System")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.auth = {
                "logged_in": False, "role": None, "school_id": None,
                "user_id": None, "name": None, "session_id": None
            }
            st.rerun()
        st.divider()
        ts = db.execute("SELECT COUNT(*) FROM schools WHERE is_active=1").fetchone()[0]
        st.metric("Active Schools", ts)

    t1, t2 = st.tabs(["➕ Create School", "📚 Schools"])
    with t1:
        with st.form("create_school"):
            sid = st.text_input("School ID *")
            sname = st.text_input("School Name *")
            pw = st.text_input("Password *", type="password")
            years = st.number_input("Subscription Years", 1, 5, 1)
            if st.form_submit_button("✅ Create School", use_container_width=True):
                if not all([sid, sname, pw]):
                    st.error("Fill all required fields")
                elif len(pw) < 6:
                    st.error("Password too short")
                elif db.execute("SELECT 1 FROM schools WHERE id=?", (sid,)).fetchone():
                    st.error("School ID already exists")
                else:
                    exp = (datetime.now() + timedelta(days=365 * years)).strftime("%Y-%m-%d")
                    db.execute("""
                        INSERT INTO schools (id, name, pass, expiry, is_active)
                        VALUES (?,?,?,?,1)
                    """, (sid, sname, hash_pw(pw), exp))
                    db.commit()
                    st.success(f"✅ School '{sname}' created!")
                    st.balloons()
    with t2:
        schools = db.execute("SELECT * FROM schools WHERE is_active=1 ORDER BY created_at DESC").fetchall()
        for s in schools:
            with st.expander(f"🏫 {s['name']} ({s['id']})"):
                st.write(f"**Plan:** {s['plan']} | **Expires:** {s['expiry']}")
                if st.button("🗑️ Deactivate", key=f"del_{s['id']}"):
                    db.execute("UPDATE schools SET is_active=0 WHERE id=?", (s['id'],))
                    db.commit()
                    st.rerun()

# =================== SHARED SIDEBAR ===================
def school_sidebar():
    auth = st.session_state.auth
    with st.sidebar:
        st.markdown(f"### {auth['name']}")
        st.caption(f"Role: {auth['role'].upper()}")
        st.divider()
        menu = st.radio("Menu", [
            "📊 Dashboard", "👨‍🏫 Teachers", "🏫 Classes & Programs",
            "👶 Students", "📋 Attendance", "📊 Reports", "🧸 Care Logs"
        ])
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            if auth.get("session_id"):
                logout_teacher_session(auth["session_id"])
            st.session_state.auth = {
                "logged_in": False, "role": None, "school_id": None,
                "user_id": None, "name": None, "session_id": None
            }
            st.rerun()
    return menu

# =================== DASHBOARD ===================
def show_dashboard(sid):
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
def show_teachers(sid):
    require_auth(["head"])
    db = get_db_conn()
    st.header("👨‍🏫 Teacher Management")

    with st.expander("➕ Add Teacher (Head Only)"):
        with st.form("add_teacher"):
            tname = st.text_input("Teacher Name *")
            tphone = st.text_input("Phone Number *")
            tpw = st.text_input("Temporary Password *", type="password")
            if st.form_submit_button("✅ Add Teacher"):
                if not all([tname, tphone, tpw]):
                    st.error("Fill all fields")
                elif len(tpw) < 6:
                    st.error("Password too short")
                elif db.execute("SELECT 1 FROM teachers WHERE phone=?", (tphone,)).fetchone():
                    st.error("Phone already exists")
                else:
                    db.execute("""
                        INSERT INTO teachers (id, school_id, name, phone, pass)
                        VALUES (?,?,?,?,?)
                    """, (gen_id(), sid, sanitize(tname), sanitize(tphone), hash_pw(tpw)))
                    db.commit()
                    st.success(f"✅ Teacher {tname} added!")
                    st.balloons()

    st.divider()
    st.subheader("📋 Teachers List")
    teachers = db.execute("SELECT * FROM teachers WHERE school_id=? AND is_active=1", (sid,)).fetchall()
    for t in teachers:
        cols = st.columns([3, 2, 2, 1])
        cols[0].write(f"**{t['name']}**")
        cols[1].write(f"📞 {t['phone']}")
        cols[2].write(f"Role: {t['role']}")
        if cols[3].button("🗑️ Remove", key=f"rmt_{t['id']}"):
            db.execute("UPDATE teachers SET is_active=0 WHERE id=?", (t['id'],))
            db.commit()
            st.rerun()

    st.info("💡 **Invite System:** Share your **School ID** with teachers. They can register via Teacher Login → 'New Teacher? Register'.")

# =================== CLASSES & PROGRAMS ===================
def show_classes_programs(sid):
    db = get_db_conn()
    st.header("🏫 Classes & Programs")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📚 Classes")
        with st.form("add_class"):
            cname = st.text_input("Class Name *", placeholder="Nursery, Grade 1...")
            csec = st.text_input("Section", placeholder="A, B, Morning...")
            if st.form_submit_button("➕ Add Class"):
                if cname:
                    db.execute("INSERT INTO classes (id, class_name, section, school_id) VALUES (?,?,?,?)",
                               (gen_id(), sanitize(cname), sanitize(csec), sid))
                    db.commit()
                    st.success(f"✅ Class {cname} {csec} added!")
                else:
                    st.error("Class name required")

        classes = db.execute("SELECT * FROM classes WHERE school_id=? AND is_active=1 ORDER BY class_name", (sid,)).fetchall()
        for c in classes:
            sc = db.execute("SELECT COUNT(*) FROM students WHERE class_id=? AND is_active=1", (c['id'],)).fetchone()[0]
            cols = st.columns([3, 1, 1])
            cols[0].write(f"**{c['class_name']} {c['section'] or ''}** ({sc} students)")
            cols[1].write(f"ID: `{c['id'][:6]}`")
            if cols[2].button("🗑️", key=f"delc_{c['id']}"):
                if sc == 0:
                    db.execute("DELETE FROM classes WHERE id=?", (c['id'],))
                    db.commit()
                    st.rerun()
                else:
                    st.error("Class has students!")

    with c2:
        st.subheader("📋 Programs (Auto-Assign Class)")
        classes = db.execute("SELECT * FROM classes WHERE school_id=? AND is_active=1", (sid,)).fetchall()
        if not classes:
            st.warning("Create classes first!")
        else:
            class_opts = {f"{c['class_name']} {c['section'] or ''}".strip(): c['id'] for c in classes}
            with st.form("add_program"):
                pname = st.text_input("Program Name *", placeholder="Playgroup, Daycare...")
                pclass = st.selectbox("Assign to Class *", list(class_opts.keys()))
                if st.form_submit_button("➕ Add Program"):
                    if pname:
                        db.execute("INSERT INTO programs (id, program_name, class_id, school_id) VALUES (?,?,?,?)",
                                   (gen_id(), sanitize(pname), class_opts[pclass], sid))
                        db.commit()
                        st.success(f"✅ Program {pname} linked to {pclass}!")
                    else:
                        st.error("Program name required")

            programs = db.execute("""
                SELECT p.*, c.class_name, c.section 
                FROM programs p JOIN classes c ON p.class_id=c.id 
                WHERE p.school_id=? AND p.is_active=1
            """, (sid,)).fetchall()
            for p in programs:
                cols = st.columns([3, 2, 1])
                cols[0].write(f"**{p['program_name']}**")
                cols[1].write(f"→ {p['class_name']} {p['section'] or ''}")
                if cols[2].button("🗑️", key=f"delp_{p['id']}"):
                    db.execute("DELETE FROM programs WHERE id=?", (p['id'],))
                    db.commit()
                    st.rerun()

# =================== STUDENTS ===================
def show_students(sid):
    db = get_db_conn()
    st.header("👶 Student Management")

    programs = db.execute("""
        SELECT p.*, c.class_name, c.section 
        FROM programs p JOIN classes c ON p.class_id=c.id 
        WHERE p.school_id=? AND p.is_active=1
    """, (sid,)).fetchall()
    prog_dict = {}
    for p in programs:
        label = f"{p['program_name']} → {p['class_name']} {p['section'] or ''}"
        prog_dict[label] = p

    t1, t2 = st.tabs(["➕ Add Student", "📋 Student List"])

    with t1:
        if not programs:
            st.warning("⚠️ Create Programs first in 'Classes & Programs' tab.")
        else:
            with st.form("add_student", clear_on_submit=True):
                st.subheader("Personal Information")
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Student Name *", placeholder="Full name")
                    mother = st.text_input("Mother's Name", placeholder="Mother's full name")
                    father = st.text_input("Father's Name", placeholder="Father's full name")
                    dob = st.date_input("Date of Birth", value=date(2020, 1, 1))
                    blood = st.selectbox("Blood Group", ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"])
                with c2:
                    prog_label = st.selectbox("Program Enrolled *", list(prog_dict.keys()))
                    phone = st.text_input("Phone Number", placeholder="Parent contact")
                    email = st.text_input("Email ID", placeholder="parent@email.com")
                    guardian = st.text_input("Guardian Name", placeholder="If different from parents")
                    likes = st.text_area("Likes / Interests", placeholder="Toys, games, food...")
                    dislikes = st.text_area("Dislikes", placeholder="Things the child dislikes")

                st.divider()
                st.subheader("📸 Profile Photo")
                photo_file = st.file_uploader("Upload from device or take photo", type=["jpg", "jpeg", "png"])
                if photo_file:
                    st.image(photo_file, width=150)

                if st.form_submit_button("✅ Register Student", use_container_width=True):
                    if not name or not prog_label:
                        st.error("Student Name and Program are required")
                    else:
                        prog = prog_dict[prog_label]
                        age = calc_age(dob.isoformat())
                        photo_b64 = compress_image(photo_file)

                        db.execute("""
                            INSERT INTO students 
                            (id, name, mother_name, father_name, dob, age, blood_group, program_id, class_id,
                             phone, email, guardian_name, likes, dislikes, school_id, is_active, profile_photo)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            gen_id(), sanitize(name), sanitize(mother), sanitize(father), dob.isoformat(), age, blood,
                            prog['id'], prog['class_id'], sanitize(phone), sanitize(email), sanitize(guardian),
                            sanitize(likes), sanitize(dislikes), sid, 1, photo_b64
                        ))
                        db.commit()
                        st.success(f"✅ {name} registered in {prog['program_name']} (Age: {age})!")
                        st.balloons()

    with t2:
        filter_prog = st.selectbox("Filter by Program", ["All Programs"] + list(prog_dict.keys()))
        q = """
            SELECT s.*, p.program_name, c.class_name, c.section
            FROM students s
            LEFT JOIN programs p ON s.program_id = p.id
            LEFT JOIN classes c ON s.class_id = c.id
            WHERE s.school_id=? AND s.is_active=1
        """
        params = [sid]
        if filter_prog != "All Programs":
            q += " AND s.program_id=?"
            params.append(prog_dict[filter_prog]['id'])
        q += " ORDER BY s.name"
        students = db.execute(q, tuple(params)).fetchall()

        if not students:
            st.info("No students found")
        else:
            st.write(f"**Total: {len(students)} students**")
            for s in students:
                with st.expander(f"👤 {s['name']} | {s['program_name'] or 'No Program'} | Age: {s['age'] or '?'}"):
                    c1, c2 = st.columns([1, 3])
                    with c1:
                        if s['profile_photo']:
                            try:
                                st.image(base64.b64decode(s['profile_photo']), width=140)
                            except:
                                st.write("📷")
                        else:
                            st.write("📷 No photo")
                    with c2:
                        st.write(f"**👩 Mother:** {s['mother_name'] or '-'} | **👨 Father:** {s['father_name'] or '-'}")
                        st.write(f"**🎂 DOB:** {s['dob'] or '-'} | **🩸 Blood:** {s['blood_group'] or '-'}")
                        st.write(f"**📱 Phone:** {s['phone'] or '-'} | **📧 Email:** {s['email'] or '-'}")
                        st.write(f"**👪 Guardian:** {s['guardian_name'] or '-'}")
                        st.write(f"**🏫 Class:** {s['class_name'] or '-'} {s['section'] or ''}")
                        st.write(f"**👍 Likes:** {s['likes'] or '-'}")
                        st.write(f"**👎 Dislikes:** {s['dislikes'] or '-'}")
                        if st.button("🗑️ Remove", key=f"rms_{s['id']}"):
                            db.execute("UPDATE students SET is_active=0 WHERE id=?", (s['id'],))
                            db.commit()
                            st.rerun()

# =================== ATTENDANCE ===================
def show_attendance(sid):
    db = get_db_conn()
    st.header("📋 Attendance with In/Out Time")

    classes = db.execute("SELECT * FROM classes WHERE school_id=? AND is_active=1", (sid,)).fetchall()
    if not classes:
        st.warning("Create classes first!")
        return

    class_opts = {f"{c['class_name']} {c['section'] or ''}".strip(): c['id'] for c in classes}

    t1, t2 = st.tabs(["📝 Mark Attendance", "📅 View by Date"])

    with t1:
        sel_class = st.selectbox("Select Class", list(class_opts.keys()), key="att_cls")
        att_date = st.date_input("Date", value=date.today(), key="att_dt")

        students = db.execute("""
            SELECT id, name, profile_photo FROM students 
            WHERE class_id=? AND school_id=? AND is_active=1 ORDER BY name
        """, (class_opts[sel_class], sid)).fetchall())

        if not students:
            st.info("No students in this class")
        else:
            existing = {r['student_id']: r for r in db.execute("""
                SELECT * FROM attendance WHERE date=? AND class_id=?
            """, (att_date.isoformat(), class_opts[sel_class])).fetchall()}

            with st.form("mark_att"):
                records = []
                for s in students:
                    cols = st.columns([2, 3, 2, 2, 3])
                    with cols[0]:
                        st.write(f"**{s['name']}**")
                    with cols[1]:
                        statuses = ["Present", "Absent", "Late", "Half Day"]
                        default = 0
                        if s['id'] in existing:
                            try:
                                default = statuses.index(existing[s['id']]['status'])
                            except:
                                pass
                        status = st.radio(f"st_{s['id']}", statuses, index=default,
                                        horizontal=True, label_visibility="collapsed", key=f"st_{s['id']}_{att_date}")
                    with cols[2]:
                        default_in = None
                        if s['id'] in existing and existing[s['id']]['in_time']:
                            try:
                                h, m = map(int, existing[s['id']]['in_time'].split(":"))
                                default_in = datetime.strptime(f"{h}:{m}", "%H:%M").time()
                            except:
                                pass
                        in_t = st.time_input("In", value=default_in, key=f"in_{s['id']}_{att_date}", label_visibility="collapsed")
                    with cols[3]:
                        default_out = None
                        if s['id'] in existing and existing[s['id']]['out_time']:
                            try:
                                h, m = map(int, existing[s['id']]['out_time'].split(":"))
                                default_out = datetime.strptime(f"{h}:{m}", "%H:%M").time()
                            except:
                                pass
                        out_t = st.time_input("Out", value=default_out, key=f"out_{s['id']}_{att_date}", label_visibility="collapsed")
                    with cols[4]:
                        note = st.text_input("Note", value=existing[s['id']]['notes'] if s['id'] in existing else "",
                                           key=f"nt_{s['id']}_{att_date}", label_visibility="collapsed", placeholder="Note")
                    records.append((s['id'], status, in_t, out_t, note))
                    st.divider()

                if st.form_submit_button("💾 Save Attendance", use_container_width=True):
                    db.execute("DELETE FROM attendance WHERE date=? AND class_id=?",
                               (att_date.isoformat(), class_opts[sel_class]))
                    for rid, stt, it, ot, nt in records:
                        its = str(it) if it else None
                        ots = str(ot) if ot else None
                        db.execute("""
                            INSERT INTO attendance (student_id, class_id, date, status, in_time, out_time, notes, marked_by)
                            VALUES (?,?,?,?,?,?,?,?)
                        """, (rid, class_opts[sel_class], att_date.isoformat(), stt, its, ots, nt, sid))
                    db.commit()
                    st.success(f"✅ Attendance saved for {len(records)} students!")
                    st.balloons()

    with t2:
        view_date = st.date_input("Select Date", value=date.today(), key="vdt")
        view_class = st.selectbox("Select Class", list(class_opts.keys()), key="vcls")
        recs = db.execute("""
            SELECT a.*, s.name, s.profile_photo FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.date=? AND a.class_id=? ORDER BY s.name
        """, (view_date.isoformat(), class_opts[view_class])).fetchall()

        if recs:
            for r in recs:
                em = {"Present": "✅", "Absent": "❌", "Late": "⏰", "Half Day": "⚠️"}.get(r['status'], "⬜")
                c1, c2, c3, c4 = st.columns([3, 2, 2, 3])
                c1.write(f"**{r['name']}**")
                c2.write(f"{em} {r['status']}")
                io_str = []
                if r['in_time']:
                    io_str.append(f"In: {r['in_time'][:5]}")
                if r['out_time']:
                    io_str.append(f"Out: {r['out_time'][:5]}")
                c3.write(" | ".join(io_str) if io_str else "-")
                c4.write(f"📝 {r['notes']}" if r['notes'] else "")
        else:
            st.info("No attendance marked for this date")

# =================== REPORTS ===================
def show_reports(sid):
    db = get_db_conn()
    st.header("📊 Attendance Reports")

    classes = db.execute("SELECT * FROM classes WHERE school_id=? AND is_active=1", (sid,)).fetchall()
    if not classes:
        st.warning("No classes available")
        return
    class_opts = {f"{c['class_name']} {c['section'] or ''}".strip(): c['id'] for c in classes}

    t1, t2 = st.tabs(["📅 Monthly Report", "📆 Yearly Report"])

    with t1:
        c1, c2, c3 = st.columns([2, 2, 2])
        with c1:
            sel_cls = st.selectbox("Class", list(class_opts.keys()), key="rcls")
        with c2:
            sel_month = st.selectbox("Month", list(calendar.month_name)[1:], key="rmon")
        with c3:
            sel_year = st.selectbox("Year", list(range(datetime.now().year, datetime.now().year - 5, -1)), key="ryr")

        month_num = list(calendar.month_name).index(sel_month)
        start_d = f"{sel_year}-{month_num:02d}-01"
        last_day = calendar.monthrange(sel_year, month_num)[1]
        end_d = f"{sel_year}-{month_num:02d}-{last_day}"

        wd_row = db.execute("""
            SELECT COUNT(DISTINCT date) FROM attendance 
            WHERE class_id=? AND date BETWEEN ? AND ?
        """, (class_opts[sel_cls], start_d, end_d)).fetchone()[0]

        students = db.execute("""
            SELECT id, name FROM students WHERE class_id=? AND school_id=? AND is_active=1 ORDER BY name
        """, (class_opts[sel_cls], sid)).fetchall()

        st.subheader(f"📋 {sel_cls} — {sel_month} {sel_year}")
        st.caption(f"**Working Days in Month:** {wd_row}")

        if students:
            data = []
            for s in students:
                stats = db.execute("""
                    SELECT 
                        SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as present,
                        SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) as absent,
                        SUM(CASE WHEN status='Late' THEN 1 ELSE 0 END) as late,
                        SUM(CASE WHEN status='Half Day' THEN 1 ELSE 0 END) as half_day,
                        COUNT(*) as total_days
                    FROM attendance
                    WHERE student_id=? AND date BETWEEN ? AND ?
                """, (s['id'], start_d, end_d)).fetchone()
                data.append({
                    "Name": s['name'],
                    "Working Days": wd_row,
                    "Present": stats['present'] or 0,
                    "Absent": stats['absent'] or 0,
                    "Late": stats['late'] or 0,
                    "Half Day": stats['half_day'] or 0,
                    "Total Marked": stats['total_days'] or 0
                })
            st.dataframe(data, use_container_width=True)
        else:
            st.info("No students in this class")

    with t2:
        c1, c2 = st.columns([2, 2])
        with c1:
            y_cls = st.selectbox("Class", list(class_opts.keys()), key="ycls")
        with c2:
            y_year = st.selectbox("Year", list(range(datetime.now().year, datetime.now().year - 5, -1)), key="yyr")

        y_start = f"{y_year}-01-01"
        y_end = f"{y_year}-12-31"

        y_wd = db.execute("""
            SELECT COUNT(DISTINCT date) FROM attendance 
            WHERE class_id=? AND date BETWEEN ? AND ?
        """, (class_opts[y_cls], y_start, y_end)).fetchone()[0]

        y_students = db.execute("""
            SELECT id, name FROM students WHERE class_id=? AND school_id=? AND is_active=1 ORDER BY name
        """, (class_opts[y_cls], sid)).fetchall()

        st.subheader(f"📋 {y_cls} — Year {y_year}")
        st.caption(f"**Working Days in Year:** {y_wd}")

        if y_students:
            y_data = []
            for s in y_students:
                stats = db.execute("""
                    SELECT 
                        SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as present,
                        SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) as absent,
                        SUM(CASE WHEN status='Late' THEN 1 ELSE 0 END) as late,
                        SUM(CASE WHEN status='Half Day' THEN 1 ELSE 0 END) as half_day,
                        COUNT(*) as total_days
                    FROM attendance
                    WHERE student_id=? AND date BETWEEN ? AND ?
                """, (s['id'], y_start, y_end)).fetchone()
                y_data.append({
                    "Name": s['name'],
                    "Working Days": y_wd,
                    "Present": stats['present'] or 0,
                    "Absent": stats['absent'] or 0,
                    "Late": stats['late'] or 0,
                    "Half Day": stats['half_day'] or 0,
                    "Total Marked": stats['total_days'] or 0
                })
            st.dataframe(y_data, use_container_width=True)
        else:
            st.info("No students in this class")

# =================== CARE LOGS ===================
def show_care_logs(sid):
    db = get_db_conn()
    st.header("🧸 Care Logs")
    students = db.execute("SELECT id, name FROM students WHERE school_id=? AND is_active=1 ORDER BY name", (sid,)).fetchall()
    if not students:
        st.warning("No active students")
        return
    stu_dict = {s['name']: s['id'] for s in students}

    t1, t2 = st.tabs(["➕ New Log", "📋 Today's Logs"])

    with t1:
        sel_stu = st.selectbox("Select Student", list(stu_dict.keys()))
        log_type = st.selectbox("Activity Type", [
            "Breakfast", "Lunch", "Diaper Change", "Pee", "Potty", "Naptime", "Daycare", "Activity"
        ])

        if log_type in ["Breakfast", "Lunch"]:
            with st.form(f"log_{log_type}"):
                portion = st.selectbox("Consumption", ["Full", "Half", "Little", "Refused"])
                notes = st.text_area("Notes")
                if st.form_submit_button("💾 Save"):
                    db.execute("""
                        INSERT INTO care_logs (id, student_id, student_name, activity, notes, school_id, type, sub_type, status)
                        VALUES (?,?,?,?,?,?,?,?,?)
                    """, (gen_id(), stu_dict[sel_stu], sel_stu, log_type, notes, sid, "food", log_type.lower(), portion))
                    db.commit()
                    st.success("✅ Saved!")

        elif log_type in ["Diaper Change", "Pee", "Potty"]:
            with st.form(f"log_{log_type}"):
                notes = st.text_area("Notes")
                if st.form_submit_button("💾 Save"):
                    db.execute("""
                        INSERT INTO care_logs (id, student_id, student_name, activity, notes, school_id, type, sub_type)
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (gen_id(), stu_dict[sel_stu], sel_stu, log_type, notes, sid, "bathroom", log_type.lower().replace(" ", "_")))
                    db.commit()
                    st.success("✅ Saved!")

        elif log_type == "Naptime":
            with st.form("log_nap"):
                start = st.time_input("Nap Start")
                end = st.time_input("Nap End")
                notes = st.text_area("Notes")
                if st.form_submit_button("💾 Save"):
                    db.execute("""
                        INSERT INTO care_logs (id, student_id, student_name, activity, notes, school_id, type, start_time, end_time)
                        VALUES (?,?,?,?,?,?,?,?,?)
                    """, (gen_id(), stu_dict[sel_stu], sel_stu, "Naptime", notes, sid, "nap", str(start), str(end)))
                    db.commit()
                    st.success("✅ Saved!")

        elif log_type in ["Daycare", "Activity"]:
            with st.form(f"log_{log_type}"):
                notes = st.text_area("Notes / Details")
                if st.form_submit_button("💾 Save"):
                    db.execute("""
                        INSERT INTO care_logs (id, student_id, student_name, activity, notes, school_id, type)
                        VALUES (?,?,?,?,?,?,?)
                    """, (gen_id(), stu_dict[sel_stu], sel_stu, log_type, notes, sid, log_type.lower()))
                    db.commit()
                    st.success("✅ Saved!")

    with t2:
        logs = db.execute("""
            SELECT * FROM care_logs 
            WHERE school_id=? AND date(time)=date('now')
            ORDER BY time DESC
        """, (sid,)).fetchall()
        if not logs:
            st.info("No logs recorded today")
        else:
            for l in logs:
                emoji = {"food": "🍽️", "bathroom": "🚽", "nap": "😴", "daycare": "🏠", "activity": "🎨"}.get(l['type'], "📝")
                st.markdown(f"{emoji} **{l['student_name']}** — {l['activity']} at {l['time'][11:16]}")
                if l['status']:
                    st.caption(f"Status: {l['status']}")
                if l['notes']:
                    st.caption(f"Note: {l['notes']}")

# =================== MAIN ROUTER ===================
def school_page():
    require_auth(["head", "teacher"])
    sid = st.session_state.auth["school_id"]
    menu = school_sidebar()

    if menu == "📊 Dashboard":
        show_dashboard(sid)
    elif menu == "👨‍🏫 Teachers":
        show_teachers(sid)
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

def main():
    if not st.session_state.auth["logged_in"]:
        login_page()
    elif st.session_state.auth["role"] == "admin":
        admin_page()
    else:
        school_page()

    st.divider()
    st.caption("SchoolOS Pro — Phase 2 | Multi-User | Attendance | Auto-Class | Care Logs")

if __name__ == "__main__":
    main()
