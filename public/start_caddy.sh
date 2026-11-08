#!/bin/sh
set -e

echo "[Caddy Init] Installing envsubst..."
apk add --no-cache gettext > /dev/null

echo "[Caddy Init] Expanding environment variables into Caddyfile..."
envsubst < /etc/caddy/Caddyfile.template > /etc/caddy/Caddyfile

# The deploy workflow compares this with the files on the host. A mismatch
# means this container runs an old config and must restart. Written only after
# the config validates, so a broken config fails the deploy instead of passing.
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
cat /etc/caddy/Caddyfile.template /start_caddy.sh | sha256sum | cut -d ' ' -f 1 > /etc/caddy/rendered.sha256

echo "[Caddy Init] Starting Caddy..."
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
