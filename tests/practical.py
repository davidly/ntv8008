#!/usr/bin/env python3
"""Validate practical examples and the reusable output-checking recipe."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUFFIX = '.exe' if os.name == 'nt' else ''
COMPILE = '--compile' in sys.argv
if COMPILE:
    sys.argv.remove('--compile')


class Practical(unittest.TestCase):
    def run_game(self, basic, commands):
        project = ROOT/'examples'/('adventure-basic' if basic else 'adventure-c')
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)/'session.txt'
            text = ((project/'program.bas').read_text() if basic else '') + commands
            session.write_bytes(text.encode('ascii'))
            image = ROOT/'a08/b8008.hex' if basic else project/'build/program.hex'
            result = subprocess.run([str(ROOT/('ntv8008'+SUFFIX)), '-n:20000000',
                                     '-l:'+str(session), str(image)], capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = result.stdout.decode().replace('\r\n','\n')
            if basic:
                output = output.split('>RUN\n')[-1]
            for error in ('?SYNTAX', '?BOUNDS', '?DIV', '?OVERFLOW'):
                self.assertNotIn(error, output)
            return output

    def check_game(self, basic):
        win = self.run_game(basic, '2\n3\n1\n1\n4\n')
        self.assertIn('KEY TAKEN', win)
        self.assertIn('YOU ESCAPED!', win)
        quit = self.run_game(basic, '4\n3\n9\n0\n')
        self.assertIn('YOU NEED THE KEY', quit)
        self.assertIn('NOTHING TO TAKE', quit)
        self.assertIn('USE 0 TO 4', quit)
        self.assertIn('GOODBYE', quit)
        self.assertNotIn('YOU ESCAPED!', quit)
        locked = self.run_game(basic, '1\n4\n0\n')
        self.assertIn('YOU NEED THE KEY', locked)
        self.assertNotIn('YOU ESCAPED!', locked)

    def test_basic(self):
        self.check_game(True)

    @unittest.skipUnless(COMPILE, 'use --compile for the SmallC practical example')
    def test_smallc(self):
        project = ROOT/'examples/adventure-c'
        (project/'build').mkdir(exist_ok=True)
        subprocess.run([sys.executable, str(ROOT/'smallc/compile.py'), str(project/'program.c'),
                        '-o', str(project/'build/program.hex')], check=True, capture_output=True)
        self.check_game(False)

    def test_comparison(self):
        languages = ['assembly', 'b8008']
        if COMPILE:
            languages += ['smallc', 'ack', 'pascal', 'modula2', 'occam']
        result = subprocess.run([sys.executable, str(ROOT/'examples/compare/run.py'),
                                 '--languages', *languages], capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for language in languages:
            self.assertIn(('| '+language+' |').encode(), result.stdout)

    @unittest.skipUnless(COMPILE, 'use --compile for optimization examples')
    def test_optimization(self):
        result = subprocess.run([sys.executable, str(ROOT/'examples/optimization/run.py')],
                                capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_output_checker(self):
        with tempfile.TemporaryDirectory() as directory:
            expected = Path(directory)/'expected.txt'
            expected.write_text('HELLO, 8008!\n')
            # Use a real image; incorrect expectations and cycle exhaustion must fail.
            command = [sys.executable, str(ROOT/'tools/check_output.py'), '--expect', str(expected),
                       '--', str(ROOT/('ntv8008'+SUFFIX)), '-n:100000', str(ROOT/'a08/hello.hex')]
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            expected.write_text('WRONG\n')
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            command[-2] = '-n:1'
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
