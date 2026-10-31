#!/usr/bin/env python3
"""Fetch verified A08 sources and build locally; no upstream files are bundled."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
A08_URL = 'https://www.retrotechnology.com/restore/a08.zip'
A08_SHA256 = '37e5061618a89debd98955d682a494c78c9d6e445d8af6a1173235b68fcf67c0'
SCELBAL_URL = 'https://www.willegal.net/scelbi/software/sc1fast.asm'
SCELBAL_SHA256 = 'f687a816cfd115cb2632c610341f75a6f64c713d7c526319357f1b8ab93853dc'


def verified(path, digest):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('SHA-256 mismatch: '+str(path))
    return data


def fetch(url, destination, digest, supplied=None):
    destination = Path(destination)
    if supplied:
        data = verified(supplied, digest)
    elif destination.exists():
        return verified(destination, digest)
    else:
        print('Downloading '+url, flush=True)
        request = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (compatible; ntv8008-setup/1.0)'})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('SHA-256 mismatch: '+url+
                             '; the upstream download may have changed. Do not bypass verification.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return data


def build_a08():
    build = ROOT/'a08/build'
    archive = build/'a08.zip'
    fetch(A08_URL, archive, A08_SHA256, os.environ.get('A08_ARCHIVE'))
    source = build/'src'
    source.mkdir(parents=True, exist_ok=True)
    # Extract only the assembler and its notices. The ZIP also contains other
    # historical programs whose redistribution terms are independent of A08.
    names = ('a85.c','a85.h','a85eval.c','a85eval_nosplit.c','a85util.c','A08.DOC','readme.txt')
    with zipfile.ZipFile(archive) as package:
        for name in names:
            (source/name).write_bytes(package.read(name))
    main = source/'a85.c'
    text = main.read_text(encoding='latin1')
    old = 'void main(argc,argv)'
    if text.count(old) != 1:
        raise ValueError('A08 main signature changed; review the portability patch')
    # The official release already fixes RTS. The sole local change makes the
    # main return type conform to hosted C, for modern Linux/macOS compilers.
    text = text.replace(old, 'int main(argc,argv)')
    main.write_bytes(text.encode('latin1'))
    (build/'LOCAL_CHANGES.txt').write_text(
        'Original source: '+A08_URL+'\nSHA-256: '+A08_SHA256+'\n'
        'Build-copy change: void main(argc,argv) -> int main(argc,argv).\n'
        'The upstream copyright notices and RTS fix are retained.\n')
    compiler = shlex.split(os.environ.get('CC', 'cl' if os.name=='nt' else 'cc'))
    sources = [str(source/name) for name in ('a85.c','a85eval.c','a85util.c')]
    output = ROOT/'a08'/('a08.exe' if os.name=='nt' else 'a08')
    if Path(compiler[0]).stem.lower() == 'cl':
        command = compiler+['/nologo','/TC','/O2','/D_CRT_SECURE_NO_WARNINGS',*sources,'/Fe:'+str(output)]
    else:
        command = compiler+['-std=gnu89','-O2',*sources,'-o',str(output)]
    subprocess.run(command, cwd=build, check=True)
    print('Built '+str(output))


def assemble_image(source):
    source=Path(source)
    exe=ROOT/'a08'/('a08.exe' if os.name=='nt' else 'a08')
    image=source.with_suffix('.hex')
    subprocess.run([str(exe),str(source),'-o'+str(image)],check=True)
    # Native Windows stdio emits CRLF; keep published HEX byte-reproducible.
    image.write_bytes(image.read_text().encode('ascii'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', choices=['a08'])
    parser.parse_args()
    try:
        build_a08()
    except (OSError, ValueError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        parser.exit(1, str(error)+'\n')


if __name__ == '__main__':
    main()
