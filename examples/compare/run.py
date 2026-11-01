#!/usr/bin/env python3
"""Build and measure equivalent sum-1-through-10 programs; all must print 55."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SUFFIX = '.exe' if os.name == 'nt' else ''
LANGUAGES = ('assembly', 'b8008', 'smallc', 'ack', 'pascal', 'modula2', 'occam')


def measure(language):
    build = HERE/'build'
    build.mkdir(exist_ok=True)
    image = build/(language+'.hex')
    if language == 'assembly':
        subprocess.run([sys.executable, str(ROOT/'tools/build_map.py'), str(HERE/'sum.asm'), str(image)],
                       check=True, capture_output=True)
    elif language == 'b8008':
        image = ROOT/'a08/b8008.hex'
    else:
        compiler = {'smallc':'smallc/compile.py', 'ack':'ack/compile.py',
                    'pascal':'ack/pascal.py', 'modula2':'ack/modula2.py', 'occam':'ack/occam.py'}[language]
        extension = {'pascal':'.p','modula2':'.mod','occam':'.ocm'}.get(language,'.c')
        subprocess.run([sys.executable, str(ROOT/compiler), str(HERE/('sum'+extension)),
                        '-o', str(image), '--assembly', str(build/(language+'.asm'))],
                       check=True, capture_output=True)
    command = [str(ROOT/('ntv8008'+SUFFIX)), '-p', '-n:20000000']
    if language == 'b8008':
        command.append('-l:'+str(HERE/'sum.bas'))
    result = subprocess.run(command+[str(image)], capture_output=True, timeout=30, check=True)
    output = result.stdout.decode().replace('\r\n','\n')
    if language == 'b8008':
        output = output.split('>RUN\n')[-1]
        if output != '55\n>':
            raise ValueError('unexpected BASIC output: '+repr(output))
    elif output != '55\n':
        raise ValueError('unexpected output: '+repr(output))
    cycles = int(re.search(rb'(\d+) cycles', result.stderr)[1])
    loaded = sum(int(line[1:3],16) for line in image.read_text().splitlines() if line[7:9]=='00')
    return loaded, cycles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--languages', nargs='+', choices=LANGUAGES, default=LANGUAGES)
    args = parser.parse_args()
    print('| Language | Loaded image bytes | Clock periods | Seconds at 500 kHz |')
    print('| --- | ---: | ---: | ---: |')
    for language in args.languages:
        size, cycles = measure(language)
        print(f'| {language} | {size:,} | {cycles:,} | {cycles/500000:.6f} |', flush=True)


if __name__ == '__main__':
    main()
