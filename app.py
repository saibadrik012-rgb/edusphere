import os
import json
import hashlib
import sqlite3
from taipy.gui import Gui, notify

# -----------------------------------------------------------------------------
# INTERNAL PERSISTENT STORAGE INITIALIZATION (NO SUPABASE NEEDED)
# -----------------------------------------------------------------------------
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_KEY:
    print("❌ ERROR: Missing GEMINI_API_KEY environment variable!")

# Initialize Google GenAI Client
from google import genai
from google.genai import types
ai_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

# Route to Hugging Face persistent block storage, fallback to local file directory
DB_DIR = "/data" if os.path.exists("/data") else "."
DB_PATH = os.path.join(DB_DIR, "edusphere.db")

def get_db_connection():
    """Establishes an internal connection to the persistent SQLite database file."""
    try:
        conn = sqlite3.connect(DB_PATH)
        # Allows accessing columns by string names like a dictionary
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"⚠️ Internal Database Connection Failure: {e}")
        return None

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    """Initializes schema locally and injects fallback admin account."""
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY, 
            password_hash TEXT, 
            role TEXT, 
            subject TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id TEXT, 
            teacher_username TEXT, 
            student_name TEXT, 
            grade_cohort TEXT, 
            subject TEXT,
            PRIMARY KEY (student_name, teacher_username)
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            teacher_username TEXT, 
            subject TEXT, 
            topic TEXT, 
            content TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS worksheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            teacher_username TEXT, 
            subject TEXT, 
            topic TEXT, 
            content TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            teacher_username TEXT, 
            student_name TEXT, 
            subject TEXT, 
            task_name TEXT, 
            mark INTEGER, 
            feedback TEXT, 
            student_submission TEXT
        );
    """)
    
    # Inject default teacher profile if system records are empty
    cursor.execute("SELECT COUNT(*) as count FROM users;")
    if cursor.fetchone()['count'] == 0:
        fallback_hash = hash_password("admin123")
        cursor.execute("INSERT INTO users (username, password_hash, role, subject) VALUES ('admin', ?, 'Teacher', 'General Science');", (fallback_hash,))
        conn.commit()
    conn.close()

# Run database setup checks
init_db()

# -----------------------------------------------------------------------------
# GLOBAL TAIPY APP STATE MANAGER (SHARED VARIABLES)
# -----------------------------------------------------------------------------
username_input = ""
password_input = ""
reg_username = ""
reg_password = ""
reg_role = "Teacher"
reg_subject = "General Science"

logged_in = False
current_user = ""
user_role = ""
user_subject = ""

selected_view = "Classroom Roster"
topic_input = ""
grade_tier = "Grade 9-12 High School"
ai_output_lesson = ""
w_topic_input = ""
ai_output_worksheet = ""

total_students_metric = "0 Enrolled"
class_mean_metric = "0.0%"
published_tasks_metric = "0 Live Sheets"
roster_table_data = []
predictive_risk_logs = []

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

selected_language = "English"
language_options = ["English", "Spanish (Español)", "French (Français)", "German (Deutsch)", "Mandarin (中文)", "Hindi (हिन्दी)", "Arabic (العربية)", "Japanese (日本語)", "Russian (Русский)", "Portuguese (Português)"]

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

UI = dict(ENGLISH_BASE)

def translate_app_ui(state):
    if state.selected_language == "English":
        state.UI = dict(ENGLISH_BASE)
        return
    try:
        translation_prompt = (
            f"You are a master localization system. Translate every single value in this JSON dictionary into {state.selected_language}. "
            f"Keep the keys identical. Output ONLY the translated JSON dictionary object directly back, no markdown ticks:\n\n"
            f"{json.dumps(ENGLISH_BASE)}"
        )
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=translation_prompt)
        state.UI = json.loads(response.text.strip())
        notify(state, "success", f"Interface localized to {state.selected_language}!")
    except Exception as e:
        print(f"Translation Error: {e}")
        notify(state, "warning", "Localization engine timeout. Using English default.")

# -----------------------------------------------------------------------------
# APP LOGIC METHODS (SQLITE ADAPTED)
# -----------------------------------------------------------------------------
def handle_login(state):
    if not state.username_input or not state.password_input:
        notify(state, "error", "Please supply both tracking credentials.")
        return
        
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?;", (state.username_input.strip(),))
    row = cursor.fetchone()
    conn.close()
    
    if row and row['password_hash'] == hash_password(state.password_input):
        state.logged_in = True
        state.current_user = row['username']
        state.user_role = row['role']
        state.user_subject = row['subject']
        notify(state, "success", f"Authenticated successfully as {state.current_user}")
        refresh_data_matrices(state)
    else:
        notify(state, "error", "Invalid credentials or user record missing.")

def handle_registration(state):
    if not state.reg_username or not state.reg_password:
        notify(state, "error", "Username and Password fields cannot be left blank.")
        return
        
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE username = ?;", (state.reg_username.strip(),))
    if cursor.fetchone():
        notify(state, "error", "This registration username already exists.")
        conn.close()
        return
        
    assigned_subject = state.reg_subject if state.reg_role == "Teacher" else "Student Framework"
    hashed_w = hash_password(state.reg_password)
    cursor.execute("INSERT INTO users (username, password_hash, role, subject) VALUES (?, ?, ?, ?);", 
                   (state.reg_username.strip(), hashed_w, state.reg_role, assigned_subject))
    conn.commit()
    conn.close()
    notify(state, "success", "Tenant deployed! You can now log in safely.")

def refresh_data_matrices(state):
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()
    
    if state.user_role == "Teacher":
        cursor.execute("SELECT student_name, grade_cohort, subject FROM students WHERE teacher_username = ?;", (state.current_user,))
        state.roster_table_data = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT count(*) as count FROM students WHERE teacher_username = ?;", (state.current_user,))
        state.total_students_metric = f"{cursor.fetchone()['count']} Enrolled"
        
        cursor.execute("SELECT avg(mark) as avg_mark FROM grades WHERE teacher_username = ?;", (state.current_user,))
        mean_score = cursor.fetchone()['avg_mark']
        state.class_mean_metric = f"{float(mean_score):.1f}%" if mean_score else "0.0%"
        
        cursor.execute("SELECT count(*) as count FROM worksheets WHERE teacher_username = ?;", (state.current_user,))
        state.published_tasks_metric = f"{cursor.fetchone()['count']} Live Sheets"
        
    elif state.user_role == "Student":
        cursor.execute("SELECT username, subject FROM users WHERE role = 'Teacher';")
        state.available_teachers = [f"{t['username']} — Dept: {t['subject']}" for t in cursor.fetchall()]
        
        cursor.execute("SELECT teacher_username, subject FROM students WHERE student_name = ?;", (state.current_user,))
        my_classes = cursor.fetchall()
        if my_classes:
            cursor.execute("SELECT topic FROM worksheets WHERE teacher_username = ? AND subject = ?;", (my_classes[0]['teacher_username'], my_classes[0]['subject']))
            state.available_worksheets = [w['topic'] for w in cursor.fetchall()]
            
        cursor.execute("SELECT task_name, subject, mark, feedback FROM grades WHERE student_name = ?;", (state.current_user,))
        state.my_grades_table_data = [dict(row) for row in cursor.fetchall()]
        
    conn.close()

def generate_lesson_plan(state):
    if not state.topic_input: return
    notify(state, "info", "Compiling custom 5E syllabus array...")
    prompt = f"Design an exhaustive 5E lesson layout regarding '{state.topic_input}' optimized for {state.grade_tier}. Write the output directly in {state.selected_language}."
    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    state.ai_output_lesson = response.text

def generate_worksheet(state):
    if not state.w_topic_input: return
    notify(state, "info", "Formulating assessment schema blocks...")
    prompt = f"Create a 5-question conceptual worksheet about '{state.w_topic_input}' for '{state.user_subject}'. Append an explicit '--- ANSWER KEY ---' block at the bottom. Write directly in {state.selected_language}."
    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    state.ai_output_worksheet = response.text

def commit_worksheet_to_cloud(state):
    if not state.ai_output_worksheet: return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO worksheets (teacher_username, subject, topic, content) VALUES (?, ?, ?, ?);",
                (state.current_user, state.user_subject, state.w_topic_input, state.ai_output_worksheet))
    conn.commit()
    conn.close()
    notify(state, "success", "Worksheet committed securely down to local storage records.")
    refresh_data_matrices(state)

def run_predictive_risk_sweep(state):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT student_name, task_name, mark, feedback, student_submission FROM grades WHERE teacher_username = ?;", (state.current_user,))
    payload = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    if not payload:
        notify(state, "warning", "Insufficient classroom grade logs to map trend lines.")
        return
        
    notify(state, "info", "Predictive diagnostics engine running variance matrix sweeps...")
    prompt = f"Analyze this classroom grade history: {json.dumps(payload)}. Identify students trending under 70%, their specific gap, and an intervention path. Translate findings to {state.selected_language}. Output strictly as a valid JSON list format: [{{\"student\":\"Name\",\"risk\":\"High/Medium\",\"weakness\":\"Gap\",\"action\":\"Strategy\"}}]"
    
    try:
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        state.predictive_risk_logs = json.loads(response.text.strip())
        notify(state, "success", "Risk analysis sweep deployed successfully!")
    except Exception as e:
        notify(state, "error", f"Parsing Fault: {e}")

def handle_class_enrollment(state):
    if not state.student_id_token or not state.selected_teacher_string: return
    t_name = state.selected_teacher_string.split(" — ")[0]
    t_sub = state.selected_teacher_string.split("Dept: ")[1]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO students (id, teacher_username, student_name, grade_cohort, subject) VALUES (?, ?, ?, ?, ?);",
                (state.student_id_token, t_name, state.current_user, state.student_grade_cohort, t_sub))
    conn.commit()
    conn.close()
    notify(state, "success", "Linked to class network successfully.")
    refresh_data_matrices(state)

def load_sanitized_worksheet(state):
    if not state.selected_worksheet_topic: return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM worksheets WHERE topic = ?;", (state.selected_worksheet_topic,))
    raw_ws = cursor.fetchone()
    conn.close()
    
    if raw_ws:
        notify(state, "info", "AI Security pipeline sanitizing test data elements...")
        prompt = f"Completely strip out and delete the answer key block section from this text. Translate the remaining clean questions into {state.selected_language}:\n\n{raw_ws['content']}"
        res = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        state.sanitized_blueprint_text = res.text

def process_student_homework_submission(state):
    if not state.student_answer_buffer: return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT content, teacher_username, subject FROM worksheets WHERE topic = ?;", (state.selected_worksheet_topic,))
    master_ws = cursor.fetchone()
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
            cursor = conn.cursor()
            cursor.execute("INSERT INTO grades (teacher_username, student_name, subject, task_name, mark, feedback, student_submission) VALUES (?,?,?,?,?,?,?);",
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
# TAIPY MARKDOWN LAYOUT BLUEPRINT
# -----------------------------------------------------------------------------
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
        <label>Username</label><input value="{username_input}" class="fullwidth"/><br/><br/>
        <label>Password</label><input value="{password_input}" type="password" class="fullwidth"/><br/><br/>
        <button label="Authenticate Access" on_action="handle_login" class="btn-primary"/>
    </part>
    <part class="card">
        <h3>📝 New Institutional Registration</h3>
        <label>Create New Profile Username</label><input value="{reg_username}" class="fullwidth"/><br/><br/>
        <label>Secure Key Password</label><input value="{reg_password}" type="password" class="fullwidth"/><br/><br/>
        <label>System Role Persona</label><selector value="{reg_role}" lov="Teacher;Student" dropdown="True"/><br/><br/>
        <label>Teaching Dept</label><selector value="{reg_subject}" lov="Mathematics;General Science;English Language Arts;Social Studies;Computer Science" dropdown="True"/><br/><br/>
        <button label="Deploy Global Tenant" on_action="handle_registration" class="btn-secondary"/>
    </part>
</layout>
</part>
</div>
"""

