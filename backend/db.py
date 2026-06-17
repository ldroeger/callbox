import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "/app/data/callbox.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS matrix (
            user_id INTEGER NOT NULL,
            audio_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, audio_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (audio_id) REFERENCES audio(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS call_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            status TEXT NOT NULL,
            audio_played TEXT,
            call_time TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()


def get_user_by_phone(phone: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE phone=? AND active=1", (phone,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_audio_for_user(user_id: int):
    conn = get_conn()
    row = conn.execute("""
        SELECT audio.filename, audio.title
        FROM audio
        JOIN matrix ON audio.id = matrix.audio_id
        WHERE matrix.user_id = ?
        LIMIT 1
    """, (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def log_call(phone: str, status: str, audio: str = None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO call_log (phone, status, audio_played, call_time) VALUES (?,?,?,?)",
        (phone, status, audio, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
