#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root: sudo ./deploy/update.sh" >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required but not installed." >&2
  exit 1
fi

echo "Updating repository..."
git -C "$REPO_ROOT" pull --ff-only

echo "Reinstalling project files..."
bash "$REPO_ROOT/deploy/install.sh"

echo "Restarting services..."
systemctl restart nginx
systemctl restart filemgr 2>/dev/null || true
systemctl restart eth0-direct 2>/dev/null || true

echo "Update complete."
echo "Check status with:"
echo "  sudo systemctl status nginx --no-pager"
echo "  sudo systemctl status filemgr --no-pager"
