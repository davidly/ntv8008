#!/usr/bin/env python3
"""Build official A08 and assemble project examples with reproducible HEX lines."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.dependencies import build_a08, assemble_image


def main():
    build_a08()
    names=sys.argv[1:] or ['hello.asm','count.asm','echo.asm','sieve.asm','e.asm','ttt.asm','robson.asm']
    for name in names:
        source=Path(name)
        if not source.is_absolute():
            source=ROOT/'a08'/source
        assemble_image(source)


if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,subprocess.CalledProcessError) as error:
        sys.exit(str(error))
