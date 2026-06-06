import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import json
from google import genai
from google.genai import types

# Initialize Streamlit Page Settings
st.set_page_config(
    page_title = "EduSphere | Unified Multi-Tenant Academy Portal",
    page_icon = "🏫",
    layout = "wide",
    initial_sidebar_state = "expanded"
)

# -----------------------------------------------------------------------------
# CRITICAL CREDENTIALS & INITIALIZATION
# -----------------------------------------------------------------------------
if "GEMINI_API_KEY" not in st.secrets or "SUPABASE_DB_URL" not in st.secrets:
    st.error("❌ Critical configuration missing! Please ensure GEMINI_API_KEY and SUPABASE_DB_URL are defined in .streamlit/secrets.toml")
    st.stop()

# Initialize Google GenAI Client
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
        # Create Students (Composite PK ensures a student can enroll in multiple subjects under different teachers)
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
# AUTHENTICATION GATEWAY & SESSION MANAGEMENT
# -----------------------------------------------------------------------------
if not st.session_state.authenticated:
    st.title("🏫 EduSphere Core Management Portal")
    st.markdown("Welcome to the unified Multi-Tenant Classroom Platform. Please sign in or register to connect to your cloud dashboard.")
    
    tab_signin, tab_register = st.tabs(["🔑 Account Sign-In", "📝 Account Registration"])
    
    with tab_signin:
        with st.form("signin_form"):
            user_input = st.text_input("Username").strip()
            pass_input = st.text_input("Password", type="password")
            btn_signin = st.form_submit_button("Authenticate Access", use_container_width=True)
            
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
                        st.success("Authentication successful! Loading workspace...")
                        st.rerun()
                    else:
                        st.error("Invalid credentials or user record missing.")
                else:
                    st.warning("Please supply both tracking components.")
                    
    with tab_register:
        with st.form("registration_form"):
            reg_user = st.text_input("Create Username").strip()
            reg_pass = st.text_input("Secure Password", type="password")
            reg_role = st.selectbox("Institutional Role Persona", ["Teacher", "Student"])
            
            # Dynamic Department Field Container
            reg_subject = st.selectbox(
                "Teaching Assignment Domain (Teachers Only)",
                ["Mathematics", "General Science", "English Language Arts", "Social Studies / Humanities", "Computer Science"]
            )
            
            btn_register = st.form_submit_button("Deploy Global Tenant", use_container_width=True)
            
            if btn_register:
                if not reg_user or not reg_pass:
                    st.error("Username and Password credentials cannot be left blank.")
                else:
                    conn = get_db_connection()
                    with conn.cursor() as cur:
                        cur.execute("SELECT username FROM users WHERE username = %s;", (reg_user,))
                        exists = cur.fetchone()
                        
                        if exists:
                            st.error("This registration profile name already exists on this server cluster.")
                        else:
                            assigned_subject = reg_subject if reg_role == "Teacher" else "Student Framework"
                            hashed_w = hash_password(reg_pass)
                            cur.execute("""
                                INSERT INTO users (username, password_hash, role, subject)
                                VALUES (%s, %s, %s, %s);
                            """, (reg_user, hashed_w, reg_role, assigned_subject))
                            conn.commit()
                            st.success("Tenant deployed! Switch tabs to login securely.")
                    conn.close()
    st.stop()

