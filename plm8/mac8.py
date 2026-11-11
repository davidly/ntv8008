#!/usr/bin/env python3
"""Run the original Intel MAC8 2.4 8008 macro cross-assembler and write modern Intel HEX."""
import argparse
import os
from pathlib import Path
import re
import sys
import tempfile

from compile import CompileError, convert_hex
import ka10
from pdp10 import NATIVE, PDP10

UPSTREAM = Path(__file__).resolve().parent / 'upstream'
# Listing to FOR22.DAT, then read the rest from FOR20.DAT. MAC8 takes later
# control lines from the new input unit, so $I must come last. The default
# hexadecimal object goes to FOR21.DAT.
CONTROLS = '$O=3\n$I=2\n'
# The 4,460-line b8008 interpreter takes 150-200M PDP-10 instructions.
BUDGET = 1_000_000_000


def code_field(line):
    """Return the part of a source line before any comment."""
    quoted = False
    for index, character in enumerate(line):
        if character == "'":
            quoted = not quoted  # a doubled quote toggles twice
        elif character == ';' and not quoted:
            return line[:index]
    return line


def assemble_object(source, symbols=False, expanded=False):
    """Return MAC8's own object file and the listing; symbols adds its symbol table.

    expanded selects MAC8E, the 1975 expanded MAC8 2.3, whose symbol table is
    eight times larger.
    """
    source.encode('ascii')
    lines = source.expandtabs(8).splitlines()
    for number, line in enumerate(lines, 1):
        code = code_field(line).rstrip()
        # MAC8's character table covers space through Z. Others, including
        # lowercase, become spaces even inside strings, so reject them.
        for character in code:
            if not ' ' <= character <= 'Z':
                raise CompileError(f'line {number}: character {character!r} is outside the MAC8 alphabet; '
                                   'use uppercase source and numeric values for other characters')
        # Columns past 72 are silently ignored, which can change an operand.
        if len(code) > 72:
            raise CompileError(f'line {number}: code exceeds MAC8\'s 72-column limit (comments may be longer)')
        if code.startswith('$'):
            raise CompileError(f'line {number}: MAC8 control lines are set by this wrapper')
    if not any(re.match(r'([A-Z][A-Z0-9]*:?)?\s+END\s*$', code_field(line)) for line in lines):
        lines.append('        END')
    with tempfile.TemporaryDirectory(prefix='mac8-') as directory:
        Path(directory, 'FOR20.DAT').write_text('\n'.join(lines) + '\n', encoding='ascii')
        image = UPSTREAM / ('mac8e.sav' if expanded else 'mac8.sav')
        runner = PDP10(image, ('$T=1\n' if symbols else '') + CONTROLS, directory)
        try:
            native = NATIVE.is_file() and not os.environ.get('PLM8_PYTHON')
            console = runner.run_native(BUDGET) if native else runner.run(BUDGET)
        except (RuntimeError, OSError, StopIteration, ZeroDivisionError) as error:
            raise CompileError(f'{image.name}: {error}\n{runner.output.getvalue()}') from error
        listing = Path(directory, 'FOR22.DAT').read_text(encoding='ascii').replace('\r', '')
        if 'NO PROGRAM ERRORS' not in console:
            # MAC8 flags each erroneous listing line in its first column.
            flagged = [line for line in listing.splitlines() if re.match(r' [A-Z] ', line)]
            raise CompileError('\n'.join(flagged + [console.strip().splitlines()[-1]]))
        return Path(directory, 'FOR21.DAT').read_text(encoding='ascii'), listing


def assemble_source(source, expanded=False):
    result, listing = assemble_object(source, expanded=expanded)
    return convert_hex(result), listing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('-o', '--output', type=Path, help='HEX path (default: source.hex)')
    parser.add_argument('--listing', type=Path, help='save the assembler listing')
    parser.add_argument('--expanded', action='store_true',
                        help='use MAC8E, the expanded 2.3 assembler with about 4,000 symbols instead of 500')
    parser.add_argument('--ka10', action='store_true', help='report how long MAC8 took on a 1967 DEC KA10')
    args = parser.parse_args()
    if args.ka10:
        PDP10.timers = []
    try:
        output, listing = assemble_source(args.source.read_text(encoding='ascii'), args.expanded)
        if args.listing:
            args.listing.write_text(listing, encoding='ascii')
        destination = args.output or args.source.with_suffix('.hex')
        destination.write_bytes(output.encode('ascii'))
        print(f'{args.source}: assembled to {destination}')
        if args.ka10:
            print(ka10.report(PDP10.timers), file=sys.stderr)
    except (OSError, ValueError, CompileError) as error:
        print(f'MAC8: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
