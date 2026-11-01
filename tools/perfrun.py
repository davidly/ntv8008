#!/usr/bin/env python3
"""Run benchmark images with -p; report unavailable optional runtimes."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
LANGUAGES=('assembly','ack','smallc','pascal','modula2','ackbasic','occam','b8008','basic','plm8','forth')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--languages',nargs='+',choices=LANGUAGES)
    args=parser.parse_args()
    host=ROOT/('ntv8008.exe' if sys.platform=='win32' else 'ntv8008')
    for language in args.languages or LANGUAGES:
        commands=[]
        for app in ('sieve','e','ttt'):
            if language in ('basic','forth','b8008'):
                folder,extension,image={'basic':('scelbal','bas','scelbal'),
                                        'forth':('forth','f','forth'),
                                        'b8008':('b8008','bas','b8008')}[language]
                session=ROOT/f'{folder}/examples/{app}.{extension}'
                target=ROOT/f'a08/{image}.hex'
                command=['-l:'+str(session),str(target)]
            else:
                folder={'assembly':'a08','ack':'ack/examples','smallc':'smallc/examples',
                        'pascal':'ack/pascal/examples','modula2':'ack/modula2/examples',
                        'ackbasic':'ack/basic/examples','occam':'ack/occam/examples','plm8':'plm8/examples'}[language]
                target=ROOT/f'{folder}/{app}.hex'
                command=[str(target)]
            if not target.is_file():
                if args.languages:
                    parser.error(f'{language}: missing {target}; see the component README')
                print(f'SKIP {language}: optional images not installed; see the component README',flush=True)
                commands=[]
                break
            commands.append((app,command))
        for app,command in commands:
            print(f'\n=== {language} / {app} ===',flush=True)
            subprocess.run([str(host),'-p','-n:500000000000',*command],check=True)


if __name__=='__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
