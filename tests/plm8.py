#!/usr/bin/env python3
"""Compile with the recovered Intel compiler, then execute real 8008 code."""
from decimal import Decimal, localcontext
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plm8'))
spec = importlib.util.spec_from_file_location('plm8_compile', ROOT / 'plm8/compile.py')
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)
HOST = ROOT / ('ntv8008.exe' if os.name == 'nt' else 'ntv8008')


@unittest.skipUnless(all((ROOT/'plm8/upstream'/n).is_file() for n in ('plm1.sav','plm2.sav')), 'optional Intel compiler images not supplied; see plm8/README.md')
class PLM8(unittest.TestCase):
    def execute(self, source, budget=1_000_000, expected_image=None):
        image, listing = compiler.compile_source(source)
        self.assertEqual(listing.count('NO PROGRAM ERRORS'), 2, listing)
        if expected_image is not None:
            self.assertEqual(image, expected_image)
        with tempfile.TemporaryDirectory(prefix='plm8 test ') as directory:
            path = Path(directory, 'compiled.hex')
            path.write_text(image, encoding='ascii')
            result = subprocess.run([str(HOST), f'-n:{budget}', str(path)],
                                    capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.replace(b'\r\n', b'\n')

    def test_examples(self):
        for name, output, budget in (('hello', b'HELLO, PL/M-8!\n', 100_000),
                                     ('arithmetic', b'OK\n', 1_000_000),
                                     ('sieve', b'1899\n', 200_000_000)):
            with self.subTest(name=name):
                source = (ROOT / f'plm8/examples/{name}.plm').read_text()
                image = (ROOT / f'plm8/examples/{name}.hex').read_text()
                self.assertEqual(self.execute(source, budget, image), output)

    def test_e(self):
        with localcontext() as context:
            context.prec = 220
            digits = str(Decimal(1).exp()).replace('.', '')[:192]
        source = (ROOT / 'plm8/examples/e.plm').read_text()
        image = (ROOT / 'plm8/examples/e.hex').read_text()
        self.assertEqual(self.execute(source, 450_000_000, image),
                         (digits + '\nDONE\n').encode())

    def test_ttt(self):
        from integration import Integration
        scores, nodes = Integration.minimax_reference()
        self.assertEqual(scores, [5, 5, 5])
        self.assertEqual(nodes, 6493)
        source = (ROOT / 'plm8/examples/ttt.plm').read_text()
        image = (ROOT / 'plm8/examples/ttt.hex').read_text()
        self.assertEqual(self.execute(source, 600_000_000, image),
                         f'{nodes} MOVES\n'.encode())

    def test_large_intermediate_files(self):
        # Exceed the runner's 640-character I/O buffers and use both taken and
        # untaken branches, DO CASE, calls, and arithmetic with known results.
        source = '''64:
DECLARE I ADDRESS, V BYTE;
V=0;
'''
        source += "V=V+1;\n" * 100
        source += '''DO I=1 TO 3;
    DO CASE I-1;
        V=V+1;
        V=V+2;
        V=V+3;
    END;
END;
IF V=106 THEN OUTPUT(2)='Y'; ELSE OUTPUT(2)='N';
HALT;
EOF
'''
        self.assertEqual(self.execute(source), b'Y')

    def test_compile_errors(self):
        with self.assertRaises(compiler.CompileError):
            compiler.compile_source('64:\nDECLARE X BYTE;\nX=;\nHALT;\n')
        with self.assertRaises(compiler.CompileError):
            compiler.compile_source('64:\nOUTPUT(2)=UNDECLARED;\nHALT;\n')
        with self.assertRaises(compiler.CompileError):
            compiler.compile_source('64:\n' + ' ' * 73 + '\nHALT;\n')
        with self.assertRaises(compiler.CompileError):
            compiler.compile_source("64:\nOUTPUT(2)='!';\nHALT;\n")
        with self.assertRaises(compiler.CompileError):
            compiler.compile_source('64:\nhalt;\n')

    def test_bad_object_records(self):
        for text in (':01004000FF00\n:0000000000\n',
                     ':01400000FFC0\n:0000000000\n',
                     ':0000000000\n:01004000FFC0\n'):
            with self.subTest(text=text), self.assertRaises(compiler.CompileError):
                compiler.convert_hex(text)

    def test_cli_paths_and_failure(self):
        with tempfile.TemporaryDirectory(prefix='plm8 cli ') as directory:
            path = Path(directory)
            source, image, listing = (path / name for name in ('hello.plm', 'hello.hex', 'hello.lst'))
            source.write_text("64:\nOUTPUT(2)='X';\nHALT;\n")
            command = [sys.executable, str(ROOT / 'plm8/compile.py'), str(source),
                       '-o', str(image), '--listing', str(listing)]
            result = subprocess.run(command, cwd=directory, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('NO PROGRAM ERRORS', listing.read_text())
            original = image.read_bytes()
            source.write_text('64:\nX=;\nHALT;\n')
            result = subprocess.run(command, cwd=directory, capture_output=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(image.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
