import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import json

# Initialize Streamlit Page Settings
st.set_page_config(
    page_title="EduSphere | Autonomous Multi-Tenant LMS",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# CRITICAL CREDENTIALS & INITIALIZATION
# -----------------------------------------------------------------------------
if "GEMINI_API_KEY" not in st.secrets or "SUPABASE_DB_URL" not in st.secrets:
    st.error("❌ Critical configuration missing! Please ensure GEMINI_API_KEY and SUPABASE_DB_URL are defined in secrets.")
    st.stop()

# Initialize Google GenAI Client
from google import genai
from google.genai import types

ai_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
DB_URL = st.secrets["SUPABASE_DB_URL"]

def get_db_connection():
    """Establishes and returns a thread-safe cursor connection to Neon PostgreSQL."""
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        st.error(f"⚠️ Cloud Database Connection Failed: {e}")
        st.stop()

def hash_password(password: str) -> str:
    """Hashes passwords securely using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

# -----------------------------------------------------------------------------
# GLOBAL REAL-TIME AI TRANSLATION ENGINE
# -----------------------------------------------------------------------------
def ai_translate(text: str, target_lang: str) -> str:
    """Translates UI text parameters dynamically into the target language using Gemini."""
    if not text or target_lang == "English":
        return text
    
    # Simple semantic cache mechanism to prevent redundant API token burn on static elements
    cache_key = f"trans_{hashlib.md5(text.encode()).hexdigest()}_{target_lang}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
        
    try:
        prompt = f"Translate the following software UI text or documentation into {target_lang}. Preserve all formatting, markdown symbols, spacing, and bracket keys like [Username]. Output ONLY the translated result without any commentary:\n\n{text}"
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="You are an expert software localization tool. Translate the text accurately, keeping developer brackets intact."
            )
        )
        translated_text = response.text.strip()
        st.session_state[cache_key] = translated_text
        return translated_text
    except Exception:
        return text # Soft fallback to original English if network drops during presentation

def init_db():
    """Initializes schema and injects emergency fallback accounts if missing."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        # Create Users
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                subject TEXT
            );
        """)
        # Create Students
        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id TEXT NOT NULL,
                teacher_username TEXT NOT NULL,
                student_name TEXT NOT NULL,
                grade_cohort TEXT NOT NULL,
                subject TEXT NOT NULL,
                PRIMARY KEY (student_name, teacher_username)
            );
        """)
        # Create Lessons
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id SERIAL PRIMARY KEY,
                teacher_username TEXT NOT NULL,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                content TEXT NOT NULL
            );
        """)
        # Create Worksheets
        cur.execute("""
            CREATE TABLE IF NOT EXISTS worksheets (
                id SERIAL PRIMARY KEY,
                teacher_username TEXT NOT NULL,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                content TEXT NOT NULL
            );
        """)
        # Create Grades / Submissions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grades (
                id SERIAL PRIMARY KEY,
                teacher_username TEXT NOT NULL,
                student_name TEXT NOT NULL,
                subject TEXT NOT NULL,
                task_name TEXT NOT NULL,
                mark INTEGER,
                feedback TEXT,
                student_submission TEXT
            );
        """)
        
        # Gimmick: Inject Fallback Administrative Account
        cur.execute("SELECT COUNT(*) FROM users;")
        if cur.fetchone()['count'] == 0:
            fallback_hash = hash_password("admin123")
            cur.execute("""
                INSERT INTO users (username, password_hash, role, subject) 
                VALUES ('admin', %s, 'Teacher', 'General Science');
            """, (fallback_hash,))
            
        conn.commit()
    conn.close()

# Invoke system database build out
init_db()

# Session State Setup
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.subject = None

# -----------------------------------------------------------------------------
# GLOBAL APPLICATION SIDEBAR CONTROL
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🌐 Global Localization Suite")
    target_lang = st.selectbox(
        "Select Webpage Interface Language",
        ["English", "Spanish (Español)", "French (Français)", "German (Deutsch)", "Mandarin (中文)", "Hindi (हिन्दी)", "Arabic (العربية)", "Japanese (日本語)", "Russian (Русский)", "Portuguese (Português)"]
    )
    st.markdown("---")

