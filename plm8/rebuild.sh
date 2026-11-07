#!/bin/sh
set -eu
cd "$(dirname "$0")"
for app in hello arithmetic sieve e ttt; do
    "${PYTHON:-python3}" compile.py "examples/$app.plm"
done
if [ -f upstream/mac8.sav ]; then
    "${PYTHON:-python3}" mac8.py examples/mac8hello.asm
fi
