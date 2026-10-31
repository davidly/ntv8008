#!/usr/bin/env python3
"""Build the emulator and selected tools without installing anything globally."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from tools.dependencies import ROOT, build_a08, fetch, verified, SCELBAL_URL, SCELBAL_SHA256, assemble_image


def python(script, *args):
    subprocess.run([sys.executable,str(ROOT/script),*map(str,args)],cwd=ROOT,check=True)


def script(name):
    if os.name=='nt':
        subprocess.run(['cmd.exe','/d','/c',str(ROOT/name)],cwd=ROOT,check=True)
    else:
        subprocess.run(['sh',str(ROOT/name)],cwd=ROOT,check=True)


def assemble(name):
    assemble_image(ROOT/'a08'/(name+'.asm'))


def supplied_files(folder, files, hashes):
    folder = Path(folder).resolve()
    for name,digest in hashes.items():
        verified(folder/name,digest)
    files.mkdir(parents=True,exist_ok=True)
    for name in hashes:
        if (folder/name).resolve() != (files/name).resolve():
            shutil.copyfile(folder/name,files/name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all',action='store_true',help='also build SmallC and ACK host tools (ACK uses Linux/WSL)')
    parser.add_argument('--smallc',action='store_true')
    parser.add_argument('--ack',action='store_true')
    parser.add_argument('--scelbal',action='store_true',help='download and build optional noncommercial SCELBAL')
    parser.add_argument('--accept-scelbal-terms',action='store_true',help='acknowledge SCELBAL educational/historical/noncommercial terms in scelbal/NOTICE.txt')
    parser.add_argument('--forth-source',type=Path,help='use lawfully obtained pinned Forth sources from this directory')
    parser.add_argument('--plm-images',type=Path,help='use lawfully obtained pinned PLM1/PLM2 images from this directory')
    parser.add_argument('--plm-tape',type=Path,help='recover compiler images from a lawfully obtained pinned tape archive')
    args=parser.parse_args()
    if args.scelbal and not args.accept_scelbal_terms:
        parser.error('--scelbal requires --accept-scelbal-terms; read scelbal/NOTICE.txt')
    if args.plm_images and args.plm_tape:
        parser.error('choose --plm-images or --plm-tape')
    script('m.bat' if os.name=='nt' else 'm.sh')
    build_a08()
    python('robson/prepare.py')
    for name in ('hello','count','echo','sieve','e','ttt','robson'):
        assemble(name)
    if args.smallc or args.all:
        python('smallc/build.py')
        for name in ('hello','arithmetic','sieve','e','ttt'):
            python('smallc/compile.py',ROOT/f'smallc/examples/{name}.c')
    if args.ack or args.all:
        if os.name=='nt' and not os.environ.get('ACK_TOOLS'):
            if args.ack:
                parser.error('ACK host tools require Linux/WSL, or native tools selected with ACK_TOOLS; see ack/README.md')
            print('ACK host build skipped on Windows; supplied ACK application HEX files remain runnable. Use WSL to rebuild.')
        else:
            if not os.environ.get('ACK_TOOLS'):
                python('ack/bootstrap.py')
            for driver,folder,extension in (('compile','examples','c'),('pascal','pascal/examples','p'),
                                             ('modula2','modula2/examples','mod'),('basic','basic/examples','bas')):
                for name in ('hello','arithmetic','sieve','e','ttt'):
                    python('ack/'+driver+'.py',ROOT/f'ack/{folder}/{name}.{extension}')
    if args.scelbal:
        fetch(SCELBAL_URL,ROOT/'scelbal/upstream/sc1fast.asm',SCELBAL_SHA256,
              os.environ.get('SCELBAL_SOURCE'))
        python('scelbal/prepare.py')
        assemble('scelbal')
    if args.forth_source:
        supplied_files(args.forth_source,ROOT/'forth/upstream',{
            'forth.asm':'87177b045c1cff2018311e6b552baf1b909d175dd82a7ce0bd1ec470586e23bc',
            'forth-extra.inc':'2f6f99bc22e1ecf02620638054cb1288067c1816096538b78ec1caf88ca2e41e',
            'bufio.inc':'2a30b5469ee614ef51288ac630298b81ad0c34969c73fe688580c2ac0834daed'})
        python('forth/prepare.py')
        assemble('forth')
    if args.plm_images or args.plm_tape:
        if args.plm_tape:
            python('plm8/recover.py',args.plm_tape.resolve())
        else:
            supplied_files(args.plm_images,ROOT/'plm8/upstream',{
                'plm1.sav':'b25f17bbd43130de88a846a76fd439ed4558ad88fe2e19345b8fd1447209dcd4',
                'plm2.sav':'ba3c4c66470e1331d4f27ce49d1488938678447647c444e3228bf292eadfc39d'})
        for name in ('hello','arithmetic','sieve','e','ttt'):
            python('plm8/compile.py',ROOT/f'plm8/examples/{name}.plm')
    print('Setup complete. Run '+('test.bat' if os.name=='nt' else './test.sh'))


if __name__=='__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
