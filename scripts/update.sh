#!/bin/bash
# Callbox Update Script

INSTALL_DIR="/opt/callbox"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${CYAN}[i]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

echo ""
echo -e "${BOLD}${CYAN}  Callbox Update${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Bitte als root ausführen: sudo bash /opt/callbox/scripts/update.sh${NC}"
  exit 1
fi

cd "$INSTALL_DIR"

# Backup config
if [ -f .env ]; then
  cp .env /tmp/callbox_env_backup
  log "Konfiguration gesichert"
fi

# Pull latest
info "Lade aktuelle Version..."
git pull --quiet

# Restore config
if [ -f /tmp/callbox_env_backup ]; then
  cp /tmp/callbox_env_backup .env
  rm /tmp/callbox_env_backup
  log "Konfiguration wiederhergestellt"
fi

# Rebuild & restart
info "Baue neue Container..."
source .env 2>/dev/null || true
docker compose build --no-cache 2>&1 | grep -E "(Step|Successfully|ERROR)" || true

info "Starte Dienste neu..."
docker compose down
docker compose up -d

log "Update abgeschlossen!"
echo ""
IP=$(hostname -I | awk '{print $1}')
echo -e "  Web-Interface: ${CYAN}http://${IP}:3000${NC}"
echo ""