# -----------------------------------------------------------------------------
# GLOBAL PLATFORM SIDEBAR & DEPLOYMENT MANAGEMENT
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"### 👤 Profile Session: **{st.session_state.username}**")
    st.caption(f"🛡️ Role: {st.session_state.role}")
    if st.session_state.role == "Teacher":
        st.info(f"📚 Dept: {st.session_state.subject}")
    
    st.markdown("---")
    
    if st.button("Log Out Securely", use_container_width=True):
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
            "Navigate Cloud Workspace",
            ["Classroom Roster", "AI Lesson Architect", "AI Worksheet Factory", "AI Evaluator & Gradebook Ledger", "📊 Student Advanced Analytics"]
        )

    st.title(f"🍎 Master Workspace — Core Field: {st.session_state.subject}")
    
    if workspace_view == "Classroom Roster":
        st.header("👥 Connected Active Roster Matrix")
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
            st.warning("No active student trackers currently registered to this tenant environment.")
            
    elif workspace_view == "AI Lesson Architect":
        st.header("🧠 AI Curriculum Engine — 5E Lesson Plan Architect")
        topic = st.text_input("Enter Topic (e.g., Quantum Mechanics Fundamental Principles, Mitosis)")
        grade_tier = st.selectbox("Target Cohort Level", ["Grade 6-8 Middle School", "Grade 9-12 High School", "Undergraduate Ivy-League"])
        
        if st.button("Synthesize Lesson Curriculum", use_container_width=True):
            with st.spinner("AI Engine Processing Cloud Stream..."):
                prompt = f"Design an exhaustive, comprehensive 5E lesson plan for '{topic}' target cohort '{grade_tier}' specializing inside '{st.session_state.subject}' environment rules."
                try:
                    response = ai_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction="You are an Elite Curriculum Instructional Designer. Generate output with precise pedagogical terminology using the 5E method (Engage, Explore, Explain, Elaborate, Evaluate)."
                        )
                    )
                    st.session_state.current_lesson = response.text
                except Exception as e:
                    st.error(f"LLM Engine Disconnection: {e}")
                    
        if "current_lesson" in st.session_state:
            edited_content = st.text_area("Review/Modify Architectural Output Content", value=st.session_state.current_lesson, height=400)
            if st.button("Save Finished Lesson to Cloud Workspace", use_container_width=True):
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO lessons (teacher_username, subject, topic, content)
                        VALUES (%s, %s, %s, %s);
                    """, (st.session_state.username, st.session_state.subject, topic, edited_content))
                    conn.commit()
                conn.close()
                st.success(f"Successfully published '{topic}' to cloud database records!")

    elif workspace_view == "AI Worksheet Factory":
        st.header("📝 AI Worksheet Factory & Key Generator")
        w_topic = st.text_input("Target Assessment Objective or Focus Unit")
        
        if st.button("Generate Master Assessment Artifact", use_container_width=True):
            with st.spinner("Compiling structured query rules..."):
                prompt = f"Create a rigorous 5-question conceptual and analytical assessment worksheet regarding '{w_topic}' for a course in '{st.session_state.subject}'. At the very bottom of the document, append a distinct section clearly titled '--- ANSWER KEY ---' that contains the model answers for the 5 questions."
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
            w_edited = st.text_area("Edit Worksheet System Content", value=st.session_state.current_worksheet, height=400)
            if st.button("Commit Worksheet to Cloud", use_container_width=True):
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO worksheets (teacher_username, subject, topic, content)
                        VALUES (%s, %s, %s, %s);
                    """, (st.session_state.username, st.session_state.subject, w_topic, w_edited))
                    conn.commit()
                conn.close()
                st.success(f"Worksheet committed securely under '{w_topic}' assignment keys.")

    elif workspace_view == "AI Evaluator & Gradebook Ledger":
        st.header("🗃️ Complete Submissions Hub & Manual Evaluation Review")
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
                with st.expander(f"📋 Record ID: {record['id']} | Student: {record['student_name']} — Task: {record['task_name']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Earned Score Parameter:** `{record['mark']}/100`")
                        st.text_area("Raw Text Student Input Log", record['student_submission'], disabled=True, key=f"sub_{record['id']}")
                    with col2:
                        st.markdown("**Diagnostic AI Evaluator Commentary Feedback:**")
                        st.info(record['feedback'])
        else:
            st.info("No logs present inside tracking matrices.")

    elif workspace_view == "📊 Student Advanced Analytics":
        st.header("📈 Management Command Grid & Metrics Engine")
        
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
        m_col1.metric("Total Roster Size", f"{total_students} Enrolled")
        m_col2.metric("Class Running Grade Mean", f"{float(class_mean):.2f}%")
        m_col3.metric("Published Assignments", f"{published_tasks} Live Sheets")
        
        st.subheader("📚 Analytics Consolidated Roster Dataframe")
        if aggregate_df:
            st.dataframe(aggregate_df, use_container_width=True)
        else:
            st.warning("Insufficient structural data to load runtime matrix aggregates.")
            
        st.subheader("📊 Individual Assignment Metric Trends")
        if chart_records:
            chart_dict = {r['task_name']: float(r['task_avg']) for r in chart_records}
            st.bar_chart(chart_dict)
        else:
            st.caption("No grade records exist to assemble trend visuals.")
            
        st.subheader("🔍 Tracking Matrix Filter Matrix Sync")
        if all_ws:
            selected_ws = st.selectbox("Select Target Assignment Audit Check", [w['topic'] for w in all_ws])
            
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
                st.success("✔️ Finished Submission Roster")
                for s in completed_list:
                    st.markdown(f"- **{s}**")
            with c_pending:
                st.error("⏳ Pending Action Roster")
                for p in pending_list:
                    st.markdown(f"- **{p}**")
        else:
            st.caption("Publish assignments first to unlock monitoring matrix filters.")

