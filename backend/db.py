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

        CREATE TABLE IF NOT EXISTS modem_status (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            connected INTEGER DEFAULT 0,
            sim_status TEXT,
            network_status TEXT,
            network_status_code INTEGER,
            signal_raw INTEGER,
            signal_percent INTEGER,
            signal_quality TEXT,
            operator TEXT,
            gnss_fix INTEGER DEFAULT 0,
            gnss_lat REAL,
            gnss_lon REAL,
            gnss_alt REAL,
            gnss_satellites INTEGER,
            gnss_utc_time TEXT,
            gnss_speed REAL,
            last_updated TEXT
        );

        INSERT OR IGNORE INTO modem_status (id) VALUES (1);

        CREATE TABLE IF NOT EXISTS pin_request (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            pin TEXT,
            requested_at TEXT,
            processed INTEGER DEFAULT 0,
            result TEXT
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


# ─── Modem Status ────────────────────────────────────────────────────────────

def get_modem_status():
    conn = get_conn()
    row = conn.execute("SELECT * FROM modem_status WHERE id=1").fetchone()
    conn.close()
    return dict(row) if row else None


def update_modem_status(**fields):
    """Update only the provided fields in the modem_status row."""
    if not fields:
        return
    conn = get_conn()
    fields["last_updated"] = datetime.now().isoformat()
    columns = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values())
    conn.execute(f"UPDATE modem_status SET {columns} WHERE id=1", values)
    conn.commit()
    conn.close()


# ─── PIN Request (Web -> Call Engine handoff) ───────────────────────────────

def request_pin_entry(pin: str):
    conn = get_conn()
    conn.execute("""
        INSERT INTO pin_request (id, pin, requested_at, processed, result)
        VALUES (1, ?, ?, 0, NULL)
        ON CONFLICT(id) DO UPDATE SET
            pin=excluded.pin,
            requested_at=excluded.requested_at,
            processed=0,
            result=NULL
    """, (pin, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_pending_pin_request():
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM pin_request WHERE id=1 AND processed=0"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def resolve_pin_request(result: str):
    conn = get_conn()
    conn.execute(
        "UPDATE pin_request SET processed=1, result=?, pin=NULL WHERE id=1",
        (result,)
    )
    conn.commit()
    conn.close()


def get_pin_request_result():
    conn = get_conn()
    row = conn.execute(
        "SELECT processed, result FROM pin_request WHERE id=1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None
