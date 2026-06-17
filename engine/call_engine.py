"""
Callbox Call Engine v2
Listens to SIM7600 modem for incoming calls, checks the database,
plays audio for authorized callers, rejects unknown numbers.
Also periodically polls modem status (signal, network, GNSS) and
writes it to the shared database for the web interface to display,
and handles PIN entry requests coming from the web interface.
Configured via environment variables set by setup wizard.
"""

import os
import re
import time
import queue
import sqlite3
import threading
import subprocess
from datetime import datetime, timezone

MODEM_PORT       = os.environ.get("MODEM_PORT",       "/dev/ttyUSB2")
BAUDRATE         = 115200
AUDIO_PATH       = os.environ.get("AUDIO_PATH",        "/audio")
DB_PATH          = os.environ.get("DB_PATH",           "/data/callbox.db")
REJECT_UNKNOWN   = os.environ.get("REJECT_UNKNOWN",    "true").lower() == "true"
NUMBER_FORMAT    = os.environ.get("NUMBER_FORMAT",     "international")
STATUS_INTERVAL  = int(os.environ.get("STATUS_INTERVAL_SECONDS", "15"))
SYNC_SYSTEM_TIME = os.environ.get("SYNC_SYSTEM_TIME_FROM_GNSS", "true").lower() == "true"

import serial

# ─── Shared serial access lock ────────────────────────────────────────────────
# The call listener loop and the status-polling thread both need to talk to
# the same serial port. Only one of them may be mid-command at a time.
serial_lock = threading.Lock()

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

def db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def normalize_phone(phone: str) -> str:
    """Normalize phone number based on configured format."""
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
            ser.write(b"AT+CLIP=1\r")   # Enable caller ID
            time.sleep(0.3)
            ser.write(b"AT+CRC=1\r")    # Extended ring indications
            time.sleep(0.3)
            ser.write(b"AT+COLP=1\r")   # Connected line identification
            time.sleep(0.3)
            ser.reset_input_buffer()
            print(f"[MODEM] Connected on {MODEM_PORT}", flush=True)
            update_modem_status(connected=1)
            return
        except Exception as e:
            print(f"[MODEM] Cannot connect ({e}) - retrying in 5s", flush=True)
            update_modem_status(connected=0)
            time.sleep(5)

def modem_hangup():
    try:
        ser.write(b"AT+CHUP\r")
        time.sleep(0.3)
    except Exception as e:
        print(f"[MODEM] Hangup error: {e}", flush=True)

def send_at_command(command: str, wait: float = 0.6, read_time: float = 0.8) -> str:
    """
    Send an AT command and collect the response.
    Must be called while holding serial_lock.
    Returns the raw decoded response text.
    """
    ser.reset_input_buffer()
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
    return response

def process_call(phone: str):
    print(f"[CALL] Incoming: {phone}", flush=True)

    user_id = get_user_by_phone(phone)

    if not user_id:
        if REJECT_UNKNOWN:
            print(f"[CALL] REJECTED - unknown number: {phone}", flush=True)
            modem_hangup()
            log_call(phone, "rejected")
        else:
            print(f"[CALL] IGNORED - unknown number: {phone}", flush=True)
            log_call(phone, "ignored")
        return

    audio = get_audio_for_user(user_id)

    if not audio:
        print(f"[CALL] REJECTED - no audio assigned for user {user_id}", flush=True)
        modem_hangup()
        log_call(phone, "no_audio")
        return

    filepath = os.path.join(AUDIO_PATH, audio["filename"])

    if not os.path.exists(filepath):
        print(f"[CALL] REJECTED - audio file missing: {filepath}", flush=True)
        modem_hangup()
        log_call(phone, "missing_file")
        return

    print(f"[CALL] ACCEPTED - playing: {audio['title']}", flush=True)
    modem_hangup()
    audio_q.put(filepath)
    log_call(phone, "accepted", audio["filename"])

# ─── Status Parsing Helpers ────────────────────────────────────────────────────

SIM_STATUS_MAP = {
    "READY":          "ready",
    "SIM PIN":        "pin_required",
    "SIM PUK":        "puk_required",
    "SIM PIN2":       "pin2_required",
    "SIM PUK2":       "puk2_required",
    "PH-SIM PIN":     "phone_sim_pin_required",
    "NOT INSERTED":   "not_inserted",
}

NETWORK_STATUS_MAP = {
    0: "not_registered",
    1: "registered_home",
    2: "searching",
    3: "registration_denied",
    4: "unknown",
    5: "registered_roaming",
}

