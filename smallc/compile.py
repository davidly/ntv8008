#!/usr/bin/env python3
"""Compile SmallC-85's integer C subset to an 8008 Intel HEX image."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from codegen import CodegenError, generate

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SUFFIX = '.exe' if os.name == 'nt' else ''

def run(command, **kwargs):
    p = subprocess.run(list(map(str, command)), capture_output=True, timeout=120, **kwargs)
    if p.returncode:
        raise CodegenError(f'{Path(command[0]).name} exited with {p.returncode}:\n' +
                           p.stdout.decode(errors='replace') + p.stderr.decode(errors='replace'))
    return p.stdout

def includes(source, active=None):
    """Flatten includes before giving the old frontend a short temporary filename."""
    source = source.resolve()
    active = set() if active is None else active
    if source in active:
        raise CodegenError('recursive include: ' + str(source))
    active.add(source)
    result = []
    for line in source.read_text().splitlines():
        match = re.fullmatch(r'\s*#\s*include\s*([<"])([^>"]+)[>"]\s*', line)
        if match:
            name = match[2]
            if match[1] == '<':
                if name != 'stdio.h':
                    raise CodegenError('unsupported system header: ' + name)
                # Functions can be called before definition in Small C.
                result.append('/* Builtin putchar/getchar/puts/kbhit/waitkey; putu supplied below. */')
            else:
                result.append(includes(source.parent / name, active))
        else:
            result.append(line)
    active.remove(source)
    return '\n'.join(result) + '\n'

def compile_source(source):
    tool = HERE / 'build' / ('scc8008' + SUFFIX)
    assembler = ROOT / 'a08' / ('a08' + SUFFIX)
    if not tool.is_file():
        raise CodegenError('Small C not built; run smallc/build.sh or smallc/build.bat')
    if not assembler.is_file():
        raise CodegenError('A08 not built; run a08/m.sh or a08/m.bat')
    text = includes(Path(source)) + '\n' + (HERE / 'console.c').read_text()
    with tempfile.TemporaryDirectory(prefix='smallc 8008 ') as directory:
        work = Path(directory)
        (work / 'unit.c').write_bytes(text.encode('ascii'))
        run([tool, '-a', 'unit.c'], cwd=work)
        ir = (work / 'unit.s').read_text()
        assembly = generate(ir)
        (work / 'program.asm').write_bytes(assembly.encode('ascii'))
        run([assembler, 'program.asm', '-oprogram.hex'], cwd=work)
        image = (work / 'program.hex').read_text()
        end = 0
        for line in image.splitlines():
            record = bytes.fromhex(line[1:])
            if record[3] == 0:
                end = max(end, int.from_bytes(record[1:3], 'big') + record[0])
        if end > 0x3d00:
            raise CodegenError('code/data exceed 15616 bytes; at least 512 bytes of stack required')
        return image, assembly, ir

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('-o', '--output', type=Path)
    p.add_argument('--assembly', type=Path)
    p.add_argument('--ir', type=Path, help='save the compile-time backend operation stream')
    args = p.parse_args()
    try:
        image, assembly, ir = compile_source(args.source)
        if args.assembly:
            args.assembly.write_bytes(assembly.encode('ascii'))
        if args.ir:
            args.ir.write_bytes(ir.encode('ascii'))
        target = args.output or args.source.with_suffix('.hex')
        target.write_bytes(image.encode('ascii'))
        print(f'{args.source}: compiled to {target}')
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print('Small C/8008: ' + str(error), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
