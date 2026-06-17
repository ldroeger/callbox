#!/bin/bash
# Callbox Reconfigure – Setup-Wizard erneut ausführen

INSTALL_DIR="/opt/callbox"

if [ "$EUID" -ne 0 ]; then
  echo "Bitte als root ausführen: sudo bash /opt/callbox/scripts/reconfigure.sh"
  exit 1
fi

export INSTALL_DIR

bash "${INSTALL_DIR}/scripts/setup_wizard.sh"
source "${INSTALL_DIR}/.env"

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
    devices:
      - "${MODEM_PORT:-/dev/ttyUSB2}:${MODEM_PORT:-/dev/ttyUSB2}"
    restart: always
    environment:
      - MODEM_PORT=${MODEM_PORT:-/dev/ttyUSB2}
      - AUDIO_PATH=/app/audio
      - DB_PATH=/app/data/callbox.db
      - SECRET_KEY=${SECRET_KEY}
      - ADMIN_USER=${ADMIN_USER}
      - ADMIN_PASS=${ADMIN_PASS}

  call-engine:
    build: ./engine
    container_name: callbox-engine
    devices:
      - "${MODEM_PORT:-/dev/ttyUSB2}:${MODEM_PORT:-/dev/ttyUSB2}"
    volumes:
      - ./audio:/audio
      - ./data:/data
    restart: always
    environment:
      - MODEM_PORT=${MODEM_PORT:-/dev/ttyUSB2}
      - AUDIO_PATH=/audio
      - DB_PATH=/data/callbox.db
      - REJECT_UNKNOWN=${REJECT_UNKNOWN:-true}
      - NUMBER_FORMAT=${NUMBER_FORMAT:-international}

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
