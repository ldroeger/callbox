#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║              CALLBOX – Setup Wizard                          ║
# ╚══════════════════════════════════════════════════════════════╝

INSTALL_DIR="${INSTALL_DIR:-/opt/callbox}"

# ─── TTY guard ────────────────────────────────────────────────────────────────
# When this script is run via `curl ... | sudo bash`, stdin is the pipe
# carrying the script itself, not the user's keyboard. Every `read` below
# would then get empty input instantly instead of waiting for a real answer.
# Re-attach stdin to the actual terminal device if one is available.
if [ ! -t 0 ] && [ -e /dev/tty ]; then
  exec < /dev/tty
fi

if [ ! -t 0 ]; then
  echo "FEHLER: Kein interaktives Terminal verfügbar (/dev/tty fehlt)."
  echo "Dieser Assistent benötigt eine echte Terminal-Sitzung (SSH/Konsole),"
  echo "z.B. läuft er nicht in manchen CI-/Automatisierungsumgebungen."
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

log()     { echo -e "  ${GREEN}✓${NC} $1"; }
info()    { echo -e "  ${BLUE}ℹ${NC} $1"; }
warn()    { echo -e "  ${YELLOW}⚠${NC} $1"; }
prompt()  { echo -e "\n  ${BOLD}${CYAN}$1${NC}"; }
step()    { echo -e "\n${BOLD}${MAGENTA}  [$1] $2${NC}"; echo -e "  ${DIM}$(printf '─%.0s' {1..50})${NC}"; }

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

# ─── Step 1: Netzwerk / IP ───────────────────────────────────────────────────

step "1/5" "Netzwerk-Konfiguration"

AUTO_IP=$(hostname -I | awk '{print $1}')
info "Erkannte IP-Adresse: ${CYAN}${AUTO_IP}${NC}"
echo ""
prompt "IP-Adresse des Raspberry Pi:"
echo -e "  ${DIM}(Unter dieser Adresse wird das Web-Interface erreichbar sein)${NC}"
read -p "  IP-Adresse [${AUTO_IP}]: " INPUT_IP
HOST_IP="${INPUT_IP:-$AUTO_IP}"
log "IP gesetzt: $HOST_IP"

# ─── Step 2: Modem erkennen ───────────────────────────────────────────────────

step "2/5" "SIM7600 Modem-Erkennung"

echo ""
echo -e "  ${BOLD}Wie ist das SIM7600 angebunden?${NC}"
echo ""
echo -e "  ${CYAN}[1]${NC} USB (UART-Jumper auf 'A', eigenes Micro-USB-Kabel zum Pi)"
echo -e "  ${CYAN}[2]${NC} GPIO-UART (UART-Jumper auf 'B', kein zusätzliches Kabel)"
echo ""
read -p "  Auswahl [1]: " CONN_TYPE
CONN_TYPE="${CONN_TYPE:-1}"

echo ""

if [ "$CONN_TYPE" = "2" ]; then
  # ─── GPIO-UART Modus ─────────────────────────────────────────────────────
  info "GPIO-UART Modus gewählt."
  echo ""

  if [ -e /dev/serial0 ]; then
    log "GPIO-UART gefunden: /dev/serial0 → $(readlink -f /dev/serial0 2>/dev/null)"
    DETECTED_PORT="/dev/serial0"
  else
    warn "/dev/serial0 nicht gefunden. UART muss aktiviert sein."
    echo -e "  ${DIM}Prüfe: enable_uart=1 und dtoverlay=disable-bt in /boot/firmware/config.txt${NC}"
    DETECTED_PORT="/dev/serial0"
  fi

  echo ""
  prompt "Modem-Port:"
  read -p "  Port [${DETECTED_PORT}]: " INPUT_PORT
  MODEM_PORT="${INPUT_PORT:-$DETECTED_PORT}"
  CONNECTION_MODE="gpio"

  echo ""
  warn "Wichtig: Bluetooth muss deaktiviert sein (UART wird sonst geteilt)."
  echo -e "  ${DIM}Falls noch nicht erledigt: sudo systemctl disable hciuart${NC}"

