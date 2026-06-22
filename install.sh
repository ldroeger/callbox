#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║           CALLBOX – One-Line Installer                       ║
# ║  curl -fsSL https://raw.githubusercontent.com/               ║
# ║    ldroeger/callbox/main/install.sh -o /tmp/callbox_install.sh║
# ║  sudo bash /tmp/callbox_install.sh                           ║
# ╚══════════════════════════════════════════════════════════════╝

set -e

# ─── Self-relaunch guard ──────────────────────────────────────────────────────
# When this script is run via `curl ... | sudo bash`, it executes while still
# being streamed through a pipe. Trying to repoint stdin to /dev/tty mid-pipe
# has been observed to race with curl/sudo on some SSH setups and hang
# indefinitely with no output at all. To make the one-liner work reliably
# in every case, detect that situation and re-exec this same script from a
# real file on disk instead - the safe, recommended way to run it anyway.
if [ ! -t 0 ]; then
  if [ -e /dev/tty ]; then
    SELF_COPY="/tmp/.callbox_install_$$.sh"
    cat > "$SELF_COPY"
    chmod +x "$SELF_COPY"
    exec bash "$SELF_COPY" "$@" < /dev/tty
  else
    echo "FEHLER: Kein interaktives Terminal verfügbar (/dev/tty fehlt)."
    echo "Lade die Datei herunter und führe sie direkt aus:"
    echo "  curl -fsSL https://raw.githubusercontent.com/ldroeger/callbox/main/install.sh -o /tmp/callbox_install.sh"
    echo "  sudo bash /tmp/callbox_install.sh"
    exit 1
  fi
fi

REPO="https://github.com/ldroeger/callbox"
REPO_RAW="https://raw.githubusercontent.com/ldroeger/callbox/main"
INSTALL_DIR="/opt/callbox"
SERVICE_USER="${SUDO_USER:-pi}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ─── Helper functions ─────────────────────────────────────────────────────────

