#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIOSK_USER="${KIOSK_USER:-dashboard}"
TARGET_ROOT="${TAISHANPI_INSTALL_ROOT:-/userdata/server}"
TARGET_APP="$TARGET_ROOT/apps/filemgr"
TARGET_MATTER="$TARGET_ROOT/apps/matter-workstation"
TARGET_WEB="$TARGET_ROOT/www/site"
FILES_ROOT="${TAISHANPI_FILES_ROOT:-/userdata/files}"
RUNTIME_ROOT="/opt/taishanpi-server"
RUNTIME_FILES="/srv/taishanpi-files"
INSTALL_KIOSK="${INSTALL_KIOSK:-1}"
INSTALL_MATTER="${INSTALL_MATTER:-1}"
SKIP_APT="${SKIP_APT:-0}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root: sudo ./deploy/install.sh" >&2
  exit 1
fi

if [ "$SKIP_APT" != "1" ]; then
  echo "Installing required packages..."
  apt-get update
  apt-get install -y --no-upgrade nginx python3 python3-pip openssh-server curl
  if [ "$INSTALL_KIOSK" = "1" ]; then
    apt-get install -y --no-upgrade x11-xserver-utils unclutter
  fi
else
  echo "Skipping APT package installation (SKIP_APT=1)."
fi

if [ "$INSTALL_MATTER" = "1" ]; then
  NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  NODE_MINOR="$(node -p 'process.versions.node.split(".")[1]' 2>/dev/null || echo 0)"
  if [ "$NODE_MAJOR" -lt 22 ] || { [ "$NODE_MAJOR" -eq 22 ] && [ "$NODE_MINOR" -lt 13 ]; }; then
    if [ "$SKIP_APT" = "1" ]; then
      echo "Node.js >= 22.13 is required when INSTALL_MATTER=1." >&2
      exit 1
    fi
    echo "Installing Node.js 22 for Matter..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y --no-upgrade nodejs
  fi
fi

if [ "$INSTALL_KIOSK" = "1" ] &&
   ! command -v chromium-browser >/dev/null 2>&1 &&
   ! command -v chromium >/dev/null 2>&1 &&
   ! command -v firefox >/dev/null 2>&1; then
  if [ "$SKIP_APT" = "1" ]; then
    echo "A browser is required when INSTALL_KIOSK=1." >&2
    exit 1
  fi
  apt-get install -y --no-upgrade chromium-browser ||
    apt-get install -y --no-upgrade chromium ||
    apt-get install -y --no-upgrade firefox
fi

echo "Creating directories..."
install -d "$TARGET_APP" "$TARGET_WEB" "$FILES_ROOT" /opt /srv
if [ "$INSTALL_MATTER" = "1" ]; then
  install -d "$TARGET_MATTER" /var/lib/matter-workstation
fi

ensure_runtime_link() {
  local target="$1"
  local link="$2"
  if [ -e "$link" ] && [ ! -L "$link" ]; then
    echo "Refusing to replace non-symlink path: $link" >&2
    exit 1
  fi
  ln -sfn "$target" "$link"
}

ensure_runtime_link "$TARGET_ROOT" "$RUNTIME_ROOT"
ensure_runtime_link "$FILES_ROOT" "$RUNTIME_FILES"

echo "Installing web UI..."
if [ -d "$REPO_ROOT/www/site" ]; then
  find "$TARGET_WEB" -mindepth 1 -maxdepth 1 -type f \( -name '*.html' -o -name '*.css' -o -name '*.js' \) -delete
  cp -a "$REPO_ROOT/www/site/." "$TARGET_WEB/"
fi

if [ "$INSTALL_MATTER" = "1" ] && [ -f "$REPO_ROOT/apps/matter-workstation/package.json" ]; then
  echo "Installing Matter workstation bridge..."
  cp -a "$REPO_ROOT/apps/matter-workstation/." "$TARGET_MATTER/"
  if command -v corepack >/dev/null 2>&1; then
    corepack pnpm --dir "$TARGET_MATTER" install --prod --frozen-lockfile
  else
    npm --prefix "$TARGET_MATTER" install --omit=dev
  fi
  npm --prefix "$TARGET_MATTER" run check
