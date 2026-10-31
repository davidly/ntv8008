#!/usr/bin/env python3
"""Check fixed-descriptor lowering and its native stack/memory behavior."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from integration import ROOT, ASSEMBLER, run
sys.path.insert(0,str(ROOT/'ack'))
from codegen import generate
from wirth import lower_fixed_arrays

class Arrays(unittest.TestCase):
    def test_fallback(self):
        for source in (' lol -2\n lar 2\n',
                       '.1\n con 0,9,1\n lae .1\n lar 2\n',
                       '.1\n rom 0,9,3\n lae .1\n lar 2\n',
                       '.1\n rom 0,9,2\n lae .1+2\n sar 2\n'):
            with self.subTest(source=source):
                self.assertEqual(lower_fixed_arrays(source),source)
    def test_descriptors_are_local_to_each_unit(self):
        fixed='.1\n rom 0,9,1\n lae .1\n lar 2\n'
        dynamic='.1\n bss 6,0,0\n lae .1\n lar 2\n'
        self.assertNotIn('lar 2',lower_fixed_arrays(fixed))
        self.assertEqual(lower_fixed_arrays(dynamic),dynamic)
    def test_aggregate_address(self):
        source='.1\n rom -2I2,4U2,6\n lae .1\n aar 2\n'
        result=lower_fixed_arrays(source)
        self.assertIn(' loc 65534\n sbu 2\n loc 6\n mlu 2\n ads 2\n',result)
        self.assertNotIn(' aar ',result)
    def test_native_accesses_and_stack(self):
        for lower,index in ((0,0),(-2,-1),(4,6)):
            for stride,value in ((1,231),(2,0x8123)):
                with self.subTest(lower=lower,stride=stride), tempfile.TemporaryDirectory() as directory:
                    offset=(index-lower)*stride
                    em=f''' pro $_m_a_i_n,0
 loc 1234
 loc {value}
 lae buffer+254
 loc {index}
 lae .1
 sar 2
 lae buffer+254
 loc {index}
 lae .1
 lar 2
 loc {value}
 cmi 2
 zne *9
 loc 1234
 cmi 2
 zne *9
 lae buffer+254
 loc {index}
 lae .1
 aar 2
 lae buffer+{254+offset}
 cmi 2
 zne *9
 loc 75
 cal $putchar
 asp 2
 ret 0
9
 loc 33
 cal $putchar
 asp 2
 ret 0
 end 0
.1
 rom {lower},9,{stride}
buffer
 bss 512,0,0
'''
                    lowered=lower_fixed_arrays(em)
                    self.assertNotIn(' lar 2',lowered)
                    self.assertNotIn(' sar 2',lowered)
                    source=Path(directory,'array.asm');image=source.with_suffix('.hex')
                    source.write_text(generate([lowered],pascal=True))
                    result=subprocess.run([str(ASSEMBLER),str(source),'-o'+str(image)],capture_output=True,timeout=10)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    result=run('-n:1000000',image)
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertEqual(result.stdout,b'K')
if __name__=='__main__': unittest.main()
