#!/usr/bin/env bash
set -euo pipefail

DASHBOARD_USER="${DASHBOARD_USER:-dashboard}"
DASHBOARD_URL="${DASHBOARD_URL:-http://127.0.0.1}"
CONFIG_FILE="/etc/dashboard-kiosk.conf"
KIOSK_SCRIPT="/usr/local/bin/dashboard-kiosk.sh"

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root, for example: sudo DASHBOARD_URL=http://127.0.0.1 ./setup-kiosk-dashboard.sh" >&2
  exit 1
fi

echo "Installing kiosk dependencies..."
apt-get update
apt-get install -y x11-xserver-utils unclutter

if ! command -v chromium-browser >/dev/null 2>&1 &&
   ! command -v chromium >/dev/null 2>&1 &&
   ! command -v firefox >/dev/null 2>&1; then
  apt-get install -y chromium-browser || apt-get install -y chromium || apt-get install -y firefox
fi

if ! id "$DASHBOARD_USER" >/dev/null 2>&1; then
  echo "Creating user: $DASHBOARD_USER"
  adduser --disabled-password --gecos "" "$DASHBOARD_USER"
fi

SESSION_FILE=""
SESSION_NAME=""
if [ -d /usr/share/xsessions ]; then
  SESSION_FILE="$(find /usr/share/xsessions -maxdepth 1 -name '*.desktop' | sort | head -n 1 || true)"
  if [ -n "$SESSION_FILE" ]; then
    SESSION_NAME="$(basename "$SESSION_FILE" .desktop)"
    SESSION_FILE="$(basename "$SESSION_FILE")"
  fi
fi

cat > "$CONFIG_FILE" <<EOF
DASHBOARD_URL="$DASHBOARD_URL"
DASHBOARD_SCALE="${DASHBOARD_SCALE:-0.75}"
EOF

cat > "$KIOSK_SCRIPT" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="/etc/dashboard-kiosk.conf"
DASHBOARD_URL="http://127.0.0.1"
DASHBOARD_SCALE="0.75"

if [ -f "$CONFIG_FILE" ]; then
  # shellcheck disable=SC1090
  . "$CONFIG_FILE"
fi

xset s off || true
xset -dpms || true
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
      --check-for-update-interval=31536000 \
      "$DASHBOARD_URL"
  elif command -v chromium >/dev/null 2>&1; then
    chromium \
      --kiosk \
      --noerrdialogs \
      --disable-infobars \
      --disable-session-crashed-bubble \
      --force-device-scale-factor="$DASHBOARD_SCALE" \
      --high-dpi-support=1 \
      --check-for-update-interval=31536000 \
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

chmod 0755 "$KIOSK_SCRIPT"

AUTOSTART_DIR="/home/$DASHBOARD_USER/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_DIR/dashboard-kiosk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Dashboard Kiosk
Exec=$KIOSK_SCRIPT
X-GNOME-Autostart-enabled=true
EOF

chown -R "$DASHBOARD_USER:$DASHBOARD_USER" "/home/$DASHBOARD_USER/.config"

configure_gdm() {
  local conf="/etc/gdm3/custom.conf"
  local tmp
  [ -f "$conf" ] || return 1

  cp -n "$conf" "$conf.bak-dashboard-kiosk" || true
  tmp="$(mktemp)"

  awk '
    BEGIN { in_daemon=0 }
    /^\[daemon\][[:space:]]*$/ {
      print
      print "AutomaticLoginEnable=true"
      print "AutomaticLogin='"$DASHBOARD_USER"'"
      print "WaylandEnable=false"
      in_daemon=1
      next
    }
    /^\[/ { in_daemon=0 }
    in_daemon && /^[#[:space:]]*(AutomaticLoginEnable|AutomaticLogin|WaylandEnable)[[:space:]]*=/ { next }
    { print }
  ' "$conf" > "$tmp"

  cat "$tmp" > "$conf"
  rm -f "$tmp"

  return 0
}

configure_lightdm() {
  [ -d /etc/lightdm ] || return 1
  mkdir -p /etc/lightdm/lightdm.conf.d
  cat > /etc/lightdm/lightdm.conf.d/50-dashboard-autologin.conf <<EOF
[Seat:*]
autologin-user=$DASHBOARD_USER
autologin-user-timeout=0
EOF
  if [ -n "$SESSION_NAME" ]; then
    echo "user-session=$SESSION_NAME" >> /etc/lightdm/lightdm.conf.d/50-dashboard-autologin.conf
  fi
  return 0
}

configure_sddm() {
  [ -d /etc/sddm.conf.d ] || [ -d /etc/sddm ] || return 1
  mkdir -p /etc/sddm.conf.d
  cat > /etc/sddm.conf.d/50-dashboard-autologin.conf <<EOF
[Autologin]
User=$DASHBOARD_USER
EOF
  if [ -n "$SESSION_FILE" ]; then
    echo "Session=$SESSION_FILE" >> /etc/sddm.conf.d/50-dashboard-autologin.conf
  fi
  return 0
}

echo "Configuring display manager autologin..."
DISPLAY_MANAGER="$(basename "$(readlink -f /etc/systemd/system/display-manager.service 2>/dev/null || true)")"

if [ "$DISPLAY_MANAGER" = "lightdm.service" ] && configure_lightdm; then
  echo "Configured active LightDM autologin."
elif [ "$DISPLAY_MANAGER" = "sddm.service" ] && configure_sddm; then
  echo "Configured active SDDM autologin."
elif [ "$DISPLAY_MANAGER" = "gdm3.service" ] && configure_gdm; then
  echo "Configured active GDM autologin."
elif configure_gdm; then
  echo "Configured GDM autologin."
elif configure_lightdm; then
  echo "Configured LightDM autologin."
elif configure_sddm; then
  echo "Configured SDDM autologin."
else
  echo "No supported display manager config was found. Autostart is installed, but autologin may need manual setup." >&2
fi

echo "Done. Reboot to test: sudo reboot"
echo "Dashboard URL: $DASHBOARD_URL"
echo "Kiosk user: $DASHBOARD_USER"
