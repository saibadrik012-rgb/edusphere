from nicegui import ui
import sqlite3
import hashlib
import os
from google import genai

# --- Configuration ---
PORT = int(os.environ.get("PORT", 8080))
DB_PATH = '/data/edusphere.db' if os.path.exists('/data') else 'edusphere.db'
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

# --- Database Management ---
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT, role TEXT)")
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            conn.execute("INSERT INTO users VALUES (?, ?, ?)", 
                         ('admin', hashlib.sha256("admin123".encode()).hexdigest(), 'Teacher'))
        conn.commit()

init_db()

# --- AI Logic ---
def generate_lesson_plan(topic, grade):
    if not ai_client: return "AI Client not configured."
    prompt = f"Design a 5E lesson on {topic} for {grade}. Return structured markdown."
    return ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text

# --- UI Layout ---
@ui.page('/')
def login_page():
    ui.query('body').classes('items-center justify-center bg-gray-100')
    with ui.card().classes('w-96 p-8 shadow-2xl transition-all duration-500 hover:scale-105'):
        ui.label('EduSphere Portal').classes('text-2xl font-bold mb-4')
        user = ui.input('Username').classes('w-full')
        pw = ui.input('Password', password=True).classes('w-full')
        
        def attempt_login():
            with get_db() as conn:
                row = conn.execute("SELECT * FROM users WHERE username = ?", (user.value,)).fetchone()
            if row and row['password_hash'] == hashlib.sha256(pw.value.encode()).hexdigest():
                ui.navigate.to('/dashboard')
            else:
                ui.notify('Invalid login credentials', type='negative')
                
        ui.button('Sign In', on_click=attempt_login).classes('w-full mt-4')

@ui.page('/dashboard')
def dashboard():
    with ui.column().classes('w-full p-8 max-w-4xl mx-auto'):
        ui.label('AI Lesson Architect').classes('text-3xl font-bold mb-6')
        
        with ui.card().classes('w-full p-6 transition-transform duration-300 hover:shadow-xl'):
            topic = ui.input('Enter Topic').classes('w-full')
            grade = ui.select(['Grade 6-8', 'Grade 9-12', 'Undergraduate'], value='Grade 9-12').classes('w-full')
            content_area = ui.markdown().classes('mt-6 p-4 bg-gray-50 rounded')
            
            async def run_ai():
                content_area.set_content('Generating content, please wait...')
                result = generate_lesson_plan(topic.value, grade.value)
                content_area.set_content(result)
            
            ui.button('Generate Lesson', on_click=run_ai).classes('mt-4 w-full bg-blue-600')

ui.run(port=PORT)