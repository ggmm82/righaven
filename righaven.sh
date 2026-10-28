#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
wait_for_runtime() {
  for _attempt in $(seq 1 60); do
    if docker compose exec -T runtime-docker docker info >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  docker compose logs --tail=100 runtime-docker >&2 || true
  return 1
}

case "${1:-}" in
  build) docker compose --profile sandbox-template build ;;
  up)
    # The worker image belongs to RigHaven's private runtime, never to the
    # host daemon. Build it locally, then load the exact image into the
    # application-owned daemon before the Gateway is started.
    docker compose --profile sandbox-template build
    docker compose up -d runtime-docker redis
    wait_for_runtime
    docker save righaven-sandbox:0.1.0 | docker compose exec -T runtime-docker docker load
    RIGHAVEN_SANDBOX_IMAGE=righaven-sandbox:0.1.0 docker compose up -d --no-build
    ;;
  stop) docker compose down ;;
  logs) docker compose logs -f gateway ;;
  check) python3 scripts/validate.py; python3 -m unittest discover -s tests -v ;;
  *) echo 'Usage: bash righaven.sh {build|up|stop|logs|check}' >&2; exit 2 ;;
esac
