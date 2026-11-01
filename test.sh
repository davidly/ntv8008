#!/bin/sh
set -eu
cd "$(dirname "$0")"
./m.sh
./a08/rebuild.sh hello.asm count.asm echo.asm sieve.asm e.asm ttt.asm robson.asm b8008.asm
build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT HUP INT TERM
${CXX:-c++} -std=c++11 -O3 -flto -Wall -Wextra -pedantic -I. tests/cpu.cxx i8008.cxx -o "$build_dir/cpu-test"
"$build_dir/cpu-test" "$build_dir/cpu.log"
"${PYTHON:-python3}" tests/run.py "$@"
