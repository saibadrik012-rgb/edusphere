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

from google import genai
from google.genai import types

ai_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
DB_URL = st.secrets["SUPABASE_DB_URL"]

def get_db_connection():
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        st.error(f"⚠️ Cloud Database Connection Failed: {e}")
        st.stop()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, role TEXT NOT NULL, subject TEXT);")
        cur.execute("CREATE TABLE IF NOT EXISTS students (id TEXT NOT NULL, teacher_username TEXT NOT NULL, student_name TEXT NOT NULL, grade_cohort TEXT NOT NULL, subject TEXT NOT NULL, PRIMARY KEY (student_name, teacher_username));")
        cur.execute("CREATE TABLE IF NOT EXISTS lessons (id SERIAL PRIMARY KEY, teacher_username TEXT NOT NULL, subject TEXT NOT NULL, topic TEXT NOT NULL, content TEXT NOT NULL);")
        cur.execute("CREATE TABLE IF NOT EXISTS worksheets (id SERIAL PRIMARY KEY, teacher_username TEXT NOT NULL, subject TEXT NOT NULL, topic TEXT NOT NULL, content TEXT NOT NULL);")
        cur.execute("CREATE TABLE IF NOT EXISTS grades (id SERIAL PRIMARY KEY, teacher_username TEXT NOT NULL, student_name TEXT NOT NULL, subject TEXT NOT NULL, task_name TEXT NOT NULL, mark INTEGER, feedback TEXT, student_submission TEXT);")
        
        cur.execute("SELECT COUNT(*) FROM users;")
        if cur.fetchone()['count'] == 0:
            fallback_hash = hash_password("admin123")
            cur.execute("INSERT INTO users (username, password_hash, role, subject) VALUES ('admin', %s, 'Teacher', 'General Science');", (fallback_hash,))
        conn.commit()
    conn.close()

init_db()

# Initialize basic authentication session keys
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.subject = None