else
  # ─── USB Modus ───────────────────────────────────────────────────────────
  info "Suche nach angeschlossenen USB-Modems..."
  echo ""

  DETECTED_PORT=""
  for port in /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyUSB2 /dev/ttyUSB3 /dev/ttyUSB4; do
    if [ -e "$port" ]; then
      echo -e "  ${GREEN}●${NC} Gefunden: ${CYAN}$port${NC}"
      DETECTED_PORT="$port"
    else
      echo -e "  ${DIM}○ Nicht vorhanden: $port${NC}"
    fi
  done

  echo ""

  if [ -n "$DETECTED_PORT" ]; then
    log "Modem erkannt: $DETECTED_PORT"
    prompt "Modem-Port:"
    read -p "  Port [${DETECTED_PORT}]: " INPUT_PORT
    MODEM_PORT="${INPUT_PORT:-$DETECTED_PORT}"
  else
    warn "Kein Modem gefunden. Bitte SIM7600 einstecken (inkl. Micro-USB-Kabel zum Pi)."
    echo ""
    prompt "Modem-Port manuell eingeben:"
    read -p "  Port [/dev/ttyUSB2]: " INPUT_PORT
    MODEM_PORT="${INPUT_PORT:-/dev/ttyUSB2}"
  fi
  CONNECTION_MODE="usb"
fi

log "Modem-Port: $MODEM_PORT (Modus: $CONNECTION_MODE)"

# ─── Step 3: Audio-Gerät ──────────────────────────────────────────────────────

step "3/5" "Audio-Konfiguration"

echo ""
info "Verfügbare Audio-Geräte:"
echo ""

if command -v aplay &>/dev/null; then
  aplay -l 2>/dev/null | grep -E "^card" | while IFS= read -r line; do
    echo -e "  ${CYAN}→${NC} $line"
  done || echo -e "  ${DIM}(keine Geräte erkannt)${NC}"
else
  echo -e "  ${DIM}(aplay nicht verfügbar)${NC}"
fi

echo ""
echo -e "  ${BOLD}Audio-Ausgabe wählen:${NC}"
echo ""
echo -e "  ${CYAN}[1]${NC} USB-Soundkarte (empfohlen, einfachste Einrichtung)"
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

# ─── Step 4: Admin-Account ────────────────────────────────────────────────────

step "4/5" "Administrator-Konto"

echo ""
echo -e "  ${DIM}Dieses Konto schützt das Web-Interface.${NC}"
echo ""

prompt "Benutzername:"
read -p "  Name [admin]: " INPUT_USER
ADMIN_USER="${INPUT_USER:-admin}"

echo ""
prompt "Passwort:"
echo -e "  ${DIM}(Mindestens 8 Zeichen empfohlen)${NC}"

