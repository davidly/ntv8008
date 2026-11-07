#!/usr/bin/env python3
"""Run core and available language tests, explicitly reporting optional skips."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compile',action='store_true',help='also rebuild/test ACK and SmallC host toolchains; run setup.py --all first')
    parser.add_argument('--basic-benchmarks',action='store_true',help='include slow optional SCELBAL benchmarks')
    args=parser.parse_args()
    compilers={'ack','smallc','pascal','modula2','ack_basic','occam','snake','native_codegen','starters','practical','wumpus'}
    tests=('wumpus','practical','symbols','integration','starters','pdp10','plm8','mac8','forth','ack','smallc','robson','b8008','pascal',
           'modula2','occam','stack','snake','native_codegen','array_codegen','ack_bootstrap','ack_msvc','ack_codegen','runtime_prune','outline8008','occam_storage','smallc_codegen','ack_basic','publication')
    if args.basic_benchmarks:
        tests+=('basic_benchmarks',)
    for name in tests:
        command=[sys.executable,str(ROOT/'tests'/(name+'.py'))]
        if args.compile and name in compilers:
            command.append('--compile')
        print('\n=== '+name+' ===',flush=True)
        subprocess.run(command,cwd=ROOT,check=True)


if __name__=='__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
