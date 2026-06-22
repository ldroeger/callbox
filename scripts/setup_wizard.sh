#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║              CALLBOX – Setup Wizard                          ║
# ╚══════════════════════════════════════════════════════════════╝

INSTALL_DIR="${INSTALL_DIR:-/opt/callbox}"

# ─── TTY guard ────────────────────────────────────────────────────────────────
if [ ! -t 0 ] && [ -e /dev/tty ]; then
  exec < /dev/tty
fi
if [ ! -t 0 ]; then
  echo "FEHLER: Kein interaktives Terminal verfügbar."
  exit 1
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

log()    { echo -e "  ${GREEN}✓${NC} $1"; }
info()   { echo -e "  ${BLUE}ℹ${NC} $1"; }
warn()   { echo -e "  ${YELLOW}⚠${NC} $1"; }
prompt() { echo -e "\n  ${BOLD}${CYAN}$1${NC}"; }
step()   { echo -e "\n${BOLD}${MAGENTA}  [$1] $2${NC}"; echo -e "  ${DIM}$(printf '─%.0s' {1..50})${NC}"; }

# ─── Banner ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${CYAN}  ┌─────────────────────────────────────────┐${NC}"
echo -e "${BOLD}${CYAN}  │         Callbox Setup-Assistent         │${NC}"
echo -e "${BOLD}${CYAN}  └─────────────────────────────────────────┘${NC}"
echo ""
echo -e "  Dieser Assistent richtet dein Callbox-System ein."
echo -e "  Du kannst alle Eingaben jederzeit mit ${YELLOW}Strg+C${NC} abbrechen."
echo ""
read -p "  Weiter mit Enter..." _

# ─── Step 1: Netzwerk ────────────────────────────────────────────────────────

step "1/6" "Netzwerk-Konfiguration"

AUTO_IP=$(hostname -I | awk '{print $1}')
HOSTNAME_SHORT=$(hostname -s)
HOST_IP="${AUTO_IP}"

info "Erkannte IP-Adresse: ${CYAN}${AUTO_IP}${NC}"
info "Hostname:            ${CYAN}${HOSTNAME_SHORT}${NC}"
echo ""
echo -e "  ${DIM}Das Web-Interface ist erreichbar über:${NC}"
echo -e "  ${CYAN}→ http://${AUTO_IP}:3000${NC}       (aktuelle IP)"
echo -e "  ${CYAN}→ http://${HOSTNAME_SHORT}.local:3000${NC} (mDNS – auch bei IP-Wechsel)"
echo ""
echo -e "  ${DIM}Das Frontend erkennt die IP automatisch aus der Browser-Adresse –${NC}"
echo -e "  ${DIM}keine manuelle Eingabe nötig.${NC}"
echo ""
read -p "  Weiter mit Enter..." _
log "Netzwerk erkannt: $HOST_IP"

# ─── Step 2: Modem ───────────────────────────────────────────────────────────

step "2/6" "SIM7600 Modem-Erkennung"

echo ""
echo -e "  ${BOLD}Wie ist das SIM7600 angebunden?${NC}"
echo ""
echo -e "  ${CYAN}[1]${NC} USB (UART-Jumper auf 'A', Micro-USB-Kabel zum Pi)"
echo -e "  ${CYAN}[2]${NC} GPIO-UART (UART-Jumper auf 'B', kein Kabel)"
echo ""
read -p "  Auswahl [1]: " CONN_TYPE
CONN_TYPE="${CONN_TYPE:-1}"
echo ""

if [ "$CONN_TYPE" = "2" ]; then
  info "GPIO-UART Modus gewählt."
  echo ""
  if [ -e /dev/serial0 ]; then
    log "GPIO-UART gefunden: /dev/serial0 → $(readlink -f /dev/serial0 2>/dev/null)"
    DETECTED_PORT="/dev/serial0"
  else
    warn "/dev/serial0 nicht gefunden."
    echo -e "  ${DIM}Prüfe: enable_uart=1 und dtoverlay=disable-bt in /boot/firmware/config.txt${NC}"
    DETECTED_PORT="/dev/serial0"
  fi
  echo ""
  prompt "Modem-Port:"
  read -p "  Port [${DETECTED_PORT}]: " INPUT_PORT
  MODEM_PORT="${INPUT_PORT:-$DETECTED_PORT}"
  CONNECTION_MODE="gpio"
  echo ""
  warn "Bluetooth muss deaktiviert sein: sudo systemctl disable hciuart"
