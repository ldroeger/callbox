#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║         Callbox – WLAN Fallback-Hotspot Einrichtung          ║
# ║  Startet automatisch einen Hotspot, wenn kein LAN/WLAN       ║
# ║  verfügbar ist (Standalone-Betrieb ohne Internet).           ║
# ╚══════════════════════════════════════════════════════════════╝

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

log()    { echo -e "  ${GREEN}✓${NC} $1"; }
info()   { echo -e "  ${CYAN}ℹ${NC} $1"; }
warn()   { echo -e "  ${YELLOW}⚠${NC} $1"; }
error()  { echo -e "  ${RED}✗${NC} $1"; exit 1; }
section(){ echo -e "\n${BOLD}${CYAN}  ━━━ $1 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

# ─── Root check ───────────────────────────────────────────────────────────────

if [ "$EUID" -ne 0 ]; then
  echo "Bitte als root ausführen: sudo bash /opt/callbox/scripts/setup_hotspot.sh"
  exit 1
fi

# ─── TTY guard (for curl | bash use) ─────────────────────────────────────────

if [ ! -t 0 ] && [ -e /dev/tty ]; then
  exec < /dev/tty
fi

# ─── Banner ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${CYAN}  ┌─────────────────────────────────────────┐${NC}"
echo -e "${BOLD}${CYAN}  │     Callbox WLAN Fallback-Hotspot       │${NC}"
echo -e "${BOLD}${CYAN}  └─────────────────────────────────────────┘${NC}"
echo ""
echo -e "  Richtet einen WLAN-Hotspot ein, der automatisch startet,"
echo -e "  wenn kein LAN oder WLAN verfügbar ist."
echo ""

# ─── Check prerequisites ──────────────────────────────────────────────────────

section "Systemprüfung"

# NetworkManager
if ! command -v nmcli &>/dev/null; then
  error "NetworkManager nicht gefunden. Installieren: sudo apt install network-manager"
fi
log "NetworkManager gefunden: $(nmcli -v 2>/dev/null | head -1)"

# WLAN-Interface
WIFI_IF=$(nmcli -t -f DEVICE,TYPE device | grep ":wifi$" | cut -d: -f1 | head -1)
if [ -z "$WIFI_IF" ]; then
  error "Kein WLAN-Interface (wlan0) gefunden. Ist das WLAN-Modul aktiv?"
fi
log "WLAN-Interface: ${WIFI_IF}"

# Check if rfkill blocking wifi
if command -v rfkill &>/dev/null; then
  if rfkill list wifi 2>/dev/null | grep -q "Soft blocked: yes"; then
    warn "WLAN ist per rfkill gesperrt. Entsperre mit: rfkill unblock wifi"
    rfkill unblock wifi
    log "WLAN entsperrt"
  fi
fi

# ─── Hotspot Konfiguration abfragen ───────────────────────────────────────────

section "Hotspot-Konfiguration"

echo ""
echo -e "  ${DIM}Du kannst alle Werte mit Enter bestätigen (Standard wird übernommen)${NC}"
echo ""

# SSID
echo -e "  ${CYAN}WLAN-Name (SSID):${NC}"
read -p "  Name [Callbox]: " INPUT_SSID
HOTSPOT_SSID="${INPUT_SSID:-Callbox}"

# Passwort
echo ""
echo -e "  ${CYAN}WLAN-Passwort:${NC}"
echo -e "  ${DIM}(mind. 8 Zeichen, leer lassen für offenes Netz ohne Passwort)${NC}"
while true; do
  read -s -p "  Passwort [callbox123]: " INPUT_PASS
  echo ""
  HOTSPOT_PASS="${INPUT_PASS:-callbox123}"
  if [ ${#HOTSPOT_PASS} -ge 8 ] || [ -z "$INPUT_PASS" -a ${#HOTSPOT_PASS} -ge 8 ]; then
    break
  fi
  warn "Passwort muss mind. 8 Zeichen haben"
done

# IP-Adresse
echo ""
echo -e "  ${CYAN}IP-Adresse des Hotspots:${NC}"
echo -e "  ${DIM}(Unter dieser Adresse wird das Web-Interface erreichbar sein)${NC}"
read -p "  IP [192.168.4.1]: " INPUT_IP
HOTSPOT_IP="${INPUT_IP:-192.168.4.1}"

# WLAN-Kanal
echo ""
echo -e "  ${CYAN}WLAN-Kanal:${NC}"
echo -e "  ${DIM}(1-13 für 2.4 GHz; 6 und 11 sind am wenigsten überfüllt)${NC}"
read -p "  Kanal [6]: " INPUT_CH
HOTSPOT_CHANNEL="${INPUT_CH:-6}"

echo ""
echo -e "${BOLD}  Zusammenfassung:${NC}"
echo -e "  ${DIM}SSID:${NC}        ${CYAN}${HOTSPOT_SSID}${NC}"
echo -e "  ${DIM}Passwort:${NC}    ${CYAN}${HOTSPOT_PASS}${NC}"
echo -e "  ${DIM}IP-Adresse:${NC}  ${CYAN}${HOTSPOT_IP}${NC}"
echo -e "  ${DIM}Kanal:${NC}       ${CYAN}${HOTSPOT_CHANNEL}${NC}"
echo -e "  ${DIM}Interface:${NC}   ${CYAN}${WIFI_IF}${NC}"
echo ""
read -p "  Hotspot einrichten? [J/n]: " CONFIRM
if [[ "${CONFIRM:-J}" =~ ^[nN]$ ]]; then
  echo "Abgebrochen."
  exit 0
fi

# ─── Hotspot einrichten ───────────────────────────────────────────────────────

section "Hotspot einrichten"

# Lösche alte Callbox-Hotspot-Verbindung falls vorhanden
nmcli connection delete "Callbox-Hotspot" 2>/dev/null && \
  info "Alte Hotspot-Konfiguration entfernt" || true

# Erstelle neue Hotspot-Verbindung
# mode=ap    = Access Point (Hotspot)
# autoconnect-priority=-100  = niedrigste Prio; bevorzugt immer echte Netze
# autoconnect=yes            = automatisch verbinden, wenn kein anderes Netz da

nmcli connection add \
  type wifi \
  ifname "${WIFI_IF}" \
  con-name "Callbox-Hotspot" \
  autoconnect yes \
  ssid "${HOTSPOT_SSID}" \
  -- \
  wifi.mode ap \
  wifi.band bg \
  wifi.channel "${HOTSPOT_CHANNEL}" \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "${HOTSPOT_PASS}" \
  ipv4.method shared \
  ipv4.addresses "${HOTSPOT_IP}/24" \
  connection.autoconnect-priority -100

log "Hotspot-Verbindung erstellt"

# ─── Dispatcher-Script für automatischen Fallback ─────────────────────────────

section "Automatischer Fallback einrichten"

# NetworkManager Dispatcher: Wenn keine andere Verbindung aktiv ist,
# Hotspot starten. Wenn eine echte Verbindung kommt, Hotspot stoppen.

mkdir -p /etc/NetworkManager/dispatcher.d/

cat > /etc/NetworkManager/dispatcher.d/99-callbox-hotspot << 'DISPATCHER_EOF'
#!/bin/bash
# Callbox Hotspot Dispatcher
# Startet den Hotspot wenn keine andere Verbindung aktiv ist.

HOTSPOT_CON="Callbox-Hotspot"
INTERFACE="$1"
EVENT="$2"

# Nur reagieren wenn es NICHT der Hotspot selbst ist
if [ "$INTERFACE" = "$(nmcli -g GENERAL.DEVICES connection show "$HOTSPOT_CON" 2>/dev/null)" ]; then
  exit 0
fi

case "$EVENT" in
  up)
    # Eine echte Verbindung ist hochgekommen → Hotspot stoppen
    if nmcli connection show --active | grep -q "$HOTSPOT_CON"; then
      logger "[Callbox] Netzwerkverbindung aktiv – Hotspot wird gestoppt"
      nmcli connection down "$HOTSPOT_CON" 2>/dev/null || true
    fi
    ;;

  down|connectivity-change)
    # Verbindung getrennt – prüfe ob noch andere Verbindungen aktiv sind
    sleep 5
    ACTIVE=$(nmcli -t -f NAME connection show --active | grep -v "$HOTSPOT_CON" | wc -l)
    if [ "$ACTIVE" -eq 0 ]; then
      logger "[Callbox] Keine Netzwerkverbindung – Hotspot wird gestartet"
      nmcli connection up "$HOTSPOT_CON" 2>/dev/null || true
    fi
    ;;
esac
DISPATCHER_EOF

chmod +x /etc/NetworkManager/dispatcher.d/99-callbox-hotspot
log "Dispatcher-Script erstellt"

# ─── NetworkManager neu laden ─────────────────────────────────────────────────

systemctl reload NetworkManager 2>/dev/null || systemctl restart NetworkManager
log "NetworkManager neu geladen"

# ─── Hotspot-Status in .env speichern ─────────────────────────────────────────

if [ -f /opt/callbox/.env ]; then
  # Remove existing hotspot vars if present, then append
  grep -v "^HOTSPOT_" /opt/callbox/.env > /tmp/callbox_env_tmp
  cat >> /tmp/callbox_env_tmp << ENVEOF

# Hotspot-Konfiguration (eingerichtet am $(date))
HOTSPOT_SSID="${HOTSPOT_SSID}"
HOTSPOT_PASS="${HOTSPOT_PASS}"
HOTSPOT_IP="${HOTSPOT_IP}"
HOTSPOT_ENABLED="true"
ENVEOF
  mv /tmp/callbox_env_tmp /opt/callbox/.env
  chmod 600 /opt/callbox/.env
  log "Hotspot-Konfiguration in .env gespeichert"
fi

# ─── Test: Hotspot direkt starten ─────────────────────────────────────────────

section "Hotspot testen"

echo ""
read -p "  Hotspot jetzt testweise starten? [J/n]: " TEST_NOW
if [[ ! "${TEST_NOW:-J}" =~ ^[nN]$ ]]; then
  nmcli connection up "Callbox-Hotspot" 2>/dev/null && \
    log "Hotspot gestartet" || \
    warn "Hotspot konnte nicht gestartet werden (vielleicht schon eine andere WLAN-Verbindung aktiv)"
fi

# ─── Fertig ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║        HOTSPOT ERFOLGREICH EINGERICHTET ✓            ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                      ║"
printf "║  📶 WLAN-Name:   %-37s║\n" "${HOTSPOT_SSID}"
printf "║  🔑 Passwort:    %-37s║\n" "${HOTSPOT_PASS}"
printf "║  🌐 IP-Adresse:  %-37s║\n" "${HOTSPOT_IP}"
echo "║                                                      ║"
echo "║  Web-Interface wenn Hotspot aktiv:                   ║"
printf "║  http://%-46s║\n" "${HOTSPOT_IP}:3000"
echo "║                                                      ║"
echo "║  Verhalten:                                          ║"
echo "║  • LAN/WLAN verfügbar  → normaler Betrieb            ║"
echo "║  • Kein Netz verfügbar → Hotspot startet auto.       ║"
echo "║                                                      ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Befehle:                                            ║"
echo "║  Hotspot manuell starten:                            ║"
echo "║    nmcli connection up Callbox-Hotspot               ║"
echo "║  Hotspot manuell stoppen:                            ║"
echo "║    nmcli connection down Callbox-Hotspot             ║"
echo "║  Hotspot entfernen:                                  ║"
echo "║    sudo bash /opt/callbox/scripts/remove_hotspot.sh  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"
