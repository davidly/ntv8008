#!/usr/bin/env python3
"""Build the preserved SmallC-85 frontend with the new 8008 backend."""
import os
from pathlib import Path
import shlex
import subprocess
import sys
HERE = Path(__file__).resolve().parent

def main():
    build = HERE / 'build'
    build.mkdir(exist_ok=True)
    # Preserve the upstream files. Apply host/target fixes only to build copies.
    for p in (HERE / 'upstream').glob('*'):
        if p.suffix not in ('.c', '.h'):
            continue
        text = p.read_text()
        if p.name == 'function.c':
            # Upstream success path falls off an int function used as a boolean.
            text = text.replace('\n}\n\ndoLocalAnsiArgument', '\n    return 1;\n}\n\ndoLocalAnsiArgument')
        if p.name == 'defs.h':
            # The fifth parameter is stack-passed on Windows x64. Without a
            # prototype, literal 0 is only an int, not a 64-bit null pointer.
            text += '\nint init(char *, int, int, int *, TAG_SYMBOL *);\n'
        if p.name == 'main.c':
            text = text.replace('main(int argc', 'int main(int argc')
        # Standard library declarations are needed on 64-bit hosts.
        text = '#include <stdlib.h>\n#include <string.h>\n' + text
        (build / p.name).write_text(text)
    compiler = shlex.split(os.environ.get('CC', 'cl' if os.name == 'nt' else 'cc'))
    sources = [build / p.name for p in sorted((HERE / 'upstream').glob('*.c'))]
    if Path(compiler[0]).stem.lower() == 'cl':
        subprocess.run(compiler + ['/nologo', '/TC', '/O2', '/w', '/DNOASLD',
            '/D_CRT_SECURE_NO_WARNINGS', '/I' + str(build),
            *map(str, sources), str(HERE / 'code8008.c'), '/Fe:scc8008.exe'],
            cwd=build, check=True)
        return 0
    subprocess.run(compiler + ['-std=gnu89', '-O2', '-w', '-Wno-return-type', '-DNOASLD',
        '-I' + str(build), *map(str, sources), str(HERE / 'code8008.c'),
        '-o', str(build / ('scc8008.exe' if os.name == 'nt' else 'scc8008'))], check=True)
    return 0

if __name__ == '__main__':
    sys.exit(main())
