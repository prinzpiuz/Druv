#!/bin/sh
set -e

echo "[Caddy Init] Installing envsubst..."
apk add --no-cache gettext > /dev/null

echo "[Caddy Init] Expanding environment variables into Caddyfile..."
envsubst < /etc/caddy/Caddyfile.template > /etc/caddy/Caddyfile

echo "[Caddy Init] Starting Caddy..."
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
