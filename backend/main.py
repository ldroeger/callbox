import os
import shutil
import asyncio
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db as database
from auth import verify_login, create_token, require_auth

AUDIO_PATH = os.environ.get("AUDIO_PATH", "/app/audio")
DB_PATH = os.environ.get("DB_PATH", "/app/data/callbox.db")

app = FastAPI(title="Callbox API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(AUDIO_PATH, exist_ok=True)
database.init_db()

# Live status shared across connections
live_status = {"last_call": None, "last_status": None, "modem": "unknown"}
ws_clients = []


# ─── Auth ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/auth/login")
def login(req: LoginRequest):
    if not verify_login(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(req.username)
    return {"token": token, "username": req.username}


# ─── Users ───────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    phone: str

@app.get("/api/users")
def get_users(user=Depends(require_auth)):
    conn = database.get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/users")
def create_user(data: UserCreate, user=Depends(require_auth)):
    conn = database.get_conn()
    try:
        conn.execute("INSERT INTO users (name, phone) VALUES (?,?)", (data.name, data.phone))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Phone number already exists")
    finally:
        conn.close()
    return {"ok": True}

@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, user=Depends(require_auth)):
    conn = database.get_conn()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.execute("DELETE FROM matrix WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.patch("/api/users/{user_id}/toggle")
def toggle_user(user_id: int, user=Depends(require_auth)):
    conn = database.get_conn()
    conn.execute("UPDATE users SET active = 1 - active WHERE id=?", (user_id,))
    conn.commit()
    row = conn.execute("SELECT active FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return {"active": row["active"]}


# ─── Audio ───────────────────────────────────────────────────────────────────

@app.get("/api/audio")
def get_audio(user=Depends(require_auth)):
    conn = database.get_conn()
    rows = conn.execute("SELECT * FROM audio ORDER BY title").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/audio")
async def upload_audio(
    title: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(require_auth)
):
    allowed = {".mp3", ".wav", ".ogg"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Only MP3, WAV, OGG allowed")

    safe_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{Path(file.filename).name}"
    dest = os.path.join(AUDIO_PATH, safe_name)

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    conn = database.get_conn()
    conn.execute("INSERT INTO audio (filename, title) VALUES (?,?)", (safe_name, title))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/audio/{audio_id}")
def delete_audio(audio_id: int, user=Depends(require_auth)):
    conn = database.get_conn()
    row = conn.execute("SELECT filename FROM audio WHERE id=?", (audio_id,)).fetchone()
    if row:
        path = os.path.join(AUDIO_PATH, row["filename"])
        if os.path.exists(path):
            os.remove(path)
        conn.execute("DELETE FROM audio WHERE id=?", (audio_id,))
        conn.execute("DELETE FROM matrix WHERE audio_id=?", (audio_id,))
        conn.commit()
    conn.close()
    return {"ok": True}


# ─── Matrix ──────────────────────────────────────────────────────────────────

@app.get("/api/matrix")
def get_matrix(user=Depends(require_auth)):
    conn = database.get_conn()
    rows = conn.execute("SELECT user_id, audio_id FROM matrix").fetchall()
    conn.close()
    return [{"user_id": r["user_id"], "audio_id": r["audio_id"]} for r in rows]

class ToggleRequest(BaseModel):
    user_id: int
    audio_id: int

@app.post("/api/matrix/toggle")
def toggle_matrix(data: ToggleRequest, user=Depends(require_auth)):
    conn = database.get_conn()
    exists = conn.execute(
        "SELECT 1 FROM matrix WHERE user_id=? AND audio_id=?",
        (data.user_id, data.audio_id)
    ).fetchone()

    if exists:
        conn.execute(
            "DELETE FROM matrix WHERE user_id=? AND audio_id=?",
            (data.user_id, data.audio_id)
        )
        active = False
    else:
        conn.execute(
            "INSERT OR IGNORE INTO matrix (user_id, audio_id) VALUES (?,?)",
            (data.user_id, data.audio_id)
        )
        active = True

    conn.commit()
    conn.close()
    return {"active": active}


# ─── Call Log ────────────────────────────────────────────────────────────────

@app.get("/api/logs")
def get_logs(limit: int = 100, user=Depends(require_auth)):
    conn = database.get_conn()
    rows = conn.execute(
        "SELECT * FROM call_log ORDER BY call_time DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.delete("/api/logs")
def clear_logs(user=Depends(require_auth)):
    conn = database.get_conn()
    conn.execute("DELETE FROM call_log")
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── Status ──────────────────────────────────────────────────────────────────

@app.get("/api/status")
def get_status(user=Depends(require_auth)):
    conn = database.get_conn()
    users = conn.execute("SELECT COUNT(*) as c FROM users WHERE active=1").fetchone()["c"]
    audios = conn.execute("SELECT COUNT(*) as c FROM audio").fetchone()["c"]
    logs = conn.execute("SELECT COUNT(*) as c FROM call_log").fetchone()["c"]
    last_call = conn.execute(
        "SELECT phone, status, call_time FROM call_log ORDER BY call_time DESC LIMIT 1"
    ).fetchone()
    conn.close()

    return {
        "active_users": users,
        "audio_files": audios,
        "total_calls": logs,
        "last_call": dict(last_call) if last_call else None,
    }


# ─── Modem Status & GNSS ─────────────────────────────────────────────────────

@app.get("/api/modem")
def get_modem(user=Depends(require_auth)):
    """
    Returns the latest modem status snapshot as written by the call engine:
    connectivity, SIM/PIN state, network registration, signal quality,
    operator name, and GNSS fix (used for position + system time sync).
    """
    status = database.get_modem_status()
    if not status:
        raise HTTPException(status_code=404, detail="No modem status available yet")
    return status

class PinSubmit(BaseModel):
    pin: str

@app.post("/api/modem/pin")
def submit_pin(data: PinSubmit, user=Depends(require_auth)):
    """
    Queues a PIN for the call engine to submit to the modem.
    The call engine polls for pending requests and resolves them;
    poll /api/modem/pin/status afterwards to see the result.
    """
    if not data.pin or not data.pin.isdigit() or len(data.pin) not in (4, 8):
        raise HTTPException(status_code=400, detail="PIN must be 4 or 8 digits")
    database.request_pin_entry(data.pin)
    return {"ok": True, "queued": True}

@app.get("/api/modem/pin/status")
def pin_status(user=Depends(require_auth)):
    """
    Poll this after submitting a PIN to see whether the call engine
    has processed it yet, and whether the modem accepted it.
    result: null (pending) | "ok" | "error" | "unknown"
    """
    result = database.get_pin_request_result()
    if not result:
        return {"processed": True, "result": None}
    return result


# ─── Hotspot ─────────────────────────────────────────────────────────────────

import subprocess as _sp

def _nmcli(*args):
    """Run an nmcli command, return (returncode, stdout)."""
    try:
        r = _sp.run(["nmcli"] + list(args), capture_output=True, text=True, timeout=10)
        return r.returncode, r.stdout.strip()
    except Exception as e:
        return -1, str(e)

@app.get("/api/hotspot")
def hotspot_status(user=Depends(require_auth)):
    """Return current hotspot state."""
    code, out = _nmcli("-t", "-f", "NAME,STATE", "connection", "show", "--active")
    active = "Callbox-Hotspot" in out

    # Also check if the connection profile exists at all
    code2, out2 = _nmcli("-t", "-f", "NAME", "connection", "show")
    configured = "Callbox-Hotspot" in out2

    # Read SSID and IP from .env if available
    env_path = "/app/data/../../../opt/callbox/.env"
    ssid, ip = None, None
    try:
        env_path = os.environ.get("ENV_PATH", "/run/secrets/callbox_env") or ""
        # Read directly from process environment (passed via docker-compose)
        ssid = os.environ.get("HOTSPOT_SSID")
        ip   = os.environ.get("HOTSPOT_IP", "192.168.4.1")
    except Exception:
        pass

    return {"active": active, "configured": configured, "ssid": ssid, "ip": ip}

@app.post("/api/hotspot/start")
def hotspot_start(user=Depends(require_auth)):
    code, out = _nmcli("connection", "up", "Callbox-Hotspot")
    if code != 0:
        raise HTTPException(status_code=500, detail=f"Hotspot konnte nicht gestartet werden: {out}")
    return {"ok": True, "active": True}

@app.post("/api/hotspot/stop")
def hotspot_stop(user=Depends(require_auth)):
    code, out = _nmcli("connection", "down", "Callbox-Hotspot")
    if code != 0:
        raise HTTPException(status_code=500, detail=f"Hotspot konnte nicht gestoppt werden: {out}")
    return {"ok": True, "active": False}


# ─── Settings ────────────────────────────────────────────────────────────────

ENV_PATH = "/opt/callbox/.env"  # Host path, mounted read-only via volume not available here
                                 # We read what was injected as env vars at container start.

@app.get("/api/settings")
def get_settings(user=Depends(require_auth)):
    """Return current runtime settings that can be changed via the web UI."""
    return {
        "audio_channels": os.environ.get("AUDIO_CHANNELS", "stereo"),
        "audio_label":    os.environ.get("AUDIO_LABEL",    ""),
        "reject_unknown": os.environ.get("REJECT_UNKNOWN", "true") == "true",
        "number_format":  os.environ.get("NUMBER_FORMAT",  "international"),
        "hotspot_enabled": os.environ.get("HOTSPOT_ENABLED", "false") == "true",
    }

class SettingsPatch(BaseModel):
    audio_channels: Optional[str] = None   # "stereo" | "mono"

@app.patch("/api/settings")
def patch_settings(data: SettingsPatch, user=Depends(require_auth)):
    """
    Persist a changed setting to /opt/callbox/.env on the host.
    Requires the .env file to be bind-mounted into the container.
    After saving, the containers must be restarted for changes to take effect.
    """
    host_env = "/data/../../../opt/callbox/.env"  # relative to /app/data mount
    # Resolve to actual host path via the mounted data volume
    env_candidates = [
        "/opt/callbox/.env",
        os.path.join(os.path.dirname(DB_PATH), "../../.env"),
    ]
    env_file = None
    for c in env_candidates:
        if os.path.exists(c):
            env_file = c
            break

    if not env_file:
        raise HTTPException(status_code=503,
            detail="Konfigurationsdatei nicht erreichbar. Bitte manuell in .env ändern.")

    # Read current content
    with open(env_file, "r") as f:
        lines = f.readlines()

    changes = {}
    if data.audio_channels and data.audio_channels in ("stereo", "mono"):
        changes["AUDIO_CHANNELS"] = data.audio_channels

    if not changes:
        raise HTTPException(status_code=400, detail="Keine gültigen Einstellungen")

    # Apply changes: update existing keys or append if missing
    new_lines = []
    applied = set()
    for line in lines:
        key = line.split("=")[0].strip().strip('"')
        if key in changes:
            new_lines.append(f'{key}="{changes[key]}"\n')
            applied.add(key)
        else:
            new_lines.append(line)

    for key, val in changes.items():
        if key not in applied:
            new_lines.append(f'{key}="{val}"\n')

    with open(env_file, "w") as f:
        f.writelines(new_lines)

    return {"ok": True, "saved": changes,
            "restart_required": True,
            "note": "Einstellungen gespeichert. Bitte Container neu starten: sudo systemctl restart callbox"}


# ─── WebSocket Live ──────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    try:
        while True:
            modem = database.get_modem_status() or {}
            await websocket.send_json({**live_status, "modem": modem})
            await asyncio.sleep(3)
    except Exception:
        ws_clients.remove(websocket)
