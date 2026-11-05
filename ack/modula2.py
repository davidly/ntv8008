#!/usr/bin/env python3
"""Compile integer Modula-2 using ACK and this project's native 8008 backend."""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from codegen import CodegenError, generate
from compile import ROOT, HERE, TOOLS, SUFFIX, run, compile_c_unit, assemble_fitting
from wirth import trim_runtime, lower_fixed_arrays

M2_SIZES = '-Vw2.2i2.2s2.2l4.2p2.2f4.2d8.2'
RUNTIME = HERE / 'modula2'


def namespace_procedures(program):
    aliases = {'$__M2M_': '$_m_a_i_n', '$_InOut_': '$_m2_init'}
    for name in re.findall(r'^ pro (\$[^,]+),', program, re.M):
        aliases.setdefault(name, '$M2_' + name[1:])
    def rename(match):
        return match[1] + aliases.get(match[2], match[2])
    return re.sub(r'^( (?:pro|cal|exp|inp|lpi) )(\$[^,\s]+)',
                  rename, program, flags=re.M)


def power_of_two_division(text):
    """Inline floor DIV/MOD by a positive power of two.

    runtime.c's dvi/rmi round toward negative infinity. For divisor 2**k that
    is an arithmetic right shift by k, and a mask of the low k bits.
    """
    def rewrite(match):
        divisor=int(match[1])
        if divisor<=0 or divisor>16384 or divisor&(divisor-1):return match[0]
        if match[2]=='rmi':return ' loc %d\n and 2' % (divisor-1)
        return ' loc %d\n sri 2' % (divisor.bit_length()-1)
    return re.sub(r'^ loc (\d+)\n cal \$(dvi|rmi)\n asp 4\n lfr 2$',rewrite,text,flags=re.M)


def compile_source(source):
    for tool in ('em_m2','cpp.ansi','em_cemcom.ansi','em_opt','em_decode'):
        if not (TOOLS / (tool+SUFFIX)).is_file():
            raise CodegenError('ACK Modula-2 tools not built; run ack/build.sh')
    assembler = ROOT / 'a08' / ('a08'+SUFFIX)
    if not assembler.is_file():
        raise CodegenError('A08 not built; run a08/m.sh or a08/m.bat')
    with tempfile.TemporaryDirectory(prefix='ack Modula2 ') as directory:
        work = Path(directory)
        # Stable source name keeps compiler filename strings reproducible across
        # operating systems, source locations, and temporary directory names.
        (work/'program.mod').write_bytes(Path(source).read_text().encode('ascii'))
        run([TOOLS/('em_m2'+SUFFIX), M2_SIZES, '-R', '-L', '-I'+str(RUNTIME), 'program.mod', 'program.k'], cwd=work)
        (work/'program.opt.k').write_bytes(run([TOOLS/('em_opt'+SUFFIX)],
                                              input=(work/'program.k').read_bytes()))
        run([TOOLS/('em_decode'+SUFFIX), work/'program.opt.k', work/'program.e'])
        program = power_of_two_division(lower_fixed_arrays(namespace_procedures((work/'program.e').read_text())))
        units = [compile_c_unit(RUNTIME/'runtime.c', work, 'support'),
                 compile_c_unit(HERE/'pascal/runtime.c', work, 'arrays'),
                 compile_c_unit(HERE/'console.c', work, 'console')]
        units = [program, *trim_runtime(program, units)]
        image, assembly = assemble_fitting(units, work, assembler, pascal=True)
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
        print('ACK Modula-2/8008: '+str(error),file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    sys.exit(main())