else
  info "Suche nach USB-Modems..."
  echo ""
  DETECTED_PORT=""
  for port in /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyUSB2 /dev/ttyUSB3 /dev/ttyUSB4; do
    if [ -e "$port" ]; then
      echo -e "  ${GREEN}●${NC} Gefunden: ${CYAN}$port${NC}"
      DETECTED_PORT="$port"
    else
      echo -e "  ${DIM}○ $port${NC}"
    fi
  done
  echo ""
  if [ -n "$DETECTED_PORT" ]; then
    log "Modem erkannt: $DETECTED_PORT"
    prompt "Modem-Port:"
    read -p "  Port [${DETECTED_PORT}]: " INPUT_PORT
    MODEM_PORT="${INPUT_PORT:-$DETECTED_PORT}"
  else
    warn "Kein Modem gefunden."
    prompt "Modem-Port manuell:"
    read -p "  Port [/dev/ttyUSB2]: " INPUT_PORT
    MODEM_PORT="${INPUT_PORT:-/dev/ttyUSB2}"
  fi
  CONNECTION_MODE="usb"
fi

log "Modem-Port: $MODEM_PORT (Modus: $CONNECTION_MODE)"

# ─── Step 3: Audio ───────────────────────────────────────────────────────────

step "3/6" "Audio-Konfiguration"

echo ""
info "Verfügbare Audio-Geräte:"
echo ""
if command -v aplay &>/dev/null; then
  aplay -l 2>/dev/null | grep -E "^card" | while IFS= read -r line; do
    echo -e "  ${CYAN}→${NC} $line"
  done || echo -e "  ${DIM}(keine erkannt)${NC}"
else
  echo -e "  ${DIM}(aplay nicht verfügbar)${NC}"
fi

echo ""
echo -e "  ${BOLD}Audio-Ausgabe:${NC}"
echo ""
echo -e "  ${CYAN}[1]${NC} USB-Soundkarte (empfohlen)"
echo -e "  ${CYAN}[2]${NC} Raspberry Pi DAC Pro HAT (IQaudio, I²S)"
echo -e "  ${CYAN}[3]${NC} Raspberry Pi 3.5mm Klinke (onboard)"
echo -e "  ${CYAN}[4]${NC} HDMI Audio"
echo ""
read -p "  Auswahl [1]: " AUDIO_CHOICE

case "${AUDIO_CHOICE:-1}" in
  2) AUDIO_DEVICE="hw:0,0"; AUDIO_LABEL="DAC Pro HAT" ;;
  3) AUDIO_DEVICE="hw:0,0"; AUDIO_LABEL="Pi Onboard 3.5mm" ;;
  4) AUDIO_DEVICE="hw:1,0"; AUDIO_LABEL="HDMI" ;;
  *) AUDIO_DEVICE="default"; AUDIO_LABEL="USB-Soundkarte" ;;
esac

log "Audio-Gerät: $AUDIO_LABEL"

echo ""
echo -e "  ${BOLD}Audio-Kanal:${NC}"
echo ""
echo -e "  ${CYAN}[1]${NC} Stereo (Standard)"
echo -e "  ${CYAN}[2]${NC} Mono  (spart Energie, reicht für Sprachansagen)"
echo ""
read -p "  Auswahl [1]: " AUDIO_CHANNEL_CHOICE
case "${AUDIO_CHANNEL_CHOICE:-1}" in
  2) AUDIO_CHANNELS="mono";   AUDIO_CHANNELS_LABEL="Mono" ;;
  *) AUDIO_CHANNELS="stereo"; AUDIO_CHANNELS_LABEL="Stereo" ;;
