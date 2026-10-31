#!/usr/bin/env python3
"""Compile integer Pascal using ACK and this project's native 8008 backend."""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from codegen import CodegenError, generate
from compile import ROOT, HERE, TOOLS, SUFFIX, run, compile_c_unit
from wirth import trim_runtime, lower_fixed_arrays

PC_SIZES = '-Vw2.2i2.2l4.2p2.2f4.2'
RUNTIME = HERE / 'pascal'


def namespace_procedures(program):
    # Pascal identifiers must not collide with C support functions such as
    # main or putu. Keep the program entry and external runtime calls intact.
    names = {name: '$P_' + name[1:] for name in
             re.findall(r'^ pro (\$[^,]+),', program, re.M)
             if name != '$_m_a_i_n'}
    def rename(match):
        return match[1] + names.get(match[2], match[2])
    return re.sub(r'^( (?:pro|cal|exp|inp|lpi) )(\$[^,\s]+)',
                  rename, program, flags=re.M)


def lower_division(program):
    """Replace known libpc arithmetic calls with native stack operations."""
    return re.sub(r'^ cal \$_(dvi|mdi)\n asp 4\n lfr 2$',
                  lambda m:' '+('dvi' if m[1]=='dvi' else 'pmod')+' 2',
                  program, flags=re.M)


def compile_source(source):
    for tool in ('em_pc','cpp.ansi','em_cemcom.ansi','em_opt','em_decode'):
        if not (TOOLS / (tool+SUFFIX)).is_file():
            raise CodegenError('ACK Pascal tools not built; run ack/build.sh')
    assembler = ROOT / 'a08' / ('a08'+SUFFIX)
    if not assembler.is_file():
        raise CodegenError('A08 not built; run a08/m.sh or a08/m.bat')
    with tempfile.TemporaryDirectory(prefix='ack Pascal ') as directory:
        work = Path(directory)
        # Stable source name keeps compiler filename strings reproducible across
        # operating systems, source locations, and temporary directory names.
        (work/'program.p').write_bytes(Path(source).read_text().encode('ascii'))
        run([TOOLS/('em_pc'+SUFFIX), PC_SIZES, '-R', 'program.p', 'program.k'], cwd=work)
        (work/'program.opt.k').write_bytes(run([TOOLS/('em_opt'+SUFFIX)],
                                              input=(work/'program.k').read_bytes()))
        run([TOOLS/('em_decode'+SUFFIX), work/'program.opt.k', work/'program.e'])
        program = lower_division(lower_fixed_arrays(namespace_procedures((work/'program.e').read_text())))
        # Console FILE values are opaque tokens; the full hosted file buffers
        # aren't used by our runtime. Keep only a word per standard stream.
        for name in ('input','output'):
            program = re.sub(r'(^'+name+r'\n) bss \d+,0,0', r'\g<1> bss 2,0,0', program, flags=re.M)
        units = [compile_c_unit(RUNTIME/'runtime.c', work, 'support'),
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
        print('ACK Pascal/8008: '+str(error),file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    sys.exit(main())
