#!/bin/sh
set -eu
export BETTER_AUTH_SECRET="$(node -e 'process.stdout.write(require("crypto").createHash("sha256").update(process.env.RIGHAVEN_PASSWORD).digest("hex"))')"
unset RIGHAVEN_PASSWORD
cd /app/frontend
exec pnpm start
