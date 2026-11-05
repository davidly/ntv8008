#!/usr/bin/env python3
"""Compile freestanding C with ACK and the native 8008 code generator."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from codegen import CodegenError, generate

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
TOOLS = Path(os.environ.get('ACK_TOOLS', str(HERE / 'build/bin')))
SUFFIX = '.exe' if os.name == 'nt' else ''
SIZES = '-Vw2.2i2.2p2.2f4.2s2.2l4.2d8.2x8.2'


def run(command, **kwargs):
    result = subprocess.run([str(item) for item in command], capture_output=True,
                            timeout=120, **kwargs)
    if result.returncode:
        raise CodegenError(result.stderr.decode(errors='replace') +
                           result.stdout.decode(errors='replace'))
    return result.stdout


def image_end(image):
    end = 0
    for line in image.splitlines():
        data = bytes.fromhex(line[1:])
        if data[3] == 0:
            end = max(end, int.from_bytes(data[1:3], 'big') + data[0])
    return end


def assemble_fitting(units, work, assembler, **options):
    """Assemble the fastest image that leaves 512 bytes of stack.

    Spill slots and stored arguments enlarge code; when the image would not
    fit, generate again with compact RAM-stack calls.
    """
    for compact in (False, True):
        assembly = generate(units, compact=compact, **options)
        (work / 'program.asm').write_bytes(assembly.encode('ascii'))
        run([assembler, work / 'program.asm', '-o' + str(work / 'program.hex')])
        image = (work / 'program.hex').read_text()
        # Keep at least 512 bytes between the image and the stack/variables.
        if image_end(image) <= 0x3d00:
            return image, assembly
    raise CodegenError('code/data exceed 15616 bytes; at least 512 bytes of stack required')


def compile_c_unit(source, work, index):
    compact, optimized, readable = [work / (str(index) + ext)
                                    for ext in ('.k', '.opt.k', '.e')]
    preprocessed = work / (str(index) + '.i')
    preprocessed.write_bytes(run([TOOLS / ('cpp.ansi' + SUFFIX),
        '-I' + str(HERE / 'include'), '-I' + str(source.resolve().parent),
        '-D__ACK', '-D__8008__', '-DEM_WSIZE=2', '-DEM_PSIZE=2',
        source.resolve()]))
    run([TOOLS / ('em_cemcom.ansi' + SUFFIX), SIZES, '-L', preprocessed, compact])
    optimized.write_bytes(run([TOOLS / ('em_opt' + SUFFIX)], input=compact.read_bytes()))
    run([TOOLS / ('em_decode' + SUFFIX), optimized, readable])
    return readable.read_text()


def compile_sources(sources):
    for tool in ('cpp.ansi', 'em_cemcom.ansi', 'em_opt', 'em_decode'):
        if not (TOOLS / (tool + SUFFIX)).is_file():
            raise CodegenError('ACK tools not built; run ack/build.sh (or set ACK_TOOLS)')
    assembler = ROOT / 'a08' / ('a08' + SUFFIX)
    if not assembler.is_file():
        raise CodegenError('A08 assembler not built; run a08/m.sh or a08/m.bat')
    units = []
    with tempfile.TemporaryDirectory(prefix='ack8008 ') as directory:
        work = Path(directory)
        for index, source in enumerate([*map(Path, sources), HERE / 'console.c']):
            units.append(compile_c_unit(source, work, index))
        output, assembly = assemble_fitting(units, work, assembler)
        return output, assembly, '\n'.join(units)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', nargs='+', type=Path)
    parser.add_argument('-o', '--output', type=Path)
    parser.add_argument('--assembly', type=Path, help='save generated A08 source')
    parser.add_argument('--em', type=Path, help='save readable optimized EM')
    args = parser.parse_args()
    try:
        image, assembly, em = compile_sources(args.source)
        if args.assembly:
            args.assembly.write_bytes(assembly.encode('ascii'))
        if args.em:
            args.em.write_bytes(em.encode('ascii'))
        output = args.output or args.source[0].with_suffix('.hex')
        output.write_bytes(image.encode('ascii'))
        print(f'{args.source[0]}: compiled to {output}')
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print('ACK/8008: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
