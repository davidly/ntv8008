#!/usr/bin/env python3
"""Build and exercise Robson's native 8008 Tiny BASIC, without extensions."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

from integration import ASSEMBLER, ROOT, run

spec = importlib.util.spec_from_file_location('robson_prepare', ROOT / 'robson/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class Robson(unittest.TestCase):
    def execute(self, source, file_input=False):
        with tempfile.TemporaryDirectory(prefix='robson input ') as directory:
            args = ['-n:10000000', '-p']
            data = source.encode('ascii')
            if file_input:
                path = Path(directory, 'session.bas')
                path.write_bytes(data)
                args.append('-l:' + str(path))
                data = b''
            result = run(*args, ROOT / 'a08/robson.hex', data=data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'input EOF', result.stderr)
        self.assertNotRegex(result.stdout, rb'\?[CSV]@')
        self.assertTrue(result.stdout.endswith(b']'), result.stdout)
        return result.stdout

    def test_build(self):
        self.assertEqual(prepare.adapt(), (ROOT / 'a08/robson.asm').read_text())
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory, 'robson.hex')
            result = subprocess.run([str(ASSEMBLER), str(ROOT / 'a08/robson.asm'),
                                     '-o' + str(image)], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(image.read_text(), (ROOT / 'a08/robson.hex').read_text())

    def test_arithmetic(self):
        expressions = {'2+3':5, '2+3*4':20, '255+2':1, '0-1':255,
                       '17/5':3, '3/0':0, '13.10':8, '13,10':7,
                       '12*0':0, '12*13':156}
        source = ''.join(f'print {expr}\n' for expr in expressions)
        output = self.execute(source)
        for expr, value in expressions.items():
            self.assertIn(f']print {expr}\n {value:03d}\n'.encode(), output)

    def test_hello(self):
        source = (ROOT / 'robson/examples/hello.bas').read_text()
        output = self.execute(source, file_input=True).split(b']xecute\n', 1)[1]
        self.assertEqual(output, b'Hello from Robson Tiny BASIC!\nSum 1..10: 055\n]')

    def test_call_and_fetch(self):
        source = (ROOT / 'robson/examples/features.bas').read_text()
        output = self.execute(source).split(b']xecute\n', 1)[1]
        self.assertEqual(output, b'After call: 007\n?21\nDouble: 042\n]')

    def test_conditionals(self):
        source = 'let A=7\n'
        for expression in ('A<8', 'A=7', 'A>6'):
            source += f'if {expression} print "yes"\n'
        for expression in ('A>8', 'A=6', 'A<6'):
            source += f'if {expression} print "bad"\n'
        output = self.execute(source)
        self.assertEqual(output.count(b'\nyes\n'), 3)
        self.assertNotIn(b'\nbad\n', output)

    def test_edit_view_new(self):
        source = ('10 print "old"\n10 print "new"\n20 print "deleted"\n20\n'
                  '127 print "last"\nview 10\nxecute\nnew\nxecute\n')
        output = self.execute(source)
        listed = output.split(b']view 10\n', 1)[1].split(b']xecute', 1)[0]
        self.assertIn(b'010 print "new"\n', listed)
        self.assertIn(b'127 print "last"\n', listed)
        self.assertNotIn(b'deleted', listed)
        self.assertIn(b']xecute\nnew\nlast\n]', output)
        self.assertTrue(output.endswith(b']new\n]xecute\n]'))

    def test_key_and_rubout(self):
        # KEY consumes exactly one character; its leftover newline is an empty
        # command. The run-loop poll must not consume it or terminate on EOF.
        output = self.execute('10 key A:print A\n20 stop\nxecute\nZ\n')
        self.assertIn(b']xecute\n 090\n]', output)
        output = self.execute('print 4X\x08+2\n')
        self.assertIn(b'\n 006\n]', output)

    def test_error_recovery(self):
        result = run('-n:10000000', ROOT / 'a08/robson.hex',
                     data=b'zebra\nlet a=3\nlet A 3\nprint 42\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        for code in (b'C', b'V', b'S'):
            self.assertIn(b'?' + code + b'@', result.stdout)
        self.assertIn(b'\n 042\n]', result.stdout)


if __name__ == '__main__':
    unittest.main()