# -----------------------------------------------------------------------------
# PERSONA 2 — STUDENT MULTI-SUBJECT WORKSPACE
# -----------------------------------------------------------------------------
elif st.session_state.role == "Student":
    with st.sidebar:
        student_view = st.radio("Student Control Desk", ["🎒 Enroll in a Class", "📂 Subject-Filtered Worksheet Desk", "🏆 My Performance Ledger"])
        
    if student_view == "🎒 Enroll in a Class":
        st.header("🎒 Connect External Course Workspace Network")
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT username, subject FROM users WHERE role = 'Teacher';")
            teachers_list = cur.fetchall()
        conn.close()
        
        if teachers_list:
            teacher_options = [f"{t['username']} — Class Department: {t['subject']}" for t in teachers_list]
            selected_option = st.selectbox("Select Academic Instructor", teacher_options)
            
            with st.form("enrollment_form"):
                student_id = st.text_input("Assign Target University/School ID Token").strip()
                grade_cohort = st.selectbox("Current Cohort Index", ["Grade 6", "Grade 7", "Grade 8", "Grade 9", "Grade 10", "Grade 11", "Grade 12", "Undergraduate"])
                btn_enroll = st.form_submit_button("Submit Secure Connection Registration")
                
                if btn_enroll:
                    if not student_id:
                        st.error("Student Identification ID sequence string must be fully declared.")
                    else:
                        chosen_teacher = selected_option.split(" — ")[0]
                        chosen_subject = selected_option.split(": ")[1]
                        
                        conn = get_db_connection()
                        with conn.cursor() as cur:
                            cur.execute("""
                                SELECT * FROM students 
                                WHERE student_name = %s AND teacher_username = %s;
                            """, (st.session_state.username, chosen_teacher))
                            already_enrolled = cur.fetchone()
                            
                            if already_enrolled:
                                st.warning("Security Exception: You are already registered into this instructor's structural namespace.")
                            else:
                                cur.execute("""
                                    INSERT INTO students (id, teacher_username, student_name, grade_cohort, subject)
                                    VALUES (%s, %s, %s, %s, %s);
                                """, (student_id, chosen_teacher, st.session_state.username, grade_cohort, chosen_subject))
                                conn.commit()
                                st.success(f"Enrolled successfully into {chosen_teacher}'s class!")
                        conn.close()
        else:
            st.info("No active cloud instructor instances available to establish target linkages.")

    elif student_view == "📂 Subject-Filtered Worksheet Desk":
        st.header("📝 Task Workspace — Subject Core View")
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT teacher_username, subject FROM students WHERE student_name = %s;", (st.session_state.username,))
            my_classes = cur.fetchall()
        conn.close()
        
        if my_classes:
            class_map = {f"{c['subject']} (Instructor: {c['teacher_username']})": c for c in my_classes}
            selected_class = st.selectbox("Choose Active Class Environment Context", list(class_map.keys()))
            target_class = class_map[selected_class]
            
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, topic, content FROM worksheets 
                    WHERE teacher_username = %s AND subject = %s;
                """, (target_class['teacher_username'], target_class['subject']))
                available_worksheets = cur.fetchall()
            conn.close()
            
            if available_worksheets:
                worksheet_map = {w['topic']: w for w in available_worksheets}
                selected_topic = st.selectbox("Select Assignment Target Focus Topic", list(worksheet_map.keys()))
                active_ws = worksheet_map[selected_topic]
                
                # Check if already graded
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM grades 
                        WHERE student_name = %s AND teacher_username = %s AND task_name = %s;
                    """, (st.session_state.username, target_class['teacher_username'], selected_topic))
                    already_graded = cur.fetchone()
                conn.close()
                
                if already_graded:
                    st.warning(f"🔒 You have already logged an official solution log for {selected_topic}. Grade: {already_graded['mark']}/100")
                else:
                    # RUN BACKGROUND AI SWEEP TO STRIP ANSWER KEYS
                    if f"stripped_{active_ws['id']}" not in st.session_state:
                        with st.spinner("AI Sweeper sanitizing assignment text parameters..."):
                            prompt = f"The following document is an academic worksheet with a model answers block appended at the bottom. Completely strip out, delete, and omit the entire answer key block, section, or anything that resembles responses. Only output the clean test sheet containing the questions.\n\nDOCUMENT:\n{active_ws['content']}"
                            try:
                                response = ai_client.models.generate_content(
                                    model='gemini-2.5-flash',
                                    contents=prompt,
                                    config=types.GenerateContentConfig(
                                        system_instruction="You are a data sanitization security script. Strip the answer key block cleanly and leave absolutely zero hints or answers."
                                    )
                                )
                                st.session_state[f"stripped_{active_ws['id']}"] = response.text
                            except Exception as e:
                                st.error(f"Sanitization Engine Timeout: {e}")
                                st.stop()
                    
                    st.subheader("📋 Core Examination Blueprint")
                    st.markdown(st.session_state[f"stripped_{active_ws['id']}"])
                    
                    st.markdown("---")
                    student_submission_text = st.text_area("Input Your Answers Below (e.g., Q1: Answer, Q2: Answer...)", height=250)
                    
                    if st.button("Finalize and Submit Assignment Log", use_container_width=True):
                        if not student_submission_text.strip():
                            st.error("Submission input content buffer cannot be completely blank.")
                        else:
                            with st.spinner("AI Real-time Evaluator Engine grading submission..."):
                                prompt = f"""
                                Master Assessment Context:
                                {active_ws['content']}
                                
                                Student Submitted Input Log:
                                {student_submission_text}
                                
                                Evaluate the student's submission against the master sheet answers. Grade it out of 100. Return a JSON object with the keys "grade" (integer) and "feedback" (string). Do not include markdown code block formatting (like ```json).
                                """
                                try:
                                    response = ai_client.models.generate_content(
                                        model='gemini-2.5-flash',
                                        contents=prompt,
                                        config=types.GenerateContentConfig(
                                            response_mime_type="application/json",
                                            system_instruction="You are a strict automated grading assistant. Evaluate submissions accurately and output raw valid JSON code only."
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
                                st.success("Assignment logged successfully inside cloud computing database.")
                                st.metric("Instant AI Computed Grade Result", f"{res_data['grade']} / 100")
                                st.info(f"Feedback Report: {res_data['feedback']}")
            else:
                st.info("No active worksheets found for this classroom instance.")
        else:
            st.warning("Please enroll into a classroom context first to view assignments.")

    elif student_view == "🏆 My Performance Ledger":
        st.header("🏆 My Performance Ledger & Report Matrix")
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT task_name, subject, mark, feedback 
                FROM grades WHERE student_name = %s;
            """, (st.session_state.username,))
            my_grades = cur.fetchall()
        conn.close()
        
        if my_grades:
            marks_list = [g['mark'] for g in my_grades]
            overall_gpa_mean = sum(marks_list) / len(marks_list)
            
            st.metric("Cumulative System Matrix Score Average", f"{overall_gpa_mean:.2f}%")
            st.subheader("📚 Historically Logged Assessment Records")
            st.dataframe(my_grades, use_container_width=True)
        else:
            st.info("No performance markers have been submitted or processed yet.")
