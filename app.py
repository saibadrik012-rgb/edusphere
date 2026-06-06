import os
import json
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from taipy.gui import Gui, notify, navigate
from google import genai
from google.genai import types

# -----------------------------------------------------------------------------
# AUTH & SECRET INITIALIZATION (HUGGING FACE / CLOUD ENVIRONMENT COMPATIBLE)
# -----------------------------------------------------------------------------
# Safely pull credentials from cloud deployment environment variables
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
DB_URL = os.environ.get("SUPABASE_DB_URL")

if not GEMINI_KEY or not DB_URL:
    print("❌ ERROR: Missing GEMINI_API_KEY or SUPABASE_DB_URL environment variables!")

# Initialize Google GenAI Client
ai_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

def get_db_connection():
    try:
        return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    except Exception as e:
        print(f"⚠️ Database Connection Failure: {e}")
        return None

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# -----------------------------------------------------------------------------
# GLOBAL TAIPY APP STATE MANAGER (SHARED VARIABLES)
# -----------------------------------------------------------------------------
# User authentication state variables
username_input = ""
password_input = ""
reg_username = ""
reg_password = ""
reg_role = "Teacher"
reg_subject = "General Science"

# Session state flags
logged_in = False
current_user = ""
user_role = ""
user_subject = ""

# Teacher Panel Content
selected_view = "Classroom Roster"
topic_input = ""
grade_tier = "Grade 9-12 High School"
ai_output_lesson = ""
w_topic_input = ""
ai_output_worksheet = ""

# Metrics / Analytics Variables
total_students_metric = "0 Enrolled"
class_mean_metric = "0.0%"
published_tasks_metric = "0 Live Sheets"
roster_table_data = []
analytics_table_data = []
predictive_risk_logs = []

# Student Panel Content
student_view = "🎒 Enroll in a Class"
student_id_token = ""
student_grade_cohort = "Undergraduate"
available_teachers = []
selected_teacher_string = ""
available_worksheets = []
selected_worksheet_topic = ""
sanitized_blueprint_text = ""
student_answer_buffer = ""
student_grade_result = "N/A"
student_feedback_report = ""
my_grades_table_data = []

# Global Localization State
selected_language = "English"
language_options = ["English", "Spanish (Español)", "French (Français)", "German (Deutsch)", "Mandarin (中文)", "Hindi (हिन्दी)", "Arabic (العربية)", "Japanese (日本語)", "Russian (Русский)", "Portuguese (Português)"]

# Baseline English Translation Dictionary Blueprint
ENGLISH_BASE = {
    "app_title": "EduSphere Core Management Portal",
    "welcome_msg": "Welcome to the unified Multi-Tenant Classroom Platform. Please sign in or register to connect to your cloud dashboard.",
    "username": "Username",
    "password": "Password",
    "btn_signin": "Authenticate Access",
    "create_user": "Create Username",
    "secure_pass": "Secure Password",
    "role_persona": "Institutional Role Persona",
    "teaching_dept": "Teaching Assignment Domain",
    "btn_deploy_tenant": "Deploy Global Tenant",
    "logout_btn": "Log Out Securely",
    "master_workspace": "Master Workspace Core",
    "btn_synth_lesson": "Synthesize Lesson Curriculum",
    "btn_gen_worksheet": "Generate Master Assessment Artifact",
    "btn_risk_sweep": "Run Automated AI Forensic Risk Sweep",
    "submit_conn_btn": "Submit Secure Connection Registration",
    "finalize_submit_btn": "Finalize and Submit Assignment Log"
}

# Active runtime UI dictionary
UI = dict(ENGLISH_BASE)

def translate_app_ui(state):
    """Translates the complete system UI blueprint dictionary in one fast, single API call to prevent interface lag."""
    if state.selected_language == "English":
        state.UI = dict(ENGLISH_BASE)
        return
        
    try:
        translation_prompt = (
            f"You are a master localization system. Translate every single value in this JSON dictionary into {state.selected_language}. "
            f"Keep the keys identical. Output ONLY the translated JSON dictionary directly back, no markdown code blocks:\n\n"
            f"{json.dumps(ENGLISH_BASE)}"
        )
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=translation_prompt)
        state.UI = json.loads(response.text.strip())
        notify(state, "success", f"Interface localized to {state.selected_language}!")
    except Exception as e:
        print(f"Translation Error: {e}")
        notify(state, "warning", "Localization engine timeout. Using English default.")

