#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
for app in hello arithmetic sieve e ttt; do
    "${PYTHON:-python3}" ack/pascal.py "ack/pascal/examples/$app.p"
done
