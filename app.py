import streamlit as st
import sqlite3
import speech_recognition as sr
from gtts import gTTS
from datetime import datetime
import google.generativeai as genai
import bcrypt
import pdfplumber
import docx
import tempfile
import os

# Configure Gemini API
GENAI_API_KEY = "AIzaSyCn48WU8scLpd3cajaq-tulRIgZnvtHitU"
genai.configure(api_key=GENAI_API_KEY)

# Database setup
def init_db():
    conn = sqlite3.connect("translations.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    input_text TEXT,
                    source_lang TEXT,
                    translated_text TEXT,
                    target_lang TEXT,
                    timestamp DATETIME)''')
    conn.commit()
    conn.close()

# User Authentication Functions
def register_user(username, password):
    conn = sqlite3.connect("translations.db")
    c = conn.cursor()
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def login_user(username, password):
    conn = sqlite3.connect("translations.db")
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    if user and bcrypt.checkpw(password.encode(), user[0]):
        return True
    return False

def save_translation(username, input_text, source_lang, translated_text, target_lang):
    conn = sqlite3.connect("translations.db")
    c = conn.cursor()
    c.execute("INSERT INTO history (username, input_text, source_lang, translated_text, target_lang, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
              (username, input_text, source_lang, translated_text, target_lang, datetime.now()))
    conn.commit()
    conn.close()

def get_translation_history(username):
    conn = sqlite3.connect("translations.db")
    c = conn.cursor()
    c.execute("SELECT input_text, source_lang, translated_text, target_lang, timestamp FROM history WHERE username = ? ORDER BY timestamp DESC", (username,))
    history = c.fetchall()
    conn.close()
    return history

# Speech Recognition
def recognize_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("Listening... Speak now!")
        try:
            audio = recognizer.listen(source)
            return recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return "Could not understand audio"
        except sr.RequestError:
            return "Speech service unavailable"

# Text-to-Speech
def text_to_speech(text, lang):
    LANGUAGE_MAP = {
        "English": "en",
        "Hindi": "hi",
        "French": "fr",
        "Spanish": "es",
        "German": "de",
        "Telugu": "te"
    }

    lang_code = LANGUAGE_MAP.get(lang, "en")  # Default to English if not found
    try:
        tts = gTTS(text, lang=lang_code)
        file_path = "output.mp3"
        tts.save(file_path)
        return file_path
    except ValueError as e:
        return f"Error: {e}"  # Handle unsupported languages gracefully

# Document Processing
def extract_text_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    return text

def extract_text_from_docx(docx_file):
    doc = docx.Document(docx_file)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text

# AI Translation
def translate_text_with_gemini(text, source_lang, target_lang):
    model = genai.GenerativeModel("gemini-1.5-pro")
    prompt = f"Translate this text from {source_lang} to {target_lang}: {text}"
    response = model.generate_content(prompt)
    return response.text.strip()

# Streamlit UI
st.set_page_config(page_title="AI Translator", layout="wide")
st.title("🌍 AI-Powered Multi-Language Translator")

init_db()

# User Authentication
st.sidebar.header("🔑 Choose Authentication")
auth_option = st.sidebar.radio("", ["Login", "Register"])
username = st.sidebar.text_input("👤 Username")
password = st.sidebar.text_input("🔒 Password", type="password")

if auth_option == "Register":
    if st.sidebar.button("Register"):
        if register_user(username, password):
            st.sidebar.success("Registration successful! Please login.")
        else:
            st.sidebar.error("Username already exists.")
elif auth_option == "Login":
    if st.sidebar.button("Login"):
        if login_user(username, password):
            st.sidebar.success(f"Welcome, {username}!")
        else:
            st.sidebar.error("Invalid username or password.")

if username and login_user(username, password):
    st.sidebar.success(f"Logged in as: {username}")
    
    source_lang = st.selectbox("🔤 Select Input Language:", ["auto", "English", "Hindi", "French", "Spanish", "German", "Telugu"])
    target_lang = st.selectbox("🎯 Select Output Language:", ["English", "Hindi", "French", "Spanish", "German", "Telugu"])

    # Text Translation
    input_text = st.text_area("✏ Enter text to translate:")
    if st.button("Translate Text"):
        if input_text:
            translated_text = translate_text_with_gemini(input_text, source_lang, target_lang)
            save_translation(username, input_text, source_lang, translated_text, target_lang)
            st.success(f"Translated Text ({target_lang}): {translated_text}")
            
            # Convert to speech
            speech_file = text_to_speech(translated_text, target_lang)
            st.audio(speech_file, format="audio/mp3")

    # Speech-to-Text Input
    if st.button("🎙️ Speak to Translate"):
        spoken_text = recognize_speech()
        if spoken_text:
            translated_text = translate_text_with_gemini(spoken_text, source_lang, target_lang)
            save_translation(username, spoken_text, source_lang, translated_text, target_lang)
            st.success(f"Translated Text ({target_lang}): {translated_text}")
            speech_file = text_to_speech(translated_text, target_lang)
            st.audio(speech_file, format="audio/mp3")

    # File Upload for Documents
    uploaded_file = st.file_uploader("📂 Upload a PDF or DOCX file", type=["pdf", "docx"])
    if uploaded_file:
        file_extension = uploaded_file.name.split(".")[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as tmp_file:
            tmp_file.write(uploaded_file.read())
            tmp_path = tmp_file.name
        
        if file_extension == "pdf":
            extracted_text = extract_text_from_pdf(tmp_path)
        else:
            extracted_text = extract_text_from_docx(tmp_path)
        
        if extracted_text:
            translated_text = translate_text_with_gemini(extracted_text, source_lang, target_lang)
            save_translation(username, extracted_text, source_lang, translated_text, target_lang)
            st.success(f"Translated Document Text ({target_lang}): {translated_text}")

    # Display Translation History
    st.subheader("📜 Translation History")
    history = get_translation_history(username)
    if history:
        for row in history:
            st.write(f"🔹 {row[0]} ({row[1]}) → {row[2]} ({row[3]}) on {row[4]}")
    else:
        st.info("No translation history found.")
