#!/bin/sh
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$project/../.." && pwd)
mkdir -p "$project/build"
"${PYTHON:-python3}" "$repo/ack/compile.py" "$project/program.c" -o "$project/build/program.hex" --assembly "$project/build/program.asm"
"${PYTHON:-python3}" "$repo/tools/build_map.py" "$project/build/program.asm" "$project/build/program.hex"
