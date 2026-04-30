#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIOSK_USER="${KIOSK_USER:-dashboard}"
TARGET_ROOT="/userdata/server"
TARGET_APP="$TARGET_ROOT/apps/filemgr"
TARGET_WEB="$TARGET_ROOT/www/site"
FILES_ROOT="/userdata/files"

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root: sudo ./deploy/install.sh" >&2
  exit 1
fi

echo "Installing packages..."
apt-get update
apt-get install -y nginx python3 python3-pip python3-venv openssh-server x11-xserver-utils unclutter

if ! command -v chromium-browser >/dev/null 2>&1 &&
   ! command -v chromium >/dev/null 2>&1 &&
   ! command -v firefox >/dev/null 2>&1; then
  apt-get install -y chromium-browser || apt-get install -y chromium || apt-get install -y firefox
fi

echo "Creating directories..."
install -d "$TARGET_APP" "$TARGET_WEB" "$FILES_ROOT"

echo "Installing web UI..."
if [ -d "$REPO_ROOT/www/site" ]; then
  find "$TARGET_WEB" -mindepth 1 -maxdepth 1 -type f \( -name '*.html' -o -name '*.css' -o -name '*.js' \) -delete
  cp -a "$REPO_ROOT/www/site/." "$TARGET_WEB/"
fi

if [ -f "$REPO_ROOT/www/kiosk.html" ]; then
  install -m 0644 "$REPO_ROOT/www/kiosk.html" "$TARGET_WEB/kiosk.html"
fi

if [ -f "$REPO_ROOT/apps/filemgr/app.py" ]; then
  echo "Installing Flask backend..."
  find "$TARGET_APP" -maxdepth 1 -type f -name '*.py' -delete
  install -m 0644 "$REPO_ROOT/apps/filemgr/app.py" "$TARGET_APP/app.py"
  if [ -f "$REPO_ROOT/apps/filemgr/requirements.txt" ]; then
    python3 -m pip install -r "$REPO_ROOT/apps/filemgr/requirements.txt"
  fi
else
  echo "Warning: apps/filemgr/app.py not found in repo." >&2
  echo "If this is a fresh board, copy app.py from the old board before enabling filemgr." >&2
fi

if [ ! -f "$TARGET_APP/devices.json" ] && [ -f "$REPO_ROOT/apps/filemgr/devices.example.json" ]; then
  install -m 0600 "$REPO_ROOT/apps/filemgr/devices.example.json" "$TARGET_APP/devices.json"
fi

if [ ! -f "$TARGET_APP/users.json" ] && [ -f "$REPO_ROOT/apps/filemgr/users.example.json" ]; then
  install -m 0600 "$REPO_ROOT/apps/filemgr/users.example.json" "$TARGET_APP/users.json"
fi

echo "Installing systemd services..."
install -m 0644 "$REPO_ROOT/deploy/systemd/filemgr.service" /etc/systemd/system/filemgr.service
install -m 0644 "$REPO_ROOT/deploy/systemd/eth0-direct.service" /etc/systemd/system/eth0-direct.service

echo "Installing nginx config..."
install -m 0644 "$REPO_ROOT/deploy/nginx-default.conf" /etc/nginx/sites-available/default
ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default
nginx -t

echo "Installing kiosk scripts..."
install -m 0755 "$REPO_ROOT/deploy/scripts/dashboard-kiosk.sh" /usr/local/bin/dashboard-kiosk.sh
install -m 0755 "$REPO_ROOT/deploy/scripts/dashboard-dpms-30m.sh" /usr/local/bin/dashboard-dpms-30m.sh

cat > /etc/dashboard-kiosk.conf <<'EOF'
DASHBOARD_URL="http://127.0.0.1/kiosk.html"
DASHBOARD_SCALE="1"
EOF

if ! id "$KIOSK_USER" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$KIOSK_USER"
fi

AUTOSTART_DIR="/home/$KIOSK_USER/.config/autostart"
install -d "$AUTOSTART_DIR"

cat > "$AUTOSTART_DIR/dashboard-kiosk.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Dashboard Kiosk Browser
Exec=/usr/local/bin/dashboard-kiosk.sh
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

cat > "$AUTOSTART_DIR/dashboard-dpms-30m.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Dashboard DPMS 30m
Exec=/usr/local/bin/dashboard-dpms-30m.sh
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

cat > "$AUTOSTART_DIR/light-locker.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Light Locker
Hidden=true
EOF

cat > "$AUTOSTART_DIR/xfce4-screensaver.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=XFCE Screensaver
Hidden=true
EOF

cat > "$AUTOSTART_DIR/xscreensaver.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=XScreenSaver
Hidden=true
EOF

chown -R "$KIOSK_USER:$KIOSK_USER" "/home/$KIOSK_USER/.config"

echo "Removing lock screens..."
apt-mark unhold xfce4-screensaver 2>/dev/null || true
apt-get remove -y --allow-change-held-packages xfce4-screensaver light-locker xscreensaver gnome-screensaver 2>/dev/null || true
pkill -f xfce4-screensaver 2>/dev/null || true

echo "Configuring desktop lock behavior..."
sudo -u "$KIOSK_USER" xfconf-query -c xfce4-session -p /shutdown/LockScreen -n -t bool -s false 2>/dev/null || true
sudo -u "$KIOSK_USER" xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/lock-screen-suspend-hibernate -n -t bool -s false 2>/dev/null || true
sudo -u "$KIOSK_USER" xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/blank-on-ac -n -t int -s 0 2>/dev/null || true

configure_lightdm() {
  [ -d /etc/lightdm ] || return 1
  install -d /etc/lightdm/lightdm.conf.d
  cat > /etc/lightdm/lightdm.conf.d/50-dashboard-autologin.conf <<EOF
[Seat:*]
autologin-user=$KIOSK_USER
autologin-user-timeout=0
user-session=xubuntu
EOF
}

configure_gdm() {
  local conf="/etc/gdm3/custom.conf"
  [ -f "$conf" ] || return 1
  cp -n "$conf" "$conf.bak-dashboard-kiosk" || true
  awk '
    BEGIN { in_daemon=0 }
    /^\[daemon\][[:space:]]*$/ {
      print
      print "AutomaticLoginEnable=true"
      print "AutomaticLogin='"$KIOSK_USER"'"
      print "WaylandEnable=false"
      in_daemon=1
      next
    }
    /^\[/ { in_daemon=0 }
    in_daemon && /^[#[:space:]]*(AutomaticLoginEnable|AutomaticLogin|WaylandEnable)[[:space:]]*=/ { next }
    { print }
  ' "$conf" > "$conf.tmp"
  cat "$conf.tmp" > "$conf"
  rm -f "$conf.tmp"
}

DISPLAY_MANAGER="$(basename "$(readlink -f /etc/systemd/system/display-manager.service 2>/dev/null || true)")"
if [ "$DISPLAY_MANAGER" = "lightdm.service" ]; then
  configure_lightdm || true
elif [ "$DISPLAY_MANAGER" = "gdm3.service" ]; then
  configure_gdm || true
else
  configure_lightdm || configure_gdm || true
fi

echo "Enabling services..."
systemctl daemon-reload
systemctl enable nginx
systemctl enable eth0-direct
if [ -f "$TARGET_APP/app.py" ]; then
  python3 -m py_compile "$TARGET_APP/app.py"
  systemctl enable filemgr
fi

systemctl restart nginx
systemctl restart eth0-direct || true
if [ -f "$TARGET_APP/app.py" ]; then
  systemctl restart filemgr
fi

echo "Install complete. Reboot to enter HDMI kiosk."
