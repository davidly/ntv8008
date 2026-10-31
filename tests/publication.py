#!/usr/bin/env python3
"""Verify the publication boundary and retained third-party license records."""
import hashlib
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.publication import validate, candidates


class Publication(unittest.TestCase):
    def test_inventory(self):
        result=subprocess.run([sys.executable,str(ROOT/'tools/publication.py')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_historical_inputs_cannot_be_published(self):
        names=candidates()
        for name in ('a08/scelbal.hex','a08/forth.asm','plm8/upstream/plm1.sav',
                     'plm8/examples/e.hex','a08/a85.c','a08/star.asm','ack/build/ack.tar.gz'):
            with self.subTest(name=name),self.assertRaises(ValueError):
                validate(names|{name})

    def test_retained_upstream_sources_and_notices(self):
        pins={
            'robson/upstream/basic.asm':'20b53d4ad4ea67011939cb6047ae091bddb6e1f5a3c33e5687cbc0da8120f4f2',
            'robson/upstream/LICENSE':'559eefa768dd23038cb43e5e348287137ddff64eac5bd71e0dca2136430acd95'}
        for name,digest in pins.items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest)
        self.assertIn('public domain',(ROOT/'smallc/upstream/LICENSE').read_text())
        self.assertIn('Redistribution and use',(ROOT/'ack/ACK-COPYRIGHT').read_text())
        self.assertIn('non-commercial',(ROOT/'scelbal/NOTICE.txt').read_text())


if __name__=='__main__':
    unittest.main()
