#!/bin/bash
# Callbox Reconfigure – Setup-Wizard erneut ausführen

INSTALL_DIR="/opt/callbox"

if [ ! -t 0 ] && [ -e /dev/tty ]; then
  exec < /dev/tty
fi

if [ "$EUID" -ne 0 ]; then
  echo "Bitte als root ausführen: sudo bash /opt/callbox/scripts/reconfigure.sh"
  exit 1
fi

export INSTALL_DIR

bash "${INSTALL_DIR}/scripts/setup_wizard.sh"
source "${INSTALL_DIR}/.env"

# Resolve symlinks (e.g. /dev/serial0 -> /dev/ttyAMA0) since Docker's
# `devices:` mapping works more reliably against the real device node.
RESOLVED_MODEM_PORT="${MODEM_PORT:-/dev/ttyUSB2}"
if [ -L "$RESOLVED_MODEM_PORT" ]; then
  RESOLVED_MODEM_PORT=$(readlink -f "$RESOLVED_MODEM_PORT")
fi

# Regenerate docker-compose with new values
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

echo ""
echo "Konfiguration angewendet. Starte Dienste neu..."
cd "$INSTALL_DIR"
docker compose down
docker compose up -d --build

echo ""
echo "✓ Neustart abgeschlossen."
