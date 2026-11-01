#!/bin/sh
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$project/../.." && pwd)
mkdir -p "$project/build"
"$repo/a08/a08" "$project/program.asm" "-o$project/build/program.hex"
