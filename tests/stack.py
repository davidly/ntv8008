#!/usr/bin/env python3
"""RAM-stack ABI and page-boundary tests for both compiler runtimes."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from integration import ROOT, ASSEMBLER, run


class Stack(unittest.TestCase):
    def execute(self, compiler, pointer, fault=False):
        runtime=(ROOT/compiler/'runtime.asm').read_text()
        # Use the actual primitives without the program-entry push or other helpers.
        runtime=runtime[runtime.index('; LOADSP'):runtime.index('LOCAL:' if compiler=='ack' else 'LD1:')]
        source='RSP EQU 3F00H\nSTACKMIN EQU 2000H\n ORG 40H\n JMP TEST\n'+runtime
        source+='''STACKFAULT: LAI 70D
 OUT 12
 HLT
TEST:
'''
        source+=f''' LHI HIGH RSP
 LLI LOW RSP
 LMI {pointer&255}D
 INL
 LMI {pointer>>8}D
 LCI 67D
 LDI 68D
 LAI 65D
 LBI 66D
 CAL PUSH
'''
        # Check AB/CD after PUSH, pointer and stored word, then POP and check again.
        def check(reg, value):
            return f' LA{reg}\n CPI {value}D\n JFZ STACKFAULT\n'
        source+=check('A',65)+check('B',66)+check('C',67)+check('D',68)
        for address,value in ((0x3f00,(pointer-2)&255),(0x3f01,(pointer-2)>>8),
                              (pointer-2,65),(pointer-1,66)):
            source+=f' LHI {address>>8}D\n LLI {address&255}D\n LAM\n CPI {value}D\n JFZ STACKFAULT\n'
        source+=' LAI 0\n LBI 0\n CAL POP\n'
        source+=check('A',65)+check('B',66)+check('C',67)+check('D',68)
        source+=f''' LHI HIGH RSP
 LLI LOW RSP
 LAM
 CPI {pointer&255}D
 JFZ STACKFAULT
 INL
 LAM
 CPI {pointer>>8}D
 JFZ STACKFAULT
 LAI 75D
 OUT 12
 HLT
 END
'''
        with tempfile.TemporaryDirectory() as directory:
            asm=Path(directory)/'stack.asm'; image=asm.with_suffix('.hex')
            asm.write_text(source)
            result=subprocess.run([str(ASSEMBLER),str(asm),'-o'+str(image)],capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=run('-n:100000',image)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout,b'F' if fault else b'K')

    def test_ack_even_addresses(self):
        for pointer in (0x2002,0x2100,0x2102,0x21fe,0x2200,0x3f00):
            with self.subTest(pointer=pointer): self.execute('ack',pointer)

    def test_smallc_even_and_odd_addresses(self):
        for pointer in (0x2002,0x2003,0x2100,0x2101,0x2102,0x2103,0x21fe,0x21ff,0x2200,0x2201,0x3f00):
            with self.subTest(pointer=pointer): self.execute('smallc',pointer)

    def test_push_bounds_on_both_paths(self):
        for compiler in ('ack','smallc'):
            for pointer in (0x2000,0x1ffe):
                with self.subTest(compiler=compiler,pointer=pointer):
                    self.execute(compiler,pointer,fault=True)


if __name__=='__main__': unittest.main()