# -----------------------------------------------------------------------------
# GLOBAL 100% DICTIONARY BATCH LOCALIZATION ENGINE
# -----------------------------------------------------------------------------
# Baseline English text repository blueprint
ENGLISH_BASE = {
    "app_title": "EduSphere Core Management Portal",
    "welcome_msg": "Welcome to the unified Multi-Tenant Classroom Platform. Please sign in or register to connect to your cloud dashboard.",
    "tab_signin": "🔑 Account Sign-In",
    "tab_register": "📝 Account Registration",
    "username": "Username",
    "password": "Password",
    "btn_signin": "Authenticate Access",
    "auth_success": "Authentication successful! Loading workspace...",
    "auth_fail": "Invalid credentials or user record missing.",
    "fields_missing": "Please supply both tracking components.",
    "create_user": "Create Username",
    "secure_pass": "Secure Password",
    "role_persona": "Institutional Role Persona",
    "teaching_dept": "Teaching Assignment Domain (Teachers Only)",
    "btn_deploy_tenant": "Deploy Global Tenant",
    "blank_error": "Username and Password credentials cannot be left blank.",
    "user_exists": "This registration profile name already exists on this server cluster.",
    "tenant_deployed": "Tenant deployed! Switch tabs to login securely.",
    "profile_session": "Profile Session",
    "role_label": "Role",
    "dept_label": "Dept",
    "logout_btn": "Log Out Securely",
    "nav_workspace": "Navigate Cloud Workspace",
    "master_workspace": "Master Workspace — Core Field",
    "active_roster": "👥 Connected Active Roster Matrix",
    "no_students": "No active student trackers currently registered to this tenant environment.",
    "lesson_architect": "🧠 AI Curriculum Engine — 5E Lesson Plan Architect",
    "topic_input": "Enter Topic (e.g., Quantum Mechanics Fundamental Principles, Mitosis)",
    "cohort_level": "Target Cohort Level",
    "btn_synth_lesson": "Synthesize Lesson Curriculum",
    "processing_stream": "AI Engine Processing Cloud Stream...",
    "review_output": "Review/Modify Architectural Output Content",
    "save_lesson_btn": "Save Finished Lesson to Cloud Workspace",
    "publish_success": "Successfully published the unit to cloud database records!",
    "worksheet_factory": "📝 AI Worksheet Factory & Key Generator",
    "target_obj": "Target Assessment Objective or Focus Unit",
    "btn_gen_worksheet": "Generate Master Assessment Artifact",
    "compiling_rules": "Compiling structured query rules...",
    "edit_ws_content": "Edit Worksheet System Content",
    "commit_ws_btn": "Commit Worksheet to Cloud",
    "ws_committed": "Worksheet committed securely under assignment keys.",
    "submissions_hub": "🗃️ Complete Submissions Hub & Manual Evaluation Review",
    "earned_score": "Earned Score Parameter",
    "raw_input_log": "Raw Text Student Input Log",
    "eval_commentary": "Diagnostic AI Evaluator Commentary Feedback",
    "no_logs": "No logs present inside tracking matrices.",
    "analytics_grid": "📈 Management Command Grid & Metrics Engine",
    "metric_roster": "Total Roster Size",
    "metric_mean": "Class Running Grade Mean",
    "metric_tasks": "Published Assignments",
    "enrolled_text": "Enrolled",
    "live_sheets_text": "Live Sheets",
    "consolidated_df": "📚 Analytics Consolidated Roster Dataframe",
    "insufficient_data": "Insufficient structural data to load runtime matrix aggregates.",
    "metric_trends": "📊 Individual Assignment Metric Trends",
    "filter_matrix": "🔍 Tracking Matrix Filter Matrix Sync",
    "select_audit": "Select Target Assignment Audit Check",
    "finished_roster": "✔️ Finished Submission Roster",
    "pending_roster": "⏳ Pending Action Roster",
    "predictive_hub": "🔮 Predictive Learning Diagnostics & Early Intervention Hub",
    "predictive_caption": "Standard platforms look backward; our AI predictive analytics suite runs dynamic risk mapping on multi-tenant database history to flag struggling students before they fail.",
    "btn_risk_sweep": "🔍 Run Automated AI Forensic Risk Sweep",
    "mapping_vulnerabilities": "AI Predictive Engine mapping class vulnerability metrics...",
    "risk_complete": "🎯 Risk Mapping Analysis Matrix Stream Complete!",
    "risk_label": "Risk",
    "student_label": "Student",
    "conceptual_gap": "Identified Conceptual Gap",
    "intervention_path": "Automated Intervention Path",
    "insufficient_history": "Insufficient multi-tenant historical grade logs available to calculate predictive trend lines.",
    "security_pane": "🛡️ Multi-Tenant Asset Security Audit Pane",
    "security_caption": "Demonstrating real-time database-level payload data-leak field sanitization.",
    "select_differential": "Select Asset to Run Differential Scan",
    "master_copy_label": "🟥 Master Copy (Database Storage — With Answer Key)",
    "database_entry_view": "Live Database Entry View",
    "sanitized_view_label": "🟩 Sanitized Student View (AI Sanitization Pipeline Active)",
    "outgoing_stream_view": "Outgoing Application Stream View",
    "audit_strip_fallback": "Select this worksheet in the student desk to generate live sanitization array.",
    "student_ctrl_desk": "Student Control Desk",
    "connect_external": "🎒 Connect External Course Workspace Network",
    "select_instructor": "Select Academic Instructor",
    "assign_id_token": "Assign Target University/School ID Token",
    "current_cohort_idx": "Current Cohort Index",
    "submit_conn_btn": "Submit Secure Connection Registration",
    "id_string_error": "Student Identification ID sequence string must be fully declared.",
    "security_exception_enrolled": "Security Exception: You are already registered into this instructor's structural namespace.",
    "enroll_success": "Enrolled successfully into the selected instructor's class!",
    "task_workspace_title": "📝 Task Workspace — Subject Core View",
    "choose_class_ctx": "Choose Active Class Environment Context",
    "select_focus_topic": "Select Assignment Target Focus Topic",
    "sweeper_sanitizing": "AI Sweeper sanitizing assignment text parameters...",
    "exam_blueprint": "📋 Core Examination Blueprint",
    "graded_lock_msg": "🔒 You have already logged an official solution log for this task.",
    "input_answers_here": "Input Your Answers Below (e.g., Q1: Answer, Q2: Answer...)",
    "finalize_submit_btn": "Finalize and Submit Assignment Log",
    "buffer_blank_error": "Submission input content buffer cannot be completely blank.",
    "evaluator_grading": "AI Real-time Evaluator Engine grading submission...",
    "grading_fault": "Grading Matrix Fault Core:",
    "log_success": "Assignment logged successfully inside cloud computing database.",
    "no_ws_found": "No active worksheets found for this classroom instance.",
    "enroll_first_warning": "Please enroll into a classroom context first to view assignments.",
    "performance_ledger_title": "🏆 My Performance Ledger & Report Matrix",
    "cumulative_average": "Cumulative System Matrix Score Average",
    "historical_records": "📚 Historically Logged Assessment Records",
    "no_performance_markers": "No performance markers have been submitted or processed yet."
}

