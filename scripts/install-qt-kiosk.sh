#!/usr/bin/env bash
set -euo pipefail

APP_SOURCE="${1:-./kiosk_qt.py}"
APP_TARGET_DIR="/userdata/server/apps/qt-kiosk"
APP_TARGET="$APP_TARGET_DIR/kiosk_qt.py"
LAUNCHER="/usr/local/bin/dashboard-kiosk-qt.sh"
AUTOSTART_DIR="/home/dashboard/.config/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/dashboard-kiosk.desktop"

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root: sudo ./install-qt-kiosk.sh /path/to/kiosk_qt.py" >&2
  exit 1
fi

if [ ! -f "$APP_SOURCE" ]; then
  echo "Qt app not found: $APP_SOURCE" >&2
  exit 1
fi

apt-get update
apt-get install -y python3-pyqt5 python3-requests

install -d "$APP_TARGET_DIR"
install -m 0755 "$APP_SOURCE" "$APP_TARGET"

cat > "$LAUNCHER" <<'EOF'
#!/usr/bin/env bash
set -uo pipefail

LOG_FILE="/tmp/dashboard-kiosk-qt.log"
APP="/userdata/server/apps/qt-kiosk/kiosk_qt.py"

exec >>"$LOG_FILE" 2>&1
echo "===== dashboard-kiosk-qt starting $(date) ====="
echo "USER=$(id -un) DISPLAY=${DISPLAY:-unset} XAUTHORITY=${XAUTHORITY:-unset}"

for _ in $(seq 1 30); do
  if [ -n "${DISPLAY:-}" ]; then
    break
  fi
  sleep 1
done

xset s off || true
xset s 0 0 || true
xset -dpms || true
xset dpms 0 0 0 || true
xset s noblank || true

while true; do
  echo "Launching Qt app: $APP"
  /usr/bin/python3 "$APP"
  code=$?
  echo "Qt app exited with code $code at $(date)"
  sleep 2
done
EOF

chmod 0755 "$LAUNCHER"
install -d "$AUTOSTART_DIR"

cat > "$AUTOSTART_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Dashboard Kiosk Qt
Exec=$LAUNCHER
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

chown -R dashboard:dashboard "/home/dashboard/.config"

echo "Installed Qt kiosk app to $APP_TARGET"
echo "Installed launcher to $LAUNCHER"
echo "Reboot to test."
