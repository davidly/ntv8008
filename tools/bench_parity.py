#!/usr/bin/env python3
"""Compare parity implementations using real 8008 applications, without host console I/O."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def pin(cpu):
    if os.name == 'nt':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        if not kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(), 1 << cpu):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        os.sched_setaffinity(0, {cpu})


def candidates():
    table = '\n'.join('        '+', '.join('true' if bin(i).count('1') % 2 == 0 else 'false'
                         for i in range(start, start+16))+',' for start in range(0, 256, 16))
    return {
        'fold': '    value ^= value >> 4;\n    value ^= value >> 2;\n    value ^= value >> 1;\n    fParity = ( 0 == ( value & 1 ) );',
        'nibble': '    value ^= value >> 4;\n    fParity = ( 0 != ( ( 0x9669u >> ( value & 15 ) ) & 1 ) );',
        'table': '    static const bool evenParity[ 256 ] = {\n'+table+'\n    };\n    fParity = evenParity[ value ];',
        'builtin': '    fParity = ( 0 == __builtin_parity( unsigned( value ) ) );',
    }


def command(args, cwd):
    result = subprocess.run(list(map(str, args)), cwd=cwd, capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', choices=('gcc', 'msvc'), default='msvc' if os.name == 'nt' else 'gcc')
    parser.add_argument('--samples', type=int, default=6)
    parser.add_argument('--pin', type=int, help='pin to this logical CPU (optional, inherited by child processes)')
    parser.add_argument('--output', type=Path, help='save raw samples, medians, target cycle counts and output hashes as JSON')
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('--samples must be positive')
    if args.pin is not None:
        if args.pin < 0:
            parser.error('--pin must be nonnegative')
        pin(args.pin)
    workloads = {'sieve': ROOT/'ack/examples/sieve.hex', 'e': ROOT/'ack/examples/e.hex',
                 'ttt': ROOT/'ack/examples/ttt.hex', 'basic-e': ROOT/'a08/b8008.hex'}
    for image in workloads.values():
        if not image.is_file():
            parser.error(f'missing {image}; run setup --ack first')
    variants = candidates()
    if args.compiler == 'msvc':
        variants.pop('builtin')
    source = (ROOT/'i8008.cxx').read_text()
    pattern = r'void I8008::set_szp\( uint8_t value \)\n\{.*?\n\} //set_szp'
    if len(re.findall(pattern, source, re.S)) != 1:
        raise ValueError('cannot locate set_szp()')
    samples, checks = {}, {}
    suffix = '.exe' if os.name == 'nt' else ''
    with tempfile.TemporaryDirectory(prefix='8008 parity ') as directory:
        work = Path(directory)
        for name, body in variants.items():
            candidate = work/name
            candidate.mkdir()
            for header in ('i8008.hxx', 'trace.hxx'):
                shutil.copy2(ROOT/header, candidate/header)
            implementation = ('void I8008::set_szp( uint8_t value )\n{\n'
                              '    fZero = ( 0 == value );\n'
                              '    fSign = ( 0 != ( value & 0x80 ) );\n'+body+'\n} //set_szp')
            (candidate/'i8008.cxx').write_text(re.sub(pattern, lambda _: implementation, source, flags=re.S))
            for kind, path in (('bench', ROOT/'tools/parity_bench.cxx'), ('cpu', ROOT/'tests/cpu.cxx')):
                output = candidate/(kind+suffix)
                if args.compiler == 'msvc':
                    options = ['cl', '/nologo', '/std:c++14', '/EHsc', '/O2', '/GL', '/W4',
                               '/D_CRT_SECURE_NO_WARNINGS', '/I'+str(candidate), path,
                               candidate/'i8008.cxx', '/Fe:'+str(output), '/link', '/LTCG']
                else:
                    options = ['g++', '-std=c++11', '-O3', '-flto', '-Wall', '-Wextra', '-pedantic',
                               '-I'+str(candidate), path, candidate/'i8008.cxx', '-o', output]
                command(options, candidate)
            command([candidate/('cpu'+suffix), candidate/'cpu.log'], candidate)
        rng = random.Random(8008)
        for round in range(args.samples+1):
            jobs = [(v, w) for v in variants for w in workloads]
            rng.shuffle(jobs)
            for variant, workload in jobs:
                invocation = [work/variant/('bench'+suffix), workloads[workload]]
                if workload == 'basic-e':
                    invocation.append(ROOT/'b8008/examples/e.bas')
                fields = command(invocation, work).decode().split()
                runs, seconds = int(fields[0]), float(fields[1])
                check = fields[2:]
                if workload in checks and checks[workload] != check:
                    raise ValueError(f'{variant}/{workload}: target cycles or output changed')
                checks[workload] = check
                if round:
                    samples.setdefault(variant, {}).setdefault(workload, []).append(seconds/runs)
            print(f'Finished {"warmup" if round == 0 else "sample " + str(round)}', file=sys.stderr, flush=True)
    medians = {v: {w: statistics.median(times) for w, times in ws.items()} for v, ws in samples.items()}
    print('| Variant | '+ ' | '.join(workloads)+' |')
    print('| --- |'+' ---: |'*len(workloads))
    for v in variants:
        print('| '+v+' | '+' | '.join(f'{medians[v][w]*1000:.3f}' for w in workloads)+' |')
    print('Milliseconds per application; CPU-only, six samples by default, one warmup round.')
    if args.output:
        args.output.write_text(json.dumps({'compiler':args.compiler, 'pin':args.pin,
            'samples':samples, 'medians':medians, 'checks':checks}, indent=2)+'\n')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        sys.exit(str(error))