def get_page_localization(target_lang: str):
    """Translates the complete system dictionary in a single, high-speed API text pipeline call."""
    if target_lang == "English":
        return ENGLISH_BASE
    
    cache_state_key = f"full_page_dictionary_{target_lang}"
    if cache_state_key in st.session_state:
        return st.session_state[cache_state_key]
        
    with st.spinner(f"Translating whole app interface to {target_lang}..."):
        try:
            translation_prompt = (
                f"You are a master localization system. I will provide you with a raw JSON dictionary of user interface strings. "
                f"Translate every single value completely into {target_lang}. Keep all the keys identical. Preserve markdown formatting, emojis, and brackets where appropriate. "
                f"Output ONLY the translated JSON dictionary object directly back, no explanations:\n\n"
                f"{json.dumps(ENGLISH_BASE, ensure_code_encoding=True)}"
            )
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=translation_prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            localized_dictionary = json.loads(response.text)
            st.session_state[cache_state_key] = localized_dictionary
            return localized_dictionary
        except Exception:
            return ENGLISH_BASE # Fail-safe back to English if the translation call drops

# -----------------------------------------------------------------------------
# GLOBAL SIDEBAR LOCALIZATION MATRIX PICKER
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🌐 Global Localization Suite")
    selected_language = st.selectbox(
        "Select Webpage Interface Language",
        ["English", "Spanish (Español)", "French (Français)", "German (Deutsch)", "Mandarin (中文)", "Hindi (हिन्दी)", "Arabic (العربية)", "Japanese (日本語)", "Russian (Русский)", "Portuguese (Português)"]
    )
    # Pull down the localized translation map for the entire interface execution frame
    UI = get_page_localization(selected_language)
    st.markdown("---")

# -----------------------------------------------------------------------------
# AUTHENTICATION GATEWAY & SESSION MANAGEMENT
# -----------------------------------------------------------------------------
if not st.session_state.authenticated:
    st.title(UI["app_title"])
    st.markdown(UI["welcome_msg"])
    
    tab_signin, tab_register = st.tabs([UI["tab_signin"], UI["tab_register"]])
    
    with tab_signin:
        with st.form("signin_form"):
            user_input = st.text_input(UI["username"]).strip()
            pass_input = st.text_input(UI["password"], type="password")
            btn_signin = st.form_submit_button(UI["btn_signin"], use_container_width=True)
            
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
                        st.success(UI["auth_success"])
                        st.rerun()
                    else:
                        st.error(UI["auth_fail"])
                else:
                    st.warning(UI["fields_missing"])
                    
    with tab_register:
        with st.form("registration_form"):
            reg_user = st.text_input(UI["create_user"]).strip()
            reg_pass = st.text_input(UI["secure_pass"], type="password")
            reg_role = st.selectbox(UI["role_persona"], ["Teacher", "Student"])
            reg_subject = st.selectbox(
                UI["teaching_dept"],
                ["Mathematics", "General Science", "English Language Arts", "Social Studies / Humanities", "Computer Science"]
            )
            
            btn_register = st.form_submit_button(UI["btn_deploy_tenant"], use_container_width=True)
            
            if btn_register:
                if not reg_user or not reg_pass:
                    st.error(UI["blank_error"])
                else:
                    conn = get_db_connection()
                    with conn.cursor() as cur:
                        cur.execute("SELECT username FROM users WHERE username = %s;", (reg_user,))
                        exists = cur.fetchone()
                        
                        if exists:
                            st.error(UI["user_exists"])
                        else:
                            assigned_subject = reg_subject if reg_role == "Teacher" else "Student Framework"
                            hashed_w = hash_password(reg_pass)
                            cur.execute("INSERT INTO users (username, password_hash, role, subject) VALUES (%s, %s, %s, %s);", (reg_user, hashed_w, reg_role, assigned_subject))
                            conn.commit()
                            st.success(UI["tenant_deployed"])
                    conn.close()
    st.stop()