# -----------------------------------------------------------------------------
# ACTIONS / APP LOGIC CONTROLLERS
# -----------------------------------------------------------------------------
def handle_login(state):
    """Validates login credentials against the Supabase/Neon PostgreSQL cluster."""
    if not state.username_input or not state.password_input:
        notify(state, "error", "Please supply both tracking credentials.")
        return
        
    conn = get_db_connection()
    if not conn:
        return
        
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = %s;", (state.username_input.strip(),))
        user_record = cur.fetchone()
    conn.close()
    
    if user_record and user_record['password_hash'] == hash_password(state.password_input):
        state.logged_in = True
        state.current_user = user_record['username']
        state.user_role = user_record['role']
        state.user_subject = user_record['subject']
        notify(state, "success", f"Authenticated successfully as {state.current_user}")
        refresh_data_matrices(state)
    else:
        notify(state, "error", "Invalid credentials or user record missing.")

def handle_registration(state):
    """Deploys a brand new secure isolated tenant record inside the database layers."""
    if not state.reg_username or not state.reg_password:
        notify(state, "error", "Username and Password fields cannot be left blank.")
        return
        
    conn = get_db_connection()
    if not conn:
        return
        
    with conn.cursor() as cur:
        cur.execute("SELECT username FROM users WHERE username = %s;", (state.reg_username.strip(),))
        if cur.fetchone():
            notify(state, "error", "This registration username already exists.")
            conn.close()
            return
            
        assigned_subject = state.reg_subject if state.reg_role == "Teacher" else "Student Framework"
        hashed_w = hash_password(state.reg_password)
        cur.execute("INSERT INTO users (username, password_hash, role, subject) VALUES (%s, %s, %s, %s);", 
                    (state.reg_username.strip(), hashed_w, state.reg_role, assigned_subject))
        conn.commit()
    conn.close()
    notify(state, "success", "Tenant deployed! You can now log in safely.")

def refresh_data_matrices(state):
    """Fetches real-time context data dynamically depending on who logged into the app instance."""
    conn = get_db_connection()
    if not conn: return
    
    with conn.cursor() as cur:
        if state.user_role == "Teacher":
            # Classroom Roster Pull
            cur.execute("SELECT student_name, grade_cohort, subject FROM students WHERE teacher_username = %s;", (state.current_user,))
            state.roster_table_data = list(cur.fetchall())
            
            # General Statistics calculations
            cur.execute("SELECT count(*) FROM students WHERE teacher_username = %s;", (state.current_user,))
            state.total_students_metric = f"{cur.fetchone()['count']} Enrolled"
            
            cur.execute("SELECT avg(mark) FROM grades WHERE teacher_username = %s;", (state.current_user,))
            mean_score = cur.fetchone()['avg']
            state.class_mean_metric = f"{float(mean_score):.1f}%" if mean_score else "0.0%"
            
            cur.execute("SELECT count(*) FROM worksheets WHERE teacher_username = %s;", (state.current_user,))
            state.published_tasks_metric = f"{cur.fetchone()['count']} Live Sheets"
            
        elif state.user_role == "Student":
            # Setup list of active academic teachers to choose from for classes
            cur.execute("SELECT username, subject FROM users WHERE role = 'Teacher';")
            state.available_teachers = [f"{t['username']} — Dept: {t['subject']}" for t in cur.fetchall()]
            
            # Setup current homework data feeds
            cur.execute("SELECT teacher_username, subject FROM students WHERE student_name = %s;", (state.current_user,))
            my_classes = cur.fetchall()
            if my_classes:
                cur.execute("SELECT topic FROM worksheets WHERE teacher_username = %s AND subject = %s;", (my_classes[0]['teacher_username'], my_classes[0]['subject']))
                state.available_worksheets = [w['topic'] for w in cur.fetchall()]
                
            # History log pulls
            cur.execute("SELECT task_name, subject, mark, feedback FROM grades WHERE student_name = %s;", (state.current_user,))
            state.my_grades_table_data = list(cur.fetchall())
            
    conn.close()

def generate_lesson_plan(state):
    """Calls Gemini to compile a comprehensive 5E lesson schema directly in the target chosen language."""
    if not state.topic_input:
        notify(state, "warning", "Please provide a lesson topic.")
        return
    notify(state, "info", "Compiling custom 5E syllabus array...")
    prompt = f"Design an exhaustive 5E lesson layout regarding '{state.topic_input}' optimized for {state.grade_tier}. Write the output directly in {state.selected_language}."
    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    state.ai_output_lesson = response.text

