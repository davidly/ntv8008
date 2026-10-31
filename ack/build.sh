#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
"${PYTHON:-python3}" ack/bootstrap.py
./a08/m.sh