# -----------------------------------------------------------------------------
# GLOBAL PLATFORM SIDEBAR & DEPLOYMENT SYNC
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"### 👤 {UI['profile_session']}: **{st.session_state.username}**")
    st.caption(f"🛡️ {UI['role_label']}: {st.session_state.role}")
    if st.session_state.role == "Teacher":
        st.info(f"📚 {UI['dept_label']}: {st.session_state.subject}")
    
    st.markdown("---")
    if st.button(UI["logout_btn"], use_container_width=True):
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
            UI["nav_workspace"],
            ["Classroom Roster", "AI Lesson Architect", "AI Worksheet Factory", "AI Evaluator & Gradebook Ledger", "📊 Student Advanced Analytics"]
        )

    st.title(f"{UI['master_workspace']}: {st.session_state.subject}")
    
    if workspace_view == "Classroom Roster":
        st.header(UI["active_roster"])
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, student_name, grade_cohort, subject FROM students WHERE teacher_username = %s;", (st.session_state.username,))
            roster_data = cur.fetchall()
        conn.close()
        
        if roster_data:
            st.dataframe(roster_data, use_container_width=True)
        else:
            st.warning(UI["no_students"])
            
    elif workspace_view == "AI Lesson Architect":
        st.header(UI["lesson_architect"])
        topic = st.text_input(UI["topic_input"])
        grade_tier = st.selectbox(UI["cohort_level"], ["Grade 6-8 Middle School", "Grade 9-12 High School", "Undergraduate Ivy-League"])
        
        if st.button(UI["btn_synth_lesson"], use_container_width=True):
            with st.spinner(UI["processing_stream"]):
                prompt = f"Design a comprehensive 5E lesson plan for '{topic}' target cohort '{grade_tier}' inside the subject system '{st.session_state.subject}'. Translate the raw content generation output cleanly into {selected_language} directly."
                try:
                    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                    st.session_state.current_lesson = response.text
                except Exception as e:
                    st.error(f"LLM Engine Fault: {e}")
                    
        if "current_lesson" in st.session_state:
            edited_content = st.text_area(UI["review_output"], value=st.session_state.current_lesson, height=400)
            if st.button(UI["save_lesson_btn"], use_container_width=True):
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO lessons (teacher_username, subject, topic, content) VALUES (%s, %s, %s, %s);", (st.session_state.username, st.session_state.subject, topic, edited_content))
                    conn.commit()
                conn.close()
                st.success(UI["publish_success"])

    elif workspace_view == "AI Worksheet Factory":
        st.header(UI["worksheet_factory"])
        w_topic = st.text_input(UI["target_obj"])
        
        if st.button(UI["btn_gen_worksheet"], use_container_width=True):
            with st.spinner(UI["compiling_rules"]):
                prompt = f"Create a rigorous 5-question conceptual assessment worksheet regarding '{w_topic}' for a course in '{st.session_state.subject}'. At the bottom, append a distinct section clearly titled '--- ANSWER KEY ---'. Generate the text directly in {selected_language}."
                try:
                    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                    st.session_state.current_worksheet = response.text
                except Exception as e:
                    st.error(f"LLM Fault: {e}")
                    
        if "current_worksheet" in st.session_state:
            w_edited = st.text_area(UI["edit_ws_content"], value=st.session_state.current_worksheet, height=400)
            if st.button(UI["commit_ws_btn"], use_container_width=True):
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO worksheets (teacher_username, subject, topic, content) VALUES (%s, %s, %s, %s);", (st.session_state.username, st.session_state.subject, w_topic, w_edited))
                    conn.commit()
                conn.close()
                st.success(UI["ws_committed"])

    elif workspace_view == "AI Evaluator & Gradebook Ledger":
        st.header(UI["submissions_hub"])
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, student_name, subject, task_name, mark, feedback, student_submission FROM grades WHERE teacher_username = %s;", (st.session_state.username,))
            grades_records = cur.fetchall()
        conn.close()
        
        if grades_records:
            for record in grades_records:
                with st.expander(f"📋 ID: {record['id']} | {record['student_name']} — {record['task_name']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**{UI['earned_score']}:** `{record['mark']}/100`")
                        st.text_area(UI["raw_input_log"], record['student_submission'], disabled=True, key=f"sub_{record['id']}")
                    with col2:
                        st.markdown(f"**{UI['eval_commentary']}:**")
                        st.info(record['feedback'])
        else:
            st.info(UI["no_logs"])

    elif workspace_view == "📊 Student Advanced Analytics":
        st.header(UI["analytics_grid"])
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM students WHERE teacher_username = %s;", (st.session_state.username,))
            total_students = cur.fetchone()['count']
            cur.execute("SELECT avg(mark) FROM grades WHERE teacher_username = %s;", (st.session_state.username,))
            class_mean = cur.fetchone()['avg'] or 0.0
            cur.execute("SELECT count(*) FROM worksheets WHERE teacher_username = %s;", (st.session_state.username,))
            published_tasks = cur.fetchone()['count']
            cur.execute("SELECT student_name, avg(mark) as avg_mark, max(mark) as max_mark, count(mark) as completed FROM grades WHERE teacher_username = %s GROUP BY student_name;", (st.session_state.username,))
            aggregate_df = cur.fetchall()
            cur.execute("SELECT topic, id FROM worksheets WHERE teacher_username = %s;", (st.session_state.username,))
            all_ws = cur.fetchall()
            cur.execute("SELECT task_name, avg(mark) as task_avg FROM grades WHERE teacher_username = %s GROUP BY task_name;", (st.session_state.username,))
            chart_records = cur.fetchall()
        conn.close()
        
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric(UI["metric_roster"], f"{total_students} {UI['enrolled_text']}")
        m_col2.metric(UI["metric_mean"], f"{float(class_mean):.2f}%")
        m_col3.metric(UI["metric_tasks"], f"{published_tasks} {UI['live_sheets_text']}")
        
        st.subheader(UI["consolidated_df"])
        if aggregate_df:
            st.dataframe(aggregate_df, use_container_width=True)
        else:
            st.warning(UI["insufficient_data"])
            
        st.subheader(UI["metric_trends"])
        if chart_records:
            chart_dict = {r['task_name']: float(r['task_avg']) for r in chart_records}
            st.bar_chart(chart_dict)
            
        st.subheader(UI["filter_matrix"])
        if all_ws:
            selected_ws = st.selectbox(UI["select_audit"], [w['topic'] for w in all_ws])
            
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
                st.success(UI["finished_roster"])
                for s in completed_list:
                    st.markdown(f"- **{s}**")
            with c_pending:
                st.error(UI["pending_roster"])
                for p in pending_list:
                    st.markdown(f"- **{p}**")

        # -----------------------------------------------------------------------------
        # PREMIUM COMPETITION EDGE: PREDICTIVE LEARNING DIAGNOSTICS & RISK MAPPING
        # -----------------------------------------------------------------------------
        st.markdown("---")
        st.subheader(UI["predictive_hub"])
        st.caption(UI["predictive_caption"])

        if st.button(UI["btn_risk_sweep"], use_container_width=True):
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT student_name, task_name, mark, feedback, student_submission FROM grades WHERE teacher_username = %s;", (st.session_state.username,))
                historical_payload = cur.fetchall()
            conn.close()

            if historical_payload:
                with st.spinner(UI["mapping_vulnerabilities"]):
                    serialized_data = json.dumps(historical_payload, default=str)
                    risk_prompt = f"Analyze this gradebook history: {serialized_data}. Identify students scoring under 70%, their key conceptual weakness, and a short intervention strategy. Translate all findings completely into {selected_language}. Output strictly as a JSON list matching: [{{\"student\": \"Name\", \"risk_level\": \"High/Medium\", \"weakness\": \"Concept\", \"intervention\": \"Strategy\"}}]"
                    try:
                        risk_response = ai_client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=risk_prompt,
                            config=types.GenerateContentConfig(response_mime_type="application/json")
                        )
                        risk_matrix = json.loads(risk_response.text)
                        st.success(UI["risk_complete"])
                        
                        for alert in risk_matrix:
                            b_color = "#FF4B4B" if alert['risk_level'] in ["High", "Alta", "Haute"] else "#FFAA00"
                            with st.container(border=True):
                                col_status, col_desc = st.columns([1, 4])
                                with col_status:
                                    st.markdown(f'<div style="background-color:{b_color}; color:white; padding:10px; border-radius:5px; text-align:center; font-weight:bold; margin-top:10px;">⚠️ {UI["risk_label"]}</div>', unsafe_html=True)
                                with col_desc:
                                    st.markdown(f"👥 **{UI['student_label']}:** `{alert['student']}`")
                                    st.markdown(f"🔬 **{UI['conceptual_gap']}:** {alert['weakness']}")
                                    st.info(f"📋 **{UI['intervention_path']}:** {alert['intervention']}")
                    except Exception as e:
                        st.error(f"Predictive Engine Error: {e}")
            else:
                st.warning(UI["insufficient_history"])

        # -----------------------------------------------------------------------------
        # TEACHER DATA AUDIT MATRIX
        # -----------------------------------------------------------------------------
        st.markdown("---")
        st.subheader(UI["security_pane"])
        st.caption(UI["security_caption"])

        if all_ws:
            audit_ws_topic = st.selectbox(UI["select_differential"], [w['topic'] for w in all_ws], key="audit_select")
            original_sheet = next(w for w in all_ws if w['topic'] == audit_ws_topic)
            
            col_master, col_student = st.columns(2)
            with col_master:
                st.warning(UI["master_copy_label"])
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("SELECT content FROM worksheets WHERE id = %s;", (original_sheet['id'],))
                    raw_content = cur.fetchone()['content']
                conn.close()
                st.text_area(UI["database_entry_view"], raw_content, height=200, disabled=True, key="audit_raw")
                
            with col_student:
                st.success(UI["sanitized_view_label"])
                student_rendered = st.session_state.get(f"stripped_{original_sheet['id']}", UI["audit_strip_fallback"])
                st.text_area(UI["outgoing_stream_view"], student_rendered, height=200, disabled=True, key="audit_strip")

