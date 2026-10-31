#!/usr/bin/env python3
"""Rebuild and execute Baker's native 8008 Forth and the benchmark ports."""
from decimal import Decimal, localcontext
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

import integration
from integration import ASSEMBLER, HOST, ROOT

spec = importlib.util.spec_from_file_location('forth_prepare', ROOT / 'forth/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


@unittest.skipUnless((ROOT/'a08/forth.hex').is_file(), 'optional Forth not installed; see forth/README.md')
class Forth(unittest.TestCase):
    def execute(self, source, budget=100_000_000):
        source = source.rstrip() + '\n'
        result = subprocess.run([str(HOST), f'-n:{budget}', '-p',
                                 str(ROOT / 'a08/forth.hex')],
                                input=source.encode('ascii'), capture_output=True,
                                timeout=120)
        output = result.stdout.replace(b'\r\n', b'\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(b'Unknown Token', output)
        self.assertNotIn(b'input EOF', result.stderr)  # BYE must actually execute.
        return output

    def app(self, name, budget):
        source = (ROOT / f'forth/examples/{name}.f').read_text()
        output = self.execute(source, budget)
        entry = {'e': 'E', 'ttt': 'TTT', 'sieve': 'SIEVE', 'hello': 'GREET'}[name]
        return output.split((entry + ' BYE\n').encode(), 1)[1]

    def test_rebuild(self):
        self.assertEqual(prepare.prepare(), (ROOT / 'a08/forth.asm').read_text())
        with tempfile.TemporaryDirectory(prefix='forth test ') as directory:
            image = Path(directory, 'forth.hex')
            subprocess.run([str(ASSEMBLER), str(ROOT / 'a08/forth.asm'),
                            '-o' + str(image)], check=True, capture_output=True,
                           timeout=10)
            self.assertEqual(image.read_text(), (ROOT / 'a08/forth.hex').read_text())

    def test_hello(self):
        self.assertEqual(self.app('hello', 10_000_000), b'HELLO, 8008 FORTH!\n')

    def test_file_input(self):
        # Exercise -l: with Windows line endings and a path containing spaces.
        source = (ROOT / 'forth/examples/hello.f').read_text()
        with tempfile.TemporaryDirectory(prefix='forth input ') as directory:
            path = Path(directory, 'hello.f')
            path.write_bytes(source.replace('\n', '\r\n').encode('ascii'))
            result = subprocess.run([str(HOST), '-n:10000000', '-p',
                                     '-l:' + str(path), str(ROOT / 'a08/forth.hex')],
                                    capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(b'input EOF', result.stderr)
        self.assertTrue(result.stdout.replace(b'\r\n', b'\n').endswith(
            b'HELLO, 8008 FORTH!\n'))

    def test_core(self):
        source = '''DECIMAL
VARIABLE A 30 ALLOT
VARIABLE B
: MEM 30 0 DO I A I + C! LOOP 12345 B ! ;
: RS 123 >R 7 R> + ;
: FACT DUP 1 > IF DUP 1- RECURSE * ELSE DROP 1 THEN ;
: BRANCHES 0 IF 111 ELSE 222 THEN . 1 IF 333 THEN . ;
: LOOPS 3 0 DO 2 0 DO J . I . LOOP LOOP ;
: BEGINTEST 3 BEGIN DUP . 1- DUP 0= UNTIL DROP ;
: CHECK MEM A C@ . A 29 + C@ . B @ . RS .
  6 FACT . BRANCHES LOOPS BEGINTEST
  30000 251 /MOD . . 30000 2 * U. CR ;
CHECK BYE
'''
        output = self.execute(source).split(b'CHECK BYE\n', 1)[1]
        self.assertEqual(output, b'0 29 12345 130 720 222 333 '
                                b'0 0 0 1 1 0 1 1 2 0 2 1 3 2 1 '
                                b'119 131 60000 \n')

    def test_native_packed_flags_and_shift(self):
        source="""DECIMAL
VARIABLE A 300 ALLOT
: CHECK
  301 0 DO 255 A I + C! LOOP
  123 >R
  2056 0 DO
    A I BIT@ 0= IF 999 . THEN
    A I BITCLR
    A I BIT@ IF 998 . THEN
  LOOP
  R> .
  A 257 + C@ .
  0 3RSHIFT U. 7 3RSHIFT U. 8 3RSHIFT U.
  255 3RSHIFT U. 256 3RSHIFT U. 32768 3RSHIFT U.
  65535 3RSHIFT U. CR ;
CHECK BYE
"""
        output=self.execute(source).split(b'CHECK BYE\n',1)[1]
        self.assertEqual(output,b'123 255 0 0 1 31 32 4096 8191 \n')

    def test_e(self):
        with localcontext() as context:
            context.prec = 220
            digits = str(Decimal(1).exp()).replace('.', '')[:192]
        self.assertEqual(self.app('e', 1_000_000_000),
                         (digits + '\ndone\n').encode())

    def test_benchmark_fill(self):
        source = (ROOT / 'forth/examples/sieve.f').read_text()
        start = source.index(': FILL')
        fill = source[start:source.index(';', start) + 1]
        output = self.execute('DECIMAL\n' + fill + '''
VARIABLE A 9 ALLOT
: CHECK
  9 0 DO 99 A I + C! LOOP
  1234 A 1+ 6 17 FILL .
  A 3 + 0 42 FILL
  9 0 DO A I + C@ . LOOP CR ;
CHECK BYE
''').split(b'CHECK BYE\n', 1)[1]
        self.assertEqual(output, b'1234 99 17 17 17 17 17 17 99 99 \n')

    def test_sieve(self):
        def prime(n):
            return all(n % d for d in range(2, int(n ** 0.5) + 1))
        count = sum(prime(n) for n in range(3, 16384, 2))
        self.assertEqual(count, 1899)
        self.assertEqual(self.app('sieve', 17_000_000_000),
                         f'count of primes: {count} \n10 iterations\n'.encode())

    def test_ttt(self):
        scores, nodes = integration.Integration.minimax_reference()
        self.assertEqual(scores, [5, 5, 5])
        self.assertEqual(nodes, 6493)
        self.assertEqual(self.app('ttt', 26_000_000_000),
                         f'10 iterations\nmoves evaluated: {nodes} \n'.encode())


if __name__ == '__main__':
    unittest.main()
