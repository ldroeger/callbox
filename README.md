# 📞 Callbox

> GSM/LTE Anruf-Steuerungssystem für den Raspberry Pi mit Web-Oberfläche

Callbox erkennt eingehende Anrufe auf einer SIM-Karte, prüft die Rufnummer gegen eine Whitelist und spielt automatisch eine zugewiesene Audio-Datei ab. Unbekannte Nummern werden sofort abgelehnt. Alles wird über ein modernes Web-Interface verwaltet.

---

## 🚀 Installation (ein Befehl)

```bash
curl -fsSL https://raw.githubusercontent.com/ldroeger/callbox/main/install.sh | sudo bash
```

Der Installer:
1. Installiert Docker und alle Abhängigkeiten
2. Klont dieses Repository nach `/opt/callbox`
3. **Startet den Setup-Assistenten** (interaktiv, ~2 Minuten)
4. Baut alle Docker-Container
5. Richtet den Autostart ein

---

## 🧰 Hardware

| Komponente | Empfehlung |
|---|---|
| Computer | Raspberry Pi 4 (4 GB RAM) |
| Modem | Waveshare SIM7600E-H LTE HAT |
| Audio | USB-Soundkarte **oder** Raspberry Pi DAC Pro HAT |
| Lautsprecher | Aktiv-Lautsprecher (3,5 mm Klinke) |
| Speicher | 32 GB microSD (Industrial) oder USB-SSD |

**SIM-Karte:** Muss **Sprachdienst** (Voice) unterstützen – reine Datentarife funktionieren nicht.

---

## 🌐 Web-Interface

Nach der Installation erreichbar unter `http://<Pi-IP>:3000`

| Seite | Funktion |
|---|---|
| **Dashboard** | Systemstatus, Modem-Status, Signalstärke, GNSS-Position, letzter Anruf |
| **Nutzer** | Telefonnummern anlegen, sperren, löschen |
| **Audio** | MP3/WAV-Dateien hochladen und verwalten |
| **Matrix** | Zuordnung Nutzer ↔ Audio (per Klick) |
| **Protokoll** | Alle Anrufe mit Zeitstempel und Status |

### Matrix-Ansicht

```
              Begrüßung   Tor öffnen   Alarm
Max Mustermann     ●           ○          ○
Lieferant          ○           ●          ○
Sicherheit         ○           ○          ●
```

● = aktiv zugewiesen  •  Klick zum Umschalten

---

## 📡 Modem-Status & GNSS

Das Dashboard zeigt live Daten direkt vom SIM7600-Modem, alle 15 Sekunden aktualisiert:

- **Signalstärke** als Balkenanzeige (0–31, in % umgerechnet) mit Qualitätsstufe
- **Netzstatus** (registriert im Heimnetz, Roaming, Suche, etc.) und Netzbetreibername
- **SIM-Status** inklusive automatischer Erkennung, ob eine PIN-Eingabe nötig ist
- **GNSS-Position** (Breite/Länge, Höhe, Anzahl Satelliten, UTC-Zeit), sofern GPS-Fix vorhanden

### PIN-Eingabe im Webinterface

Falls die SIM-Karte beim Start eine PIN erwartet, erscheint im Dashboard automatisch ein Eingabefeld. Die PIN wird sicher an die Call-Engine übergeben, die sie direkt ans Modem sendet – kein Minicom/SSH mehr nötig.

> **Für den Dauerbetrieb empfehlenswert:** Die SIM-PIN dauerhaft deaktivieren (im Modem selbst, siehe Fehlerbehebung), damit das System nach jedem Neustart automatisch ins Netz kommt, ohne dass jemand die PIN eingeben muss.

### Systemzeit per GNSS

Da das SIM7600 GNSS (GPS/GLONASS/BeiDou) unterstützt, kann die Pi-Systemzeit beim Start einmalig aus einem GNSS-Fix gesetzt werden – nützlich, wenn der Pi keinen Internetzugang für NTP hat oder ohne RTC-Modul betrieben wird. Steuerbar über `SYNC_SYSTEM_TIME_FROM_GNSS=true/false` in der `.env`.

---

## ⚙️ Anruf-Logik

```
Anruf eingehend
      │
      ▼
Rufnummer erkannt (+CLIP)
      │
      ▼
Nummer in Whitelist?
   ┌──┴──┐
  JA    NEIN
   │      │
   │      └──► Sofort ablehnen (ATH)
   │           Log: "rejected"
   ▼
Audio zugewiesen?
   │
   ▼
Auflegen → Audio abspielen → Log: "accepted"
```

---

## 🔧 Konfiguration

### Setup-Assistent erneut ausführen

```bash
sudo bash /opt/callbox/scripts/reconfigure.sh
```

### Konfigurationsdatei direkt bearbeiten

```bash
sudo nano /opt/callbox/.env
sudo systemctl restart callbox
```

### Wichtige Einstellungen