# -----------------------------------------------------------------------------
# PERSONA 2 — STUDENT MULTI-SUBJECT WORKSPACE
# -----------------------------------------------------------------------------
elif st.session_state.role == "Student":
    with st.sidebar:
        student_view = st.radio(UI["student_ctrl_desk"], ["🎒 Enroll in a Class", "📂 Subject-Filtered Worksheet Desk", "🏆 My Performance Ledger"])
        
    if student_view == "🎒 Enroll in a Class":
        st.header(UI["connect_external"])
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT username, subject FROM users WHERE role = 'Teacher';")
            teachers_list = cur.fetchall()
        conn.close()
        
        if teachers_list:
            teacher_options = [f"{t['username']} — Dept: {t['subject']}" for t in teachers_list]
            selected_option = st.selectbox(UI["select_instructor"], teacher_options)
            
            with st.form("enrollment_form"):
                student_id = st.text_input(UI["assign_id_token"]).strip()
                grade_cohort = st.selectbox(UI["current_cohort_idx"], ["Grade 6", "Grade 7", "Grade 8", "Grade 9", "Grade 10", "Grade 11", "Grade 12", "Undergraduate"])
                btn_enroll = st.form_submit_button(UI["submit_conn_btn"])
                
                if btn_enroll:
                    if not student_id:
                        st.error(UI["id_string_error"])
                    else:
                        chosen_teacher = selected_option.split(" — ")[0]
                        chosen_subject = selected_option.split(": ")[1]
                        
                        conn = get_db_connection()
                        with conn.cursor() as cur:
                            cur.execute("SELECT * FROM students WHERE student_name = %s AND teacher_username = %s;", (st.session_state.username, chosen_teacher))
                            already_enrolled = cur.fetchone()
                            
                            if already_enrolled:
                                st.warning(UI["security_exception_enrolled"])
                            else:
                                cur.execute("INSERT INTO students (id, teacher_username, student_name, grade_cohort, subject) VALUES (%s, %s, %s, %s, %s);", (student_id, chosen_teacher, st.session_state.username, grade_cohort, chosen_subject))
                                conn.commit()
                                st.success(UI["enroll_success"])
                        conn.close()

    elif student_view == "📂 Subject-Filtered Worksheet Desk":
        st.header(UI["task_workspace_title"])
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT teacher_username, subject FROM students WHERE student_name = %s;", (st.session_state.username,))
            my_classes = cur.fetchall()
        conn.close()
        
        if my_classes:
            class_map = {f"{c['subject']} ({c['teacher_username']})": c for c in my_classes}
            selected_class = st.selectbox(UI["choose_class_ctx"], list(class_map.keys()))
            target_class = class_map[selected_class]
            
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT id, topic, content FROM worksheets WHERE teacher_username = %s AND subject = %s;", (target_class['teacher_username'], target_class['subject']))
                available_worksheets = cur.fetchall()
            conn.close()
            
            if available_worksheets:
                worksheet_map = {w['topic']: w for w in available_worksheets}
                selected_topic = st.selectbox(UI["select_focus_topic"], list(worksheet_map.keys()))
                active_ws = worksheet_map[selected_topic]
                
                # RUN BACKGROUND AI SWEEP TO STRIP ANSWER KEYS & TRANSLATE TO TARGET LANGUAGE
                if f"stripped_{active_ws['id']}" not in st.session_state:
                    with st.spinner(UI["sweeper_sanitizing"]):
                        prompt = f"The following document is an academic worksheet with answers at the bottom. Strip out the entire answer key cleanly. Translate the remaining questions completely into {selected_language}.\n\nDOCUMENT:\n{active_ws['content']}"
                        try:
                            response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                            st.session_state[f"stripped_{active_ws['id']}"] = response.text
                        except Exception as e:
                            st.error(f"Sanitization Engine Timeout: {e}")
                            st.stop()
                
                st.subheader(UI["exam_blueprint"])
                st.markdown(st.session_state[f"stripped_{active_ws['id']}"])

                st.markdown("---")
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM grades WHERE student_name = %s AND teacher_username = %s AND task_name = %s;", (st.session_state.username, target_class['teacher_username'], selected_topic))
                    already_graded = cur.fetchone()
                conn.close()

                if already_graded:
                    st.warning(UI["graded_lock_msg"])
                else:
                    student_submission_text = st.text_area(UI["input_answers_here"], height=250)
                    
                    if st.button(UI["finalize_submit_btn"], use_container_width=True):
                        if not student_submission_text.strip():
                            st.error(UI["buffer_blank_error"])
                        else:
                            with st.spinner(UI["evaluator_grading"]):
                                prompt = f"Master Context:\n{active_ws['content']}\n\nStudent Answers:\n{student_submission_text}\n\nGrade out of 100. Return a JSON object with keys \"grade\" (integer) and \"feedback\" (string, written cleanly in {selected_language})."
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
                                    st.error(f"{UI['grading_fault']} {e}")
                                    st.stop()
                                    
                                conn = get_db_connection()
                                with conn.cursor() as cur:
                                    cur.execute("INSERT INTO grades (teacher_username, student_name, subject, task_name, mark, feedback, student_submission) VALUES (%s, %s, %s, %s, %s, %s, %s);", (target_class['teacher_username'], st.session_state.username, target_class['subject'], selected_topic, int(res_data['grade']), res_data['feedback'], student_submission_text))
                                    conn.commit()
                                conn.close()
                                
                                st.balloons()
                                st.success(UI["log_success"])
                                st.rerun()
            else:
                st.info(UI["no_ws_found"])
        else:
            st.warning(UI["enroll_first_warning"])

    elif student_view == "🏆 My Performance Ledger":
        st.header(UI["performance_ledger_title"])
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT task_name, subject, mark, feedback FROM grades WHERE student_name = %s;", (st.session_state.username,))
            my_grades = cur.fetchall()
        conn.close()
        
        if my_grades:
            marks_list = [g['mark'] for g in my_grades]
            overall_gpa_mean = sum(marks_list) / len(marks_list)
            
            st.metric(UI["cumulative_average"], f"{overall_gpa_mean:.2f}%")
            st.subheader(UI["historical_records"])
            st.dataframe(my_grades, use_container_width=True)
        else:
            st.info(UI["no_performance_markers"])