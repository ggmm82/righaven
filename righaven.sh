#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
case "${1:-}" in
  build) docker compose build ;;
  up) docker compose up -d ;;
  stop) docker compose down ;;
  logs) docker compose logs -f gateway ;;
  check) python3 scripts/validate.py; python3 -m unittest discover -s tests -v ;;
  *) echo 'Usage: bash righaven.sh {build|up|stop|logs|check}' >&2; exit 2 ;;
esac
