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
    conn.close()
    return {
        "active_users": users,
        "audio_files": audios,
        "total_calls": logs,
        **live_status
    }


# ─── WebSocket Live ──────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    try:
        while True:
            await websocket.send_json(live_status)
            await asyncio.sleep(3)
    except Exception:
        ws_clients.remove(websocket)
