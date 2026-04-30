#!/usr/bin/env bash
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/userdata/backup}"
STAMP="$(date +%Y%m%d-%H%M%S)"
NAME="taishanpi-config-backup-${STAMP}"
WORK_DIR="$(mktemp -d)"
STAGE_DIR="$WORK_DIR/$NAME"
OUT_FILE="$BACKUP_ROOT/${NAME}.tar.gz"

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root: sudo ./deploy/backup.sh" >&2
  exit 1
fi

mkdir -p "$BACKUP_ROOT"
mkdir -p "$STAGE_DIR"

copy_path() {
  local src="$1"
  local rel="${src#/}"
  local dst="$STAGE_DIR/$rel"
  if [ -e "$src" ]; then
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
    echo "/$rel" >> "$STAGE_DIR/included-files.txt"
  fi
}

echo "Collecting private configuration files..."

copy_path /userdata/server/apps/filemgr/users.json
copy_path /userdata/server/apps/filemgr/devices.json
copy_path /etc/nginx/sites-available/default
copy_path /etc/systemd/system/filemgr.service
copy_path /etc/systemd/system/eth0-direct.service
copy_path /etc/sudoers.d/filemgr-syncthing
copy_path /etc/dashboard-kiosk.conf
copy_path /etc/lightdm/lightdm.conf.d/50-dashboard-autologin.conf
copy_path /etc/gdm3/custom.conf
copy_path /home/dashboard/.config/autostart
copy_path /home/lckfb/.local/state/syncthing/config.xml
copy_path /etc/systemd/system/cloudflared.service
copy_path /etc/cloudflared
copy_path /etc/default/cloudflared

cat > "$STAGE_DIR/metadata.txt" <<EOF
backup_name=$NAME
created_at=$(date -Is)
hostname=$(hostname)
kernel=$(uname -r)
user_data_root=/userdata
notes=Contains private runtime configuration. Do not commit this archive to GitHub.
EOF

{
  echo
  echo "==== ip -4 addr ===="
  ip -4 addr || true
  echo
  echo "==== ip route ===="
  ip route || true
  echo
  echo "==== systemctl enabled ===="
  systemctl is-enabled nginx filemgr eth0-direct ssh 2>/dev/null || true
  echo
  echo "==== systemctl enabled (optional) ===="
  systemctl is-enabled cloudflared syncthing@lckfb 2>/dev/null || true
} >> "$STAGE_DIR/metadata.txt"

tar -C "$WORK_DIR" -czf "$OUT_FILE" "$NAME"
rm -rf "$WORK_DIR"

echo "Backup created:"
echo "  $OUT_FILE"
echo
echo "Archive contains private config files only."
echo "Do not upload this backup to GitHub."
