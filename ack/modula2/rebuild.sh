#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
for app in hello arithmetic sieve e ttt; do
    "${PYTHON:-python3}" ack/modula2.py "ack/modula2/examples/$app.mod"
done
