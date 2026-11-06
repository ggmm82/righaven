#!/bin/sh
set -eu
: "${RIGHAVEN_PASSWORD:?Impostare RIGHAVEN_PASSWORD in Hostinger}"
export RIGHAVEN_USER="${RIGHAVEN_USER:-admin}"
export RIGHAVEN_PASSWORD_HASH="$(caddy hash-password --plaintext "$RIGHAVEN_PASSWORD")"
unset RIGHAVEN_PASSWORD
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
