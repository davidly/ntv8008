#!/usr/bin/env python3
"""Compile integer BASIC using ACK and this project's native 8008 backend."""
import argparse
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from codegen import CodegenError, generate
from compile import ROOT, HERE, TOOLS, SUFFIX, run, compile_c_unit
from wirth import trim_runtime, lower_fixed_arrays

BASIC_SIZES = '-Vw2p2f4'
RUNTIME = HERE / 'basic'
_spec=importlib.util.spec_from_file_location('basic_optimize',RUNTIME/'optimize.py')
_optimizations=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_optimizations)
lower_assignments=_optimizations.lower_assignments


def prepare_program(program):
    # EM's pointer-initialized BSS is one initialized word here.
    program=program.replace(' bss 2,dummy3,0',' con dummy3')
    program=re.sub(r'( bss \d+),0[IU]2,',r'\1,0,',program)
    # Keep user DEF FN names separate from C support functions.
    names={name:'$BASIC_'+name[1:] for name in
           re.findall(r'^ pro (\$[^,]+),',program,re.M) if name!='$main'}
    program=re.sub(r'^( (?:pro|cal|exp|inp|lpi) )(\$[^,\s]+)',
                   lambda m:m[1]+names.get(m[2],m[2]),program,flags=re.M)
    if re.search(r' loc (?!-1\n)-?\d+\n cal \$_setchan',program):
        raise CodegenError('only console I/O is supported; DATA/READ and file channels are unavailable')
    return lower_assignments(lower_fixed_arrays(program))


def compile_source(source):
    for tool in ('em_bem','cpp.ansi','em_cemcom.ansi','em_opt','em_decode'):
        if not (TOOLS / (tool+SUFFIX)).is_file():
            raise CodegenError('ACK BASIC tools not built; run ack/build.sh')
    assembler = ROOT / 'a08' / ('a08'+SUFFIX)
    if not assembler.is_file():
        raise CodegenError('A08 not built; run a08/m.sh or a08/m.bat')
    with tempfile.TemporaryDirectory(prefix='ack BASIC ') as directory:
        work = Path(directory)
        # Stable source name keeps compiler filename strings reproducible across
        # operating systems, source locations, and temporary directory names.
        text=Path(source).read_text()
        if not text.endswith('\n'): text+='\n'
        (work/'program.bas').write_bytes(text.encode('ascii'))
        run([TOOLS/('em_bem'+SUFFIX), BASIC_SIZES, '-8', 'program.bas', 'program.k', 'program.b'], cwd=work)
        (work/'program.opt.k').write_bytes(run([TOOLS/('em_opt'+SUFFIX)],
                                              input=(work/'program.k').read_bytes()))
        run([TOOLS/('em_decode'+SUFFIX), work/'program.opt.k', work/'program.e'])
        program = prepare_program((work/'program.e').read_text())
        if re.search(r'^ (?:adf|sbf|mlf|dvf|cmf|ngf|cif|cfi)\b|[Ff][48](?:,|$)',program,re.M):
            raise CodegenError('floating point is unsupported; use DEFINT A-Z (or % suffixes) and integer division \\')
        units = [compile_c_unit(RUNTIME/'runtime.c', work, 'support'),
                 compile_c_unit(HERE/'pascal/runtime.c', work, 'arrays'),
                 compile_c_unit(HERE/'console.c', work, 'console')]
        units = [program, *trim_runtime(program, units)]
        assembly = generate(units, pascal=True)
        (work/'program.asm').write_bytes(assembly.encode('ascii'))
        run([assembler, work/'program.asm', '-o'+str(work/'program.hex')])
        image = (work/'program.hex').read_text()
        end = 0
        for line in image.splitlines():
            record = bytes.fromhex(line[1:])
            if record[3] == 0:
                end = max(end, int.from_bytes(record[1:3],'big')+record[0])
        if end > 0x3d00:
            raise CodegenError('code/data exceed 15616 bytes; at least 512 bytes of stack required')
        return image, assembly, '\n'.join(units)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('-o','--output',type=Path)
    parser.add_argument('--assembly',type=Path)
    parser.add_argument('--em',type=Path)
    args = parser.parse_args()
    try:
        image, assembly, em = compile_source(args.source)
        if args.assembly:
            args.assembly.write_bytes(assembly.encode('ascii'))
        if args.em:
            args.em.write_bytes(em.encode('ascii'))
        output = args.output or args.source.with_suffix('.hex')
        output.write_bytes(image.encode('ascii'))
        print(f'{args.source}: compiled to {output}')
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print('ACK BASIC/8008: '+str(error),file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    sys.exit(main())
