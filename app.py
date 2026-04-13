import streamlit as st
import json, os, uuid
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
st.set_page_config(page_title="SchoolOS Pro", layout="wide")

# ---------------- DATABASE ----------------
def load_db(file, default):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump(default, f)
    with open(file, "r") as f:
        return json.load(f)

def save_db(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

schools_db = load_db("schools.json", {})
students_db = load_db("students.json", [])
broadcasts = load_db("broadcasts.json", [])

# ---------------- PRICING ----------------
PLAN_LIMITS = {
    "Basic": 30,
    "Standard": 80,
    "Premium": 500,
    "Enterprise": float('inf')
}

PLAN_PRICES = {
    "Basic": 2000,
    "Standard": 4000,
    "Premium": 7999,
    "Enterprise": 9999
}

# ---------------- SESSION ----------------
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}

# ---------------- LOGIN ----------------
if not st.session_state.auth["logged_in"]:
    st.title("🏫 SchoolOS Pro Login")

    user = st.text_input("User ID")
    pw = st.text_input("Password", type="password")

    if st.button("Login"):
        if user == "admin" and pw == "admin123":
            st.session_state.auth = {"logged_in": True, "role": "admin"}
            st.rerun()

        elif user in schools_db and schools_db[user]["pass"] == pw:
            expiry = datetime.strptime(schools_db[user]["expiry"], "%Y-%m-%d")

            if datetime.now() < expiry:
                st.session_state.auth = {
                    "logged_in": True,
                    "role": "school",
                    "school_id": user
                }
                st.rerun()
            else:
                st.error("Subscription expired")

# ---------------- MAIN APP ----------------
else:

    if st.sidebar.button("Logout"):
        st.session_state.auth = {"logged_in": False, "role": None, "school_id": None}
        st.rerun()

    # ================= ADMIN =================
    if st.session_state.auth["role"] == "admin":
        st.title("👑 Admin Dashboard")

        tab1, tab2 = st.tabs(["➕ Add School", "📢 Broadcast"])

        with tab1:
            st.subheader("Create New School")

            sid = st.text_input("School ID")
            name = st.text_input("School Name")
            pw = st.text_input("Password")
            plan = st.selectbox("Plan", list(PLAN_LIMITS.keys()))

            if st.button("Create School"):
                expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

                schools_db[sid] = {
                    "name": name,
                    "pass": pw,
                    "plan": plan,
                    "expiry": expiry,
                    "extra_students": 0
                }

                save_db("schools.json", schools_db)
                st.success("✅ School created successfully!")

        with tab2:
            msg = st.text_area("Send message to all schools")

            if st.button("Send Broadcast"):
                broadcasts.append({"msg": msg, "date": str(datetime.now())})
                save_db("broadcasts.json", broadcasts)
                st.success("📢 Broadcast sent!")

    # ================= SCHOOL =================
    elif st.session_state.auth["role"] == "school":

        sid = st.session_state.auth["school_id"]
        school = schools_db[sid]

        st.title(f"🏫 {school['name']} Dashboard")

        # ---- PLAN INFO ----
        base_limit = PLAN_LIMITS[school["plan"]]
        extra = school.get("extra_students", 0)
        max_students = base_limit if base_limit == float('inf') else base_limit + (extra * 50)

        school_students = [s for s in students_db if s["school_id"] == sid]

        st.sidebar.markdown("### 📊 Plan Info")
        st.sidebar.info(f"""
Plan: {school['plan']}
Students: {len(school_students)} / {max_students}
        """)

        menu = st.sidebar.selectbox("Menu", ["Dashboard", "Students", "Upgrade"])

        # -------- DASHBOARD --------
        if menu == "Dashboard":
            st.subheader("📊 Overview")

            col1, col2 = st.columns(2)
            col1.metric("Total Students", len(school_students))
            col2.metric("Current Plan", school["plan"])

            if broadcasts:
                st.warning(f"📢 {broadcasts[-1]['msg']}")

        # -------- STUDENTS --------
        elif menu == "Students":
            st.subheader("👨‍🎓 Manage Students")

            with st.form("student_form"):
                name = st.text_input("Student Name")
                blood = st.selectbox("Blood Group", ["O+", "A+", "B+", "AB+"])
                allergy = st.text_input("Allergies")

                submitted = st.form_submit_button("➕ Add Student")

                if submitted:
                    if len(school_students) >= max_students:
                        st.error("⚠️ Limit reached! Upgrade plan.")
                    else:
                        exists = any(
                            s["name"].lower() == name.lower() and s["school_id"] == sid
                            for s in students_db
                        )

                        if exists:
                            st.warning("⚠️ Student already exists!")
                        else:
                            students_db.append({
                                "id": str(uuid.uuid4()),
                                "name": name,
                                "blood": blood,
                                "allergy": allergy,
                                "school_id": sid
                            })
                            save_db("students.json", students_db)
                            st.success("✅ Student added!")

            st.write("### 📋 Student List")

            for s in school_students:
                col1, col2 = st.columns([4,1])
                col1.write(f"{s['name']} ({s['blood']})")

                if col2.button("❌", key=s["id"]):
                    students_db = [stu for stu in students_db if stu["id"] != s["id"]]
                    save_db("students.json", students_db)
                    st.rerun()

        # -------- UPGRADE --------
        elif menu == "Upgrade":
            st.subheader("💰 Upgrade Plan")

            for plan, price in PLAN_PRICES.items():
                st.write(f"**{plan}** - ₹{price}")

            new_plan = st.selectbox("Choose Plan", list(PLAN_LIMITS.keys()))

            if st.button("Upgrade"):
                school["plan"] = new_plan
                save_db("schools.json", schools_db)
                st.success("✅ Plan upgraded!")

            st.write("### ➕ Add Student Capacity")

            add_option = st.selectbox("Add", ["+50", "+100"])

            if st.button("Add Capacity"):
                if add_option == "+50":
                    school["extra_students"] += 1
                else:
                    school["extra_students"] += 2

                save_db("schools.json", schools_db)
                st.success("✅ Capacity updated!")
                
