#!/bin/sh
set -eu
cd "$(dirname "$0")"
./m.sh
exec "${PYTHON:-python3}" tools/perfrun.py "$@"