log()     { echo -e "${GREEN}[✓]${NC} $1"; }
info()    { echo -e "${BLUE}[i]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }
section() { echo -e "\n${BOLD}${CYAN}━━━ $1 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

# ─── Banner ───────────────────────────────────────────────────────────────────

clear
echo -e "${CYAN}"
cat << 'BANNER'
  ██████╗ █████╗ ██╗     ██╗     ██████╗  ██████╗ ██╗  ██╗
 ██╔════╝██╔══██╗██║     ██║     ██╔══██╗██╔═══██╗╚██╗██╔╝
 ██║     ███████║██║     ██║     ██████╔╝██║   ██║ ╚███╔╝
 ██║     ██╔══██║██║     ██║     ██╔══██╗██║   ██║ ██╔██╗
 ╚██████╗██║  ██║███████╗███████╗██████╔╝╚██████╔╝██╔╝ ██╗
  ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝
BANNER
echo -e "${NC}"
echo -e "${BOLD}  GSM/LTE Anruf-Steuerungssystem für Raspberry Pi${NC}"
echo -e "  ${BLUE}https://github.com/ldroeger/callbox${NC}"
echo ""

# ─── Root check ───────────────────────────────────────────────────────────────

if [ "$EUID" -ne 0 ]; then
  error "Bitte als root ausführen:\n  curl -fsSL ${REPO}/raw/main/install.sh | sudo bash"
fi

# ─── OS check ─────────────────────────────────────────────────────────────────

if [ ! -f /etc/os-release ]; then
  error "Unbekanntes Betriebssystem"
fi
. /etc/os-release
info "System: ${PRETTY_NAME}"

# ─── Step 1: System-Pakete ────────────────────────────────────────────────────

section "Schritt 1/6: System vorbereiten"

apt-get update -qq
apt-get install -y -qq \
  git curl wget unzip \
  docker.io docker-compose \
  mpg123 alsa-utils \
  avahi-daemon avahi-utils \
  2>/dev/null

systemctl enable avahi-daemon --quiet 2>/dev/null || true
systemctl start avahi-daemon 2>/dev/null || true

systemctl enable docker --quiet
systemctl start docker

if id "$SERVICE_USER" &>/dev/null; then
  usermod -aG docker "$SERVICE_USER" 2>/dev/null || true
fi

log "System-Pakete installiert"

# ─── Step 2: Repository klonen ────────────────────────────────────────────────

section "Schritt 2/6: Repository herunterladen"

if [ -d "$INSTALL_DIR" ]; then
  warn "Vorhandene Installation gefunden. Wird aktualisiert..."
  cd "$INSTALL_DIR"
  # Preserve config if exists
  if [ -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env" /tmp/callbox_env_backup
  fi
  git pull --quiet
  log "Repository aktualisiert"
else
  git clone --quiet "$REPO" "$INSTALL_DIR"
  log "Repository geklont nach $INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Restore config backup
if [ -f /tmp/callbox_env_backup ]; then
  cp /tmp/callbox_env_backup "$INSTALL_DIR/.env"
  rm /tmp/callbox_env_backup
  log "Bestehende Konfiguration wiederhergestellt"
fi

mkdir -p "$INSTALL_DIR/audio" "$INSTALL_DIR/data"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR" 2>/dev/null || true

# ─── Step 3: Setup Wizard ─────────────────────────────────────────────────────

section "Schritt 3/6: Setup-Assistent"

# Check if already configured
if [ -f "$INSTALL_DIR/.env" ]; then
  echo -e "${YELLOW}Eine bestehende Konfiguration wurde gefunden.${NC}"
  read -p "  Neu konfigurieren? [j/N]: " RECONFIG
  if [[ ! "$RECONFIG" =~ ^[jJ]$ ]]; then
    info "Bestehende Konfiguration wird verwendet."

    # Migrate older .env files that don't quote their values yet (older
    # installs could break on values containing spaces or a leading '#'
    # after a space, e.g. AUDIO_LABEL=DAC Pro HAT being parsed as a
    # command). Quote any KEY=value line that isn't already quoted.
    if grep -qE '^[A-Z_]+=[^"]' "$INSTALL_DIR/.env"; then
      info "Aktualisiere .env-Format (Werte werden in Anführungszeichen gesetzt)..."
      TMP_ENV=$(mktemp)
      while IFS= read -r line; do
        if [[ "$line" =~ ^([A-Z_]+)=(.*)$ ]]; then
          key="${BASH_REMATCH[1]}"
          val="${BASH_REMATCH[2]}"
          if [[ "$val" == \"*\" ]]; then
            echo "${key}=${val}"
          else
            echo "${key}=\"${val}\""
          fi
        else
          echo "$line"
        fi
      done < "$INSTALL_DIR/.env" > "$TMP_ENV"
      mv "$TMP_ENV" "$INSTALL_DIR/.env"
      chmod 600 "$INSTALL_DIR/.env"
      log ".env-Format aktualisiert"
    fi

    source "$INSTALL_DIR/.env"
    SKIP_WIZARD=true
  fi
fi

if [ "${SKIP_WIZARD:-false}" != "true" ]; then
  bash "$INSTALL_DIR/scripts/setup_wizard.sh"
  source "$INSTALL_DIR/.env"
fi

# ─── Step 4: Docker Compose generieren ───────────────────────────────────────

section "Schritt 4/6: Konfiguration anwenden"

# Resolve symlinks (e.g. /dev/serial0 -> /dev/ttyAMA0) since Docker's
# `devices:` mapping works more reliably against the real device node.
RESOLVED_MODEM_PORT="${MODEM_PORT:-/dev/ttyUSB2}"
if [ -L "$RESOLVED_MODEM_PORT" ]; then
  REAL_PORT=$(readlink -f "$RESOLVED_MODEM_PORT")
  info "Löse Symlink auf: ${RESOLVED_MODEM_PORT} → ${REAL_PORT}"
  RESOLVED_MODEM_PORT="$REAL_PORT"
fi

# Inject env vars into docker-compose
cat > "$INSTALL_DIR/docker-compose.yml" << COMPOSE
version: "3.8"

services:

  backend:
    build: ./backend
    container_name: callbox-backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./audio:/app/audio
      - /run/dbus/system_bus_socket:/run/dbus/system_bus_socket
    devices:
      - "${RESOLVED_MODEM_PORT}:${RESOLVED_MODEM_PORT}"
    restart: always
    environment:
      - MODEM_PORT=${RESOLVED_MODEM_PORT}
      - AUDIO_PATH=/app/audio
      - DB_PATH=/app/data/callbox.db
      - SECRET_KEY=${SECRET_KEY}
      - ADMIN_USER=${ADMIN_USER}
      - ADMIN_PASS=${ADMIN_PASS}
      - HOTSPOT_SSID=${HOTSPOT_SSID:-}
      - HOTSPOT_IP=${HOTSPOT_IP:-192.168.4.1}

  call-engine:
    build: ./engine
    container_name: callbox-engine
    devices:
      - "${RESOLVED_MODEM_PORT}:${RESOLVED_MODEM_PORT}"
    volumes:
      - ./audio:/audio
      - ./data:/data
    cap_add:
      - SYS_TIME
    restart: always
    environment:
      - MODEM_PORT=${RESOLVED_MODEM_PORT}
      - AUDIO_PATH=/audio
      - DB_PATH=/data/callbox.db
      - REJECT_UNKNOWN=${REJECT_UNKNOWN:-true}
      - NUMBER_FORMAT=${NUMBER_FORMAT:-international}
      - AUDIO_CHANNELS=${AUDIO_CHANNELS:-stereo}
      - STATUS_INTERVAL_SECONDS=${STATUS_INTERVAL_SECONDS:-15}

  frontend:
    build:
      context: ./frontend
      args:
        - REACT_APP_API_URL=http://${HOST_IP:-localhost}:8000/api
    container_name: callbox-frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    restart: always
COMPOSE

log "docker-compose.yml generiert"

# ─── Step 5: Docker Build & Start ─────────────────────────────────────────────

section "Schritt 5/6: Container bauen & starten"
info "Das dauert beim ersten Mal 5–10 Minuten..."

cd "$INSTALL_DIR"
docker compose down --remove-orphans 2>/dev/null || true
docker compose build --no-cache 2>&1 | grep -E "(Step|Successfully|ERROR)" || true
docker compose up -d

log "Container gestartet"

# ─── Step 6: Systemd Autostart ────────────────────────────────────────────────

section "Schritt 6/6: Autostart einrichten"

cat > /etc/systemd/system/callbox.service << SERVICE
[Unit]
Description=Callbox GSM Audio System
Requires=docker.service
After=docker.service network-online.target

[Service]
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down
Restart=on-failure
RestartSec=10
TimeoutStartSec=120
StandardOutput=journal
User=root

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable callbox.service --quiet

log "Autostart aktiv (startet nach jedem Neustart)"

# ─── Done ─────────────────────────────────────────────────────────────────────

IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║        INSTALLATION ERFOLGREICH ABGESCHLOSSEN ✓      ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                      ║"
echo -e "║  🌐 Web-Oberfläche:  ${CYAN}http://${IP}:3000${GREEN}${BOLD}           ║"
echo "║                                                      ║"
echo -e "║  👤 Benutzer:        ${CYAN}${ADMIN_USER}${GREEN}${BOLD}"
printf  "║  🔑 Passwort:        %-37s║\n" "${ADMIN_PASS}"
echo "║                                                      ║"
echo -e "║  📡 Modem-Port:      ${CYAN}${MODEM_PORT}${GREEN}${BOLD}"
echo "║                                                      ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Befehle:                                            ║"
echo "║    Logs:     docker compose -C /opt/callbox logs -f  ║"
echo "║    Neustart: sudo systemctl restart callbox          ║"
echo "║    Update:   sudo bash /opt/callbox/scripts/update.sh║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"
