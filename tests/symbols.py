#!/usr/bin/env python3
"""Exercise map generation and real instruction-trace annotations."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUFFIX = '.exe' if os.name == 'nt' else ''
spec = importlib.util.spec_from_file_location('symbol_tool', ROOT/'tools/symbols.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class Symbols(unittest.TestCase):
    def test_octal_aliases_and_listing_rows(self):
        text = '   000 100   377  START: HLT\n\f000 100  START    001 377  LAST    000 100  ALIAS\n'
        self.assertEqual(tool.symbols(text), '0040 ALIAS|START\n01ff LAST\n')
        with self.assertRaises(ValueError):
            tool.symbols('no symbol table')

    def test_trace_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            source = work/'program.asm'
            source.write_text('        ORG 0040H\nSTART: CAL PRINT\n        HLT\nPRINT: LAI 0101\n        OUT 12\n        RET\n        END\n')
            subprocess.run([str(ROOT/'a08'/('a08'+SUFFIX)), str(source),
                            '-l'+str(work/'program.lst'), '-o'+str(work/'program.hex')],
                           check=True, capture_output=True)
            symbol_map = work/'program.map'
            symbol_map.write_text(tool.symbols((work/'program.lst').read_text()))
            command = [str(ROOT/('ntv8008'+SUFFIX)), '-t', '-i', '-n:1000',
                       '-m:'+str(symbol_map), str(work/'program.hex')]
            result = subprocess.run(command, cwd=work, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, b'A')
            log = (work/'ntv8008.log').read_text()
            self.assertIn('START:\n', log)
            self.assertIn('PRINT:\n', log)
            self.assertIn('START + 3:\n', log)
            # A map is optional and does not affect target output or cycles.
            plain = subprocess.run([command[0], '-p', str(work/'program.hex')],
                                   cwd=work, capture_output=True)
            mapped = subprocess.run([command[0], '-p', '-m:'+str(symbol_map),
                                    str(work/'program.hex')], cwd=work, capture_output=True)
            self.assertEqual(plain.stdout, mapped.stdout)
            for text in ('4000 bad\n', '0040 a\n0040 b\n', '0040 a extra\n', 'xyz a\n'):
                symbol_map.write_text(text)
                bad = subprocess.run(command, cwd=work, capture_output=True)
                self.assertNotEqual(bad.returncode, 0)
                self.assertIn(b'invalid symbol map', bad.stderr)
            symbol_map.write_text('0040 automatic\n0044 routine\n')
            automatic = [arg for arg in command if not arg.startswith('-m:')]
            self.assertEqual(subprocess.run(automatic, cwd=work, capture_output=True).returncode, 0)
            self.assertIn('automatic:\n', (work/'ntv8008.log').read_text())
            override = work/'override.map'
            override.write_text('0040 explicit\n')
            subprocess.run(automatic + ['-m:'+str(override)], cwd=work, check=True, capture_output=True)
            self.assertIn('explicit:\n', (work/'ntv8008.log').read_text())
            self.assertNotIn('automatic:', (work/'ntv8008.log').read_text())
            symbol_map.write_text('xyz map\n')
            self.assertNotEqual(subprocess.run(automatic, cwd=work, capture_output=True).returncode, 0)
            # Ordinary execution ignores maps; malformed debug metadata cannot break it.
            self.assertEqual(subprocess.run([command[0], str(work/'program.hex')], cwd=work,
                                           capture_output=True).returncode, 0)
            symbol_map.unlink()
            self.assertEqual(subprocess.run(automatic, cwd=work, capture_output=True).returncode, 0)
            missing = subprocess.run(command, cwd=work, capture_output=True)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn(b"can't open symbol map", missing.stderr)


if __name__ == '__main__':
    unittest.main()
