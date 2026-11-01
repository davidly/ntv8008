#!/usr/bin/env python3
"""Assemble A08 source with a listing and adjacent trace map."""
import argparse
import os
from pathlib import Path
import subprocess
from symbols import symbols

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    image = args.output.resolve()
    listing = image.with_suffix('.lst')
    mapping = image.with_suffix('.map')
    image.parent.mkdir(parents=True, exist_ok=True)
    # Never leave an old map beside a newly assembled image after a failure.
    mapping.unlink(missing_ok=True)
    subprocess.run([str(ROOT/'a08'/('a08.exe' if os.name == 'nt' else 'a08')),
                    str(args.source.resolve()), '-o'+str(image), '-l'+str(listing)], check=True)
    mapping.write_text(symbols(listing.read_text()), encoding='ascii')


if __name__ == '__main__':
    main()
