#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -d .venv ]; then source .venv/bin/activate; fi
if [ $# -lt 1 ]; then
  echo "Usage: ./run.sh \"<feature request>\" [--repo PATH] [--no-reviewer] [--max-rounds N]"
  exit 1
fi
python -m team.main build "$@"