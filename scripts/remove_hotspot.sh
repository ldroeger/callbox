#!/bin/bash
# Callbox – Hotspot entfernen

if [ "$EUID" -ne 0 ]; then
  echo "Bitte als root ausführen: sudo bash /opt/callbox/scripts/remove_hotspot.sh"
  exit 1
fi

echo ""
echo "  Entferne Callbox-Hotspot..."

# Stop and remove the NM connection
nmcli connection down "Callbox-Hotspot" 2>/dev/null && echo "  ✓ Hotspot gestoppt" || true
nmcli connection delete "Callbox-Hotspot" 2>/dev/null && echo "  ✓ Verbindung entfernt" || echo "  (Verbindung nicht gefunden)"

# Remove dispatcher script
rm -f /etc/NetworkManager/dispatcher.d/99-callbox-hotspot && echo "  ✓ Dispatcher entfernt"

# Remove from .env
if [ -f /opt/callbox/.env ]; then
  grep -v "^HOTSPOT_" /opt/callbox/.env > /tmp/env_tmp
  # Remove the comment line above hotspot vars
  grep -v "^# Hotspot-Konfiguration" /tmp/env_tmp > /opt/callbox/.env
  rm -f /tmp/env_tmp
  echo "  ✓ .env bereinigt"
fi

systemctl reload NetworkManager 2>/dev/null || true

echo ""
echo "  ✓ Hotspot vollständig entfernt."
echo ""