while true; do
  read -s -p "  Passwort: " ADMIN_PASS
  echo ""
  if [ ${#ADMIN_PASS} -lt 4 ]; then
    warn "Passwort zu kurz (mind. 4 Zeichen)"
    continue
  fi
  if [[ "$ADMIN_PASS" == *'"'* ]] || [[ "$ADMIN_PASS" == *'\'* ]]; then
    warn 'Bitte kein " oder \ im Passwort verwenden (technische Einschränkung der Konfigurationsdatei)'
    continue
  fi
  read -s -p "  Passwort wiederholen: " ADMIN_PASS2
  echo ""
  if [ "$ADMIN_PASS" = "$ADMIN_PASS2" ]; then
    break
  else
    warn "Passwörter stimmen nicht überein. Nochmal:"
  fi
done

log "Administrator-Konto konfiguriert: $ADMIN_USER"

# ─── Step 5: Erweiterte Optionen ─────────────────────────────────────────────

step "5/5" "Erweiterte Optionen"

echo ""
echo -e "  ${BOLD}Optionale Funktionen:${NC}"
echo ""

# Reject unknown callers
echo -e "  ${CYAN}[1]${NC} Unbekannte Anrufer sofort ablehnen"
read -p "      Aktivieren? [J/n]: " OPT_REJECT
REJECT_UNKNOWN=$([[ "${OPT_REJECT:-J}" =~ ^[nN]$ ]] && echo "false" || echo "true")
[ "$REJECT_UNKNOWN" = "true" ] && log "Unbekannte Anrufer werden abgelehnt" || info "Unbekannte Anrufer werden ignoriert"

echo ""

# Log retention
echo -e "  ${CYAN}[2]${NC} Anruf-Protokoll Aufbewahrung"
read -p "      Wie viele Tage? [30]: " LOG_DAYS
LOG_RETENTION="${LOG_DAYS:-30}"
log "Log-Aufbewahrung: ${LOG_RETENTION} Tage"

echo ""

# CLIP mode
echo -e "  ${CYAN}[3]${NC} Rufnummern-Format"
echo -e "      ${DIM}Manche SIM-Karten senden +49..., andere 0...${NC}"
echo -e "      ${CYAN}[a]${NC} International (+491701234567)"
echo -e "      ${CYAN}[b]${NC} National (01701234567)"
read -p "      Format [a]: " NUMBER_FORMAT
NUMBER_FMT=$([[ "${NUMBER_FORMAT:-a}" = "b" ]] && echo "national" || echo "international")
log "Rufnummernformat: $NUMBER_FMT"

echo ""

# GNSS system time sync
echo -e "  ${CYAN}[4]${NC} Systemzeit per GNSS synchronisieren"
echo -e "      ${DIM}Das SIM7600 kann die Pi-Uhr beim Start setzen (kein NTP/Internet nötig)${NC}"
read -p "      Aktivieren? [J/n]: " OPT_GNSS_TIME
SYNC_GNSS_TIME=$([[ "${OPT_GNSS_TIME:-J}" =~ ^[nN]$ ]] && echo "false" || echo "true")
[ "$SYNC_GNSS_TIME" = "true" ] && log "GNSS-Zeitsynchronisation aktiviert" || info "GNSS-Zeitsynchronisation deaktiviert"

# ─── Zusammenfassung ──────────────────────────────────────────────────────────

echo ""
echo ""
echo -e "${BOLD}${CYAN}  ┌─────────────────────────────────────────┐${NC}"
echo -e "${BOLD}${CYAN}  │         Zusammenfassung                 │${NC}"
echo -e "${BOLD}${CYAN}  └─────────────────────────────────────────┘${NC}"
echo ""
echo -e "  ${DIM}IP-Adresse:${NC}        ${CYAN}${HOST_IP}${NC}"
echo -e "  ${DIM}Verbindungsart:${NC}    ${CYAN}${CONNECTION_MODE}${NC}"
echo -e "  ${DIM}Modem-Port:${NC}        ${CYAN}${MODEM_PORT}${NC}"
echo -e "  ${DIM}Audio-Gerät:${NC}       ${CYAN}${AUDIO_LABEL}${NC}"
echo -e "  ${DIM}Admin-User:${NC}        ${CYAN}${ADMIN_USER}${NC}"
echo -e "  ${DIM}Unbekannte ablehnen:${NC} ${CYAN}${REJECT_UNKNOWN}${NC}"
echo -e "  ${DIM}Log-Aufbewahrung:${NC}  ${CYAN}${LOG_RETENTION} Tage${NC}"
echo -e "  ${DIM}Rufnummernformat:${NC}  ${CYAN}${NUMBER_FMT}${NC}"
echo -e "  ${DIM}GNSS-Zeitsync:${NC}     ${CYAN}${SYNC_GNSS_TIME}${NC}"
echo ""
read -p "  Konfiguration speichern und fortfahren? [J/n]: " CONFIRM
if [[ "${CONFIRM:-J}" =~ ^[nN]$ ]]; then
  echo ""
  warn "Setup abgebrochen."
  exit 1
fi

# ─── .env schreiben ───────────────────────────────────────────────────────────

# Generate random secret key
SECRET_KEY=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)

cat > "${INSTALL_DIR}/.env" << ENV
# Callbox Konfiguration
# Erstellt am: $(date)
# Bearbeite diese Datei und führe 'sudo systemctl restart callbox' aus um Änderungen anzuwenden.

HOST_IP="${HOST_IP}"
CONNECTION_MODE="${CONNECTION_MODE}"
MODEM_PORT="${MODEM_PORT}"
AUDIO_DEVICE="${AUDIO_DEVICE}"
AUDIO_LABEL="${AUDIO_LABEL}"

ADMIN_USER="${ADMIN_USER}"
ADMIN_PASS="${ADMIN_PASS}"
SECRET_KEY="${SECRET_KEY}"

REJECT_UNKNOWN="${REJECT_UNKNOWN}"
LOG_RETENTION_DAYS="${LOG_RETENTION}"
NUMBER_FORMAT="${NUMBER_FMT}"
SYNC_SYSTEM_TIME_FROM_GNSS="${SYNC_GNSS_TIME}"
ENV

chmod 600 "${INSTALL_DIR}/.env"

echo ""
log "Konfiguration gespeichert in ${INSTALL_DIR}/.env"
echo ""