```env
CONNECTION_MODE=usb           # usb (UART-Jumper A) oder gpio (UART-Jumper B)
MODEM_PORT=/dev/ttyUSB2       # SIM7600 Port (USB) oder /dev/serial0 (GPIO-UART)
HOST_IP=192.168.1.100         # IP des Raspberry Pi
ADMIN_USER=admin              # Web-Interface Benutzer
ADMIN_PASS=sicheres-passwort  # Web-Interface Passwort
REJECT_UNKNOWN=true           # Unbekannte Nummern ablehnen
NUMBER_FORMAT=international   # international (+49...) oder national (0...)
LOG_RETENTION_DAYS=30         # Protokoll-Aufbewahrung
SYNC_SYSTEM_TIME_FROM_GNSS=true  # Pi-Systemzeit einmalig aus GNSS-Fix setzen
STATUS_INTERVAL_SECONDS=15    # Wie oft Signal/GNSS/SIM-Status abgefragt werden
```

### Verbindungsart: USB vs. GPIO-UART

Das SIM7600 kann auf zwei Arten mit dem Pi verbunden werden – die Wahl wird über den **UART-Jumper** auf dem HAT getroffen (Stellung A/B/C):

| Jumper | Verbindungsart | Zusätzliches Kabel | Modem-Port |
|---|---|---|---|
| **A** | USB | Ja, Micro-USB-Kabel HAT → Pi | `/dev/ttyUSB0`–`ttyUSB3` |
| **B** | GPIO-UART | Nein | `/dev/serial0` |

Bei **GPIO-UART** muss zusätzlich in `/boot/firmware/config.txt` Folgendes gesetzt sein:

```ini
enable_uart=1
dtoverlay=disable-bt
```

und Bluetooth deaktiviert werden:

```bash
sudo systemctl disable hciuart
sudo reboot
```

> **Hinweis (Pi 4):** Bluetooth ist fest mit dem vollwertigen UART verdrahtet. Ohne `disable-bt` zeigt `/dev/serial0` auf den langsameren Mini-UART, was zu instabiler Kommunikation führen kann.

---

## 📋 Nützliche Befehle

```bash
# Logs in Echtzeit
docker compose -f /opt/callbox/docker-compose.yml logs -f

# Nur Call-Engine Logs
docker compose -f /opt/callbox/docker-compose.yml logs -f call-engine

# System neu starten
sudo systemctl restart callbox

# System stoppen
sudo systemctl stop callbox

# Update auf neueste Version
sudo bash /opt/callbox/scripts/update.sh

# Setup erneut ausführen
sudo bash /opt/callbox/scripts/reconfigure.sh

# Container Status
docker compose -f /opt/callbox/docker-compose.yml ps
```

---

## 📁 Projektstruktur

```
callbox/
├── install.sh              ← One-Click Installer
├── docker-compose.yml      ← Container-Konfiguration
├── .env                    ← Deine Einstellungen (nicht im Git)
├── backend/                ← FastAPI REST-API
│   ├── main.py             ← API-Routen
│   ├── db.py               ← Datenbank-Funktionen
│   ├── auth.py             ← JWT-Authentifizierung
│   └── Dockerfile
├── engine/                 ← SIM7600 Call-Engine
│   ├── call_engine.py      ← Modem-Listener & Logik
│   └── Dockerfile
├── frontend/               ← React Web-Interface
│   ├── src/App.js          ← Haupt-UI
│   └── Dockerfile
├── scripts/
│   ├── setup_wizard.sh     ← Interaktiver Einrichtungsassistent
│   ├── update.sh           ← Update-Script
│   └── reconfigure.sh      ← Neukonfiguration
├── audio/                  ← Audio-Dateien (runtime, nicht im Git)
└── data/                   ← SQLite-Datenbank (runtime, nicht im Git)
```

---

## 🔒 Sicherheit

- JWT-Token-basierte Authentifizierung
- HTTPS: empfohlen über einen Reverse Proxy (z. B. Nginx + Let's Encrypt)
- Für Fernzugriff: **VPN (WireGuard)** statt offener Portfreigabe empfohlen
- `.env` wird nicht in Git versioniert (steht in `.gitignore`)

---

## 🐛 Fehlerbehebung

**Modem wird nicht erkannt:**
```bash
ls -la /dev/ttyUSB*
# Falls leer: lsusb prüfen
lsusb | grep -i sim
```

**Audio spielt nicht:**
```bash
# Test direkt auf dem Pi
mpg123 /opt/callbox/audio/test.mp3
# Soundkarte prüfen
aplay -l
```

**Keine Rufnummernkennung:**
- SIM-Karte muss CLIP (Calling Line Identification Presentation) unterstützen
- Beim Mobilfunkanbieter ggf. aktivieren
- Überprüfe `NUMBER_FORMAT` in `.env`

---

## 📜 Lizenz

MIT License – Freie Verwendung, auch kommerziell.