# -----------------------------------------------------------------------------
# AUTHENTICATION GATEWAY & SESSION MANAGEMENT
# -----------------------------------------------------------------------------
if not st.session_state.authenticated:
    st.title(ai_translate("🏫 EduSphere Core Management Portal", target_lang))
    st.markdown(ai_translate("Welcome to the unified Multi-Tenant Classroom Platform. Please sign in or register to connect to your cloud dashboard.", target_lang))
    
    tab_signin, tab_register = st.tabs([ai_translate("🔑 Account Sign-In", target_lang), ai_translate("📝 Account Registration", target_lang)])
    
    with tab_signin:
        with st.form("signin_form"):
            user_input = st.text_input(ai_translate("Username", target_lang)).strip()
            pass_input = st.text_input(ai_translate("Password", target_lang), type="password")
            btn_signin = st.form_submit_button(ai_translate("Authenticate Access", target_lang), use_container_width=True)
            
            if btn_signin:
                if user_input and pass_input:
                    conn = get_db_connection()
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM users WHERE username = %s;", (user_input,))
                        user_record = cur.fetchone()
                    conn.close()
                    
                    if user_record and user_record['password_hash'] == hash_password(pass_input):
                        st.session_state.authenticated = True
                        st.session_state.username = user_record['username']
                        st.session_state.role = user_record['role']
                        st.session_state.subject = user_record['subject']
                        st.success(ai_translate("Authentication successful! Loading workspace...", target_lang))
                        st.rerun()
                    else:
                        st.error(ai_translate("Invalid credentials or user record missing.", target_lang))
                else:
                    st.warning(ai_translate("Please supply both tracking components.", target_lang))
                    
    with tab_register:
        with st.form("registration_form"):
            reg_user = st.text_input(ai_translate("Create Username", target_lang)).strip()
            reg_pass = st.text_input(ai_translate("Secure Password", target_lang), type="password")
            reg_role = st.selectbox(ai_translate("Institutional Role Persona", target_lang), ["Teacher", "Student"])
            reg_subject = st.selectbox(
                ai_translate("Teaching Assignment Domain (Teachers Only)", target_lang),
                ["Mathematics", "General Science", "English Language Arts", "Social Studies / Humanities", "Computer Science"]
            )
            
            btn_register = st.form_submit_button(ai_translate("Deploy Global Tenant", target_lang), use_container_width=True)
            
            if btn_register:
                if not reg_user or not reg_pass:
                    st.error(ai_translate("Username and Password credentials cannot be left blank.", target_lang))
                else:
                    conn = get_db_connection()
                    with conn.cursor() as cur:
                        cur.execute("SELECT username FROM users WHERE username = %s;", (reg_user,))
                        exists = cur.fetchone()
                        
                        if exists:
                            st.error(ai_translate("This registration profile name already exists on this server cluster.", target_lang))
                        else:
                            assigned_subject = reg_subject if reg_role == "Teacher" else "Student Framework"
                            hashed_w = hash_password(reg_pass)
                            cur.execute("""
                                INSERT INTO users (username, password_hash, role, subject)
                                VALUES (%s, %s, %s, %s);
                            """, (reg_user, hashed_w, reg_role, assigned_subject))
                            conn.commit()
                            st.success(ai_translate("Tenant deployed! Switch tabs to login securely.", target_lang))
                    conn.close()
    st.stop()

