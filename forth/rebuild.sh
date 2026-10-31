#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
"${PYTHON:-python3}" forth/prepare.py
./a08/rebuild.sh forth.asm
