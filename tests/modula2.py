#!/usr/bin/env python3
"""Run Modula-2 examples; --compile also exercises the ACK frontend."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
COMPILE='--compile' in sys.argv
if COMPILE: sys.argv.remove('--compile')
import pascal
from integration import ROOT, run

spec=importlib.util.spec_from_file_location('ack_modula2',ROOT/'ack/modula2.py')
compiler=importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)

class Runtime(pascal.Runtime):
    def app(self,name,budget=100_000_000):
        result=run(f'-n:{budget}',ROOT/f'ack/modula2/examples/{name}.hex',timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        return result.stdout
    def test_hello(self):
        self.assertEqual(self.app('hello'),b'HELLO, ACK MODULA-2!\n')
    def test_arithmetic(self):
        self.assertEqual(self.app('arithmetic'),b'8 checks\n')

class Compiler(unittest.TestCase):
    def compile_run(self,text,data=b''):
        with tempfile.TemporaryDirectory(prefix='Modula2 test ') as directory:
            source=Path(directory,'example.mod'); source.write_text(text)
            image,_,_=compiler.compile_source(source)
            target=source.with_suffix('.hex'); target.write_text(image)
            result=run('-n:500000000',target,data=data,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        return result.stdout
    def test_rebuild(self):
        for source in (ROOT/'ack/modula2/examples').glob('*.mod'):
            with self.subTest(source=source.name):
                image,_,_=compiler.compile_source(source)
                self.assertEqual(image,source.with_suffix('.hex').read_text())
    def test_signed_division(self):
        left=[-32768,-257,-17,-1,0,1,255,32767]
        right=[-32768,-257,-5,-1,1,5,257,32767]
        body=[]; expected=[]
        for a in left:
            for b in right:
                if a==-32768 and b==-1: continue
                body.append(f'a:={"MIN(INTEGER)" if a==-32768 else a};b:={"MIN(INTEGER)" if b==-32768 else b};WriteInt(a DIV b,1);Write(" ");WriteInt(a MOD b,1);WriteLn;')
                expected.append(f'{a//b} {a%b}\n')
        source='''MODULE Test; FROM InOut IMPORT WriteInt,Write,WriteLn;
VAR a,b:INTEGER; BEGIN '''+'\n'.join(body)+' END Test.'
        self.assertEqual(self.compile_run(source),''.join(expected).encode())
    def test_power_of_two_division(self):
        # Constant DIV/MOD by 2**k lower to a shift and a mask (floor semantics).
        body=[]; expected=[]
        for a in (-32768,-257,-5,-4,-3,-1,0,1,3,4,5,255,32767):
            for b in (1,2,4,256):
                body.append(f'a:={"MIN(INTEGER)" if a==-32768 else a};WriteInt(a DIV {b},1);Write(" ");WriteInt(a MOD {b},1);WriteLn;')
                expected.append(f'{a//b} {a%b}\n')
        source='''MODULE Test; FROM InOut IMPORT WriteInt,Write,WriteLn;
VAR a:INTEGER; BEGIN '''+'\n'.join(body)+' END Test.'
        self.assertEqual(self.compile_run(source),''.join(expected).encode())
    def test_nested_and_var(self):
        self.assertEqual(self.compile_run('''MODULE Test;
FROM InOut IMPORT WriteInt,WriteLn;
VAR x:INTEGER;
PROCEDURE Outer(VAR a:INTEGER);
VAR b:INTEGER;
  PROCEDURE Middle(n:INTEGER);
  VAR c:INTEGER;
    PROCEDURE Inner;
    BEGIN a:=a+b+c+n; INC(b) END Inner;
  BEGIN c:=3;Inner;Inner END Middle;
BEGIN b:=2;Middle(4) END Outer;
BEGIN x:=10;Outer(x);WriteInt(x,1);WriteLn END Test.'''),b'29\n')
    def test_console_and_open_array(self):
        self.assertEqual(self.compile_run('''MODULE Test;
FROM InOut IMPORT Write,WriteString,WriteCard,WriteInt,WriteLn,Read;
VAR text:ARRAY [0..3] OF CHAR;c:CHAR;
BEGIN
text[0]:='O';text[1]:='K';text[2]:=CHR(0);text[3]:='!';
WriteString(text);WriteCard(65535,7);WriteInt(MIN(INTEGER),8);
Read(c);Write(c);WriteLn
END Test.''',b'Z'),b'OK  65535  -32768Z\n')
    def test_multidimensional(self):
        self.assertEqual(self.compile_run('''MODULE Test;
FROM InOut IMPORT WriteInt,Write,WriteLn;
VAR a:ARRAY [-1..1],[2..4] OF INTEGER;i,j:INTEGER;
BEGIN
FOR i:=-1 TO 1 DO FOR j:=2 TO 4 DO a[i,j]:=i*10+j END END;
WriteInt(a[-1,2],1);Write(' ');WriteInt(a[0,3],1);Write(' ');
WriteInt(a[1,4],1);WriteLn END Test.'''),b'-8 3 14\n')
    def test_dynamic_open_array_descriptor(self):
        self.assertEqual(self.compile_run("""MODULE Test;
FROM InOut IMPORT Write,WriteLn;
VAR a:ARRAY [3..5] OF CHAR;
PROCEDURE Cell(VAR values:ARRAY OF CHAR;i:CARDINAL):CHAR;
BEGIN RETURN values[i] END Cell;
PROCEDURE Set(VAR values:ARRAY OF CHAR;i:CARDINAL;c:CHAR);
BEGIN values[i]:=c END Set;
BEGIN a[3]:='O';Set(a,1,'K');Write(Cell(a,0));Write(Cell(a,1));WriteLn
END Test."""),b'OK\n')
    def test_runtime_traps(self):
        self.assertIn(b'ACK division by zero',self.compile_run("""MODULE Test;
FROM InOut IMPORT WriteInt; VAR a,b:INTEGER;
BEGIN a:=17;b:=0;WriteInt(a DIV b,1) END Test."""))
    def test_procedure_names(self):
        self.assertEqual(self.compile_run("""MODULE Test;
FROM InOut IMPORT WriteInt,WriteLn;
PROCEDURE main():INTEGER;BEGIN RETURN 40 END main;
PROCEDURE putu(n:INTEGER):INTEGER;BEGIN RETURN n+2 END putu;
BEGIN WriteInt(main()+putu(2),1);WriteLn END Test."""),b'44\n')
    def test_stable_paths_and_newlines(self):
        original=ROOT/'ack/modula2/examples/hello.mod'
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory,'other.mod')
            source.write_bytes(original.read_bytes().replace(b'\n',b'\r\n'))
            self.assertEqual(compiler.compile_source(source)[0],original.with_suffix('.hex').read_text())
    def test_errors_preserve_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory,'bad.mod');target=source.with_suffix('.hex')
            for text in ('MODULE Bad; BEGIN nonsense END Bad.',
                         'MODULE Bad; VAR a:ARRAY [0..8191] OF INTEGER; BEGIN a[0]:=1 END Bad.'):
                source.write_text(text);target.write_bytes(b'keep me')
                result=subprocess.run([sys.executable,str(ROOT/'ack/modula2.py'),str(source),'-o',str(target)],capture_output=True,timeout=120)
                self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(target.read_bytes(),b'keep me')

def load_tests(loader,tests,pattern):
    suite=loader.loadTestsFromTestCase(Runtime)
    if COMPILE: suite.addTests(loader.loadTestsFromTestCase(Compiler))
    return suite
if __name__=='__main__': unittest.main()
