#!/usr/bin/env python3
"""Build Wumpus with SmallC (default) or ACK C, retaining a listing and map."""
import argparse
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('compiler', nargs='?', choices=('smallc','ack'), default='smallc')
    args = parser.parse_args()
    build = HERE/'build'
    build.mkdir(exist_ok=True)
    image = build/(args.compiler+'.hex')
    assembly = image.with_suffix('.asm')
    subprocess.run([sys.executable, str(ROOT/args.compiler/'compile.py'), str(HERE/'program.c'),
                    '-o', str(image), '--assembly', str(assembly)], check=True)
    subprocess.run([sys.executable, str(ROOT/'tools/build_map.py'), str(assembly), str(image)], check=True)


if __name__ == '__main__':
    main()
