#!/bin/sh
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$project/../.." && pwd)
mkdir -p "$project/build"
"${PYTHON:-python3}" "$repo/tools/build_map.py" "$project/program.asm" "$project/build/program.hex"