fi

if [ -f "$REPO_ROOT/www/kiosk.html" ]; then
  install -m 0644 "$REPO_ROOT/www/kiosk.html" "$TARGET_WEB/kiosk.html"
fi

if [ -f "$REPO_ROOT/apps/filemgr/app.py" ]; then
  echo "Installing Flask backend..."
  find "$TARGET_APP" -maxdepth 1 -type f -name '*.py' -delete
  install -m 0644 "$REPO_ROOT/apps/filemgr/app.py" "$TARGET_APP/app.py"
  if [ -f "$REPO_ROOT/apps/filemgr/requirements.txt" ]; then
    if ! python3 -c 'import flask, werkzeug, paramiko' >/dev/null 2>&1; then
      if python3 -m pip --version >/dev/null 2>&1; then
        python3 -m pip install -r "$REPO_ROOT/apps/filemgr/requirements.txt"
      else
        echo "Python dependencies are missing and python3-pip is unavailable." >&2
        echo "Install Flask, Werkzeug and Paramiko, then rerun with SKIP_APT=1." >&2
        exit 1
      fi
    fi
  fi
else
  echo "Warning: apps/filemgr/app.py not found in repo." >&2
  echo "If this is a fresh board, copy app.py from the old board before enabling filemgr." >&2
fi

echo "Installing systemd services..."
install -m 0644 "$REPO_ROOT/deploy/systemd/filemgr.service" /etc/systemd/system/filemgr.service
install -m 0644 "$REPO_ROOT/deploy/systemd/eth0-direct.service" /etc/systemd/system/eth0-direct.service
if [ ! -f /etc/default/filemgr ]; then
  install -m 0644 "$REPO_ROOT/deploy/filemgr.env" /etc/default/filemgr
fi
if [ ! -f /etc/default/eth0-direct ]; then
  install -m 0644 "$REPO_ROOT/deploy/eth0-direct.env" /etc/default/eth0-direct
fi
if [ "$INSTALL_MATTER" = "1" ]; then
  install -m 0644 "$REPO_ROOT/deploy/systemd/matter-workstation.service" /etc/systemd/system/matter-workstation.service
fi
if [ "$INSTALL_MATTER" = "1" ] && [ ! -f /etc/default/matter-workstation ]; then
  install -m 0644 "$REPO_ROOT/deploy/matter-workstation.env" /etc/default/matter-workstation
fi

if [ "$INSTALL_MATTER" = "1" ]; then
  if ! id matter-workstation >/dev/null 2>&1; then
    useradd --system --home /var/lib/matter-workstation --shell /usr/sbin/nologin matter-workstation
  fi
  chown -R matter-workstation:matter-workstation /var/lib/matter-workstation "$TARGET_MATTER"
fi

echo "Installing nginx config..."
install -m 0644 "$REPO_ROOT/deploy/nginx-default.conf" /etc/nginx/sites-available/default
ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default
nginx -t

if [ "$INSTALL_KIOSK" = "1" ]; then
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
fi

echo "Enabling services..."
systemctl daemon-reload
systemctl enable nginx
systemctl enable eth0-direct
if [ -f "$TARGET_APP/app.py" ]; then
  python3 -m py_compile "$TARGET_APP/app.py"
  systemctl enable filemgr
fi
if [ "$INSTALL_MATTER" = "1" ] && [ -f "$TARGET_MATTER/src/index.mjs" ]; then
  systemctl enable matter-workstation
fi

systemctl restart nginx
systemctl restart eth0-direct || true
if [ -f "$TARGET_APP/app.py" ]; then
  systemctl restart filemgr
fi
if [ "$INSTALL_MATTER" = "1" ] && [ -f "$TARGET_MATTER/src/index.mjs" ]; then
  systemctl restart matter-workstation
fi

echo "Install complete."
if [ "$INSTALL_KIOSK" = "1" ]; then
  echo "Reboot to enter HDMI kiosk."
fi
