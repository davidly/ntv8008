#!/usr/bin/env python3
"""Run ACK BASIC examples; --compile also checks the integer toolchain."""
from decimal import Decimal, localcontext
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import integration
from integration import ROOT, run
sys.path.insert(0,str(ROOT/'ack'))
spec=importlib.util.spec_from_file_location('ack_basic',ROOT/'ack/basic.py')
compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler)
COMPILE='--compile' in sys.argv
if COMPILE: sys.argv.remove('--compile')

class Runtime(unittest.TestCase):
    def app(self,name,budget=100_000_000):
        result=run(f'-n:{budget}',ROOT/f'ack/basic/examples/{name}.hex',timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        return result.stdout
    def test_hello(self):
        self.assertEqual(self.app('hello'),b'HELLO, ACK BASIC!\n 42 \n')
    def test_arithmetic(self):
        self.assertEqual(self.app('arithmetic'),b'12 checks\n')
    def test_sieve(self):
        count=sum(all(n%d for d in range(2,int(n**0.5)+1)) for n in range(3,16384,2))
        self.assertEqual(count,1899)
        self.assertEqual(self.app('sieve',10_000_000_000),b'1899 primes.\n')
    def test_e(self):
        with localcontext() as context:
            context.prec=220
            digits=str(Decimal(1).exp()).replace('.','')[:192]
        self.assertEqual(self.app('e',1_000_000_000),(digits+'\ndone.\n').encode())
    def test_ttt(self):
        scores,nodes=integration.Integration.minimax_reference()
        self.assertEqual(scores,[5,5,5]);self.assertEqual(nodes,6493)
        self.assertEqual(self.app('ttt',6_000_000_000),b'6493 moves\n10 iterations\n')

class Compiler(unittest.TestCase):
    def compile_run(self,text,data=b'',budget=200_000_000):
        with tempfile.TemporaryDirectory(prefix='BASIC test ') as directory:
            source=Path(directory,'example.bas');source.write_text(text)
            image,_,_=compiler.compile_source(source)
            target=source.with_suffix('.hex');target.write_text(image)
            result=run(f'-n:{budget}',target,data=data,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        return result.stdout
    def test_rebuild(self):
        for source in (ROOT/'ack/basic/examples').glob('*.bas'):
            with self.subTest(source=source.name):
                image,_,_=compiler.compile_source(source)
                self.assertEqual(image,source.with_suffix('.hex').read_text())
    def test_assignment_lowering_matches_generic_path(self):
        from unittest.mock import patch
        text="""10 DEFINT A-Z
20 DIM A(9),B(2,2)
30 X=7:Y=X*256+1:PRINT Y
40 I=2:A(I)=7:A(I+1)=A(I)+5:PRINT A(2);A(3)
50 A(5)=I*2+1:PRINT A(5)
60 X=(A(2)<A(3)):PRINT X
70 S$=CHR$(65):PRINT S$
80 B(2,1)=123:PRINT B(2,1)
90 END
"""
        expected=b' 1793 \n 7  12 \n 5 \n-1 \nA\n 123 \n'
        self.assertEqual(self.compile_run(text),expected)
        with patch.object(compiler,'lower_assignments',lambda program:program):
            self.assertEqual(self.compile_run(text),expected)

    def test_for_directions_empty_and_bound_evaluation(self):
        self.assertEqual(self.compile_run('''10 DEFINT A-Z
20 X=0:S=-2:H=1
30 FOR I=5 TO H STEP S:X=X+I:H=99:S=1:NEXT I
40 PRINT X
50 FOR I=1 TO 5 STEP -1:X=999:NEXT I
60 FOR I=5 TO 1 STEP 1:X=999:NEXT I
70 PRINT X
80 X=0:FOR I=-32768 TO -32766:X=X+1:NEXT I
90 PRINT X
100 END
'''),b' 9 \n 9 \n 3 \n')
    def test_default_types_arrays_and_option_base(self):
        self.assertEqual(self.compile_run('''10 DEFINT A-Z
20 OPTION BASE 1
30 DIM A(3),B(2,3)
40 A(1)=11:A(3)=31:B(2,3)=123
50 PRINT A(1)+A(3);B(2,3)
60 PRINT (1<2);(1>2);(NOT 0)
70 END
'''),b' 42  123 \n-1  0 -1 \n')
    def test_signed_division_and_remainder(self):
        left=[-32768,-257,-17,-1,0,1,255,32767];right=[1,2,5,255]
        source='10 DEFINT A-Z\n20 DIM A(7),B(3)\n'
        source+='30 '+':'.join(f'A({i})={n}' for i,n in enumerate(left))+'\n'
        source+='40 '+':'.join(f'B({i})={n}' for i,n in enumerate(right))+'\n'
        source+='''50 FOR I=0 TO 7:FOR J=0 TO 3
60 PRINT A(I)\\B(J);A(I) MOD B(J)
70 NEXT J:NEXT I
80 END
'''
        expected=''
        for a in left:
            for b in right:
                q=abs(a)//b*(-1 if a<0 else 1);r=a-q*b
                expected+=(' '+str(q) if q>=0 else str(q))+' '+(' '+str(r) if r>=0 else str(r))+' \n'
        self.assertEqual(self.compile_run(source),expected.encode())
    def test_gosub_and_computed_jumps(self):
        self.assertEqual(self.compile_run('''10 DEFINT A-Z
20 FOR I=1 TO 3
30 ON I GOSUB 100,200,300
40 NEXT I
50 ON 2 GOTO 60,70
60 PRINT "FAIL":END
70 PRINT "OK":END
100 PRINT "A";:RETURN
200 PRINT "B";:RETURN
300 PRINT "C";:RETURN
'''),b'ABCOK\n')
    def test_strings_and_numeric_input(self):
        self.assertEqual(self.compile_run('''10 DEFINT A-Z
20 S$="hello":T$=CHR$(65)
30 PRINT S$;T$
40 PRINT LEN(S$);ASC(T$)
50 IF S$<"world" THEN PRINT "less"
60 INPUT "N";X,Y
70 PRINT X;Y
80 END
''',b'-32768,17\n'),b'helloA\n 5  65 \nless\nN?-32768  17 \n')
    def test_gosub_runtime_errors(self):
        self.assertIn(b'ACK BASIC error',self.compile_run('10 RETURN\n20 END\n'))
        self.assertIn(b'ACK BASIC error',self.compile_run('10 GOSUB 10\n20 END\n'))
        self.assertIn(b'ACK division by zero',self.compile_run('10 DEFINT A-Z\n20 X=0:PRINT 4\\X\n30 END\n'))
    def test_paths_newlines_and_no_final_newline(self):
        original=ROOT/'ack/basic/examples/hello.bas'
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory,'other.bas')
            for data in (original.read_bytes().replace(b'\n',b'\r\n'),original.read_bytes().rstrip(b'\n')):
                source.write_bytes(data)
                self.assertEqual(compiler.compile_source(source)[0],original.with_suffix('.hex').read_text())
    def test_errors_preserve_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory,'bad.bas');target=source.with_suffix('.hex')
            for text in ('10 PRINT 1.5\n20 END\n','10 X=1\n20 END\n',
                         '10 DEFINT A-Z\n20 DIM A(8191)\n30 PRINT A(0)\n40 END\n',
                         '10 DEFINT A-Z\n20 READ X\n30 END\n',
                         '10 POKE 100,1\n20 END\n',
                         '10 LET =\n20 END\n'):
                source.write_text(text);target.write_bytes(b'keep me')
                result=subprocess.run([sys.executable,str(ROOT/'ack/basic.py'),str(source),'-o',str(target)],capture_output=True,timeout=120)
                self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(target.read_bytes(),b'keep me')

def load_tests(loader,tests,pattern):
    suite=loader.loadTestsFromTestCase(Runtime)
    if COMPILE: suite.addTests(loader.loadTestsFromTestCase(Compiler))
    return suite
if __name__=='__main__': unittest.main()
