#!/usr/bin/env python3
"""Run a bounded emulator application and check its console output."""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expect', required=True, type=Path)
    parser.add_argument('--contains', action='store_true', help='match a result fragment instead of exact output')
    parser.add_argument('--after', help='check output after the last marker, e.g. >RUN')
    parser.add_argument('--reject', action='append', default=[], help='reject an error substring; repeat as needed')
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command[:1] == ['--']:
        command = command[1:]
    if not command:
        parser.error('supply an emulator command after --, including a -n: cycle budget')
    if not any(item.startswith('-n:') for item in command):
        parser.error('the emulator command must include a -n: cycle budget')
    try:
        result = subprocess.run(command, capture_output=True, timeout=args.timeout)
        output = result.stdout.decode(errors='replace').replace('\r\n', '\n')
        if result.returncode:
            raise ValueError(f'process exited {result.returncode}: ' + result.stderr.decode(errors='replace'))
        if args.after:
            if args.after not in output:
                raise ValueError('missing execution marker: ' + args.after)
            output = output.rsplit(args.after, 1)[1].lstrip('\n')
        for message in args.reject:
            if message in output:
                raise ValueError('target error: ' + message)
        expected = args.expect.read_text().replace('\r\n', '\n')
        if not (expected in output if args.contains else expected == output):
            raise ValueError(f'output mismatch: expected {expected!r}, received {output!r}')
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        return 1
    print('Output matched.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
