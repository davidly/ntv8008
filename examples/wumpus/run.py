#!/usr/bin/env python3
"""Run Wumpus: run.py [smallc|ack] [emulator options]. Build first."""
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
options = sys.argv[1:]
compiler = options.pop(0) if options and options[0] in ('smallc','ack') else 'smallc'
sys.exit(subprocess.call([str(ROOT/('ntv8008.exe' if os.name=='nt' else 'ntv8008')),
                         *options, str(HERE/'build'/(compiler+'.hex'))]))