def parse_cpin(response: str):
    m = re.search(r"\+CPIN:\s*([A-Z0-9 \-]+)", response)
    if not m:
        return None
    raw = m.group(1).strip()
    return SIM_STATUS_MAP.get(raw, raw.lower().replace(" ", "_"))

def parse_creg(response: str):
    m = re.search(r"\+CREG:\s*\d+,\s*(\d+)", response)
    if not m:
        return None, None
    code = int(m.group(1))
    return code, NETWORK_STATUS_MAP.get(code, "unknown")

def parse_csq(response: str):
    m = re.search(r"\+CSQ:\s*(\d+),(\d+)", response)
    if not m:
        return None, None, None
    raw = int(m.group(1))
    if raw == 99:
        return raw, None, "no_signal"
    percent = min(100, round((raw / 31) * 100))
    if raw >= 20:
        quality = "excellent"
    elif raw >= 15:
        quality = "good"
    elif raw >= 10:
        quality = "fair"
    else:
        quality = "poor"
    return raw, percent, quality

def parse_cops(response: str):
    m = re.search(r'\+COPS:\s*\d+,\d+,"([^"]+)"', response)
    return m.group(1) if m else None

def parse_cgnssinfo(response: str):
    """
    Typical SIM7600 response:
    +CGNSSINFO: <fix>,<GPS-SVs>,<GLONASS-SVs>,<BEIDOU-SVs>,<lat>,<N/S>,<lon>,<E/W>,
                <date>,<time>,<alt>,<speed>,<course>
    Example (fixed):
    +CGNSSINFO: 2,03,00,02,4915.123456,N,01130.654321,E,170626,134210.0,123.4,0.21,0.0
    Example (no fix):
    +CGNSSINFO: ,,,,,,,,,,,,
    """
    m = re.search(r"\+CGNSSINFO:\s*(.*)", response)
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(",")]
    if len(parts) < 13 or not parts[0] or parts[0] == "0":
        return {"fix": False}

    try:
        fix_type = int(parts[0])
        gps_sv = int(parts[1]) if parts[1] else 0
        glonass_sv = int(parts[2]) if parts[2] else 0
        beidou_sv = int(parts[3]) if parts[3] else 0
        total_sv = gps_sv + glonass_sv + beidou_sv

        lat_raw, lat_dir = parts[4], parts[5]
        lon_raw, lon_dir = parts[6], parts[7]
        date_raw = parts[8]
        time_raw = parts[9]
        alt = float(parts[10]) if parts[10] else None
        speed = float(parts[11]) if parts[11] else None

        if not lat_raw or not lon_raw:
            return {"fix": False}

        # ddmm.mmmmmm -> decimal degrees
        lat_deg = int(float(lat_raw) / 100)
        lat_min = float(lat_raw) - lat_deg * 100
        lat = lat_deg + lat_min / 60
        if lat_dir == "S":
            lat = -lat

        lon_deg = int(float(lon_raw) / 100)
        lon_min = float(lon_raw) - lon_deg * 100
        lon = lon_deg + lon_min / 60
        if lon_dir == "W":
            lon = -lon

        utc_iso = None
        if date_raw and time_raw and len(date_raw) == 6:
            day = date_raw[0:2]
            month = date_raw[2:4]
            year = "20" + date_raw[4:6]
            time_part = time_raw.split(".")[0].zfill(6)
            hh, mm, ss = time_part[0:2], time_part[2:4], time_part[4:6]
            utc_iso = f"{year}-{month}-{day}T{hh}:{mm}:{ss}+00:00"

        return {
            "fix": True,
            "fix_type": fix_type,
            "satellites": total_sv,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "alt": alt,
            "speed": speed,
            "utc_time": utc_iso,
        }
    except (ValueError, IndexError) as e:
        print(f"[GNSS] Parse error: {e}", flush=True)
        return {"fix": False}

# ─── Status Polling Thread ─────────────────────────────────────────────────────

_gnss_enabled = False

