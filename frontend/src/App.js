import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_API_URL || "http://localhost:8000/api";

const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = {
  body: {
    margin: 0,
    fontFamily: "'Segoe UI', system-ui, sans-serif",
    background: "#0f172a",
    color: "#e2e8f0",
    minHeight: "100vh",
  },
  nav: {
    background: "#1e293b",
    padding: "0 24px",
    display: "flex",
    alignItems: "center",
    gap: "8px",
    borderBottom: "1px solid #334155",
    position: "sticky",
    top: 0,
    zIndex: 100,
  },
  navBrand: {
    fontSize: "20px",
    fontWeight: "700",
    color: "#38bdf8",
    padding: "16px 0",
    marginRight: "24px",
  },
  navBtn: (active) => ({
    padding: "16px 16px",
    cursor: "pointer",
    background: "none",
    border: "none",
    color: active ? "#38bdf8" : "#94a3b8",
    borderBottom: active ? "2px solid #38bdf8" : "2px solid transparent",
    fontSize: "14px",
    fontWeight: active ? "600" : "400",
  }),
  navRight: { marginLeft: "auto" },
  logoutBtn: {
    padding: "8px 16px",
    background: "#ef4444",
    color: "white",
    border: "none",
    borderRadius: "6px",
    cursor: "pointer",
    fontSize: "13px",
  },
  page: { padding: "24px", maxWidth: "1200px", margin: "0 auto" },
  card: {
    background: "#1e293b",
    borderRadius: "12px",
    padding: "24px",
    marginBottom: "24px",
    border: "1px solid #334155",
  },
  h2: { margin: "0 0 20px", fontSize: "18px", color: "#f1f5f9" },
  row: { display: "flex", gap: "12px", marginBottom: "12px", flexWrap: "wrap" },
  input: {
    padding: "10px 14px",
    background: "#0f172a",
    border: "1px solid #334155",
    borderRadius: "8px",
    color: "#e2e8f0",
    fontSize: "14px",
    flex: 1,
    minWidth: "160px",
  },
  btn: (color = "#3b82f6") => ({
    padding: "10px 18px",
    background: color,
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "600",
    whiteSpace: "nowrap",
  }),
  table: { width: "100%", borderCollapse: "collapse" },
  th: {
    padding: "10px 14px",
    background: "#0f172a",
    textAlign: "left",
    fontSize: "12px",
    color: "#94a3b8",
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  td: {
    padding: "12px 14px",
    borderBottom: "1px solid #1e293b",
    fontSize: "14px",
  },
  badge: (color) => ({
    display: "inline-block",
    padding: "2px 10px",
    borderRadius: "12px",
    fontSize: "12px",
    fontWeight: "600",
    background: color === "green" ? "#065f46" : color === "red" ? "#7f1d1d" : "#1e3a5f",
    color: color === "green" ? "#6ee7b7" : color === "red" ? "#fca5a5" : "#7dd3fc",
  }),
  matrixTable: { borderCollapse: "separate", borderSpacing: "4px" },
  matrixCell: (active) => ({
    width: "40px",
    height: "40px",
    textAlign: "center",
    cursor: "pointer",
    background: active ? "#065f46" : "#1e293b",
    border: active ? "2px solid #10b981" : "2px solid #334155",
    borderRadius: "8px",
    fontSize: "18px",
    transition: "all 0.15s",
    color: active ? "#6ee7b7" : "#475569",
  }),
  matrixHeader: {
    padding: "6px 8px",
    fontSize: "11px",
    color: "#94a3b8",
    maxWidth: "100px",
    wordBreak: "break-word",
    textAlign: "center",
  },
  statusCard: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: "12px",
    marginBottom: "24px",
  },
  statBox: {
    background: "#1e293b",
    border: "1px solid #334155",
    borderRadius: "10px",
    padding: "16px",
    textAlign: "center",
  },
  statNum: { fontSize: "28px", fontWeight: "700", color: "#38bdf8" },
  statLabel: { fontSize: "12px", color: "#64748b", marginTop: "4px" },
  signalBars: { display: "flex", gap: "3px", alignItems: "flex-end", justifyContent: "center", height: "28px" },
  signalBar: (active, color) => ({
    width: "6px",
    background: active ? color : "#334155",
    borderRadius: "2px",
  }),
  pinForm: { display: "flex", gap: "10px", alignItems: "center", marginTop: "12px" },
};

