#!/usr/bin/env python3
"""Build pinned ACK host tools and Lua locally; no system installation."""
import hashlib
import os
import posixpath
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'
REVISION = '7afa32a0a0f13e865fa2e8104e442689005cd627'
ACK_SHA256 = '142ad8834ed5409dda0fed8e3ddb1e50f72c772858ef1e2cc9570f13e9cc6ad3'
LUA_SHA256 = '9fbf5e28ef86c69858f6d3d34eccc32e911c1a28b4120ff3e84aaa70cfbf1e30'


def unpack(name, url, digest, variable):
    directory = BUILD / 'src' / name
    archive = Path(os.environ.get(variable, str(BUILD / (name + '.tar.gz'))))
    if not archive.exists():
        print('Downloading ' + url, flush=True)
        data = urllib.request.urlopen(url, timeout=60).read()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('SHA-256 mismatch: ' + url)
        archive.write_bytes(data)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise ValueError('SHA-256 mismatch: ' + str(archive))
    cached = BUILD / (name + '.tar.gz')
    if archive.resolve() != cached.resolve() and not cached.exists():
        shutil.copy2(archive, cached)
    if not (directory / '.unpacked').exists():
        directory.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as source:
            for member in source.getmembers():
                # Strip the top directory. Materialize in-archive symlinks as
                # ordinary files so Windows does not require symlink privileges.
                parts = Path(member.name).parts[1:]
                if not parts:
                    continue
                if '..' in parts or Path(member.name).is_absolute():
                    raise ValueError('unsafe archive member: ' + member.name)
                path = directory.joinpath(*parts)
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                elif member.isfile() or member.issym() or member.islnk():
                    target = member
                    for _ in range(16):
                        if not (target.issym() or target.islnk()):
                            break
                        link = (posixpath.join(posixpath.dirname(target.name), target.linkname)
                                if target.issym() else target.linkname)
                        link = posixpath.normpath(link)
                        if link.split('/')[0] != member.name.split('/')[0]:
                            raise ValueError('unsafe archive link: ' + member.name)
                        target = source.getmember(link)
                    if not target.isfile():
                        raise ValueError('invalid archive link: ' + member.name)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(source.extractfile(target).read())
                    path.chmod(target.mode & 0o777)
        (directory / '.unpacked').touch()
    return directory


def patch_sources(ack):
    # Match Pascal's runtime/ISO MOD semantics during constant folding too.
    # Upstream used C's negative remainder, producing a different constant.
    folding = ack / 'lang/pc/comp/cstoper.c'
    old = "\t\t\telse\n\t\t\t\to1 %= o2;\n"
    new = ("\t\t\telse {\n\t\t\t\to1 %= o2;\n"
           "\t\t\t\tif (o1 < 0 && o2 > 0) o1 += o2;\n\t\t\t}\n")
    text = folding.read_text()
    original = text
    if old not in text and new not in text:
        raise ValueError('unexpected Pascal constant-folding source')
    text = text.replace(old, new)
    text = text.replace("case MOD:\n\t\t\tif( o2 == 0 )",
                        "case MOD:\n\t\t\tif( o2 <= 0 )")
    text = text.replace('"modulo by 0"', '"modulo divisor must be positive"')
    if text != original:
        folding.write_text(text)
    import runpy
    runpy.run_path(str(HERE/'basic/patch.py'))['apply'](ack)
    runpy.run_path(str(HERE/'occam/patch.py'))['apply'](ack)


def main():
    for tool in ('make', 'ninja', 'gcc', 'flex', 'yacc'):
        if not shutil.which(tool):
            raise SystemExit('Missing build tool: ' + tool)
    BUILD.mkdir(exist_ok=True)
    lua = unpack('lua', 'https://www.lua.org/ftp/lua-5.4.7.tar.gz', LUA_SHA256, 'LUA_ARCHIVE')
    ack = unpack('ack', 'https://codeload.github.com/davidgiven/ack/tar.gz/' + REVISION,
                 ACK_SHA256, 'ACK_ARCHIVE')
    patch_sources(ack)
    jobs = str(min(os.cpu_count() or 2, 8))
    subprocess.run(['make', '-j' + jobs, 'posix'], cwd=lua, check=True)
    makefile = ack / 'Makefile'
    makefile.write_text(makefile.read_text().replace('PLATS = all', 'PLATS = em22'))
    environment = dict(os.environ)
    environment['PATH'] = str(lua / 'src') + os.pathsep + environment['PATH']
    subprocess.run(['make', 'NINJA=ninja -j' + jobs,
                    'lang/cem/cemcom.ansi/+all', 'lang/cem/cpp.ansi/+all',
                    'lang/pc/comp/+all', 'lang/m2/comp/+all', 'lang/basic/src/+all',
                    'util/misc/+all', 'util/opt/+all'], cwd=ack,
                   env=environment, check=True)
    subprocess.run(['make', 'NINJA=ninja -j'+jobs, 'lang/occam/comp/+all'],
                   cwd=ack, env=environment, check=True)
    destination = BUILD / 'bin'
    destination.mkdir(exist_ok=True)
    suffix = '.exe' if os.name == 'nt' else ''
    for name in ('em_cemcom.ansi', 'cpp.ansi', 'em_opt', 'em_opt2', 'em_decode', 'em_pc', 'em_m2', 'em_bem', 'em_occam'):
        shutil.copy2(ack / '.obj/staging/lib/ack' / (name + suffix), destination)
    licenses = BUILD / 'licenses'
    licenses.mkdir(exist_ok=True)
    shutil.copy2(ack / 'Copyright', licenses / 'ACK-Copyright')
    shutil.copy2(lua / 'README', licenses / 'Lua-README')
    print('ACK host tools ready in ' + str(destination))


if __name__ == '__main__':
    main()