def poll_status_once():
    global _gnss_enabled

    with serial_lock:
        # SIM status
        resp = send_at_command("AT+CPIN?")
        sim_status = parse_cpin(resp)

        # Network registration
        resp = send_at_command("AT+CREG?")
        net_code, net_status = parse_creg(resp)

        # Signal quality
        resp = send_at_command("AT+CSQ")
        raw, percent, quality = parse_csq(resp)

        # Operator name (only meaningful once registered)
        operator = None
        if net_code in (1, 5):
            resp = send_at_command("AT+COPS?", wait=0.8, read_time=1.2)
            operator = parse_cops(resp)

        # GNSS: power it on once, then poll
        if not _gnss_enabled:
            send_at_command("AT+CGNSSPWR=1", wait=1.0, read_time=1.0)
            _gnss_enabled = True

        resp = send_at_command("AT+CGNSSINFO", wait=0.8, read_time=1.0)
        gnss = parse_cgnssinfo(resp)

    fields = {
        "sim_status": sim_status,
        "network_status_code": net_code,
        "network_status": net_status,
        "signal_raw": raw,
        "signal_percent": percent,
        "signal_quality": quality,
        "operator": operator,
    }

    if gnss:
        fields["gnss_fix"] = 1 if gnss.get("fix") else 0
        if gnss.get("fix"):
            fields["gnss_lat"] = gnss.get("lat")
            fields["gnss_lon"] = gnss.get("lon")
            fields["gnss_alt"] = gnss.get("alt")
            fields["gnss_satellites"] = gnss.get("satellites")
            fields["gnss_utc_time"] = gnss.get("utc_time")
            fields["gnss_speed"] = gnss.get("speed")

            if SYNC_SYSTEM_TIME and gnss.get("utc_time"):
                sync_system_time(gnss["utc_time"])

    update_modem_status(**fields)

_time_synced = False

def sync_system_time(utc_iso: str):
    """Set the system clock from a GNSS UTC fix, once per process lifetime
    (and only if the GNSS time looks sane)."""
    global _time_synced
    if _time_synced:
        return
    try:
        dt = datetime.fromisoformat(utc_iso)
        if dt.year < 2020:
            return  # clearly invalid fix, don't trust it
        subprocess.run(
            ["date", "-u", "-s", dt.strftime("%Y-%m-%d %H:%M:%S")],
            check=True, capture_output=True, timeout=5
        )
        print(f"[GNSS] System time synced to {utc_iso}", flush=True)
        _time_synced = True
    except Exception as e:
        print(f"[GNSS] Time sync failed: {e}", flush=True)

def status_loop():
    # Give the call listener time to establish the connection first.
    time.sleep(8)
    while True:
        try:
            poll_status_once()
        except Exception as e:
            print(f"[STATUS] Poll error: {e}", flush=True)
        time.sleep(STATUS_INTERVAL)

# ─── PIN Entry Handler ──────────────────────────────────────────────────────

def pin_handler_loop():
    while True:
        try:
            req = get_pending_pin_request()
            if req and req.get("pin"):
                pin = req["pin"]
                print("[PIN] Processing pending PIN entry request", flush=True)
                with serial_lock:
                    resp = send_at_command(f'AT+CPIN="{pin}"', wait=1.0, read_time=2.0)
                if "OK" in resp:
                    resolve_pin_request("ok")
                    print("[PIN] PIN accepted", flush=True)
                elif "ERROR" in resp:
                    resolve_pin_request("error")
                    print("[PIN] PIN rejected", flush=True)
                else:
                    resolve_pin_request("unknown")
        except Exception as e:
            print(f"[PIN] Handler error: {e}", flush=True)
        time.sleep(3)

# ─── Main Call Listener Loop ────────────────────────────────────────────────

def listen():
    modem_connect()
    pending_ring = False
    last_ring_time = 0

    while True:
        try:
            with serial_lock:
                raw = ser.readline()

            if not raw:
                continue

            line = raw.decode(errors="ignore").strip()
            if not line:
                continue

            print(f"[MODEM] << {line}", flush=True)

            if "RING" in line or "+CRING:" in line:
                now = time.time()
                if now - last_ring_time > 2:
                    pending_ring = True
                    last_ring_time = now

            if "+CLIP:" in line and pending_ring:
                pending_ring = False
                try:
                    phone = line.split('"')[1]
                    process_call(phone)
                except (IndexError, ValueError):
                    print(f"[CLIP] Could not parse number from: {line}", flush=True)

            if "NO CARRIER" in line or "+CIEV: call,0" in line:
                pending_ring = False

        except serial.SerialException as e:
            print(f"[MODEM] Serial error: {e} - reconnecting", flush=True)
            update_modem_status(connected=0)
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
    print(f" Status poll interval: {STATUS_INTERVAL}s", flush=True)
    print(f" Sync system time from GNSS: {SYNC_SYSTEM_TIME}", flush=True)
    print("=" * 50, flush=True)

    wait_for_db()

    threading.Thread(target=status_loop, daemon=True).start()
    threading.Thread(target=pin_handler_loop, daemon=True).start()

    listen()
