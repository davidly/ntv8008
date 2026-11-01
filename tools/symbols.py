#!/usr/bin/env python3
"""Convert an A08 listing's symbol table to an ntv8008 trace map."""
import argparse
from pathlib import Path
import re


def symbols(text):
    result = {}
    # Symbol-table rows contain repeated octal page/offset/name triples.
    # Listing rows start with whitespace and contain opcode/source columns.
    for line in text.splitlines():
        if not re.match(r"^[0-7]{3} [0-7]{3}  ", line):
            continue
        for page, offset, name in re.findall(
                r"([0-7]{3}) ([0-7]{3})  ([A-Za-z_.$?][A-Za-z_0-9.$?]*)", line):
            address = int(page, 8) * 256 + int(offset, 8)
            if address < 16384:
                result.setdefault(address, []).append(name)
    if not result:
        raise ValueError("no A08 symbols found; generate a listing with -lfile.lst")
    return "".join(f"{address:04x} {'|'.join(sorted(set(names)))}\n"
                   for address, names in sorted(result.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('listing', type=Path)
    parser.add_argument('-o', '--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        args.output.write_text(symbols(args.listing.read_text()), encoding='ascii')
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
