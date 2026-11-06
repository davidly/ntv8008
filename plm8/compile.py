#!/usr/bin/env python3
"""Run the original Intel PL/M-8 3.3 cross-compiler and write modern Intel HEX."""
import argparse
import os
from pathlib import Path
import re
import sys
import tempfile

from pdp10 import NATIVE, PDP10

UPSTREAM = Path(__file__).resolve().parent / 'upstream'


class CompileError(Exception):
    pass


def convert_hex(text):
    """Remove paper-tape framing and replace the 1970s zero-length terminator."""
    lines = []
    ended = False
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(':'):
            if line and line != '$' and set(line) != {'*'}:
                raise CompileError('unrecognized compiler object-file framing')
            continue
        if ended:
            raise CompileError('object data after end record')
        try:
            raw = bytes.fromhex(line[1:])
        except ValueError as error:
            raise CompileError('invalid compiler HEX record') from error
        if len(raw) < 5 or len(raw) != raw[0] + 5 or sum(raw) & 255:
            raise CompileError('invalid compiler HEX length or checksum')
        address = int.from_bytes(raw[1:3], 'big')
        if raw[3] != 0 or address + raw[0] > 16384:
            raise CompileError('compiler output is outside 8008 RAM')
        if raw[0] == 0:
            if address:
                raise CompileError('invalid compiler end record')
            lines.append(':00000001FF')
            ended = True
        else:
            lines.append(':' + raw.hex().upper())
    if not ended or len(lines) < 2:
        raise CompileError('incomplete or empty compiler output')
    return '\n'.join(lines) + '\n'


def compile_source(source):
    source.encode('ascii')
    # The original lexer maps characters outside its 52-character alphabet
    # to spaces, even inside strings. Reject them rather than changing text.
    code = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
    allowed = set(" ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789$=./()+-'*,<>:;\n\r\t")
    for character in code:
        if character not in allowed:
            raise CompileError(f'character {character!r} is outside the original PL/M alphabet; '
                               'use uppercase source and numeric ASCII values for other characters')
    for number, line in enumerate(source.splitlines(), 1):
        if len(line.expandtabs(8)) > 72:
            raise CompileError(f'line {number} exceeds the compiler\'s 72-column limit')
    # EOF is a PL/M token, not host EOF. Accept files with or without it.
    if not re.search(r'\bEOF\s*$', source):
        source = source.rstrip() + '\nEOF\n'
    logs = []
    with tempfile.TemporaryDirectory(prefix='plm8-') as directory:
        for name, data in (('plm1.sav', source.expandtabs(8)),
                           ('plm2.sav', '$B=7\n$Q=1\n$F=1\n$G=1\n$M=1\n\n')):
            runner = PDP10(UPSTREAM / name, data, directory)
            try:
                # The native runner is much faster; PLM8_PYTHON=1 forces the reference.
                native = NATIVE.is_file() and not os.environ.get('PLM8_PYTHON')
                listing = runner.run_native() if native else runner.run()
            except (RuntimeError, OSError, StopIteration, ZeroDivisionError) as error:
                raise CompileError(f'{name}: {error}\n{runner.output.getvalue()}') from error
            logs.append(listing)
            if 'NO PROGRAM ERRORS' not in listing or re.search(r'\bERROR\s+\d+', listing):
                raise CompileError('\n'.join(logs))
        result = Path(directory, 'FOR21.DAT').read_text(encoding='ascii')
        return convert_hex(result), '\n'.join(logs).replace('\r', '')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('-o', '--output', type=Path, help='HEX path (default: source.hex)')
    parser.add_argument('--listing', type=Path, help='save both compiler passes\' listings')
    args = parser.parse_args()
    try:
        output, listing = compile_source(args.source.read_text(encoding='ascii'))
        if args.listing:
            args.listing.write_text(listing, encoding='ascii')
        destination = args.output or args.source.with_suffix('.hex')
        destination.write_bytes(output.encode('ascii'))
        print(f'{args.source}: compiled to {destination}')
    except (OSError, ValueError, CompileError) as error:
        print(f'PL/M-8: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
