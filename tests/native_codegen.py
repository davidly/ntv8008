#!/usr/bin/env python3
"""Differential native optimizer tests and optional C byte-state regressions."""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from integration import ROOT, ASSEMBLER, run
sys.path.insert(0,str(ROOT/'tools'))
from native8008 import optimize_functions

COMPILE='--compile' in sys.argv
if COMPILE:sys.argv.remove('--compile')


def frame(offset,base='FP'):
    offset&=65535
    return [f'LHI HIGH {base}',f'LLI LOW {base}','LAM',f'ADI {offset&255}D',
            'LEA','INL','LAM',f'ACI {offset>>8}D','LHA','LLE']


class Native(unittest.TestCase):
    def execute(self,code,pointer=0x2100,optimize=False,aligned=False,data=()):
        lines=['        ; function TEST','TEST:']+[s if s.endswith(':') else '        '+s for s in code]
        if optimize:lines=optimize_functions(lines,list(data),aligned=aligned)
        setup=f'''FP EQU 3F02H
RSP EQU 3F00H
 ORG 40H
 LHI HIGH FP
 LLI LOW FP
 LMI {pointer&255}D
 INL
 LMI {pointer>>8}D
 JMP TEST
'''
        # The values differ across page boundaries; no compiler tools needed.
        contents=' ORG 1F00H\n'+''.join(' DB '+','.join(str(((a*13)+(a>>8))&127)+'D' for a in range(i,i+16))+'\n'
                                               for i in range(0x1f00,0x2300,16))
        with tempfile.TemporaryDirectory() as directory:
            asm=Path(directory)/'test.asm';image=asm.with_suffix('.hex')
            asm.write_text(setup+'\n'.join(lines)+'\n'+ '\n'.join(data)+'\n'+contents+' END\n')
            result=subprocess.run([str(ASSEMBLER),str(asm),'-o'+str(image)],capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=run('-p','-n:1000000',image)
            self.assertEqual(result.returncode,0,result.stderr)
            return result.stdout,int(re.search(rb'(\d+) cycles',result.stderr)[1]),lines

    def differential(self,code,**kwargs):
        original=self.execute(code,**kwargs)
        optimized=self.execute(code,optimize=True,**kwargs)
        self.assertEqual(optimized[0],original[0])
        return original,optimized

    def test_frame_reuse_at_page_boundaries(self):
        improved=0
        for aligned in (False,True):
            for pointer in (0x20fe,0x20ff,0x2100,0x2101):
                if aligned and pointer&1:continue
                for first in (-2,-1,0,1,2):
                    for delta in (-2,-1,0,1,2):
                        code=frame(first)+['LAM','OUT 12']+frame(first+delta)+['LAM','OUT 12','HLT']
                        with self.subTest(aligned=aligned,pointer=pointer,first=first,delta=delta):
                            before,after=self.differential(code,pointer=pointer,aligned=aligned)
                            improved+=after[1]<before[1]
        self.assertGreater(improved,50)

    def test_live_address_results_and_flags(self):
        for suffix in (['LAE','OUT 12'],['OUT 12'],
                       ['JTC YES','LAI 48D','JMP DONE','YES:','LAI 49D','DONE:','OUT 12'],
                       ['JTZ YES','LAI 48D','JMP DONE','YES:','LAI 49D','DONE:','OUT 12']):
            for pointer in (0x20ff,0x2100):
                self.differential(frame(0)+['LAM','OUT 12']+frame(-1)+suffix+['HLT'],pointer=pointer)

    def test_unknown_return_label_and_join(self):
        # A software-call continuation has an unknown HL; its other incoming
        # branch must not make the optimizer assume HL still addresses FP.
        code=frame(0)+['NDA','JTZ JOIN','LAI LOW RESUME','LBI HIGH RESUME',
                      'JMP CALLEE','RESUME:','LHI 33D','LLI 20D','JOIN:']+frame(0)+['LAM','OUT 12','HLT']
        self.differential(code,data=('CALLEE: JMP RESUME',))

    def test_truth_masks_preserve_live_flags_and_registers(self):
        for high in (0,255):
            for low in (0,1,127,255):
                for suffix in (['OUT 12'],['LAE','OUT 12'],['JTZ YES','LAI 48D','JMP DONE','YES:','LAI 49D','DONE:','OUT 12']):
                    code=['LAI 129D','LBI 128D','LEI 75D',f'NDI {low}D','LEA','LAB',f'NDI {high}D','LBA','LAE']+suffix+['HLT']
                    self.differential(code)

    def test_leaf_register_interference_and_alias_escape(self):
        for interference in ([],['LCI 66D'],['; escaped frame']):
            store=['; local byte store -1','LBA']+frame(-1)+['LAB','LMA','; end local byte']
            load=['; local byte load -1']+frame(-1)+['LAM','LBI 0','; end local byte']
            code=['LAI 65D']+store+interference+load+['OUT 12']+load+['OUT 12','HLT']
            before,after=self.differential(code)
            self.assertEqual(after[0],b'AA')
            allocated=any('leaf register C' in s for s in after[2])
            self.assertEqual(allocated,not interference)


    def test_leaf_initialization_and_overlapping_word(self):
        store=['; local byte store -1','LBA']+frame(-1)+['LAB','LMA','; end local byte']
        load=['; local byte load -1']+frame(-1)+['LAM','LBI 0','; end local byte']
        cases=[['LAI 0D','NDA','JTZ SKIP','LAI 65D']+store+['SKIP:']+load+['OUT 12','HLT'],
               ['LAI 65D']+store+['; local word store -2','LHI 32D','LLI 255D','LMI 66D']+load+['OUT 12','HLT']]
        for code in cases:
            before,after=self.differential(code)
            self.assertFalse(any('leaf register C' in s for s in after[2]))


SOURCE='''#include <stdio.h>
unsigned char board[3];
probe(move)
unsigned char move;
{
 unsigned char p;
 p=board[move];
 if((p==board[0] && p==board[1]) || (p>board[1] && p<=board[2])) return p;
 return 0;
}
recurse(n)
int n;
{
 unsigned char x;
 x=n+250;
 if(n) return x+recurse(n-1);
 return x;
}
aliased(n)
int n;
{
 unsigned char x;
 unsigned char *p;
 x=1; p=&x; *p=n;
 return x;
}
main()
{
 unsigned int i;
 for(i=0;i<256;++i) {
  board[0]=i;board[1]=255-i;board[2]=255;
  putu(probe(0));putchar(',');
 }
 putu(recurse(8));putchar(',');putu(aliased(511));
 return 0;
}
'''


@unittest.skipUnless(COMPILE,'pass --compile to test the C frontends')
class Compilers(unittest.TestCase):
    def compiler(self,name):
        suffix='.exe' if os.name=='nt' else ''
        tool=ROOT/name/'build'/('bin/em_cemcom.ansi'+suffix if name=='ack' else 'scc8008'+suffix)
        if not tool.is_file():self.skipTest(name+' host tools unavailable')
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'bytes.c';source.write_text(SOURCE)
            target=source.with_suffix('.hex')
            result=subprocess.run([sys.executable,'-B',str(ROOT/name/'compile.py'),str(source),'-o',str(target)],capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=run('-n:200000000',target)
            self.assertEqual(result.returncode,0,result.stderr)
            expected=''.join(str(i if i==255-i or i>255-i else 0)+',' for i in range(256))
            expected+=str(sum((i+250)&255 for i in range(9)))+',255'
            self.assertEqual(result.stdout,expected.encode())

    def test_ack(self):self.compiler('ack')
    def test_smallc(self):self.compiler('smallc')


if __name__=='__main__':unittest.main()
