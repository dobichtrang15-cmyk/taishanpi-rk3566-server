#!/usr/bin/env bash
set -u

sleep 8

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/home/dashboard/.Xauthority}"

for _ in $(seq 1 20); do
  if xset q >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

xset s off || true
xset s noblank || true
xset +dpms || true
xset dpms 1800 1800 1800 || true

for _ in $(seq 1 5); do
  sleep 10
  xset +dpms || true
  xset dpms 1800 1800 1800 || true
done
