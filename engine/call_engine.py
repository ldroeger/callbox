"""
Callbox Call Engine v2
Listens to SIM7600 modem for incoming calls, checks the database,
plays audio for authorized callers, rejects unknown numbers.
Configured via environment variables set by setup wizard.
"""

import os
import time
import queue
import sqlite3
import threading
import subprocess
from datetime import datetime

MODEM_PORT      = os.environ.get("MODEM_PORT",      "/dev/ttyUSB2")
BAUDRATE        = 115200
AUDIO_PATH      = os.environ.get("AUDIO_PATH",      "/audio")
DB_PATH         = os.environ.get("DB_PATH",         "/data/callbox.db")
REJECT_UNKNOWN  = os.environ.get("REJECT_UNKNOWN",  "true").lower() == "true"
NUMBER_FORMAT   = os.environ.get("NUMBER_FORMAT",   "international")

import serial

# ─── Audio Queue ──────────────────────────────────────────────────────────────

audio_q = queue.Queue()

def audio_worker():
    while True:
        filepath = audio_q.get()
        try:
            print(f"[AUDIO] Playing: {filepath}", flush=True)
            subprocess.run(["mpg123", "-q", filepath], timeout=180)
        except Exception as e:
            print(f"[AUDIO] Error: {e}", flush=True)
        finally:
            audio_q.task_done()

threading.Thread(target=audio_worker, daemon=True).start()

# ─── Database ─────────────────────────────────────────────────────────────────

def wait_for_db():
    while not os.path.exists(DB_PATH):
        print(f"[DB] Waiting for database at {DB_PATH}...", flush=True)
        time.sleep(5)
    print("[DB] Database ready.", flush=True)

def normalize_phone(phone: str) -> str:
    """Normalize phone number based on configured format."""
    phone = phone.strip()
    if NUMBER_FORMAT == "national":
        # Strip leading + and country code (49 for Germany)
        if phone.startswith("+49"):
            phone = "0" + phone[3:]
        elif phone.startswith("0049"):
            phone = "0" + phone[4:]
    return phone

def get_user_by_phone(phone: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        # Try exact match first, then normalized
        for p in [phone, normalize_phone(phone)]:
            row = conn.execute(
                "SELECT id FROM users WHERE phone=? AND active=1", (p,)
            ).fetchone()
            if row:
                conn.close()
                return row["id"]
        conn.close()
        return None
    except Exception as e:
        print(f"[DB] get_user error: {e}", flush=True)
        return None

def get_audio_for_user(user_id: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
            SELECT audio.filename, audio.title
            FROM audio
            JOIN matrix ON audio.id = matrix.audio_id
            WHERE matrix.user_id = ?
            LIMIT 1
        """, (user_id,)).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        print(f"[DB] get_audio error: {e}", flush=True)
        return None

def log_call(phone: str, status: str, audio: str = None):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO call_log (phone, status, audio_played, call_time) VALUES (?,?,?,?)",
            (phone, status, audio, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] log error: {e}", flush=True)

# ─── Modem ────────────────────────────────────────────────────────────────────

ser = None

def modem_connect():
    global ser
    while True:
        try:
            ser = serial.Serial(MODEM_PORT, BAUDRATE, timeout=1)
            time.sleep(1)
            ser.write(b"AT+CLIP=1\r")   # Enable caller ID
            time.sleep(0.3)
            ser.write(b"AT+CRC=1\r")    # Extended ring indications
            time.sleep(0.3)
            ser.write(b"AT+COLP=1\r")   # Connected line identification
            time.sleep(0.3)
            # Flush
            ser.reset_input_buffer()
            print(f"[MODEM] Connected on {MODEM_PORT}", flush=True)
            return
        except Exception as e:
            print(f"[MODEM] Cannot connect ({e}) – retrying in 5s", flush=True)
            time.sleep(5)

def modem_hangup():
    try:
        ser.write(b"AT+CHUP\r")
        time.sleep(0.3)
    except Exception as e:
        print(f"[MODEM] Hangup error: {e}", flush=True)

def process_call(phone: str):
    print(f"[CALL] Incoming: {phone}", flush=True)

    user_id = get_user_by_phone(phone)

    if not user_id:
        if REJECT_UNKNOWN:
            print(f"[CALL] REJECTED – unknown number: {phone}", flush=True)
            modem_hangup()
            log_call(phone, "rejected")
        else:
            print(f"[CALL] IGNORED – unknown number: {phone}", flush=True)
            log_call(phone, "ignored")
        return

    audio = get_audio_for_user(user_id)

    if not audio:
        print(f"[CALL] REJECTED – no audio assigned for user {user_id}", flush=True)
        modem_hangup()
        log_call(phone, "no_audio")
        return

    filepath = os.path.join(AUDIO_PATH, audio["filename"])

    if not os.path.exists(filepath):
        print(f"[CALL] REJECTED – audio file missing: {filepath}", flush=True)
        modem_hangup()
        log_call(phone, "missing_file")
        return

    print(f"[CALL] ACCEPTED – playing: {audio['title']}", flush=True)
    modem_hangup()
    audio_q.put(filepath)
    log_call(phone, "accepted", audio["filename"])

# ─── Main Loop ────────────────────────────────────────────────────────────────

def listen():
    modem_connect()
    pending_ring = False
    last_ring_time = 0

    while True:
        try:
            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode(errors="ignore").strip()
            if not line:
                continue

            # Debug: show all modem output
            print(f"[MODEM] << {line}", flush=True)

            if "RING" in line or "+CRING:" in line:
                now = time.time()
                # Debounce: ignore RING within 2s of a previous one
                if now - last_ring_time > 2:
                    pending_ring = True
                    last_ring_time = now

            if "+CLIP:" in line and pending_ring:
                pending_ring = False
                try:
                    # Format: +CLIP: "+491701234567",145,...
                    phone = line.split('"')[1]
                    process_call(phone)
                except (IndexError, ValueError):
                    print(f"[CLIP] Could not parse number from: {line}", flush=True)

            # Reset if call ended
            if "NO CARRIER" in line or "+CIEV: call,0" in line:
                pending_ring = False

        except serial.SerialException as e:
            print(f"[MODEM] Serial error: {e} – reconnecting", flush=True)
            modem_connect()
        except Exception as e:
            print(f"[ENGINE] Unexpected error: {e}", flush=True)
            time.sleep(1)

# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50, flush=True)
    print(" Callbox Call Engine v2", flush=True)
    print(f" Modem:  {MODEM_PORT}", flush=True)
    print(f" Audio:  {AUDIO_PATH}", flush=True)
    print(f" DB:     {DB_PATH}", flush=True)
    print(f" Reject unknown: {REJECT_UNKNOWN}", flush=True)
    print(f" Number format:  {NUMBER_FORMAT}", flush=True)
    print("=" * 50, flush=True)
    wait_for_db()
    listen()
