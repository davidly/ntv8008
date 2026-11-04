"""Selective outlining policy and executable byte/word helper checks."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from integration import ROOT, ASSEMBLER, run

sys.path.insert(0, str(ROOT / 'tools'))
from outline8008 import outline_frame_loads, share_return_values, RETURN_STORE


def load(base, offset, width=2):
    return f'''        LHI HIGH {base}
        LLI LOW {base}
        LAM
        ADI {offset & 255}D
        LEA
        INL
        LAM
        ACI {(offset >> 8) & 255}D
        LHA
        LLE
        LAM
'''+('        LBI 0' if width == 1 else '        INL\n        LBM')


class Outlining(unittest.TestCase):
    def test_requires_net_savings(self):
        text='; function F_MAIN\nF_MAIN:\n'+load('FP', 0)+'\n'
        self.assertEqual(outline_frame_loads(text, 'FP'), (text, ''))
        self.assertEqual(share_return_values(RETURN_STORE), RETURN_STORE)
        self.assertEqual(share_return_values(RETURN_STORE+'\n'+RETURN_STORE),
                         '        JMP LEAVEVALUE\n        JMP LEAVEVALUE')

    def test_loops_and_mutual_recursion_stay_inline(self):
        sites='\n'.join(load('FP', i*2) for i in range(8))+'\n'
        for body in [('; function F_A\nF_A:\nLOOP:\n'+sites+'        JFZ LOOP\n'),
                     ('; function F_A\nF_A:\n'+sites+'        JMP F_B\n'
                      '; function F_B\nF_B:\n        JMP F_A\n')]:
            self.assertEqual(outline_frame_loads(body, 'FP'), (body, ''))

    def test_helpers_execute_across_address_page(self):
        for base in ('FP', 'RSP'):
            for width, negative in ((w, n) for w in (1, 2) for n in (False, True)):
                with self.subTest(base=base, width=width, negative=negative):
                    pointer=0x2208 if negative else 0x21f8
                    setup=f'''{base} EQU 3F00H
        ORG 40H
        LHI 3FH
        LLI 0
        LMI {pointer & 255}D
        INL
        LMI {pointer >> 8}D
'''
                    body='; function F_MAIN\nF_MAIN:\n'
                    for i in range(8):
                        body+=load(base,i*2-(16 if negative else 0),width)+'\n        OUT 12\n        LAB\n        OUT 12\n'
                    body+='        HLT\n'
                    outlined,helpers=outline_frame_loads(body,base)
                    self.assertIn('CAL NATIVE_FRAME_LOAD',outlined)
                    values=','.join(str(x)+'D' for i in range(8) for x in (65+i,97+i))
                    suffix='        ORG 21F8H\n        DB '+values+'\n        END\n'
                    expected=b''.join(bytes((65+i,97+i if width==2 else 0)) for i in range(8))
                    for code in (body,outlined+helpers):
                        with tempfile.TemporaryDirectory() as directory:
                            source=Path(directory)/'test.asm';image=source.with_suffix('.hex')
                            source.write_text(setup+code+suffix)
                            p=subprocess.run([str(ASSEMBLER),str(source),'-o'+str(image)],capture_output=True)
                            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                            result=run('-n:100000',image)
                            self.assertEqual(result.returncode,0,result.stderr)
                            self.assertEqual(result.stdout,expected)


if __name__=='__main__':
    unittest.main()