# -----------------------------------------------------------------------------
# GLOBAL PLATFORM SIDEBAR & PROFILE SYNC
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"### 👤 {ai_translate('Profile Session', target_lang)}: **{st.session_state.username}**")
    st.caption(f"🛡️ {ai_translate('Role', target_lang)}: {ai_translate(st.session_state.role, target_lang)}")
    if st.session_state.role == "Teacher":
        st.info(f"📚 {ai_translate('Dept', target_lang)}: {ai_translate(st.session_state.subject, target_lang)}")
    
    st.markdown("---")
    
    if st.button(ai_translate("Log Out Securely", target_lang), use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.subject = None
        st.rerun()

# -----------------------------------------------------------------------------
# PERSONA 1 — TEACHER COMPREHENSIVE WORKSPACE
# -----------------------------------------------------------------------------
if st.session_state.role == "Teacher":
    with st.sidebar:
        workspace_view = st.radio(
            ai_translate("Navigate Cloud Workspace", target_lang),
            ["Classroom Roster", "AI Lesson Architect", "AI Worksheet Factory", "AI Evaluator & Gradebook Ledger", "📊 Student Advanced Analytics"]
        )

    st.title(f"🍎 {ai_translate('Master Workspace — Core Field', target_lang)}: {ai_translate(st.session_state.subject, target_lang)}")
    
    if workspace_view == "Classroom Roster":
        st.header(ai_translate("👥 Connected Active Roster Matrix", target_lang))
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, student_name, grade_cohort, subject 
                FROM students WHERE teacher_username = %s;
            """, (st.session_state.username,))
            roster_data = cur.fetchall()
        conn.close()
        
        if roster_data:
            st.dataframe(roster_data, use_container_width=True)
        else:
            st.warning(ai_translate("No active student trackers currently registered to this tenant environment.", target_lang))
            
    elif workspace_view == "AI Lesson Architect":
        st.header(ai_translate("🧠 AI Curriculum Engine — 5E Lesson Plan Architect", target_lang))
        topic = st.text_input(ai_translate("Enter Topic (e.g., Quantum Mechanics Fundamental Principles, Mitosis)", target_lang))
        grade_tier = st.selectbox(ai_translate("Target Cohort Level", target_lang), ["Grade 6-8 Middle School", "Grade 9-12 High School", "Undergraduate Ivy-League"])
        
        if st.button(ai_translate("Synthesize Lesson Curriculum", target_lang), use_container_width=True):
            with st.spinner(ai_translate("AI Engine Processing Cloud Stream...", target_lang)):
                prompt = f"Design an exhaustive, comprehensive 5E lesson plan for '{topic}' target cohort '{grade_tier}' specializing inside '{st.session_state.subject}' environment rules."
                try:
                    response = ai_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction="You are an Elite Curriculum Instructional Designer. Generate output with precise pedagogical terminology using the 5E method."
                        )
                    )
                    st.session_state.current_lesson = response.text
                except Exception as e:
                    st.error(f"LLM Engine Disconnection: {e}")
                    
        if "current_lesson" in st.session_state:
            translated_lesson = ai_translate(st.session_state.current_lesson, target_lang)
            edited_content = st.text_area(ai_translate("Review/Modify Architectural Output Content", target_lang), value=translated_lesson, height=400)
            if st.button(ai_translate("Save Finished Lesson to Cloud Workspace", target_lang), use_container_width=True):
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO lessons (teacher_username, subject, topic, content)
                        VALUES (%s, %s, %s, %s);
                    """, (st.session_state.username, st.session_state.subject, topic, edited_content))
                    conn.commit()
                conn.close()
                st.success(ai_translate(f"Successfully published '{topic}' to cloud database records!", target_lang))

    elif workspace_view == "AI Worksheet Factory":
        st.header(ai_translate("📝 AI Worksheet Factory & Key Generator", target_lang))
        w_topic = st.text_input(ai_translate("Target Assessment Objective or Focus Unit", target_lang))
        
        if st.button(ai_translate("Generate Master Assessment Artifact", target_lang), use_container_width=True):
            with st.spinner(ai_translate("Compiling structured query rules...", target_lang)):
                prompt = f"Create a rigorous 5-question conceptual assessment worksheet regarding '{w_topic}' for a course in '{st.session_state.subject}'. At the very bottom, append a distinct section clearly titled '--- ANSWER KEY ---' containing model answers."
                try:
                    response = ai_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction="You are an Elite Curriculum Instructional Designer. Always append a clear and explicit '--- ANSWER KEY ---' section at the end of every worksheet."
                        )
                    )
                    st.session_state.current_worksheet = response.text
                except Exception as e:
                    st.error(f"LLM Fault: {e}")
                    
        if "current_worksheet" in st.session_state:
            translated_worksheet = ai_translate(st.session_state.current_worksheet, target_lang)
            w_edited = st.text_area(ai_translate("Edit Worksheet System Content", target_lang), value=translated_worksheet, height=400)
            if st.button(ai_translate("Commit Worksheet to Cloud", target_lang), use_container_width=True):
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO worksheets (teacher_username, subject, topic, content)
                        VALUES (%s, %s, %s, %s);
                    """, (st.session_state.username, st.session_state.subject, w_topic, w_edited))
                    conn.commit()
                conn.close()
                st.success(ai_translate(f"Worksheet committed securely under '{w_topic}' assignment keys.", target_lang))

    elif workspace_view == "AI Evaluator & Gradebook Ledger":
        st.header(ai_translate("🗃️ Complete Submissions Hub & Manual Evaluation Review", target_lang))
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, student_name, subject, task_name, mark, feedback, student_submission 
                FROM grades WHERE teacher_username = %s;
            """, (st.session_state.username,))
            grades_records = cur.fetchall()
        conn.close()
        
        if grades_records:
            for record in grades_records:
                with st.expander(f"📋 {ai_translate('Record ID', target_lang)}: {record['id']} | {ai_translate('Student', target_lang)}: {record['student_name']} — {ai_translate('Task', target_lang)}: {record['task_name']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**{ai_translate('Earned Score Parameter', target_lang)}:** `{record['mark']}/100`")
                        st.text_area(ai_translate("Raw Text Student Input Log", target_lang), record['student_submission'], disabled=True, key=f"sub_{record['id']}")
                    with col2:
                        st.markdown(f"**{ai_translate('Diagnostic AI Evaluator Commentary Feedback', target_lang)}:**")
                        st.info(ai_translate(record['feedback'], target_lang))
        else:
            st.info(ai_translate("No logs present inside tracking matrices.", target_lang))

    elif workspace_view == "📊 Student Advanced Analytics":
        st.header(ai_translate("📈 Management Command Grid & Metrics Engine", target_lang))
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM students WHERE teacher_username = %s;", (st.session_state.username,))
            total_students = cur.fetchone()['count']
            cur.execute("SELECT avg(mark) FROM grades WHERE teacher_username = %s;", (st.session_state.username,))
            class_mean = cur.fetchone()['avg'] or 0.0
            cur.execute("SELECT count(*) FROM worksheets WHERE teacher_username = %s;", (st.session_state.username,))
            published_tasks = cur.fetchone()['count']
            cur.execute("""
                SELECT student_name, avg(mark) as avg_mark, max(mark) as max_mark, count(mark) as completed 
                FROM grades WHERE teacher_username = %s GROUP BY student_name;
            """, (st.session_state.username,))
            aggregate_df = cur.fetchall()
            cur.execute("SELECT topic, id FROM worksheets WHERE teacher_username = %s;", (st.session_state.username,))
            all_ws = cur.fetchall()
            cur.execute("SELECT task_name, avg(mark) as task_avg FROM grades WHERE teacher_username = %s GROUP BY task_name;", (st.session_state.username,))
            chart_records = cur.fetchall()
        conn.close()
        
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric(ai_translate("Total Roster Size", target_lang), f"{total_students} {ai_translate('Enrolled', target_lang)}")
        m_col2.metric(ai_translate("Class Running Grade Mean", target_lang), f"{float(class_mean):.2f}%")
        m_col3.metric(ai_translate("Published Assignments", target_lang), f"{published_tasks} {ai_translate('Live Sheets', target_lang)}")
        
        st.subheader(ai_translate("📚 Analytics Consolidated Roster Dataframe", target_lang))
        if aggregate_df:
            st.dataframe(aggregate_df, use_container_width=True)
        else:
            st.warning(ai_translate("Insufficient structural data to load runtime matrix aggregates.", target_lang))
            
        st.subheader(ai_translate("📊 Individual Assignment Metric Trends", target_lang))
        if chart_records:
            chart_dict = {r['task_name']: float(r['task_avg']) for r in chart_records}
            st.bar_chart(chart_dict)
            
        st.subheader(ai_translate("🔍 Tracking Matrix Filter Matrix Sync", target_lang))
        if all_ws:
            selected_ws = st.selectbox(ai_translate("Select Target Assignment Audit Check", target_lang), [w['topic'] for w in all_ws])
            
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT student_name FROM grades WHERE teacher_username = %s AND task_name = %s;", (st.session_state.username, selected_ws))
                completed_list = [r['student_name'] for r in cur.fetchall()]
                cur.execute("SELECT student_name FROM students WHERE teacher_username = %s;", (st.session_state.username,))
                all_rostered = [r['student_name'] for r in cur.fetchall()]
            conn.close()
            
            pending_list = list(set(all_rostered) - set(completed_list))
            
            c_done, c_pending = st.columns(2)
            with c_done:
                st.success(ai_translate("✔️ Finished Submission Roster", target_lang))
                for s in completed_list:
                    st.markdown(f"- **{s}**")
            with c_pending:
                st.error(ai_translate("⏳ Pending Action Roster", target_lang))
                for p in pending_list:
                    st.markdown(f"- **{p}**")

        # -----------------------------------------------------------------------------
        # PREMIUM COMPETITION EDGE: PREDICTIVE LEARNING DIAGNOSTICS & RISK MAPPING
        # -----------------------------------------------------------------------------
        st.markdown("---")
        st.subheader(ai_translate("🔮 Predictive Learning Diagnostics & Early Intervention Hub", target_lang))
        st.caption(ai_translate("Standard platforms look backward; our AI predictive analytics suite runs dynamic risk mapping on multi-tenant database history to flag struggling students before they fail.", target_lang))

        if st.button(ai_translate("🔍 Run Automated AI Forensic Risk Sweep", target_lang), use_container_width=True):
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT student_name, task_name, mark, feedback, student_submission 
                    FROM grades WHERE teacher_username = %s;
                """, (st.session_state.username,))
                historical_payload = cur.fetchall()
            conn.close()

            if historical_payload:
                with st.spinner(ai_translate("AI Predictive Engine mapping class vulnerability metrics...", target_lang)):
                    serialized_data = json.dumps(historical_payload, default=str)
                    risk_prompt = f"Analyze this raw JSON gradebook history: {serialized_data}. Identify students performing poorly (under 70%), their core conceptual weakness, and a 1-sentence intervention strategy. Output strictly as a JSON array matching: [{{\"student\": \"Name\", \"risk_level\": \"High/Medium\", \"weakness\": \"Concept\", \"intervention\": \"Strategy\"}}]"
                    try:
                        risk_response = ai_client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=risk_prompt,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                system_instruction="You are a senior predictive psychometrician. Output raw JSON lists only."
                            )
                        )
                        risk_matrix = json.loads(risk_response.text)
                        st.success(ai_translate("🎯 Risk Mapping Analysis Matrix Stream Complete!", target_lang))
                        
                        for alert in risk_matrix:
                            b_color = "#FF4B4B" if alert['risk_level'] == "High" else "#FFAA00"
                            with st.container(border=True):
                                col_status, col_desc = st.columns([1, 4])
                                with col_status:
                                    st.markdown(f'<div style="background-color:{b_color}; color:white; padding:10px; border-radius:5px; text-align:center; font-weight:bold; margin-top:10px;">⚠️ {ai_translate(alert["risk_level"], target_lang)} {ai_translate("Risk", target_lang)}</div>', unsafe_html=True)
                                with col_desc:
                                    st.markdown(f"👥 **{ai_translate('Student', target_lang)}:** `{alert['student']}`")
                                    st.markdown(f"🔬 **{ai_translate('Identified Conceptual Gap', target_lang)}:** {ai_translate(alert['weakness'], target_lang)}")
                                    st.info(f"📋 **{ai_translate('Automated Intervention Path', target_lang)}:** {ai_translate(alert['intervention'], target_lang)}")
                    except Exception as e:
                        st.error(f"Predictive Engine Error: {e}")
            else:
                st.warning(ai_translate("Insufficient multi-tenant historical grade logs available to calculate predictive trend lines.", target_lang))

        # -----------------------------------------------------------------------------
        # GIMMICK: TEACHER DATA AUDIT MATRIX (WHAT THE STUDENT CANNOT SEE)
        # -----------------------------------------------------------------------------
        st.markdown("---")
        st.subheader(ai_translate("🛡️ Multi-Tenant Asset Security Audit Pane", target_lang))
        st.caption(ai_translate("Demonstrating real-time database-level payload data-leak field sanitization.", target_lang))

        if all_ws:
            audit_ws_topic = st.selectbox(ai_translate("Select Asset to Run Differential Scan", target_lang), [w['topic'] for w in all_ws], key="audit_select")
            original_sheet = next(w for w in all_ws if w['topic'] == audit_ws_topic)
            
            col_master, col_student = st.columns(2)
            with col_master:
                st.warning(ai_translate("🟥 Master Copy (Database Storage — With Answer Key)", target_lang))
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("SELECT content FROM worksheets WHERE id = %s;", (original_sheet['id'],))
                    raw_content = cur.fetchone()['content']
                conn.close()
                st.text_area(ai_translate("Live Database Entry View", target_lang), raw_content, height=200, disabled=True, key="audit_raw")
                
            with col_student:
                st.success(ai_translate("🟩 Sanitized Student View (AI Sanitization Pipeline Active)", target_lang))
                student_rendered = st.session_state.get(f"stripped_{original_sheet['id']}", ai_translate("Select this worksheet in the student desk to generate live sanitization array.", target_lang))
                st.text_area(ai_translate("Outgoing Application Stream View", target_lang), student_rendered, height=200, disabled=True, key="audit_strip")

# -----------------------------------------------------------------------------
# PERSONA 2 — STUDENT MULTI-SUBJECT WORKSPACE
# -----------------------------------------------------------------------------
elif st.session_state.role == "Student":
    with st.sidebar:
        student_view = st.radio(ai_translate("Student Control Desk", target_lang), ["🎒 Enroll in a Class", "📂 Subject-Filtered Worksheet Desk", "🏆 My Performance Ledger"])
        
    if student_view == "🎒 Enroll in a Class":
        st.header(ai_translate("🎒 Connect External Course Workspace Network", target_lang))
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT username, subject FROM users WHERE role = 'Teacher';")
            teachers_list = cur.fetchall()
        conn.close()
        
        if teachers_list:
            teacher_options = [f"{t['username']} — Class Department: {t['subject']}" for t in teachers_list]
            selected_option = st.selectbox(ai_translate("Select Academic Instructor", target_lang), teacher_options)
            
            with st.form("enrollment_form"):
                student_id = st.text_input(ai_translate("Assign Target University/School ID Token", target_lang)).strip()
                grade_cohort = st.selectbox(ai_translate("Current Cohort Index", target_lang), ["Grade 6", "Grade 7", "Grade 8", "Grade 9", "Grade 10", "Grade 11", "Grade 12", "Undergraduate"])
                btn_enroll = st.form_submit_button(ai_translate("Submit Secure Connection Registration", target_lang))
                
                if btn_enroll:
                    if not student_id:
                        st.error(ai_translate("Student Identification ID sequence string must be fully declared.", target_lang))
                    else:
                        chosen_teacher = selected_option.split(" — ")[0]
                        chosen_subject = selected_option.split(": ")[1]
                        
                        conn = get_db_connection()
                        with conn.cursor() as cur:
                            cur.execute("SELECT * FROM students WHERE student_name = %s AND teacher_username = %s;", (st.session_state.username, chosen_teacher))
                            already_enrolled = cur.fetchone()
                            
                            if already_enrolled:
                                st.warning(ai_translate("Security Exception: You are already registered into this instructor's structural namespace.", target_lang))
                            else:
                                cur.execute("""
                                    INSERT INTO students (id, teacher_username, student_name, grade_cohort, subject)
                                    VALUES (%s, %s, %s, %s, %s);
                                """, (student_id, chosen_teacher, st.session_state.username, grade_cohort, chosen_subject))
                                conn.commit()
                                st.success(ai_translate(f"Enrolled successfully into {chosen_teacher}'s class!", target_lang))
                        conn.close()

    elif student_view == "📂 Subject-Filtered Worksheet Desk":
        st.header(ai_translate("📝 Task Workspace — Subject Core View", target_lang))
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT teacher_username, subject FROM students WHERE student_name = %s;", (st.session_state.username,))
            my_classes = cur.fetchall()
        conn.close()
        
        if my_classes:
            class_map = {f"{c['subject']} (Instructor: {c['teacher_username']})": c for c in my_classes}
            selected_class = st.selectbox(ai_translate("Choose Active Class Environment Context", target_lang), list(class_map.keys()))
            target_class = class_map[selected_class]
            
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT id, topic, content FROM worksheets WHERE teacher_username = %s AND subject = %s;", (target_class['teacher_username'], target_class['subject']))
                available_worksheets = cur.fetchall()
            conn.close()
            
            if available_worksheets:
                worksheet_map = {w['topic']: w for w in available_worksheets}
                selected_topic = st.selectbox(ai_translate("Select Assignment Target Focus Topic", target_lang), list(worksheet_map.keys()))
                active_ws = worksheet_map[selected_topic]
                
                # RUN BACKGROUND AI SWEEP TO STRIP ANSWER KEYS
                if f"stripped_{active_ws['id']}" not in st.session_state:
                    with st.spinner(ai_translate("AI Sweeper sanitizing assignment text parameters...", target_lang)):
                        prompt = f"The following document is an academic worksheet with a model answers block appended at the bottom. Completely strip out, delete, and omit the entire answer key block. Only output the clean test sheet containing the questions.\n\nDOCUMENT:\n{active_ws['content']}"
                        try:
                            response = ai_client.models.generate_content(
                                model='gemini-2.5-flash',
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    system_instruction="You are a data data sanitization security script. Strip the answer key block cleanly and leave absolutely zero hints or answers."
                                )
                            )
                            st.session_state[f"stripped_{active_ws['id']}"] = response.text
                        except Exception as e:
                            st.error(f"Sanitization Engine Timeout: {e}")
                            st.stop()
                
                st.subheader(ai_translate("📋 Core Examination Blueprint", target_lang))
                st.markdown(ai_translate(st.session_state[f"stripped_{active_ws['id']}"], target_lang))

                # SUBMISSION HANDLING & SECURE ENTRY LOCK
                st.markdown("---")
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM grades WHERE student_name = %s AND teacher_username = %s AND task_name = %s;", (st.session_state.username, target_class['teacher_username'], selected_topic))
                    already_graded = cur.fetchone()
                conn.close()

                if already_graded:
                    st.warning(f"{ai_translate('🔒 You have already logged an official solution log for', target_lang)} {selected_topic}. {ai_translate('Grade', target_lang)}: {already_graded['mark']}/100")
                else:
                    student_submission_text = st.text_area(ai_translate("Input Your Answers Below (e.g., Q1: Answer, Q2: Answer...)", target_lang), height=250)
                    
                    if st.button(ai_translate("Finalize and Submit Assignment Log", target_lang), use_container_width=True):
                        if not student_submission_text.strip():
                            st.error(ai_translate("Submission input content buffer cannot be completely blank.", target_lang))
                        else:
                            with st.spinner(ai_translate("AI Real-time Evaluator Engine grading submission...", target_lang)):
                                prompt = f"Master Assessment Context:\n{active_ws['content']}\n\nStudent Submitted Input Log:\n{student_submission_text}\n\nEvaluate the student's submission against the master answers. Grade it out of 100. Return a JSON object with keys \"grade\" (integer) and \"feedback\" (string)."
                                try:
                                    response = ai_client.models.generate_content(
                                        model='gemini-2.5-flash',
                                        contents=prompt,
                                        config=types.GenerateContentConfig(
                                            response_mime_type="application/json",
                                            system_instruction="You are a strict automated grading assistant. Output raw valid JSON code only."
                                        )
                                    )
                                    res_data = json.loads(response.text)
                                except Exception as e:
                                    st.error(f"Grading Matrix Fault Core: {e}")
                                    st.stop()
                                    
                                conn = get_db_connection()
                                with conn.cursor() as cur:
                                    cur.execute("""
                                        INSERT INTO grades (teacher_username, student_name, subject, task_name, mark, feedback, student_submission)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s);
                                    """, (target_class['teacher_username'], st.session_state.username, target_class['subject'], selected_topic, int(res_data['grade']), res_data['feedback'], student_submission_text))
                                    conn.commit()
                                conn.close()
                                
                                st.balloons()
                                st.success(ai_translate("Assignment logged successfully inside cloud computing database.", target_lang))
                                st.rerun()
            else:
                st.info(ai_translate("No active worksheets found for this classroom instance.", target_lang))
        else:
            st.warning(ai_translate("Please enroll into a classroom context first to view assignments.", target_lang))

    elif student_view == "🏆 My Performance Ledger":
        st.header(ai_translate("🏆 My Performance Ledger & Report Matrix", target_lang))
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT task_name, subject, mark, feedback FROM grades WHERE student_name = %s;", (st.session_state.username,))
            my_grades = cur.fetchall()
        conn.close()
        
        if my_grades:
            marks_list = [g['mark'] for g in my_grades]
            overall_gpa_mean = sum(marks_list) / len(marks_list)
            
            st.metric(ai_translate("Cumulative System Matrix Score Average", target_lang), f"{overall_gpa_mean:.2f}%")
            st.subheader(ai_translate("📚 Historically Logged Assessment Records", target_lang))
            st.dataframe(my_grades, use_container_width=True)
        else:
            st.info(ai_translate("No performance markers have been submitted or processed yet.", target_lang))