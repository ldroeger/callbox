"""
Callbox Call Engine v2
Listens to SIM7600 modem for incoming calls, checks the database,
plays audio for authorized callers, rejects unknown numbers.
Periodically polls signal/network/SIM status and writes to the DB
so the web dashboard can display live modem information.
Handles PIN entry requests queued by the web interface.
"""

import os
import re
import time
import queue
import sqlite3
import threading
import subprocess
from datetime import datetime

MODEM_PORT       = os.environ.get("MODEM_PORT",    "/dev/ttyUSB2")
BAUDRATE         = 115200
AUDIO_PATH       = os.environ.get("AUDIO_PATH",     "/audio")
AUDIO_CHANNELS   = os.environ.get("AUDIO_CHANNELS", "stereo")  # "stereo" or "mono"
DB_PATH          = os.environ.get("DB_PATH",        "/data/callbox.db")
REJECT_UNKNOWN   = os.environ.get("REJECT_UNKNOWN", "true").lower() == "true"
NUMBER_FORMAT    = os.environ.get("NUMBER_FORMAT",  "international")
STATUS_INTERVAL  = int(os.environ.get("STATUS_INTERVAL_SECONDS", "30"))

import serial

# ─── Shared serial lock + intercepted call-line queue ─────────────────────────
# Both the call listener and the status-polling thread share the same UART.
# Only one may be mid-command at a time (lock). If a +CRING/+CLIP line
# arrives while the status thread owns the lock and is reading an AT response,
# it would normally be lost; instead we scan every response blob for call
# indicators and forward them here so the listener can still act on them.
serial_lock = threading.Lock()
intercepted_call_lines = queue.Queue()

# ─── Audio Queue ──────────────────────────────────────────────────────────────

audio_q = queue.Queue()

def audio_worker():
    while True:
        filepath = audio_q.get()
        try:
            print(f"[AUDIO] Playing: {filepath}", flush=True)
            cmd = ["mpg123", "-q"]
            if AUDIO_CHANNELS == "mono":
                cmd += ["-m"]   # force mono downmix
            cmd.append(filepath)
            subprocess.run(cmd, timeout=180)
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

def db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def normalize_phone(phone: str) -> str:
    phone = phone.strip()
    if NUMBER_FORMAT == "national":
        if phone.startswith("+49"):
            phone = "0" + phone[3:]
        elif phone.startswith("0049"):
            phone = "0" + phone[4:]
    return phone

def get_user_by_phone(phone: str):
    try:
        conn = db_conn()
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
        conn = db_conn()
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
        conn = db_conn()
        conn.execute(
            "INSERT INTO call_log (phone, status, audio_played, call_time) VALUES (?,?,?,?)",
            (phone, status, audio, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] log error: {e}", flush=True)

def update_modem_status(**fields):
    if not fields:
        return
    try:
        conn = db_conn()
        fields["last_updated"] = datetime.now().isoformat()
        columns = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values())
        conn.execute(f"UPDATE modem_status SET {columns} WHERE id=1", values)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] update_modem_status error: {e}", flush=True)

