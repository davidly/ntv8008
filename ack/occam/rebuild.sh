#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
for app in hello arithmetic sieve e ttt; do
    "${PYTHON:-python3}" ack/occam.py "ack/occam/examples/$app.ocm"
done