// ─── Login ────────────────────────────────────────────────────────────────────

function Login({ onLogin }) {
  const [u, setU] = useState("admin");
  const [p, setP] = useState("");
  const [err, setErr] = useState("");

  const submit = async () => {
    try {
      const res = await api.post("/auth/login", { username: u, password: p });
      localStorage.setItem("token", res.data.token);
      onLogin(res.data.username);
    } catch {
      setErr("Falsches Passwort oder Benutzername");
    }
  };

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "#0f172a" }}>
      <div style={{ ...styles.card, width: "360px" }}>
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <div style={{ fontSize: "40px" }}>📞</div>
          <h1 style={{ color: "#38bdf8", margin: "8px 0 4px" }}>Callbox</h1>
          <div style={{ color: "#64748b", fontSize: "13px" }}>Bitte anmelden</div>
        </div>
        {err && <div style={{ color: "#f87171", marginBottom: "12px", fontSize: "13px" }}>{err}</div>}
        <input style={{ ...styles.input, width: "100%", boxSizing: "border-box", marginBottom: "10px" }}
          value={u} onChange={e => setU(e.target.value)} placeholder="Benutzername" />
        <input style={{ ...styles.input, width: "100%", boxSizing: "border-box", marginBottom: "16px" }}
          type="password" value={p} onChange={e => setP(e.target.value)}
          placeholder="Passwort" onKeyDown={e => e.key === "Enter" && submit()} />
        <button style={{ ...styles.btn(), width: "100%" }} onClick={submit}>Anmelden</button>
      </div>
    </div>
  );
}

// ─── Users Page ───────────────────────────────────────────────────────────────

function UsersPage() {
  const [users, setUsers] = useState([]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");

  const load = useCallback(async () => {
    const r = await api.get("/users");
    setUsers(r.data);
  }, []);

  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!name || !phone) return;
    await api.post("/users", { name, phone });
    setName(""); setPhone(""); load();
  };

  const del = async (id) => {
    if (!window.confirm("Nutzer löschen?")) return;
    await api.delete(`/users/${id}`); load();
  };

  const toggle = async (id) => { await api.patch(`/users/${id}/toggle`); load(); };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h2 style={styles.h2}>Nutzer hinzufügen</h2>
        <div style={styles.row}>
          <input style={styles.input} value={name} onChange={e => setName(e.target.value)} placeholder="Name" />
          <input style={styles.input} value={phone} onChange={e => setPhone(e.target.value)} placeholder="+491701234567" />
          <button style={styles.btn("#10b981")} onClick={add}>+ Hinzufügen</button>
        </div>
      </div>
      <div style={styles.card}>
        <h2 style={styles.h2}>Alle Nutzer ({users.length})</h2>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Name</th>
              <th style={styles.th}>Telefon</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Aktionen</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} style={{ background: u.active ? "transparent" : "#0a0f1a" }}>
                <td style={styles.td}>{u.name}</td>
                <td style={{ ...styles.td, fontFamily: "monospace", color: "#7dd3fc" }}>{u.phone}</td>
                <td style={styles.td}>
                  <span style={styles.badge(u.active ? "green" : "red")}>
                    {u.active ? "✓ Aktiv" : "✗ Inaktiv"}
                  </span>
                </td>
                <td style={styles.td}>
                  <button style={{ ...styles.btn(u.active ? "#92400e" : "#065f46"), marginRight: "8px", padding: "6px 12px" }}
                    onClick={() => toggle(u.id)}>{u.active ? "Deaktivieren" : "Aktivieren"}</button>
                  <button style={{ ...styles.btn("#7f1d1d"), padding: "6px 12px" }} onClick={() => del(u.id)}>Löschen</button>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr><td colSpan={4} style={{ ...styles.td, color: "#475569", textAlign: "center" }}>Keine Nutzer angelegt</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Audio Page ───────────────────────────────────────────────────────────────

