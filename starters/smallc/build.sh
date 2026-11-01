#!/bin/sh
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$project/../.." && pwd)
mkdir -p "$project/build"
"${PYTHON:-python3}" "$repo/smallc/compile.py" "$project/program.c" -o "$project/build/program.hex" --assembly "$project/build/program.asm"
