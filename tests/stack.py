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


    def frame(self,compiler,pointer,result=0x1234,fault=False):
        runtime=(ROOT/compiler/'runtime.asm').read_text()
        primitives=runtime[runtime.index('; LOADSP'):runtime.index('LD1:')]
        if compiler=='smallc':primitives+=runtime[runtime.index('SCRETURN:'):runtime.index('JUMPAB:')]
        code='RSP EQU 3F00H\nFP EQU 3F02H\nRV EQU 3F04H\nSTACKMIN EQU 2000H\n ORG 40H\n JMP TEST\n'+primitives
        code+='STACKFAULT: LAI 70D\n OUT 12\n HLT\nTEST:\n'
        code+=f' LHI HIGH RSP\n LLI LOW RSP\n LMI {pointer&255}D\n INL\n LMI {pointer>>8}D\n'
        code+=' LLI LOW FP\n LMI 0D\n INL\n LMI 37D\n'
        code+=' LAI LOW RESUME\n LBI HIGH RESUME\n CAL PUSH\n'
        def check(reg,value):return f' LA{reg}\n CPI {value}D\n JFZ STACKFAULT\n'
        if compiler=='ack':
            code+=' LCI 67D\n LDI 68D\n CAL ENTER\n'
            code+=check('C',67)+check('D',68)
            # A real frame contains locals below FP; LEAVE discards them.
            code+=' LAI 250D\n LBI 255D\n CAL ADDSP\n'
            code+=f' LHI HIGH RV\n LLI LOW RV\n LMI {result&255}D\n INL\n LMI {result>>8}D\n JMP LEAVE\n'
        else:code+=f' LAI {result&255}D\n LBI {result>>8}D\n JMP SCRETURN\n'
        code+='RESUME:\n'
        if compiler=='ack':code+=' LHI HIGH RV\n LLI LOW RV\n LAM\n INL\n LBM\n'
        code+=check('A',result&255)+check('B',result>>8)
        for address,value in ((0x3f00,pointer&255),(0x3f01,pointer>>8),(0x3f02,0),(0x3f03,37)):
            code+=f' LHI {address>>8}D\n LLI {address&255}D\n LAM\n CPI {value}D\n JFZ STACKFAULT\n'
        code+=' LAI 75D\n OUT 12\n HLT\n END\n'
        with tempfile.TemporaryDirectory() as directory:
            asm=Path(directory)/'frame.asm';image=asm.with_suffix('.hex');asm.write_text(code)
            p=subprocess.run([str(ASSEMBLER),str(asm),'-o'+str(image)],capture_output=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            p=run('-n:100000',image)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(p.stdout,b'F' if fault else b'K')

    def test_ack_enter_leave_frames_and_bounds(self):
        for pointer in (0x2100,0x2102,0x2104,0x21fe,0x2200,0x3f00):
            for result in (0,0x1234,0xffff):
                with self.subTest(pointer=pointer,result=result):self.frame('ack',pointer,result)
        self.frame('ack',0x2002,fault=True)

    def test_smallc_return_on_odd_and_even_pages(self):
        for pointer in (0x2100,0x2101,0x2102,0x2103,0x21ff,0x2200,0x2201,0x3f00):
            for result in (0,0x1234,0xffff):
                with self.subTest(pointer=pointer,result=result):self.frame('smallc',pointer,result)


if __name__=='__main__': unittest.main()
