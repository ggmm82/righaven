#!/bin/sh
set -eu
export DEER_FLOW_INTERNAL_GATEWAY_BASE_URL="${RIGHAVEN_INTERNAL_GATEWAY_BASE_URL:-http://gateway:8001}"
export BETTER_AUTH_SECRET="$(node -e 'process.stdout.write(require("crypto").createHash("sha256").update(process.env.RIGHAVEN_PASSWORD).digest("hex"))')"
unset RIGHAVEN_PASSWORD
cd /app/frontend
exec pnpm start
