#!/bin/sh
set -eu
cd "$(dirname "$0")"
./m.sh
python3 tests/basic_benchmarks.py
