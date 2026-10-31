#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
./smallc/build.sh
for app in hello arithmetic sieve e ttt snake; do
    python3 smallc/compile.py "smallc/examples/$app.c"
done
