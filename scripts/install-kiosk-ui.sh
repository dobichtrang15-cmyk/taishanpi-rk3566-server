#!/usr/bin/env bash
set -euo pipefail

SOURCE="${1:-./kiosk.html}"
TARGET_DIR="/userdata/server/www/site"
TARGET="$TARGET_DIR/kiosk.html"
CONFIG_FILE="/etc/dashboard-kiosk.conf"
KIOSK_USER="${KIOSK_USER:-dashboard}"
LAUNCHER="/usr/local/bin/dashboard-kiosk.sh"
AUTOSTART_DIR="/home/$KIOSK_USER/.config/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/dashboard-kiosk.desktop"

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root: sudo ./install-kiosk-ui.sh /path/to/kiosk.html" >&2
  exit 1
fi

if [ ! -f "$SOURCE" ]; then
  echo "kiosk html not found: $SOURCE" >&2
  exit 1
fi

install -d "$TARGET_DIR"
install -m 0644 "$SOURCE" "$TARGET"

cat > "$CONFIG_FILE" <<'EOF'
DASHBOARD_URL="http://127.0.0.1/kiosk.html"
DASHBOARD_SCALE="1"
EOF

apt-get update
apt-get install -y x11-xserver-utils unclutter

if ! command -v chromium-browser >/dev/null 2>&1 &&
   ! command -v chromium >/dev/null 2>&1 &&
   ! command -v firefox >/dev/null 2>&1; then
  apt-get install -y chromium-browser || apt-get install -y chromium || apt-get install -y firefox
fi

cat > "$LAUNCHER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="/etc/dashboard-kiosk.conf"
DASHBOARD_URL="http://127.0.0.1/kiosk.html"
DASHBOARD_SCALE="1"

if [ -f "$CONFIG_FILE" ]; then
  # shellcheck disable=SC1090
  . "$CONFIG_FILE"
fi

xset s off || true
xset s 0 0 || true
xset -dpms || true
xset dpms 0 0 0 || true
xset s noblank || true
unclutter -idle 1 -root >/dev/null 2>&1 &

while true; do
  if command -v chromium-browser >/dev/null 2>&1; then
    chromium-browser \
      --kiosk \
      --noerrdialogs \
      --disable-infobars \
      --disable-session-crashed-bubble \
      --force-device-scale-factor="$DASHBOARD_SCALE" \
      --high-dpi-support=1 \
      "$DASHBOARD_URL"
  elif command -v chromium >/dev/null 2>&1; then
    chromium \
      --kiosk \
      --noerrdialogs \
      --disable-infobars \
      --disable-session-crashed-bubble \
      --force-device-scale-factor="$DASHBOARD_SCALE" \
      --high-dpi-support=1 \
      "$DASHBOARD_URL"
  elif command -v firefox >/dev/null 2>&1; then
    firefox --kiosk "$DASHBOARD_URL"
  else
    echo "No supported browser found. Install chromium-browser, chromium, or firefox." >&2
    exit 1
  fi

  sleep 2
done
EOF

chmod 0755 "$LAUNCHER"

if id "$KIOSK_USER" >/dev/null 2>&1; then
  install -d "$AUTOSTART_DIR"
  cat > "$AUTOSTART_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Dashboard Kiosk Browser
Exec=$LAUNCHER
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
  chown -R "$KIOSK_USER:$KIOSK_USER" "/home/$KIOSK_USER/.config"
else
  echo "Warning: user '$KIOSK_USER' does not exist. Browser launcher was installed, but autostart was not updated." >&2
fi

echo "Installed: $TARGET"
echo "Updated: $CONFIG_FILE"
echo "Installed browser launcher: $LAUNCHER"
echo "Updated autostart: $AUTOSTART_FILE"
echo "Reboot or restart the kiosk session to use the browser UI."
