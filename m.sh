#!/bin/sh
set -eu
cd "$(dirname "$0")"
${CXX:-c++} -std=c++11 -O3 -flto -Wall -Wextra -pedantic ntv8008.cxx i8008.cxx -o ntv8008
${CXX:-c++} -std=c++11 -O3 -flto -Wall -Wextra -pedantic plm8/pdp10.cxx -o plm8/pdp10
