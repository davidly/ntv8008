#!/usr/bin/env python3
"""Build, verify, and measure three pairs of C optimization examples."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
EXPECTED = {'words':8128, 'bytes':8128, 'calls':16256, 'inline':16256,
            'remainder':568, 'counter':568}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compilers', nargs='+', choices=('smallc','ack'), default=('smallc','ack'))
    args = parser.parse_args()
    build = HERE/'build'
    build.mkdir(exist_ok=True)
    print('| Compiler | Variant | Loaded bytes | Clock periods |')
    print('| --- | --- | ---: | ---: |')
    for compiler in args.compilers:
        for variant, expected in EXPECTED.items():
            image = build/(compiler+'-'+variant+'.hex')
            assembly = image.with_suffix('.asm')
            subprocess.run([sys.executable, str(ROOT/compiler/'compile.py'), str(HERE/(variant+'.c')),
                            '-o', str(image), '--assembly', str(assembly)], check=True, capture_output=True)
            result = subprocess.run([str(ROOT/('ntv8008.exe' if os.name=='nt' else 'ntv8008')),
                                     '-p', '-n:20000000', str(image)], check=True, capture_output=True, timeout=30)
            if result.stdout.replace(b'\r\n',b'\n') != (str(expected)+'\n').encode():
                raise ValueError(f'{compiler}/{variant}: unexpected output {result.stdout!r}')
            cycles = int(re.search(rb'(\d+) cycles', result.stderr)[1])
            size = sum(int(line[1:3],16) for line in image.read_text().splitlines() if line[7:9]=='00')
            print(f'| {compiler} | {variant} | {size:,} | {cycles:,} |', flush=True)


if __name__ == '__main__':
    main()