def generate_worksheet(state):
    """Assembles a clean textbook test worksheet layout with answer blocks embedded on the back end."""
    if not state.w_topic_input:
        notify(state, "warning", "Provide a unit focal objective topic.")
        return
    notify(state, "info", "Formulating assessment schema blocks...")
    prompt = f"Create a 5-question conceptual worksheet about '{state.w_topic_input}' for '{state.user_subject}'. Append an explicit '--- ANSWER KEY ---' block at the bottom. Write directly in {state.selected_language}."
    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    state.ai_output_worksheet = response.text

def commit_worksheet_to_cloud(state):
    """Commits finished teacher worksheets directly down to the shared relational network partitions."""
    if not state.ai_output_worksheet: return
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO worksheets (teacher_username, subject, topic, content) VALUES (%s, %s, %s, %s);",
                    (state.current_user, state.user_subject, state.w_topic_input, state.ai_output_worksheet))
        conn.commit()
    conn.close()
    notify(state, "success", "Worksheet committed securely down to infrastructure records.")
    refresh_data_matrices(state)

def run_predictive_risk_sweep(state):
    """PREMIUM ENGINE: Forensic relational metric scanner running prediction mappings on grade histories."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT student_name, task_name, mark, feedback, student_submission FROM grades WHERE teacher_username = %s;", (state.current_user,))
        payload = cur.fetchall()
    conn.close()
    
    if not payload:
        notify(state, "warning", "Insufficient classroom grade logs to map trend lines.")
        return
        
    notify(state, "info", "Predictive diagnostics engine running variance matrix sweeps...")
    prompt = f"Analyze this classroom grade history payload: {json.dumps(payload, default=str)}. Identify students trending under 70%, their specific gap, and an intervention path. Translate findings to {state.selected_language}. Output strictly as raw JSON list: [{{\"student\":\"Name\",\"risk\":\"High/Medium\",\"weakness\":\"Gap\",\"action\":\"Strategy\"}}]"
    
    try:
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        state.predictive_risk_logs = json.loads(response.text.strip())
        notify(state, "success", "Risk analysis sweep deployed successfully!")
    except Exception as e:
        notify(state, "error", f"Parsing Fault: {e}")

def handle_class_enrollment(state):
    """Links a student to an instructor course namespace partition dynamically."""
    if not state.student_id_token or not state.selected_teacher_string:
        notify(state, "error", "Complete all enrollment field strings.")
        return
    t_name = state.selected_teacher_string.split(" — ")[0]
    t_sub = state.selected_teacher_string.split(": ")[1]
    
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO students (id, teacher_username, student_name, grade_cohort, subject) VALUES (%s, %s, %s, %s, %s);",
                    (state.student_id_token, t_name, state.current_user, state.student_grade_cohort, t_sub))
        conn.commit()
    conn.close()
    notify(state, "success", f"Linked to class network successfully.")
    refresh_data_matrices(state)

def load_sanitized_worksheet(state):
    """AI SWEATING INTERCEPT: Hides answer keys and localizes questions before they load on the student screen."""
    if not state.selected_worksheet_topic: return
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT content FROM worksheets WHERE topic = %s;", (state.selected_worksheet_topic,))
        raw_ws = cur.fetchone()
    conn.close()
    
    if raw_ws:
        notify(state, "info", "AI Security pipeline sanitizing test data elements...")
        prompt = f"Completely strip out and delete the answer key block section from this text. Translate the remaining clean questions into {state.selected_language}:\n\n{raw_ws['content']}"
        res = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        state.sanitized_blueprint_text = res.text

def process_student_homework_submission(state):
    """Instantly evaluates student homework logs against backend keys and logs the result."""
    if not state.student_answer_buffer: return
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT content, teacher_username, subject FROM worksheets WHERE topic = %s;", (state.selected_worksheet_topic,))
        master_ws = cur.fetchone()
    conn.close()
    
    if master_ws:
        notify(state, "info", "Real-time AI evaluator computing grading parameters...")
        prompt = f"Master Sheet: {master_ws['content']}. Student submission text: {state.student_answer_buffer}. Grade out of 100. Return a JSON object with keys \"grade\" (integer) and \"feedback\" (string, written directly in {state.selected_language})."
        
        try:
            res = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json"))
            data = json.loads(res.text.strip())
            
            state.student_grade_result = str(data['grade'])
            state.student_feedback_report = data['feedback']
            
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("INSERT INTO grades (teacher_username, student_name, subject, task_name, mark, feedback, student_submission) VALUES (%s,%s,%s,%s,%s,%s,%s);",
                            (master_ws['teacher_username'], state.current_user, master_ws['subject'], state.selected_worksheet_topic, int(data['grade']), data['feedback'], state.student_answer_buffer))
                conn.commit()
            conn.close()
            notify(state, "success", f"Assignment logged! Score: {state.student_grade_result}/100")
            refresh_data_matrices(state)
        except Exception as e:
            notify(state, "error", f"Grading Fault: {e}")

def trigger_logout(state):
    state.logged_in = False
    state.current_user = ""
    state.user_role = ""

# -----------------------------------------------------------------------------
# TAIPY FLUID MARKDOWN UI ENGINE DEFINITION
# -----------------------------------------------------------------------------
# 1. Login Matrix Interface View Layout
login_layout = """
<center>
<h1><tpl>{UI['app_title']}</tpl></h1>
<p><tpl>{UI['welcome_msg']}</tpl></p>
</center>