teacher_layout = """
<part render="{logged_in and user_role == 'Teacher'}">
<h2>🍎 Instructor Console — Dept: <tpl>{user_subject}</tpl></h2>
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
            <label>Syllabus Target Topic</label><input value="{topic_input}" class="fullwidth"/><br/><br/>
            <label>Target Cohort Grade Tier Selection</label><selector value="{grade_tier}" lov="Grade 6-8 Middle School;Grade 9-12 High School;Undergraduate Ivy-League" dropdown="True"/><br/><br/>
            <button label="Synthesize Lesson Plan" on_action="generate_lesson_plan" class="btn-primary"/><br/><br/>
            <text_area value="{ai_output_lesson}" height="350px" class="fullwidth"/>
        </part>
        <part render="{selected_view == 'AI Worksheet Factory'}">
            <h3>📝 Assessment Factory & Blueprint Key Generator</h3>
            <label>Target Core Unit Objective</label><input value="{w_topic_input}" class="fullwidth"/><br/><br/>
            <button label="Generate Test Sheet & Key" on_action="generate_worksheet" class="btn-primary"/><br/><br/>
            <text_area value="{ai_output_worksheet}" height="300px" class="fullwidth"/><br/><br/>
            <button label="Commit Worksheet to Local Storage Database" on_action="commit_worksheet_to_cloud" class="btn-success"/>
        </part>
        <part render="{selected_view == '📊 Student Advanced Analytics'}">
            <h3>📈 Command System Metrics Grid</h3>
            <layout columns="1 1 1" gap="15px">
                <div style="background:#222;padding:15px;border-radius:8px;text-align:center;"><h5>Roster Volume</h5><h2><tpl>{total_students_metric}</tpl></h2></div>
                <div style="background:#222;padding:15px;border-radius:8px;text-align:center;"><h5>Grade Mean</h5><h2><tpl>{class_mean_metric}</tpl></h2></div>
                <div style="background:#222;padding:15px;border-radius:8px;text-align:center;"><h5>Live Test Forms</h5><h2><tpl>{published_tasks_metric}</tpl></h2></div>
            </layout>
            <hr/>
            <h3>🔮 Predictive Student Risk Diagnostics Mapping Suite</h3>
            <button label="Run Automated AI Forensic Risk Sweep" on_action="run_predictive_risk_sweep" class="btn-warning"/><br/><br/>
            <part render="{len(predictive_risk_logs) > 0}">
                <table data="{predictive_risk_logs}"/>
            </part>
        </part>
    </part>
</layout>
</part>
"""

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
            <h3>🎒 Connect Course Workspace Network</h3>
            <label>Select Academic Instructor</label><selector value="{selected_teacher_string}" lov="{available_teachers}" dropdown="True"/><br/><br/>
            <label>Assign Student ID Token</label><input value="{student_id_token}" class="fullwidth"/><br/><br/>
            <label>Current Study Cohort Group</label><selector value="{student_grade_cohort}" lov="Grade 6;Grade 9;Grade 11;Undergraduate" dropdown="True"/><br/><br/>
            <button label="Submit Secure Connection Registration" on_action="handle_class_enrollment" class="btn-primary"/>
        </part>
        <part render="{student_view == '📂 Subject-Filtered Worksheet Desk'}">
            <h3>📝 Automated Sanitized Task Workspace</h3>
            <label>Select Active Assignment Target</label><selector value="{selected_worksheet_topic}" lov="{available_worksheets}" dropdown="True" on_change="load_sanitized_worksheet"/>
            <br/><br/>
            <part render="{selected_worksheet_topic != ''}">
                <h5>📋 Sanitized Examination Blueprint (Answers Stripped by AI)</h5>
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

localization_bar = """
<div style="background:#111;padding:10px;border-radius:6px;margin-bottom:10px;">
<layout columns="3 1">
    <p style="margin-top:8px;">🌐 <b>Global Localization Platform Engine Suite:</b> Choose application interface language:</p>
    <selector value="{selected_language}" lov="{language_options}" dropdown="True" on_change="translate_app_ui"/>
</layout>
</div>
"""

full_ui_blueprint = localization_bar + login_layout + teacher_layout + student_layout

app = Gui(page=full_ui_blueprint)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860, use_reloader=True)