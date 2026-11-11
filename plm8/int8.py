#!/usr/bin/env python3
"""Run 8008 programs in Intel's original INTERP/8 2.1 simulator (INT8)."""
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
CONSOLE = 0o101 | 10 << 1  # OUT 10, ntv8008's console port
# INTERP/8 counts 8008 states, and adds 16 once, when a session first runs;
# HLT itself costs the usual 4. ntv8008 counts clock periods, two per state.
START_STATES = 16


def read_hex(text):
    """Return the memory image of an Intel HEX file."""
    memory = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = bytes.fromhex(line[1:]) if line[0] == ':' else b''
        except ValueError:
            raw = b''
        if len(raw) < 5 or len(raw) != raw[0] + 5 or sum(raw) & 255:
            raise CompileError(f'invalid Intel HEX record: {line}')
        address = int.from_bytes(raw[1:3], 'big')
        if raw[3] == 1:
            return memory
        if raw[3] != 0 or address + raw[0] > 16384:
            raise CompileError(f'unsupported or out-of-range HEX record: {line}')
        memory.update((address + i, b) for i, b in enumerate(raw[4:-1]))
    raise CompileError('HEX file has no end record')


def mac8_object(memory):
    """Write memory as a MAC8-style hexadecimal object, the format INT8 loads."""
    lines, addresses = [], sorted(memory)
    index = 0
    while index < len(addresses):
        start, data = addresses[index], []
        # INT8 accepts at most 16 data bytes per record.
        while index < len(addresses) and addresses[index] == start + len(data) and len(data) < 16:
            data.append(memory[addresses[index]])
            index += 1
        record = bytes([len(data), start >> 8, start & 255, 0, *data])
        lines.append(' :' + (record + bytes([-sum(record) & 255])).hex().upper())
    return ' $\n' + '\n'.join(lines) + '\n :0000000000\n $\n'


def load_program(path):
    """Return the object file text, INT8's LOAD command and the memory image."""
    text = Path(path).read_text(encoding='ascii')
    if Path(path).suffix.lower() == '.hex':
        memory = read_hex(text)
        return mac8_object(memory), 'LOAD 7.', memory
    import mac8
    obj, _ = mac8.assemble_object(text, symbols=True)
    # The symbol table ends at the first $ line; the HEX records follow.
    return obj, 'LOAD 7 7.', read_hex(convert_hex(obj.split(' $\n', 1)[1]))


def simulate(obj, commands, budget):
    """Run one INT8 session and return its console transcript."""
    with tempfile.TemporaryDirectory(prefix='int8-') as directory:
        Path(directory, 'FOR21.DAT').write_text(obj, encoding='ascii')
        runner = PDP10(UPSTREAM / 'int8.sav', commands, directory)
        try:
            native = NATIVE.is_file() and not os.environ.get('PLM8_PYTHON')
            return (runner.run_native(budget) if native else runner.run(budget)).replace('\r', '')
        except (RuntimeError, OSError, StopIteration, ZeroDivisionError) as error:
            raise CompileError(f'int8.sav: {error}\n{runner.output.getvalue()}') from error


def check(transcript):
    for line in transcript.splitlines():
        if 'ERROR' in line:
            raise CompileError('INTERP/8: ' + line.strip())


def run_program(obj, load, memory, entry=64, limit=2_000_000_000):
    """Run to HLT; return console output and the ntv8008-equivalent clock periods.

    The output is the A register at every executed OUT 10, recovered from an
    INT8 trace of exactly the addresses that hold that opcode.
    """
    states = limit // 2 + START_STATES
    traces = ''.join(f'TRACE {a}.\n' for a in sorted(memory) if memory[a] == CONSOLE)
    session = f'$F\n{load}\n{traces}CYCLE {states}.\nSET PC = {entry}.\nGO.\n$E\n'
    # Roughly 35 PDP-10 instructions simulate one 8008 state.
    transcript = simulate(obj, session, 100 * states + 50_000_000)
    check(transcript)
    if 'CYCLE AT' in transcript:
        raise CompileError(f'INTERP/8: no HLT within {limit} clock periods')
    halted = re.search(r'^HLT CYCLE (\d+)$', transcript, re.M)
    if not halted:
        raise CompileError('INTERP/8 did not halt:\n' + transcript)
    output, a = [], None
    for line in transcript.splitlines():
        row = re.match(r'[ *]\d{4}[ *](\d{3})[ *]', line)
        if row:
            a = int(row.group(1))
        elif line.strip() == 'O10' and a is not None:
            character = chr(a & 127)  # ntv8008's 7-bit console maps CR to LF
            output.append('\n' if character == '\r' else character)
    return ''.join(output), 2 * (int(halted.group(1)) - START_STATES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('program', type=Path, help='Intel HEX file, or MAC8 source (.asm) assembled with symbols')
    parser.add_argument('-a', '--address', type=lambda s: int(s, 0), default=64, help='entry address (default 64)')
    parser.add_argument('-n', '--cycles', type=int, default=2_000_000_000,
                        help='fail without HLT after this many clock periods')
    parser.add_argument('-p', action='store_true', help='report clock periods, as ntv8008 -p does')
    parser.add_argument('--commands', type=Path,
                        help='run this INT8 command session after loading instead of running to HLT')
    parser.add_argument('--ka10', action='store_true', help='report how long INT8 took on a 1967 DEC KA10')
    args = parser.parse_args()
    try:
        obj, load, memory = load_program(args.program)
        if args.ka10:
            PDP10.timers = []
        if args.commands:
            session = args.commands.read_text(encoding='ascii')
            if not re.search(r'^\$E\s*$', session, re.M):
                session += '\n$E\n'
            print(simulate(obj, f'$F\n{load}\nSET PC = {args.address}.\n{session}', 10 ** 11), end='')
            if args.ka10:
                print(ka10.report(PDP10.timers), file=sys.stderr)
            return 0
        output, clocks = run_program(obj, load, memory, args.address, args.cycles)
        sys.stdout.write(output)
        if args.p:
            print(f'{clocks} cycles (INTERP/8 {clocks // 2 + START_STATES} states)')
        if args.ka10:
            print(ka10.report(PDP10.timers), file=sys.stderr)
    except (OSError, ValueError, CompileError) as error:
        print(f'INT8: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