<hr/>

<div class="container">
<part render="{not logged_in}">
<layout columns="1 1" gap="30px">
    <part class="card">
        <h3>🔑 Sign-In Gateway</h3>
        <label>Username</label>
        <input value="{username_input}" class="fullwidth"/>
        <br/><br/>
        <label>Password</label>
        <input value="{password_input}" type="password" class="fullwidth"/>
        <br/><br/>
        <button label="Authenticate Access" on_action="handle_login" class="btn-primary"/>
    </part>

    <part class="card">
        <h3>📝 New Institutional Registration</h3>
        <label>Create New Profile Username</label>
        <input value="{reg_username}" class="fullwidth"/>
        <br/><br/>
        <label>Secure Key Password</label>
        <input value="{reg_password}" type="password" class="fullwidth"/>
        <br/><br/>
        <label>System Role Persona</label>
        <selector value="{reg_role}" lov="Teacher;Student" dropdown="True"/>
        <br/><br/>
        <label>Teaching Dept (Teachers Only)</label>
        <selector value="{reg_subject}" lov="Mathematics;General Science;English Language Arts;Social Studies / Humanities;Computer Science" dropdown="True"/>
        <br/><br/>
        <button label="Deploy Global Tenant" on_action="handle_registration" class="btn-secondary"/>
    </part>
</layout>
</part>
</div>
"""

# 2. Complete Instructor/Teacher Console Interface Layout
teacher_layout = """
<part render="{logged_in and user_role == 'Teacher'}">
<h2>🍎 Master Dashboard Matrix — Dept: <tpl>{user_subject}</tpl></h2>
<hr/>

<layout columns="1 4" gap="20px">
    <part class="sidebar-card">
        <h4>Navigation Desk</h4>
        <selector value="{selected_view}" lov="Classroom Roster;AI Lesson Architect;AI Worksheet Factory;📊 Student Advanced Analytics" mode="radio"/>
        <br/><br/>
        <button label="Log Out" on_action="trigger_logout" class="btn-danger"/>
    </part>

    <part class="main-content">
        <part render="{selected_view == 'Classroom Roster'}">
            <h3>👥 Active Class Enrollment Roster</h3>
            <table data="{roster_table_data}"/>
        </part>

        <part render="{selected_view == 'AI Lesson Architect'}">
            <h3>🧠 Core 5E Lesson Plan Synthesis Machine</h3>
            <label>Syllabus Target Unit Topic</label>
            <input value="{topic_input}" class="fullwidth"/>
            <br/><br/>
            <label>Target Cohort Grade Tier Selection</label>
            <selector value="{grade_tier}" lov="Grade 6-8 Middle School;Grade 9-12 High School;Undergraduate Ivy-League" dropdown="True"/>
            <br/><br/>
            <button label="Synthesize Lesson Plan" on_action="generate_lesson_plan" class="btn-primary"/>
            <br/><br/>
            <text_area value="{ai_output_lesson}" height="350px" class="fullwidth"/>
        </part>

        <part render="{selected_view == 'AI Worksheet Factory'}">
            <h3>📝 Assessment Factory & Blueprint Key Generator</h3>
            <label>Target Core Unit Objective Focus</label>
            <input value="{w_topic_input}" class="fullwidth"/>
            <br/><br/>
            <button label="Generate Test Sheet & Key" on_action="generate_worksheet" class="btn-primary"/>
            <br/><br/>
            <text_area value="{ai_output_worksheet}" height="300px" class="fullwidth"/>
            <br/><br/>
            <button label="Commit Worksheet to Live Tenant Database" on_action="commit_worksheet_to_cloud" class="btn-success"/>
        </part>

        <part render="{selected_view == '📊 Student Advanced Analytics'}">
            <h3>📈 Management Control Command System Grid</h3>
            <layout columns="1 1 1" gap="15px">
                <div class="metric-box"><h5>Roster Volume</h5><h2><tpl>{total_students_metric}</tpl></h2></div>
                <div class="metric-box"><h5>Grade running Mean</h5><h2><tpl>{class_mean_metric}</tpl></h2></div>
                <div class="metric-box"><h5>Live Test Forms</h5><h2><tpl>{published_tasks_metric}</tpl></h2></div>
            </layout>
            
            <hr/>
            <h3>🔮 Predictive Student Risk Diagnostics Mapping Suite</h3>
            <p>Our platform evaluates historical grade telemetry data to detect conceptual vulnerabilities before they map into exam failures.</p>
            <button label="Run Automated AI Forensic Risk Sweep" on_action="run_predictive_risk_sweep" class="btn-warning"/>
            
            <br/><br/>
            <part render="{len(predictive_risk_logs) > 0}">
                <table data="{predictive_risk_logs}"/>
            </part>
        </part>
    </part>
