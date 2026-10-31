#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
for app in hello arithmetic sieve e ttt; do
    "${PYTHON:-python3}" ack/compile.py "ack/examples/$app.c"
done
