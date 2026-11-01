#!/usr/bin/env python3
"""Compile and exercise the shared Wumpus example with both C backends."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT/'examples/wumpus'
COMPILE = '--compile' in sys.argv
if COMPILE:
    sys.argv.remove('--compile')


@unittest.skipUnless(COMPILE, 'use --compile after setup --smallc --ack to build Wumpus')
class Wumpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for compiler in ('smallc','ack'):
            result = subprocess.run([sys.executable, str(HERE/'build.py'), compiler],
                                    capture_output=True, timeout=120)
            if result.returncode:
                raise RuntimeError((result.stdout+result.stderr).decode(errors='replace'))

    def execute(self, compiler, data):
        result = subprocess.run([str(ROOT/('ntv8008.exe' if os.name=='nt' else 'ntv8008')),
                                 '-n:200000000', str(HERE/'build'/(compiler+'.hex'))],
                                input=data, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.replace(b'\r\n',b'\n')

    def test_transcripts(self):
        for session in sorted((HERE/'sessions').glob('*.txt')):
            for compiler in ('smallc','ack'):
                with self.subTest(session=session.stem, compiler=compiler):
                    self.assertEqual(self.execute(compiler, session.read_bytes()),
                                     session.with_suffix('.out').read_bytes())

    def test_computer_seeds(self):
        for seed in (1, 2, 42, 1000, 32767):
            outputs = []
            for compiler in ('smallc','ack'):
                with self.subTest(seed=seed, compiler=compiler):
                    output = self.execute(compiler, f'C\n{seed}\n'.encode())
                    self.assertIn(b'AHA! YOU GOT THE WUMPUS!', output)
                    self.assertNotIn(b'YOU LOSE!', output)
                    outputs.append(output)
            self.assertEqual(outputs[0], outputs[1])

    def test_maps_and_image_headroom(self):
        for compiler in ('smallc','ack'):
            image = HERE/'build'/(compiler+'.hex')
            self.assertTrue(image.with_suffix('.map').read_text().strip())
            records = [bytes.fromhex(line[1:]) for line in image.read_text().splitlines()]
            end = max(int.from_bytes(row[1:3],'big')+row[0] for row in records if row[3]==0)
            self.assertLessEqual(end, 0x3d00)


if __name__ == '__main__':
    unittest.main()
