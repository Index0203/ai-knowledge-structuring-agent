#!/usr/bin/env sh
# Prints the links for this project: one for this machine, one to share with
# people on the same network, plus a quick health check of the running stack.
#
#   sh scripts/link.sh

set -eu

frontend_port="${FRONTEND_PORT:-3000}"
backend_port="${BACKEND_PORT:-8000}"

address="$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')"
if [ -z "$address" ]; then
  address="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi

check_http() {
  if curl -s -o /dev/null -m 3 "$1"; then
    echo up
  else
    echo down
  fi
}

front_state="$(check_http "http://127.0.0.1:${frontend_port}/")"
back_state="$(check_http "http://127.0.0.1:${backend_port}/health")"

echo ""
echo "On this machine:  http://localhost:${frontend_port}"
if [ -n "$address" ]; then
  echo "Share on the LAN: http://${address}:${frontend_port}"
else
  echo "No LAN address found - connect to WiFi or Ethernet first."
fi
echo ""
if [ "$front_state" = "up" ] && [ "$back_state" = "up" ]; then
  echo "Services: web and API are both listening - share the link above."
else
  echo "Services: web ${front_state}, api ${back_state}"
  echo "Start them first: sh scripts/deploy.sh (or docker compose up -d)"
fi
echo ""
echo "Use the localhost link for yourself; the shared one changes with the network."
