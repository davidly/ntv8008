#!/usr/bin/env python3
"""Audit the explicit publication inventory; local ignored builds are excluded."""
import argparse
import fnmatch
import hashlib
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
MANIFEST='publication-manifest.json'
EXCLUDED_PREFIXES=('a08/build/','ack/build/','smallc/build/','forth/upstream/','scelbal/upstream/')
EXCLUDED_NAMES={'a08/a85.c','a08/a85.h','a08/a85eval.c','a08/a85eval_nosplit.c',
                'a08/a85util.c','a08/A08.DOC','a08/readme.txt','a08/MONITOR8.ASM',
                'a08/scelbal.asm','a08/scelbal.hex','a08/forth.asm','a08/forth.hex',
                'a08/a08','ntv8008'}
REQUIRED={'LICENSE','THIRD_PARTY_NOTICES.md','PROVENANCE.md','licenses/CC0-1.0.txt',
          'ack/ACK-COPYRIGHT','ack/NOTICE.txt','smallc/upstream/LICENSE',
          'smallc/NOTICE.txt','robson/upstream/LICENSE','robson/NOTICE.txt',
          'scelbal/NOTICE.txt','forth/NOTICE.txt','plm8/upstream/NOTICE.txt',
          'ack/generators/byacc/upstream/LICENSE','ack/generators/reflex/upstream/COPYING'}


def ignored(name):
    # The repository's intentionally simple ignore rules also work in source
    # ZIPs and on systems without Git. Git remains authoritative when present.
    for line in (ROOT/'.gitignore').read_text().splitlines():
        pattern=line.strip()
        if not pattern or pattern.startswith('#'):
            continue
        anchored=pattern.startswith('/')
        pattern=pattern.lstrip('/')
        if pattern.endswith('/'):
            directory=pattern.rstrip('/')
            if (name.startswith(directory+'/') if anchored else directory in Path(name).parts):
                return True
        elif fnmatch.fnmatchcase(name if anchored or '/' in pattern else Path(name).name,pattern):
            return True
    return False


def candidates():
    if (ROOT/'.git').exists() and shutil.which('git'):
        safe=ROOT.as_posix()
        if os.name=='nt' and safe.startswith('//'):
            safe='%(prefix)/'+safe
        command=['git','-c','safe.directory='+safe,'-C',str(ROOT)]
        names=set(subprocess.check_output(command+['ls-files','-z','--cached','--others','--exclude-standard']).decode().strip('\0').split('\0'))
    else:
        names=set()
        for directory,folders,files in os.walk(ROOT):
            relative=Path(directory).relative_to(ROOT)
            folders[:]=[n for n in folders if n!='.git' and not ignored((relative/n).as_posix()+'/')]
            for name in files:
                name=(relative/name).as_posix()
                if not ignored(name):
                    names.add(name)
    names.discard('')
    names.discard(MANIFEST)
    return names


def validate(names):
    missing=REQUIRED-names
    if missing:
        raise ValueError('missing licensing records: '+', '.join(sorted(missing)))
    for name in names:
        path=Path(name)
        if (name in EXCLUDED_NAMES or name.startswith(EXCLUDED_PREFIXES) or
                name.startswith('plm8/examples/') and path.suffix=='.hex' or
                name.startswith(('a08/star.','a08/mon8.','a08/08_72','a08/dollar.')) or
                path.suffix.lower() in ('.exe','.obj','.o','.log','.lst','.sav','.zip','.gz','.bz2','.pyc') or
                '__pycache__' in path.parts or path.is_absolute() or '..' in path.parts):
            raise ValueError('excluded publication candidate: '+name)
        if not (ROOT/name).is_file() or (ROOT/name).is_symlink():
            raise ValueError('missing or symlinked publication candidate: '+name)


def category(name):
    if name.startswith('ack/generators/byacc/upstream/'):
        return 'LicenseRef-Public-Domain','Berkeley Yacc 20260126; ack/generators/byacc/NOTICE.txt and upstream/LICENSE'
    if name.startswith('ack/generators/reflex/upstream/'):
        return 'LicenseRef-Reflex','Reflex 20260131; full MIT/Flex acknowledgement terms in upstream/COPYING; ack/generators/reflex/NOTICE.txt'
    if name=='ack/msvc/recipe.json':
        return 'BSD-3-Clause','Build metadata derived from pinned ACK graph; ack/ACK-COPYRIGHT and ack/NOTICE.txt'
    if name.startswith('smallc/upstream/'):
        return 'Unlicense','ncb85/SmallC-85 cfeb1bce46d6454a91ec0d819626a1c75358a030; smallc/NOTICE.txt'
    if name.startswith('robson/upstream/'):
        return 'MIT','paulscottrobson/1k-coding-challenge 996fd54bc665d1499838bf431e1540aa06c2177e; robson/NOTICE.txt'
    if name in ('a08/robson.asm','a08/robson.hex'):
        return 'MIT AND BSD-3-Clause','Robson MIT interpreter with project adaptation; robson/NOTICE.txt'
    if name=='ack/ACK-COPYRIGHT':
        return 'LicenseRef-ACK-BSD','ACK upstream permission notice; ack/NOTICE.txt'
    if name=='licenses/CC0-1.0.txt':
        return 'CC0-1.0','CC0 legal text retained from davidly/cpm_compilers/LICENSE'
    if name=='scelbal/NOTICE.txt':
        return 'LicenseRef-SCELBAL-Notice','Required historical permission comment only; interpreter not included'
    if '/examples/' in name or name in ('a08/sieve.asm','a08/sieve.hex','a08/e.asm','a08/e.hex','a08/ttt.asm','a08/ttt.hex'):
        return 'BSD-3-Clause','Project example/port; any inherited CC0 material remains CC0; PROVENANCE.md'
    return 'BSD-3-Clause','Project contribution or publication documentation; THIRD_PARTY_NOTICES.md'


def inventory(names):
    result={}
    for name in sorted(names):
        license,origin=category(name)
        result[name]={'sha256':hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),
                      'license':license,'origin':origin}
    return {'format':1,'reviewed':'2026-10-31','files':result}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update',action='store_true',help='record reviewed source changes; does not establish third-party rights')
    args=parser.parse_args()
    names=candidates()
    validate(names)
    actual=inventory(names)
    manifest=ROOT/MANIFEST
    if args.update:
        manifest.write_text(json.dumps(actual,indent=2,ensure_ascii=False)+'\n')
        print('Recorded',len(names),'reviewed files plus the manifest itself.')
    else:
        expected=json.loads(manifest.read_text())
        if actual['files']!=expected['files']:
            old=expected['files']
            changed=[n for n in sorted(names|old.keys()) if actual['files'].get(n)!=old.get(n)]
            raise ValueError('publication inventory changed; review before --update: '+', '.join(changed))
        print('Publication audit passed:',len(names),'files plus manifest; required notices present.')


if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,subprocess.CalledProcessError) as error:
        sys.exit(str(error))
