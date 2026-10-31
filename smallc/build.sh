#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 smallc/build.py
./a08/m.sh