def get_pending_pin_request():
    try:
        conn = db_conn()
        row = conn.execute(
            "SELECT * FROM pin_request WHERE id=1 AND processed=0"
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        print(f"[DB] get_pending_pin_request error: {e}", flush=True)
        return None

def resolve_pin_request(result: str):
    try:
        conn = db_conn()
        conn.execute(
            "UPDATE pin_request SET processed=1, result=?, pin=NULL WHERE id=1",
            (result,)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] resolve_pin_request error: {e}", flush=True)

# ─── Modem ────────────────────────────────────────────────────────────────────

ser = None

def modem_connect():
    global ser
    while True:
        try:
            ser = serial.Serial(MODEM_PORT, BAUDRATE, timeout=1)
            time.sleep(1)
            ser.write(b"AT+CLIP=1\r"); time.sleep(0.3)
            ser.write(b"AT+CRC=1\r");  time.sleep(0.3)
            ser.write(b"AT+COLP=1\r"); time.sleep(0.3)
            ser.reset_input_buffer()
            print(f"[MODEM] Connected on {MODEM_PORT}", flush=True)
            update_modem_status(connected=1)
            return
        except Exception as e:
            print(f"[MODEM] Cannot connect ({e}) – retrying in 5s", flush=True)
            update_modem_status(connected=0)
            time.sleep(5)

def modem_answer():
    """Answer an incoming call."""
    try:
        ser.write(b"ATA\r")
        time.sleep(1.0)
    except Exception as e:
        print(f"[MODEM] Answer error: {e}", flush=True)

def modem_hangup():
    try:
        ser.write(b"AT+CHUP\r")
        time.sleep(0.3)
    except Exception as e:
        print(f"[MODEM] Hangup error: {e}", flush=True)

# ─── AT command helper ────────────────────────────────────────────────────────

CALL_INDICATORS = ("RING", "+CRING:", "+CLIP:", "NO CARRIER", "+CIEV: call,0")

def _extract_call_lines(text: str):
    """Forward any call-related lines found in an AT response to the listener."""
    for line in text.splitlines():
        line = line.strip()
        if line and any(m in line for m in CALL_INDICATORS):
            intercepted_call_lines.put(line)

def send_at_command(command: str, wait: float = 0.6, read_time: float = 0.8) -> str:
    """
    Send an AT command and return the raw response.
    Must be called while holding serial_lock.
    Does NOT call reset_input_buffer so that incoming call notifications
    already in the buffer aren't silently discarded.
    """
    ser.write((command + "\r").encode())
    time.sleep(wait)
    response = ""
    deadline = time.time() + read_time
    while time.time() < deadline:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            response += chunk.decode(errors="ignore")
        else:
            time.sleep(0.05)
    _extract_call_lines(response)
    return response

# ─── Call processing ──────────────────────────────────────────────────────────

# Short announcement played into the phone line (caller hears this).
# Upload a file called "announcement.mp3" via the web interface to customize.
# Default: 4 seconds of silence/hold if no file is present.
ANNOUNCEMENT_FILE   = os.path.join(AUDIO_PATH, "announcement.mp3")
ANNOUNCEMENT_HOLD_SEC = float(os.environ.get("ANNOUNCEMENT_DURATION_SEC", "4"))

def _play_announcement():
    """
    Play the announcement into the line while the call is connected.
    If announcement.mp3 exists in the audio folder it is played via mpg123.
    Otherwise the line is held open for ANNOUNCEMENT_HOLD_SEC seconds so the
    caller at least hears silence (better than dead air with instant hangup).
    """
    if os.path.exists(ANNOUNCEMENT_FILE):
        try:
            cmd = ["mpg123", "-q"]
            if AUDIO_CHANNELS == "mono":
                cmd += ["-m"]
            cmd.append(ANNOUNCEMENT_FILE)
            subprocess.run(cmd, timeout=30)
            return
        except Exception as e:
            print(f"[ANNOUNCE] mpg123 error: {e}", flush=True)
    print(f"[ANNOUNCE] No announcement.mp3 – holding {ANNOUNCEMENT_HOLD_SEC}s", flush=True)
    time.sleep(ANNOUNCEMENT_HOLD_SEC)

def process_call(phone: str):
    print(f"[CALL] Incoming: {phone}", flush=True)
    user_id = get_user_by_phone(phone)

    if not user_id:
        if REJECT_UNKNOWN:
            print(f"[CALL] REJECTED – unknown: {phone}", flush=True)
            modem_hangup()
            log_call(phone, "rejected")
        else:
            log_call(phone, "ignored")
        return

    audio = get_audio_for_user(user_id)
    if not audio:
        print(f"[CALL] REJECTED – no audio for user {user_id}", flush=True)
        modem_hangup()
        log_call(phone, "no_audio")
        return

    filepath = os.path.join(AUDIO_PATH, audio["filename"])
    if not os.path.exists(filepath):
        print(f"[CALL] REJECTED – file missing: {filepath}", flush=True)
        modem_hangup()
        log_call(phone, "missing_file")
        return

    # 1. Answer – caller is now connected
    print(f"[CALL] ACCEPTED – answering, then playing: {audio['title']}", flush=True)
    modem_answer()

    # 2. Play announcement into the line (caller hears this)
    _play_announcement()

    # 3. Hang up the phone call
    modem_hangup()

    # 4. Play the assigned audio on the local speaker
    audio_q.put(filepath)
    log_call(phone, "accepted", audio["filename"])

# ─── Status parsing ───────────────────────────────────────────────────────────

SIM_STATUS_MAP = {
    "READY": "ready",
    "SIM PIN": "pin_required",
    "SIM PUK": "puk_required",
    "SIM PIN2": "pin2_required",
    "SIM PUK2": "puk2_required",
    "PH-SIM PIN": "phone_sim_pin_required",
    "NOT INSERTED": "not_inserted",
}

NETWORK_STATUS_MAP = {
    0: "not_registered", 1: "registered_home", 2: "searching",
    3: "registration_denied", 4: "unknown", 5: "registered_roaming",
}

def parse_cpin(r):
    m = re.search(r"\+CPIN:\s*([A-Z0-9 \-]+)", r)
    if not m: return None
    return SIM_STATUS_MAP.get(m.group(1).strip(), m.group(1).strip().lower())

def parse_creg(r):
    m = re.search(r"\+CREG:\s*\d+,\s*(\d+)", r)
    if not m: return None, None
    code = int(m.group(1))
    return code, NETWORK_STATUS_MAP.get(code, "unknown")

def parse_csq(r):
    m = re.search(r"\+CSQ:\s*(\d+),(\d+)", r)
    if not m: return None, None, None
    raw = int(m.group(1))
    if raw == 99: return raw, None, "no_signal"
    pct = min(100, round((raw / 31) * 100))
    quality = "excellent" if raw >= 20 else "good" if raw >= 15 else "fair" if raw >= 10 else "poor"
    return raw, pct, quality

def parse_cops(r):
    m = re.search(r'\+COPS:\s*\d+,\d+,"([^"]+)"', r)
    return m.group(1) if m else None

# ─── Status polling thread ────────────────────────────────────────────────────

def poll_status_once():
    with serial_lock:
        resp = send_at_command("AT+CPIN?")
        sim_status = parse_cpin(resp)

        resp = send_at_command("AT+CREG?")
        net_code, net_status = parse_creg(resp)

        resp = send_at_command("AT+CSQ")
        raw, percent, quality = parse_csq(resp)

        operator = None
        if net_code in (1, 5):
            resp = send_at_command("AT+COPS?", wait=0.8, read_time=1.2)
            operator = parse_cops(resp)

    update_modem_status(
        sim_status=sim_status,
        network_status_code=net_code,
        network_status=net_status,
        signal_raw=raw,
        signal_percent=percent,
        signal_quality=quality,
        operator=operator,
    )

def status_loop():
    time.sleep(10)   # Let the call listener connect first
    while True:
        try:
            poll_status_once()
        except Exception as e:
            print(f"[STATUS] Poll error: {e}", flush=True)
        time.sleep(STATUS_INTERVAL)

# ─── PIN handler thread ───────────────────────────────────────────────────────

def pin_handler_loop():
    while True:
        try:
            req = get_pending_pin_request()
            if req and req.get("pin"):
                pin = req["pin"]
                print("[PIN] Processing PIN request", flush=True)
                with serial_lock:
                    resp = send_at_command(f'AT+CPIN="{pin}"', wait=1.0, read_time=2.0)
                if "OK" in resp:
                    resolve_pin_request("ok")
                    print("[PIN] Accepted", flush=True)
                elif "ERROR" in resp:
                    resolve_pin_request("error")
                    print("[PIN] Rejected", flush=True)
                else:
                    resolve_pin_request("unknown")
        except Exception as e:
            print(f"[PIN] Handler error: {e}", flush=True)
        time.sleep(3)

# ─── Main call listener ───────────────────────────────────────────────────────

def listen():
    modem_connect()
    state = {"pending_ring": False, "last_ring_time": 0.0}

    def handle_line(line: str, source: str):
        print(f"[MODEM] << {line}  ({source})", flush=True)

        if "RING" in line or "+CRING:" in line:
            now = time.time()
            if now - state["last_ring_time"] > 2:
                state["pending_ring"] = True
                state["last_ring_time"] = now

        if "+CLIP:" in line and state["pending_ring"]:
            state["pending_ring"] = False
            try:
                phone = line.split('"')[1]
                process_call(phone)
            except (IndexError, ValueError):
                print(f"[CLIP] Parse failed: {line}", flush=True)

        if "NO CARRIER" in line or "+CIEV: call,0" in line:
            state["pending_ring"] = False

    while True:
        try:
            # Drain call lines intercepted by the status thread first
            while True:
                try:
                    handle_line(intercepted_call_lines.get_nowait(), "intercepted")
                except queue.Empty:
                    break

            with serial_lock:
                raw = ser.readline()

            if not raw:
                continue
            line = raw.decode(errors="ignore").strip()
            if not line:
                continue
            handle_line(line, "direct")

        except serial.SerialException as e:
            print(f"[MODEM] Serial error: {e} – reconnecting", flush=True)
            update_modem_status(connected=0)
            modem_connect()
        except Exception as e:
            print(f"[ENGINE] Unexpected error: {e}", flush=True)
            time.sleep(1)

# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50, flush=True)
    print(f" Callbox Call Engine v2", flush=True)
    print(f" Modem:  {MODEM_PORT}", flush=True)
    print(f" Audio:  {AUDIO_PATH}  ({AUDIO_CHANNELS})", flush=True)
    print(f" DB:     {DB_PATH}", flush=True)
    print(f" Reject unknown: {REJECT_UNKNOWN}", flush=True)
    print(f" Number format:  {NUMBER_FORMAT}", flush=True)
    print(f" Status interval: {STATUS_INTERVAL}s", flush=True)
    print("=" * 50, flush=True)
    wait_for_db()
    threading.Thread(target=status_loop, daemon=True).start()
    threading.Thread(target=pin_handler_loop, daemon=True).start()
    listen()