</layout>
</part>
"""

# 3. Complete Student Learning Desktop UI Layout Frame
student_layout = """
<part render="{logged_in and user_role == 'Student'}">
<h2>🎒 Student Action Desktop Portal</h2>
<hr/>

<layout columns="1 4" gap="20px">
    <part class="sidebar-card">
        <h4>Student Control Desk</h4>
        <selector value="{student_view}" lov="🎒 Enroll in a Class;📂 Subject-Filtered Worksheet Desk;🏆 My Performance Ledger" mode="radio"/>
        <br/><br/>
        <button label="Log Out" on_action="trigger_logout" class="btn-danger"/>
    </part>

    <part class="main-content">
        <part render="{student_view == '🎒 Enroll in a Class'}">
            <h3>🎒 Connect External Core Course Workspace Network</h3>
            <label>Select Target Academic Instructor Tenant Assignment</label>
            <selector value="{selected_teacher_string}" lov="{available_teachers}" dropdown="True"/>
            <br/><br/>
            <label>Assign Target Student Identification Number Token</label>
            <input value="{student_id_token}" class="fullwidth"/>
            <br/><br/>
            <label>Current Study Cohort Group Index Selection</label>
            <selector value="{student_grade_cohort}" lov="Grade 6;Grade 9;Grade 11;Undergraduate" dropdown="True"/>
            <br/><br/>
            <button label="Submit Secure Connection Registration" on_action="handle_class_enrollment" class="btn-primary"/>
        </part>

        <part render="{student_view == '📂 Subject-Filtered Worksheet Desk'}">
            <h3>📝 Automated Sanitized Task Workspace</h3>
            <label>Select Active Assignment Target Focus Topic Unit</label>
            <selector value="{selected_worksheet_topic}" lov="{available_worksheets}" dropdown="True" on_change="load_sanitized_worksheet"/>
            
            <br/><br/>
            <part render="{selected_worksheet_topic != ''}">
                <h5>📋 Sanitized Examination Blueprint (Answer Key Blocks Stripped Privately by AI)</h5>
                <text_area value="{sanitized_blueprint_text}" height="250px" class="fullwidth" active="False"/>
                <br/><hr/>
                <h5>Input Your Final Solution Answers Log Below:</h5>
                <text_area value="{student_answer_buffer}" height="150px" class="fullwidth"/>
                <br/><br/>
                <button label="Finalize and Submit Assignment Log" on_action="process_student_homework_submission" class="btn-success"/>
                <br/><hr/>
                <h5>Instant Grading Analysis Reports:</h5>
                <p><b>Computed Grade:</b> <tpl>{student_grade_result}</tpl>/100</p>
                <p><b>Evaluator Commentary:</b> <tpl>{student_feedback_report}</tpl></p>
            </part>
        </part>

        <part render="{student_view == '🏆 My Performance Ledger'}">
            <h3>🏆 Historical Academic Performance Ledger Matrix</h3>
            <table data="{my_grades_table_data}"/>
        </part>
    </part>
</layout>
</part>
"""

# 4. Central Global Sidebar Selector and Localization Module Injector
localization_bar = """
<div class="locale-bar">
<layout columns="3 1">
    <p>🌐 <b>Global Localization Platform Engine Suite:</b> Choose application dashboard interface language context:</p>
    <selector value="{selected_language}" lov="{language_options}" dropdown="True" on_change="translate_app_ui"/>
</layout>
</div>
<hr/>
"""

# Compile all sub-components into one unified page markdown structure file context
full_ui_blueprint = localization_bar + login_layout + teacher_layout + student_layout

# Initialize and spin the UI build server up engine
app = Gui(page=full_ui_blueprint)

if __name__ == "__main__":
    # Hugging Face Spaces defaults to port 7860 natively
    app.run(host="0.0.0.0", port=7860, use_reloader=True)