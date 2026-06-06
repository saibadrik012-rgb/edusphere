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
# APP LOGIC METHODS
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
# TAIPY NATIVE MARKDOWN BLUEPRINTS (100% CORRECTED COMPONENT CODES)
# -----------------------------------------------------------------------------
localization_bar = """
|<card>|
|<layout|columns=3 1|
**🌐 Global Localization Platform Engine Suite:** Choose application interface language:

<|<{selected_language}>|selector|lov={language_options}|dropdown=True|on_change=translate_app_ui|>
|
|

---
"""

login_layout = """
|<text-center>|
# {UI['app_title']}
{UI['welcome_msg']}
|

---

|<{not logged_in}>|
|<container>|
|<layout|columns=1 1|gap=30px|
|<card>|
### 🔑 Sign-In Gateway
**Username**
<|<{username_input}>|input|class_name=fullwidth|>

**Password**
<|<{password_input}>|input|password=True|class_name=fullwidth|>
<br/><br/>
<|<{UI['btn_signin']}>|button|on_action=handle_login|class_name=btn-primary|>
|

|<card>|
### 📝 New Institutional Registration
**Create New Profile Username**
<|<{reg_username}>|input|class_name=fullwidth|>

**Secure Key Password**
<|<{reg_password}>|input|password=True|class_name=fullwidth|>

**System Role Persona**
<|<{reg_role}>|selector|lov=Teacher;Student|dropdown=True|>

**Teaching Dept**
<|<{reg_subject}>|selector|lov=Mathematics;General Science;English Language Arts;Social Studies;Computer Science|dropdown=True|>
<br/><br/>
<|<{UI['btn_deploy_tenant']}>|button|on_action=handle_registration|class_name=btn-secondary|>
|
|
|
|
"""

teacher_layout = """
|<{logged_in and user_role == 'Teacher'}>|
## 🍎 Instructor Console — Dept: {user_subject}

---

|<layout|columns=1 4|gap=20px|
|<sidebar-card>|
#### Navigation Desk
<|<{selected_view}>|selector|lov=Classroom Roster;AI Lesson Architect;AI Worksheet Factory;📊 Student Advanced Analytics|mode=radio|>
<br/><br/>
<|<{UI['logout_btn']}>|button|on_action=trigger_logout|class_name=btn-danger|>
|

|<main-content>|
|<{selected_view == 'Classroom Roster'}>|
### 👥 Active Class Enrollment Roster
<|<{roster_table_data}>|table|>
|

|<{selected_view == 'AI Lesson Architect'}>|
### 🧠 Core 5E Lesson Plan Synthesis Machine
**Syllabus Target Topic**
<|<{topic_input}>|input|class_name=fullwidth|>

**Target Cohort Grade Tier Selection**
<|<{grade_tier}>|selector|lov=Grade 6-8 Middle School;Grade 9-12 High School;Undergraduate Ivy-League|dropdown=True|>
<br/><br/>
<|<{UI['btn_synth_lesson']}>|button|on_action=generate_lesson_plan|class_name=btn-primary|>
<br/><br/>
<|<{ai_output_lesson}>|text_area|height=350px|class_name=fullwidth|>
|

|<{selected_view == 'AI Worksheet Factory'}>|
### 📝 Assessment Factory & Blueprint Key Generator
**Target Core Unit Objective**
<|<{w_topic_input}>|input|class_name=fullwidth|>
<br/><br/>
<|<{UI['btn_gen_worksheet']}>|button|on_action=generate_worksheet|class_name=btn-primary|>
<br/><br/>
<|<{ai_output_worksheet}>|text_area|height=300px|class_name=fullwidth|>
<br/><br/>
<|Commit Worksheet to Local Storage Database|button|on_action=commit_worksheet_to_cloud|class_name=btn-success|>
|

|<{selected_view == '📊 Student Advanced Analytics'}>|
### 📈 Command System Metrics Grid
|<layout|columns=1 1 1|gap=15px|
|<card text-center>|
##### Roster Volume
## {total_students_metric}
|
|<card text-center>|
##### Grade Mean
## {class_mean_metric}
|
|<card text-center>|
##### Live Test Forms
## {published_tasks_metric}
|
|

---

### 🔮 Predictive Student Risk Diagnostics Mapping Suite
<|<{UI['btn_risk_sweep']}>|button|on_action=run_predictive_risk_sweep|class_name=btn-warning|>
<br/><br/>
|<{len(predictive_risk_logs) > 0}>|
<|<{predictive_risk_logs}>|table|>
|
|
|
|
|
"""

student_layout = """
|<{logged_in and user_role == 'Student'}>|
## 🎒 Student Action Desktop Portal

---

|<layout|columns=1 4|gap=20px|
|<sidebar-card>|
#### Student Control Desk
<|<{student_view}>|selector|lov=🎒 Enroll in a Class;📂 Subject-Filtered Worksheet Desk;🏆 My Performance Ledger|mode=radio|>
<br/><br/>
<|<{UI['logout_btn']}>|button|on_action=trigger_logout|class_name=btn-danger|>
|

|<main-content>|
|<{student_view == '🎒 Enroll in a Class'}>|
### 🎒 Connect Course Workspace Network
**Select Academic Instructor**
<|<{selected_teacher_string}>|selector|lov={available_teachers}|dropdown=True|>

**Assign Student ID Token**
<|<{student_id_token}>|input|class_name=fullwidth|>

**Current Study Cohort Group**
<|<{student_grade_cohort}>|selector|lov=Grade 6;Grade 9;Grade 11;Undergraduate|dropdown=True|>
<br/><br/>
<|<{UI['submit_conn_btn']}>|button|on_action=handle_class_enrollment|class_name=btn-primary|>
|

|<{student_view == '📂 Subject-Filtered Worksheet Desk'}>|
### 📝 Automated Sanitized Task Workspace
**Select Active Assignment Target**
<|<{selected_worksheet_topic}>|selector|lov={available_worksheets}|dropdown=True|on_change=load_sanitized_worksheet|>
<br/><br/>
|<{selected_worksheet_topic != ''}>|
##### 📋 Sanitized Examination Blueprint (Answers Stripped by AI)
<|<{sanitized_blueprint_text}>|text_area|height=250px|class_name=fullwidth|active=False|>

---

##### Input Your Final Solution Answers Log Below:
<|<{student_answer_buffer}>|text_area|height=150px|class_name=fullwidth|>
<br/><br/>
<|<{UI['finalize_submit_btn']}>|button|on_action=process_student_homework_submission|class_name=btn-success|>

---

##### Instant Grading Analysis Reports:
**Computed Grade:** {student_grade_result}/100

**Evaluator Commentary:** {student_feedback_report}
|
|

|<{student_view == '🏆 My Performance Ledger'}>|
### 🏆 Historical Academic Performance Ledger Matrix
<|<{my_grades_table_data}>|table|>
|
|
|
|
"""

full_ui_blueprint = localization_bar + login_layout + teacher_layout + student_layout

app = Gui(page=full_ui_blueprint)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860, use_reloader=True)