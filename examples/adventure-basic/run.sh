#!/bin/sh
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$project/../.." && pwd)
mkdir -p "$project/build"
# The interpreter reads the program, RUN command, and INPUT response in order.
cat "$project/program.bas" "$project/input.txt" > "$project/build/session.bas"
exec "$repo/ntv8008" "$@" "-l:$project/build/session.bas" "$repo/a08/b8008.hex"
