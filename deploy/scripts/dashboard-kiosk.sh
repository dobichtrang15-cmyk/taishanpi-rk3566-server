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
xset s noblank || true
unclutter -idle 1 -root >/dev/null 2>&1 &

while true; do
  if command -v chromium-browser >/dev/null 2>&1; then
    chromium-browser --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --force-device-scale-factor="$DASHBOARD_SCALE" --high-dpi-support=1 "$DASHBOARD_URL"
  elif command -v chromium >/dev/null 2>&1; then
    chromium --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --force-device-scale-factor="$DASHBOARD_SCALE" --high-dpi-support=1 "$DASHBOARD_URL"
  elif command -v firefox >/dev/null 2>&1; then
    firefox --kiosk "$DASHBOARD_URL"
  else
    echo "No supported browser found." >&2
    exit 1
  fi

  sleep 2
done
