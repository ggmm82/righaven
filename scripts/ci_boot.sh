#!/usr/bin/env bash
set -euo pipefail
export RIGHAVEN_PASSWORD=ci-only-not-a-real-credential-123456
export RIGHAVEN_BIND_IP=127.0.0.1
export RIGHAVEN_PUBLIC_URL=http://localhost:2026
cleanup() {
  docker compose logs --no-color --tail=100 gateway frontend proxy runtime-docker || true
  docker compose down -v || true
}
trap cleanup EXIT
docker compose up -d --no-build runtime-docker redis
for attempt in $(seq 1 60); do
  if docker compose exec -T runtime-docker docker info >/dev/null 2>&1; then break; fi
  sleep 1
done
# CI verifies the exact local candidate in the application-owned daemon. A
# production Compose pulls the same immutable digest directly from GHCR.
docker save righaven-sandbox:0.1.0 | docker compose exec -T runtime-docker docker load
export RIGHAVEN_SANDBOX_IMAGE=righaven-sandbox:0.1.0
docker compose up -d --no-build
for attempt in $(seq 1 60); do
  if curl -fsS --user "admin:$RIGHAVEN_PASSWORD" http://127.0.0.1:2026/health/ready >/dev/null; then
    break
  fi
  sleep 2
done
curl -fsS --user "admin:$RIGHAVEN_PASSWORD" http://127.0.0.1:2026/health/ready
curl -fsS --user "admin:$RIGHAVEN_PASSWORD" http://127.0.0.1:2026/ >/dev/null
test "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:2026/harness/)" = 401
# RigHaven is inside RigHaven: before app login it may require the RigHaven session.
status="$(curl -s -o /tmp/rh-http -w '%{http_code}' --user "admin:$RIGHAVEN_PASSWORD" http://127.0.0.1:2026/harness/)"
case "$status" in
  200) grep -q 'RigHaven' /tmp/rh-http ;;
  401|403) echo 'RigHaven requires its authenticated account before opening RigHaven' ;;
  *) cat /tmp/rh-http; exit 1 ;;
esac
python scripts/ci_http.py

if [ "${RIGHAVEN_LIFECYCLE_CHECK:-0}" = "1" ]; then
  python scripts/ci_environment_lifecycle.py
fi