esac
log "Audio-Kanal: $AUDIO_CHANNELS_LABEL"

# ─── Step 4: Admin-Konto ─────────────────────────────────────────────────────

step "4/6" "Administrator-Konto"

echo ""
echo -e "  ${DIM}Dieses Konto schützt das Web-Interface.${NC}"
echo ""
prompt "Benutzername:"
read -p "  Name [admin]: " INPUT_USER
ADMIN_USER="${INPUT_USER:-admin}"

echo ""
prompt "Passwort:"
echo -e "  ${DIM}(Mindestens 8 Zeichen empfohlen – kein \" oder \\)${NC}"
while true; do
  read -s -p "  Passwort: " ADMIN_PASS
  echo ""
  if [ ${#ADMIN_PASS} -lt 4 ]; then
    warn "Passwort zu kurz (mind. 4 Zeichen)"; continue
  fi
  if [[ "$ADMIN_PASS" == *'"'* ]] || [[ "$ADMIN_PASS" == *'\'* ]]; then
    warn 'Bitte kein " oder \ verwenden'; continue
  fi
  read -s -p "  Passwort wiederholen: " ADMIN_PASS2
  echo ""
  if [ "$ADMIN_PASS" = "$ADMIN_PASS2" ]; then break
  else warn "Passwörter stimmen nicht überein. Nochmal:"; fi
done
log "Administrator-Konto: $ADMIN_USER"

# ─── Step 5: WLAN Hotspot ────────────────────────────────────────────────────

step "5/6" "WLAN Fallback-Hotspot"

echo ""
echo -e "  ${DIM}Der Pi startet automatisch einen WLAN-Hotspot wenn kein Netz"
echo -e "  verfügbar ist. So ist das Web-Interface immer erreichbar.${NC}"
echo ""
read -p "  Hotspot einrichten? [J/n]: " OPT_HOTSPOT

HOTSPOT_ENABLED="false"
HOTSPOT_SSID="Callbox"
HOTSPOT_PASS="callbox123"
HOTSPOT_IP="192.168.4.1"
HOTSPOT_CHANNEL="6"

if [[ ! "${OPT_HOTSPOT:-J}" =~ ^[nN]$ ]]; then

  # Check if NetworkManager and wifi are available
  if ! command -v nmcli &>/dev/null; then
    warn "NetworkManager nicht gefunden – Hotspot wird übersprungen."
    warn "Nachträglich einrichten: sudo bash /opt/callbox/scripts/setup_hotspot.sh"
  else
    WIFI_IF=$(nmcli -t -f DEVICE,TYPE device 2>/dev/null | grep ":wifi$" | cut -d: -f1 | head -1)
    if [ -z "$WIFI_IF" ]; then
      warn "Kein WLAN-Interface gefunden – Hotspot wird übersprungen."
      warn "Nachträglich einrichten: sudo bash /opt/callbox/scripts/setup_hotspot.sh"
    else
      log "WLAN-Interface: $WIFI_IF"
      echo ""

      prompt "Hotspot WLAN-Name (SSID):"
      read -p "  Name [Callbox]: " INPUT_SSID
      HOTSPOT_SSID="${INPUT_SSID:-Callbox}"

      echo ""
      prompt "Hotspot Passwort:"
      echo -e "  ${DIM}(mind. 8 Zeichen, WPA2-Verschlüsselung)${NC}"
      while true; do
        read -s -p "  Passwort [callbox123]: " INPUT_HPASS
        echo ""
        HOTSPOT_PASS="${INPUT_HPASS:-callbox123}"
        if [ ${#HOTSPOT_PASS} -ge 8 ]; then break
        else warn "Passwort muss mind. 8 Zeichen haben"; fi
      done

      echo ""
      prompt "Hotspot IP-Adresse:"
      echo -e "  ${DIM}(Geräte bekommen automatisch IPs im gleichen Netz per DHCP)${NC}"
      read -p "  IP [192.168.4.1]: " INPUT_HIP
      HOTSPOT_IP="${INPUT_HIP:-192.168.4.1}"

      echo ""
      prompt "WLAN-Kanal:"
      echo -e "  ${DIM}(1-13 für 2.4 GHz; Kanal 6 ist am wenigsten überfüllt)${NC}"
      read -p "  Kanal [6]: " INPUT_HCH
      HOTSPOT_CHANNEL="${INPUT_HCH:-6}"

      # Create the NM hotspot profile
      nmcli connection delete "Callbox-Hotspot" 2>/dev/null || true
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
        connection.autoconnect-priority -100 2>/dev/null \
        && log "Hotspot-Verbindung erstellt: ${HOTSPOT_SSID}" \
        || warn "Hotspot konnte nicht erstellt werden – nachträglich einrichten möglich"

      # Install dispatcher for automatic fallback
      mkdir -p /etc/NetworkManager/dispatcher.d/
      cat > /etc/NetworkManager/dispatcher.d/99-callbox-hotspot << 'DISPATCHER'
#!/bin/bash
HOTSPOT_CON="Callbox-Hotspot"
INTERFACE="$1"
EVENT="$2"
HS_IF=$(nmcli -g GENERAL.DEVICES connection show "$HOTSPOT_CON" 2>/dev/null)
[ "$INTERFACE" = "$HS_IF" ] && exit 0
case "$EVENT" in
  up)
    nmcli connection show --active | grep -q "$HOTSPOT_CON" && \
      nmcli connection down "$HOTSPOT_CON" 2>/dev/null && \
      logger "[Callbox] Netz aktiv – Hotspot gestoppt"
    ;;
  down|connectivity-change)
    sleep 5
    ACTIVE=$(nmcli -t -f NAME connection show --active | grep -v "$HOTSPOT_CON" | wc -l)
    [ "$ACTIVE" -eq 0 ] && nmcli connection up "$HOTSPOT_CON" 2>/dev/null && \
      logger "[Callbox] Kein Netz – Hotspot gestartet"
    ;;
esac
DISPATCHER
      chmod +x /etc/NetworkManager/dispatcher.d/99-callbox-hotspot
      systemctl reload NetworkManager 2>/dev/null || true
      log "Automatischer Fallback eingerichtet"

      HOTSPOT_ENABLED="true"

      echo ""
      echo -e "  ${DIM}Hotspot startet automatisch wenn kein Netz vorhanden ist.${NC}"
      echo -e "  ${DIM}Manuell: nmcli connection up Callbox-Hotspot${NC}"
    fi
  fi
else
  info "Hotspot übersprungen. Nachträglich: sudo bash /opt/callbox/scripts/setup_hotspot.sh"
fi

# ─── Step 6: Erweiterte Optionen ─────────────────────────────────────────────

step "6/6" "Erweiterte Optionen"

echo ""
echo -e "  ${BOLD}Optionale Einstellungen:${NC}"
echo ""

echo -e "  ${CYAN}[1]${NC} Unbekannte Anrufer sofort ablehnen"
read -p "      Aktivieren? [J/n]: " OPT_REJECT
REJECT_UNKNOWN=$([[ "${OPT_REJECT:-J}" =~ ^[nN]$ ]] && echo "false" || echo "true")
[ "$REJECT_UNKNOWN" = "true" ] && log "Unbekannte Anrufer werden abgelehnt" || info "Unbekannte Anrufer werden ignoriert"

echo ""
echo -e "  ${CYAN}[2]${NC} Anruf-Protokoll Aufbewahrung"
read -p "      Wie viele Tage? [30]: " LOG_DAYS
LOG_RETENTION="${LOG_DAYS:-30}"
log "Log-Aufbewahrung: ${LOG_RETENTION} Tage"

echo ""
echo -e "  ${CYAN}[3]${NC} Rufnummern-Format"
echo -e "      ${DIM}Manche SIM-Karten senden +49..., andere 0...${NC}"
echo -e "      ${CYAN}[a]${NC} International (+491701234567)"
echo -e "      ${CYAN}[b]${NC} National (01701234567)"
read -p "      Format [a]: " NUMBER_FORMAT
NUMBER_FMT=$([[ "${NUMBER_FORMAT:-a}" = "b" ]] && echo "national" || echo "international")
log "Rufnummernformat: $NUMBER_FMT"

# ─── Zusammenfassung ─────────────────────────────────────────────────────────

echo ""
echo ""
echo -e "${BOLD}${CYAN}  ┌─────────────────────────────────────────┐${NC}"
echo -e "${BOLD}${CYAN}  │         Zusammenfassung                 │${NC}"
echo -e "${BOLD}${CYAN}  └─────────────────────────────────────────┘${NC}"
echo ""
echo -e "  ${DIM}IP-Adresse:${NC}          ${CYAN}${HOST_IP}${NC}"
echo -e "  ${DIM}mDNS-Adresse:${NC}        ${CYAN}http://$(hostname -s).local:3000${NC}"
echo -e "  ${DIM}Verbindungsart:${NC}      ${CYAN}${CONNECTION_MODE}${NC}"
echo -e "  ${DIM}Modem-Port:${NC}          ${CYAN}${MODEM_PORT}${NC}"
echo -e "  ${DIM}Audio-Gerät:${NC}         ${CYAN}${AUDIO_LABEL}${NC}"
echo -e "  ${DIM}Audio-Kanal:${NC}         ${CYAN}${AUDIO_CHANNELS_LABEL}${NC}"
echo -e "  ${DIM}Admin-User:${NC}          ${CYAN}${ADMIN_USER}${NC}"
echo -e "  ${DIM}Hotspot:${NC}             ${CYAN}$([ "$HOTSPOT_ENABLED" = "true" ] && echo "${HOTSPOT_SSID} (${HOTSPOT_IP})" || echo "nicht eingerichtet")${NC}"
echo -e "  ${DIM}Unbekannte ablehnen:${NC} ${CYAN}${REJECT_UNKNOWN}${NC}"
echo -e "  ${DIM}Log-Aufbewahrung:${NC}    ${CYAN}${LOG_RETENTION} Tage${NC}"
echo -e "  ${DIM}Rufnummernformat:${NC}    ${CYAN}${NUMBER_FMT}${NC}"
echo ""
read -p "  Konfiguration speichern und fortfahren? [J/n]: " CONFIRM
if [[ "${CONFIRM:-J}" =~ ^[nN]$ ]]; then
  echo ""
  warn "Setup abgebrochen."
  exit 1
fi

# ─── .env schreiben ───────────────────────────────────────────────────────────

SECRET_KEY=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)

cat > "${INSTALL_DIR}/.env" << ENV
# Callbox Konfiguration
# Erstellt am: $(date)
# Bearbeite diese Datei und führe 'sudo systemctl restart callbox' aus.

HOST_IP="${HOST_IP}"
CONNECTION_MODE="${CONNECTION_MODE}"
MODEM_PORT="${MODEM_PORT}"
AUDIO_DEVICE="${AUDIO_DEVICE}"
AUDIO_LABEL="${AUDIO_LABEL}"
AUDIO_CHANNELS="${AUDIO_CHANNELS}"

ADMIN_USER="${ADMIN_USER}"
ADMIN_PASS="${ADMIN_PASS}"
SECRET_KEY="${SECRET_KEY}"

REJECT_UNKNOWN="${REJECT_UNKNOWN}"
LOG_RETENTION_DAYS="${LOG_RETENTION}"
NUMBER_FORMAT="${NUMBER_FMT}"

HOTSPOT_ENABLED="${HOTSPOT_ENABLED}"
HOTSPOT_SSID="${HOTSPOT_SSID}"
HOTSPOT_PASS="${HOTSPOT_PASS}"
HOTSPOT_IP="${HOTSPOT_IP}"
HOTSPOT_CHANNEL="${HOTSPOT_CHANNEL}"
ENV

chmod 600 "${INSTALL_DIR}/.env"

echo ""
log "Konfiguration gespeichert in ${INSTALL_DIR}/.env"
echo ""