function AudioPage() {
  const [audios, setAudios] = useState([]);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState(null);

  const load = useCallback(async () => {
    const r = await api.get("/audio");
    setAudios(r.data);
  }, []);

  useEffect(() => { load(); }, [load]);

  const upload = async () => {
    if (!title || !file) return;
    const fd = new FormData();
    fd.append("title", title);
    fd.append("file", file);
    await api.post("/audio", fd);
    setTitle(""); setFile(null); load();
  };

  const del = async (id) => {
    if (!window.confirm("Audio-Datei löschen?")) return;
    await api.delete(`/audio/${id}`); load();
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h2 style={styles.h2}>Audio hochladen</h2>
        <div style={styles.row}>
          <input style={styles.input} value={title} onChange={e => setTitle(e.target.value)} placeholder="Bezeichnung (z.B. Begrüßung)" />
          <input style={{ ...styles.input, flex: "none" }} type="file" accept=".mp3,.wav,.ogg"
            onChange={e => setFile(e.target.files[0])} />
          <button style={styles.btn("#10b981")} onClick={upload}>⬆ Upload</button>
        </div>
        <div style={{ color: "#475569", fontSize: "12px" }}>Erlaubte Formate: MP3, WAV, OGG</div>
      </div>
      <div style={styles.card}>
        <h2 style={styles.h2}>Audio-Dateien ({audios.length})</h2>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Bezeichnung</th>
              <th style={styles.th}>Dateiname</th>
              <th style={styles.th}>Aktionen</th>
            </tr>
          </thead>
          <tbody>
            {audios.map(a => (
              <tr key={a.id}>
                <td style={styles.td}>{a.title}</td>
                <td style={{ ...styles.td, fontFamily: "monospace", fontSize: "12px", color: "#94a3b8" }}>{a.filename}</td>
                <td style={styles.td}>
                  <button style={{ ...styles.btn("#7f1d1d"), padding: "6px 12px" }} onClick={() => del(a.id)}>Löschen</button>
                </td>
              </tr>
            ))}
            {audios.length === 0 && (
              <tr><td colSpan={3} style={{ ...styles.td, color: "#475569", textAlign: "center" }}>Keine Audio-Dateien vorhanden</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Matrix Page ──────────────────────────────────────────────────────────────

function MatrixPage() {
  const [users, setUsers] = useState([]);
  const [audios, setAudios] = useState([]);
  const [matrix, setMatrix] = useState(new Set());

  const load = useCallback(async () => {
    const [ur, ar, mr] = await Promise.all([
      api.get("/users"), api.get("/audio"), api.get("/matrix")
    ]);
    setUsers(ur.data);
    setAudios(ar.data);
    setMatrix(new Set(mr.data.map(m => `${m.user_id}-${m.audio_id}`)));
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggle = async (user_id, audio_id) => {
    await api.post("/matrix/toggle", { user_id, audio_id });
    const key = `${user_id}-${audio_id}`;
    setMatrix(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  if (users.length === 0 || audios.length === 0) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <h2 style={styles.h2}>Matrix: Nutzer × Audio</h2>
          <p style={{ color: "#64748b" }}>
            {users.length === 0 && "⚠ Bitte zuerst Nutzer anlegen. "}
            {audios.length === 0 && "⚠ Bitte zuerst Audio-Dateien hochladen."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h2 style={styles.h2}>Matrix: Nutzer × Audio</h2>
        <p style={{ color: "#64748b", fontSize: "13px", marginTop: "-12px", marginBottom: "16px" }}>
          Klicke auf eine Zelle, um Audio einem Nutzer zuzuweisen. ● = aktiv
        </p>
        <div style={{ overflowX: "auto" }}>
          <table style={styles.matrixTable}>
            <thead>
              <tr>
                <th style={{ ...styles.matrixHeader, textAlign: "left", minWidth: "140px" }}>Nutzer</th>
                {audios.map(a => (
                  <th key={a.id} style={styles.matrixHeader}>{a.title}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id}>
                  <td style={{ padding: "4px 8px", fontSize: "13px", color: u.active ? "#e2e8f0" : "#475569" }}>
                    <div>{u.name}</div>
                    <div style={{ fontSize: "11px", color: "#7dd3fc", fontFamily: "monospace" }}>{u.phone}</div>
                  </td>
                  {audios.map(a => {
                    const active = matrix.has(`${u.id}-${a.id}`);
                    return (
                      <td key={a.id} style={{ padding: "4px", textAlign: "center" }}>
                        <button
                          style={styles.matrixCell(active)}
                          onClick={() => toggle(u.id, a.id)}
                          title={`${u.name} → ${a.title}`}
                        >
                          {active ? "●" : "○"}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ─── Logs Page ────────────────────────────────────────────────────────────────

function LogsPage() {
  const [logs, setLogs] = useState([]);

  const load = useCallback(async () => {
    const r = await api.get("/logs?limit=200");
    setLogs(r.data);
  }, []);

  useEffect(() => { load(); }, [load]);

  const clear = async () => {
    if (!window.confirm("Alle Logs löschen?")) return;
    await api.delete("/logs"); load();
  };

  const statusColor = (s) => s === "accepted" ? "green" : s === "rejected" ? "red" : "blue";
  const statusLabel = (s) => ({ accepted: "✓ Angenommen", rejected: "✗ Abgelehnt", no_audio: "Kein Audio", missing_file: "Datei fehlt" }[s] || s);

  return (
    <div style={styles.page}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <h2 style={{ ...styles.h2, margin: 0 }}>Anrufprotokoll ({logs.length})</h2>
        <button style={styles.btn("#7f1d1d")} onClick={clear}>Logs löschen</button>
      </div>
      <div style={styles.card}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Zeitpunkt</th>
              <th style={styles.th}>Rufnummer</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Audio</th>
            </tr>
          </thead>
          <tbody>
            {logs.map(l => (
              <tr key={l.id}>
                <td style={{ ...styles.td, fontSize: "12px", color: "#64748b" }}>{l.call_time}</td>
                <td style={{ ...styles.td, fontFamily: "monospace", color: "#7dd3fc" }}>{l.phone}</td>
                <td style={styles.td}><span style={styles.badge(statusColor(l.status))}>{statusLabel(l.status)}</span></td>
                <td style={{ ...styles.td, fontSize: "12px", color: "#94a3b8" }}>{l.audio_played || "–"}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr><td colSpan={4} style={{ ...styles.td, color: "#475569", textAlign: "center" }}>Noch keine Anrufe</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

function SignalBars({ percent, quality }) {
  const barCount = 5;
  const filled = percent == null ? 0 : Math.ceil((percent / 100) * barCount);
  const color = quality === "excellent" || quality === "good" ? "#10b981"
              : quality === "fair" ? "#f59e0b"
              : "#ef4444";
  return (
    <div style={styles.signalBars}>
      {Array.from({ length: barCount }).map((_, i) => (
        <div key={i} style={{ ...styles.signalBar(i < filled, color), height: `${8 + i * 5}px` }} />
      ))}
    </div>
  );
}

const QUALITY_LABEL = { excellent: "Sehr gut", good: "Gut", fair: "Mittel", poor: "Schwach", no_signal: "Kein Signal" };
const SIM_STATUS_LABEL = {
  ready: "Bereit", pin_required: "PIN erforderlich", puk_required: "PUK erforderlich",
  not_inserted: "Keine SIM-Karte", phone_sim_pin_required: "PIN erforderlich",
};
const NETWORK_STATUS_LABEL = {
  registered_home: "Im Heimnetz", registered_roaming: "Roaming",
  searching: "Suche Netz…", not_registered: "Nicht registriert",
  registration_denied: "Registrierung verweigert", unknown: "Unbekannt",
};

function PinEntry({ onSubmitted }) {
  const [pin, setPin] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  const submit = async () => {
    if (!pin) return;
    setSubmitting(true);
    setResult(null);
    try {
      await api.post("/modem/pin", { pin });
      // Poll for the result a few times
      for (let i = 0; i < 8; i++) {
        await new Promise(r => setTimeout(r, 1500));
        const res = await api.get("/modem/pin/status");
        if (res.data.processed && res.data.result) {
          setResult(res.data.result);
          if (res.data.result === "ok") {
            setPin("");
            onSubmitted?.();
          }
          break;
        }
      }
    } catch {
      setResult("error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div style={styles.pinForm}>
        <input
          style={{ ...styles.input, maxWidth: "140px" }}
          type="password"
          inputMode="numeric"
          placeholder="SIM-PIN eingeben"
          value={pin}
          onChange={e => setPin(e.target.value.replace(/\D/g, ""))}
          onKeyDown={e => e.key === "Enter" && submit()}
          disabled={submitting}
        />
        <button style={styles.btn("#10b981")} onClick={submit} disabled={submitting || !pin}>
          {submitting ? "Wird geprüft…" : "PIN senden"}
        </button>
      </div>
      {result === "ok" && <div style={{ color: "#6ee7b7", fontSize: "13px", marginTop: "8px" }}>✓ PIN akzeptiert</div>}
      {result === "error" && <div style={{ color: "#fca5a5", fontSize: "13px", marginTop: "8px" }}>✗ PIN falsch oder abgelehnt</div>}
      {result === "unknown" && <div style={{ color: "#fbbf24", fontSize: "13px", marginTop: "8px" }}>⚠ Unklare Antwort vom Modem, bitte Status prüfen</div>}
    </div>
  );
}

function ModemCard({ modem, onRefresh }) {
  if (!modem) {
    return (
      <div style={styles.card}>
        <h2 style={styles.h2}>📡 Modem &amp; Mobilfunk</h2>
        <p style={{ color: "#475569" }}>Noch keine Daten vom Modem empfangen…</p>
      </div>
    );
  }

  const needsPin = modem.sim_status === "pin_required" || modem.sim_status === "phone_sim_pin_required";

  return (
    <div style={styles.card}>
      <h2 style={styles.h2}>📡 Modem &amp; Mobilfunk</h2>

      <div style={styles.statusCard}>
        <div style={styles.statBox}>
          <SignalBars percent={modem.signal_percent} quality={modem.signal_quality} />
          <div style={styles.statLabel}>
            {modem.signal_raw != null ? `${modem.signal_raw}/31 · ` : ""}
            {QUALITY_LABEL[modem.signal_quality] || "–"}
          </div>
        </div>
        <div style={styles.statBox}>
          <div style={{ ...styles.statNum, fontSize: "16px" }}>
            {NETWORK_STATUS_LABEL[modem.network_status] || "–"}
          </div>
          <div style={styles.statLabel}>{modem.operator || "Netzstatus"}</div>
        </div>
        <div style={styles.statBox}>
          <div style={{ ...styles.statNum, fontSize: "16px", color: needsPin ? "#f59e0b" : "#10b981" }}>
            {SIM_STATUS_LABEL[modem.sim_status] || modem.sim_status || "–"}
          </div>
          <div style={styles.statLabel}>SIM-Status</div>
        </div>
        <div style={styles.statBox}>
          <div style={{ ...styles.statNum, color: modem.connected ? "#10b981" : "#f59e0b" }}>
            {modem.connected ? "●" : "○"}
          </div>
          <div style={styles.statLabel}>Verbindung</div>
        </div>
      </div>

      {needsPin && (
        <div style={{ marginTop: "8px", paddingTop: "16px", borderTop: "1px solid #334155" }}>
          <div style={{ color: "#fbbf24", fontSize: "13px", marginBottom: "4px" }}>
            ⚠ Die SIM-Karte wartet auf die PIN-Eingabe
          </div>
          <PinEntry onSubmitted={onRefresh} />
        </div>
      )}

      {modem.last_updated && (
        <div style={{ color: "#475569", fontSize: "11px", marginTop: "12px" }}>
          Zuletzt aktualisiert: {new Date(modem.last_updated).toLocaleString("de-DE")}
        </div>
      )}
    </div>
  );
}

function HotspotCard() {
  const [hs, setHs] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { const r = await api.get("/hotspot"); setHs(r.data); } catch {}
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 8000); return () => clearInterval(t); }, [load]);

  const toggle = async () => {
    if (!hs || busy) return;
    setBusy(true);
    try {
      await api.post(hs.active ? "/hotspot/stop" : "/hotspot/start");
      await load();
    } catch (e) {
      alert(e?.response?.data?.detail || "Fehler beim Steuern des Hotspots");
    } finally {
      setBusy(false);
    }
  };

  if (!hs?.configured) return null;

  return (
    <div style={styles.card}>
      <h2 style={styles.h2}>📶 WLAN Hotspot</h2>
      <div style={styles.statusCard}>
        <div style={styles.statBox}>
          <div style={{ ...styles.statNum, color: hs.active ? "#10b981" : "#64748b" }}>
            {hs.active ? "●" : "○"}
          </div>
          <div style={styles.statLabel}>{hs.active ? "Aktiv" : "Inaktiv"}</div>
        </div>
        {hs.ssid && (
          <div style={styles.statBox}>
            <div style={{ ...styles.statNum, fontSize: "16px" }}>{hs.ssid}</div>
            <div style={styles.statLabel}>WLAN-Name</div>
          </div>
        )}
        {hs.ip && (
          <div style={styles.statBox}>
            <div style={{ ...styles.statNum, fontSize: "14px", fontFamily: "monospace" }}>{hs.ip}</div>
            <div style={styles.statLabel}>Hotspot-IP</div>
          </div>
        )}
      </div>

      {hs.active && (
        <div style={{ background: "#0f172a", borderRadius: "8px", padding: "12px 16px", marginTop: "12px", fontSize: "13px", color: "#94a3b8" }}>
          Verbinde dich mit WLAN <strong style={{ color: "#e2e8f0" }}>{hs.ssid || "Callbox"}</strong> und öffne{" "}
          <span style={{ color: "#7dd3fc", fontFamily: "monospace" }}>http://{hs.ip || "192.168.4.1"}:3000</span>
        </div>
      )}

      <div style={{ marginTop: "12px", display: "flex", gap: "10px" }}>
        <button
          style={styles.btn(hs.active ? "#7f1d1d" : "#065f46")}
          onClick={toggle}
          disabled={busy}
        >
          {busy ? "Bitte warten…" : hs.active ? "Hotspot stoppen" : "Hotspot starten"}
        </button>
        <div style={{ fontSize: "12px", color: "#475569", alignSelf: "center" }}>
          Startet automatisch wenn kein Netz verfügbar
        </div>
      </div>
    </div>
  );
}

function Dashboard() {
  const [status, setStatus] = useState(null);
  const [modem, setModem] = useState(null);

  const loadModem = useCallback(async () => {
    try { const r = await api.get("/modem"); setModem(r.data); } catch {}
  }, []);

  useEffect(() => {
    const load = async () => {
      try { const r = await api.get("/status"); setStatus(r.data); } catch {}
      loadModem();
    };
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [loadModem]);

  return (
    <div style={styles.page}>
      <div style={styles.statusCard}>
        <div style={styles.statBox}>
          <div style={styles.statNum}>{status?.active_users ?? "–"}</div>
          <div style={styles.statLabel}>Aktive Nutzer</div>
        </div>
        <div style={styles.statBox}>
          <div style={styles.statNum}>{status?.audio_files ?? "–"}</div>
          <div style={styles.statLabel}>Audio-Dateien</div>
        </div>
        <div style={styles.statBox}>
          <div style={styles.statNum}>{status?.total_calls ?? "–"}</div>
          <div style={styles.statLabel}>Anrufe gesamt</div>
        </div>
        <div style={styles.statBox}>
          <div style={{ ...styles.statNum, color: modem?.connected ? "#10b981" : "#f59e0b" }}>
            {modem?.connected ? "●" : "○"}
          </div>
          <div style={styles.statLabel}>Modem</div>
        </div>
      </div>

      <ModemCard modem={modem} onRefresh={loadModem} />
      <HotspotCard />

      {status?.last_call && (
        <div style={styles.card}>
          <h2 style={styles.h2}>Letzter Anruf</h2>
          <div style={{ fontFamily: "monospace", color: "#7dd3fc", fontSize: "18px" }}>{status.last_call.phone}</div>
          <div style={{ color: "#64748b", fontSize: "13px", marginTop: "8px" }}>
            Status: {status.last_call.status} · {new Date(status.last_call.call_time).toLocaleString("de-DE")}
          </div>
        </div>
      )}

      <div style={styles.card}>
        <h2 style={styles.h2}>📖 Kurzanleitung</h2>
        <ol style={{ color: "#94a3b8", lineHeight: "2", paddingLeft: "20px" }}>
          <li><strong style={{ color: "#e2e8f0" }}>Nutzer</strong> – Lege Nutzer mit Telefonnummer an</li>
          <li><strong style={{ color: "#e2e8f0" }}>Audio</strong> – Lade MP3/WAV-Dateien hoch</li>
          <li><strong style={{ color: "#e2e8f0" }}>Matrix</strong> – Weise jedem Nutzer eine Audio-Datei zu</li>
          <li>Bei Anruf: bekannte Nummer → Audio abspielen, unbekannte → sofort ablehnen</li>
        </ol>
      </div>
    </div>
  );
}

// ─── Settings Page ────────────────────────────────────────────────────────────

function SettingsPage() {
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = useCallback(async () => {
    try { const r = await api.get("/settings"); setSettings(r.data); } catch {}
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async (patch) => {
    setSaving(true);
    setMsg(null);
    try {
      const r = await api.patch("/settings", patch);
      setMsg({ ok: true, text: r.data.note || "Gespeichert." });
      load();
    } catch (e) {
      setMsg({ ok: false, text: e?.response?.data?.detail || "Fehler beim Speichern." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={styles.page}>

      {/* Audio-Kanal */}
      <div style={styles.card}>
        <h2 style={styles.h2}>🔊 Audio-Ausgabe</h2>
        <p style={{ color: "#64748b", fontSize: "13px", marginBottom: "16px" }}>
          Aktuelles Audio-Gerät: <strong style={{ color: "#e2e8f0" }}>{settings?.audio_label || "–"}</strong>
        </p>
        <div style={{ marginBottom: "16px" }}>
          <div style={{ color: "#94a3b8", fontSize: "13px", marginBottom: "10px" }}>
            <strong style={{ color: "#e2e8f0" }}>Audio-Kanal</strong><br />
            Mono spart Energie und reicht vollständig für Sprachansagen.
            Stereo ist sinnvoll bei Musik oder räumlichen Klängen.
          </div>
          <div style={{ display: "flex", gap: "10px" }}>
            {["stereo", "mono"].map(ch => (
              <button
                key={ch}
                style={{
                  ...styles.btn(settings?.audio_channels === ch ? "#1e3a5f" : "#1e293b"),
                  border: settings?.audio_channels === ch ? "2px solid #38bdf8" : "2px solid #334155",
                  color: settings?.audio_channels === ch ? "#38bdf8" : "#94a3b8",
                }}
                onClick={() => save({ audio_channels: ch })}
                disabled={saving || settings?.audio_channels === ch}
              >
                {ch === "mono" ? "🔈 Mono" : "🔊 Stereo"}
                {settings?.audio_channels === ch && " ✓"}
              </button>
            ))}
          </div>
        </div>
        {msg && (
          <div style={{
            padding: "10px 14px",
            borderRadius: "8px",
            fontSize: "13px",
            background: msg.ok ? "#064e3b" : "#7f1d1d",
            color: msg.ok ? "#6ee7b7" : "#fca5a5",
            marginTop: "8px",
          }}>
            {msg.text}
            {msg.ok && (
              <div style={{ marginTop: "6px", color: "#94a3b8", fontSize: "12px" }}>
                Neustart nötig damit Änderung aktiv wird:<br />
                <code style={{ color: "#7dd3fc" }}>sudo systemctl restart callbox</code>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Hotspot-Info */}
      <div style={styles.card}>
        <h2 style={styles.h2}>📶 WLAN Hotspot</h2>
        {settings?.hotspot_enabled ? (
          <p style={{ color: "#64748b", fontSize: "13px" }}>
            Hotspot ist eingerichtet. Status und Steuerung im <strong style={{ color: "#e2e8f0" }}>Dashboard</strong>.
            <br />Konfiguration ändern: <code style={{ color: "#7dd3fc" }}>sudo bash /opt/callbox/scripts/setup_hotspot.sh</code>
          </p>
        ) : (
          <div>
            <p style={{ color: "#64748b", fontSize: "13px", marginBottom: "12px" }}>
              Kein Hotspot eingerichtet. Der Pi startet automatisch einen WLAN-Zugriffspunkt
              wenn kein Netz verfügbar ist – ideal für den Standalone-Betrieb.
            </p>
            <code style={{ color: "#7dd3fc", fontSize: "13px" }}>sudo bash /opt/callbox/scripts/setup_hotspot.sh</code>
          </div>
        )}
      </div>

      {/* mDNS Info */}
      <div style={styles.card}>
        <h2 style={styles.h2}>🌐 Erreichbarkeit</h2>
        <p style={{ color: "#64748b", fontSize: "13px", marginBottom: "12px" }}>
          Das Web-Interface ist immer erreichbar, auch wenn sich die IP-Adresse des Pi ändert:
        </p>
        <div style={{ background: "#0f172a", borderRadius: "8px", padding: "14px 16px" }}>
          <div style={{ fontSize: "13px", color: "#94a3b8", marginBottom: "6px" }}>mDNS-Adresse (empfohlen):</div>
          <div style={{ fontFamily: "monospace", color: "#7dd3fc", fontSize: "16px" }}>
            http://{window.location.hostname.includes(".local") ? window.location.hostname : "<hostname>.local"}:3000
          </div>
          <div style={{ fontSize: "12px", color: "#475569", marginTop: "8px" }}>
            Funktioniert ohne Router-Konfiguration auf Mac, iOS, Android und Windows 10+
          </div>
        </div>
      </div>

    </div>
  );
}

// ─── App Root ─────────────────────────────────────────────────────────────────

export default function App() {
  const [user, setUser] = useState(localStorage.getItem("cbuser") || null);
  const [tab, setTab] = useState("dashboard");

  const onLogin = (u) => { localStorage.setItem("cbuser", u); setUser(u); };
  const logout = () => { localStorage.removeItem("token"); localStorage.removeItem("cbuser"); setUser(null); };

  if (!user) return <Login onLogin={onLogin} />;

  const tabs = [
    { id: "dashboard", label: "📊 Dashboard" },
    { id: "users", label: "👥 Nutzer" },
    { id: "audio", label: "🔊 Audio" },
    { id: "matrix", label: "⬛ Matrix" },
    { id: "logs", label: "📋 Protokoll" },
    { id: "settings", label: "⚙️ Einstellungen" },
  ];

  return (
    <div style={styles.body}>
      <nav style={styles.nav}>
        <div style={styles.navBrand}>📞 Callbox</div>
        {tabs.map(t => (
          <button key={t.id} style={styles.navBtn(tab === t.id)} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
        <div style={styles.navRight}>
          <button style={styles.logoutBtn} onClick={logout}>Abmelden</button>
        </div>
      </nav>
      {tab === "dashboard" && <Dashboard />}
      {tab === "users" && <UsersPage />}
      {tab === "audio" && <AudioPage />}
      {tab === "matrix" && <MatrixPage />}
      {tab === "logs" && <LogsPage />}
      {tab === "settings" && <SettingsPage />}
    </div>
  );
}
