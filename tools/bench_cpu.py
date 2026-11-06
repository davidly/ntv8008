#!/usr/bin/env python3
"""Compare runtime opcode decoding with specialized dispatch and inline helpers."""
import argparse
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
from bench_parity import ROOT, command, pin


def variants(source, header):
    start = source.index('    switch ( op )\n', source.index('I8008_FORCE_INLINE unsigned I8008::execute('))
    end = source.index('    unsigned clocks = ', start)
    runtime = source[:start]+'    states = execute_decoded( op );\n'+source[end:]
    # Restore ordinary compiler inlining choices for the runtime baseline.
    for signature in ('uint8_t I8008::fetch(', 'void I8008::set_reg(',
                      'void I8008::set_szp(', 'bool I8008::condition(', 'void I8008::alu('):
        runtime = runtime.replace('I8008_FORCE_INLINE '+signature, signature)
    runtime_header = header
    for signature in ('uint16_t pc() const', 'uint16_t address() const', 'uint8_t get_reg('):
        runtime_header = runtime_header.replace('I8008_FORCE_INLINE '+signature, signature)
    return {'runtime':(runtime,runtime_header), 'specialized':(source,header)}


def stop_variants(source, header):
    """Reconstruct the previous stop-field checks, retaining opcode dispatch."""
    before = source.replace('4 | executionStopped', '4')
    before = before.replace('                    states |= executionStopped;\n', '')
    before = before.replace('( states & 0xff ) * 2', 'states * 2')
    before = before.replace('( states & executionStopped ) && m_tracer',
                            'm_tracer && ( halted || invalid )')
    if before == source:
        raise ValueError('cannot locate decoder stop markers')
    return {'runtime':(before,header), 'specialized':(source,header)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', choices=('gcc','msvc'), default='msvc' if os.name=='nt' else 'gcc')
    parser.add_argument('--samples', type=int, default=6)
    parser.add_argument('--pin', type=int)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--extra', action='store_true', help='also measure assembly and SmallC sieve/e/TTT')
    parser.add_argument('--stop-check', action='store_true',
                        help='compare stop-field checks with decoder stop markers instead of opcode decoding')
    args = parser.parse_args()
    if args.samples < 1 or (args.pin is not None and args.pin < 0):
        parser.error('samples must be positive and CPU number nonnegative')
    if args.pin is not None:
        pin(args.pin)
    workloads = {'sieve':ROOT/'ack/examples/sieve.hex', 'e':ROOT/'ack/examples/e.hex',
                 'ttt':ROOT/'ack/examples/ttt.hex', 'basic-e':ROOT/'a08/b8008.hex'}
    if args.extra:
        for language, folder in (('asm','a08'),('smallc','smallc/examples')):
            for app in ('sieve','e','ttt'):
                workloads[language+'-'+app] = ROOT/folder/(app+'.hex')
    for image in workloads.values():
        if not image.is_file():
            parser.error(f'missing image {image}; run setup --ack --smallc first')
    implementations = (stop_variants if args.stop_check else variants)(
        (ROOT/'i8008.cxx').read_text(), (ROOT/'i8008.hxx').read_text())
    suffix = '.exe' if os.name=='nt' else ''
    samples, checks = {}, {}
    with tempfile.TemporaryDirectory(prefix='8008 decode ') as directory:
        work = Path(directory)
        for name, (source, header) in implementations.items():
            candidate = work/name
            candidate.mkdir()
            (candidate/'i8008.cxx').write_text(source)
            (candidate/'i8008.hxx').write_text(header)
            shutil.copy2(ROOT/'trace.hxx', candidate/'trace.hxx')
            for kind, path in (('bench', ROOT/'tools/parity_bench.cxx'), ('cpu', ROOT/'tests/cpu.cxx')):
                output = candidate/(kind+suffix)
                if args.compiler=='msvc':
                    options = ['cl','/nologo','/std:c++14','/EHsc','/O2','/GL','/W4',
                               '/D_CRT_SECURE_NO_WARNINGS','/I'+str(candidate),path,
                               candidate/'i8008.cxx','/Fe:'+str(output),'/link','/LTCG']
                else:
                    options = ['g++','-std=c++11','-O3','-flto','-Wall','-Wextra','-pedantic',
                               '-I'+str(candidate),path,candidate/'i8008.cxx','-o',output]
                command(options, candidate)
            command([candidate/('cpu'+suffix), candidate/'cpu.log'], candidate)
        rng = random.Random(8008)
        for round in range(args.samples+1):
            jobs = [(v,w) for v in implementations for w in workloads]
            rng.shuffle(jobs)
            for variant, workload in jobs:
                invocation = [work/variant/('bench'+suffix), workloads[workload]]
                if workload=='basic-e':
                    invocation.append(ROOT/'b8008/examples/e.bas')
                fields = command(invocation, work).decode().split()
                runs, seconds = int(fields[0]), float(fields[1])
                check = fields[2:]
                if workload in checks and checks[workload] != check:
                    raise ValueError(f'{variant}/{workload}: cycles or console output changed')
                checks[workload] = check
                if round:
                    samples.setdefault(variant,{}).setdefault(workload,[]).append(seconds/runs)
            print(f'Finished {"warmup" if round==0 else "sample "+str(round)}', file=sys.stderr, flush=True)
    medians = {v:{w:statistics.median(t) for w,t in ws.items()} for v,ws in samples.items()}
    print('| Workload | '+('Stop fields (ms) | Decoder marker (ms)' if args.stop_check else
                          'Runtime decode (ms) | Specialized (ms)')+' | Host time saved |')
    print('| --- | ---: | ---: | ---: |')
    for w in workloads:
        before, after = medians['runtime'][w], medians['specialized'][w]
        print(f'| {w} | {before*1000:.3f} | {after*1000:.3f} | {100*(1-after/before):.1f}% |')
    if args.output:
        args.output.write_text(json.dumps({'compiler':args.compiler,'pin':args.pin,
            'samples':samples,'medians':medians,'checks':checks}, indent=2)+'\n')


if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
        sys.exit(str(error))
