#!/usr/bin/env python3
"""Execute Pascal examples; --compile also validates ACK's Pascal toolchain."""
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
spec=importlib.util.spec_from_file_location('ack_pascal',ROOT/'ack/pascal.py')
compiler=importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)
COMPILE='--compile' in sys.argv
if COMPILE:
    sys.argv.remove('--compile')

class Runtime(unittest.TestCase):
    def app(self,name,budget=100_000_000):
        result=run(f'-n:{budget}',ROOT/f'ack/pascal/examples/{name}.hex',timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        return result.stdout

    def test_hello(self):
        self.assertEqual(self.app('hello'),b'HELLO, ACK PASCAL!\n')

    def test_arithmetic(self):
        self.assertEqual(self.app('arithmetic'),b'13 checks\n')

    def test_sieve(self):
        count=sum(all(n%d for d in range(2,int(n**0.5)+1)) for n in range(3,16384,2))
        self.assertEqual(count,1899)
        self.assertEqual(self.app('sieve',7_000_000_000),f'{count} primes.\n'.encode())

    def test_e(self):
        with localcontext() as ctx:
            ctx.prec=220
            digits=str(Decimal(1).exp()).replace('.','')[:192]
        self.assertEqual(self.app('e',2_000_000_000),(digits+'\ndone.\n').encode())

    def test_ttt(self):
        scores,nodes=integration.Integration.minimax_reference()
        self.assertEqual(scores,[5,5,5])
        self.assertEqual(nodes,6493)
        self.assertEqual(self.app('ttt',20_000_000_000),
                         f'{nodes} moves\n10 iterations\n'.encode())

class Compiler(unittest.TestCase):
    def compile_run(self,text,data=b'',budget=200_000_000):
        with tempfile.TemporaryDirectory(prefix='Pascal test ') as directory:
            source=Path(directory,'example.p')
            source.write_text(text)
            image,_,_=compiler.compile_source(source)
            target=source.with_suffix('.hex')
            target.write_text(image)
            result=run(f'-n:{budget}',target,data=data,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        return result.stdout

    def test_rebuild(self):
        for name in ('hello','arithmetic','sieve','e','ttt'):
            with self.subTest(name=name):
                source=ROOT/f'ack/pascal/examples/{name}.p'
                image,_,_=compiler.compile_source(source)
                self.assertEqual(image,source.with_suffix('.hex').read_text())

    def test_fixed_arrays_match_generic_runtime(self):
        from unittest.mock import patch
        source=ROOT/'ack/pascal/examples/arithmetic.p'
        optimized=compiler.compile_source(source)
        with patch.object(compiler,'lower_fixed_arrays',lambda text:text):
            generic=compiler.compile_source(source)
        self.assertNotIn(' lar 2',optimized[2])
        self.assertNotIn(' sar 2',optimized[2])
        self.assertIn(' lar 2',generic[2])
        self.assertIn(' sar 2',generic[2])
        with tempfile.TemporaryDirectory() as directory:
            for image,_,_ in (optimized,generic):
                target=Path(directory,'array.hex');target.write_text(image)
                result=run('-n:100000000',target,timeout=60)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(result.stdout,b'13 checks\n')

    def test_nested_static_links_and_var_arrays(self):
        self.assertEqual(self.compile_run('''program test(output);
type cells=packed array[-1..1] of 0..255;
var x:integer; values:cells;
procedure outer(var a:integer);
var b:integer;
  procedure middle(n:integer);
  var c:integer;
    procedure inner;
    begin a:=a+n+b+c; b:=b+1 end;
  begin c:=3; inner; inner end;
begin b:=2; middle(4) end;
procedure fill(var a:cells);
var i:integer;
begin for i:=-1 to 1 do a[i]:=i+100 end;
begin
 x:=10;outer(x);fill(values);
 writeln(x:1,' ',values[-1]:1,' ',values[1]:1)
end.'''),b'29 99 101\n')

    def test_multidimensional_arrays(self):
        self.assertEqual(self.compile_run("""program test(output);
var a:array[-1..1,2..4]of integer;i,j:integer;
begin
 for i:=-1 to 1 do for j:=2 to 4 do a[i,j]:=i*10+j;
 writeln(a[-1,2]:1,' ',a[0,3]:1,' ',a[1,4]:1)
end."""), b'-8 3 14\n')

    def test_pascal_names_do_not_collide_with_c_runtime(self):
        self.assertEqual(self.compile_run("""program test(output);
function main:integer;begin main:=40 end;
function putu(n:integer):integer;begin putu:=n+2 end;
begin writeln(main+putu(2):1) end."""), b'44\n')

    def test_signed_division_and_modulo(self):
        left=[-32768,-257,-17,-1,0,1,255,32767]
        right=[1,2,5,255,256,32767]
        init=';'.join(f'a[{i+1}]:={v}' for i,v in enumerate(left))+';'
        init+=';'.join(f'b[{i+1}]:={v}' for i,v in enumerate(right))+';'
        source='''program test(output);
var a:array[1..8]of integer;b:array[1..6]of integer;i,j:integer;
begin '''+init+'''
 for i:=1 to 8 do for j:=1 to 6 do
  writeln(a[i] div b[j]:1,',',a[i] mod b[j]:1);
 writeln(((-17) mod 5):1)
end.'''
        expected=''
        for a in left:
            for b in right:
                q=abs(a)//b*(-1 if a<0 else 1)
                expected+=f'{q},{a%b}\n'
        self.assertEqual(self.compile_run(source), (expected+'3\n').encode())

    def test_native_division_matches_wrappers(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory,'arithmetic.p')
            source.write_text("""program test(output);
var a,b:integer;
begin
 a:=-32768;b:=-1;writeln(a div b:1);
 a:=-257;b:=256;writeln(a div b:1,' ',a mod b:1);
 b:=-7;writeln(a div b:1)
end.""")
            native=compiler.compile_source(source)
            with patch.object(compiler,'lower_division',lambda text:text):
                wrappers=compiler.compile_source(source)
            self.assertIn(' pmod 2',native[2])
            self.assertNotIn(' cal $_mdi',native[2])
            for image,_,_ in (native,wrappers):
                target=source.with_suffix('.hex');target.write_text(image)
                result=run('-n:200000000',target,timeout=60)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(result.stdout,b'-32768\n-1 255\n36\n')

    def test_console_formatting_and_input(self):
        self.assertEqual(self.compile_run('''program test(input,output);
var n:integer;c:char;
begin
 read(n);readln;read(c);
 writeln(n:1,':',c);
 writeln(17:4,' ',true,' ',false:5,' ','abc':5)
end.''',b'-32768\nZ\n'),
                         ('-32768:Z\n'+f'{17:4d} {"true":>5} {"false":>5} {"abc":>5}\n').encode())

    def test_traps(self):
        self.assertEqual(self.compile_run('''program test(output);
var zero:integer;begin zero:=0;writeln(4 div zero:1) end.'''),
                         b'ACK division by zero\n')
        self.assertEqual(self.compile_run('''program test(output);
var n:integer;begin n:=-1;writeln(4 mod n:1) end.'''),
                         b'Pascal invalid MOD divisor\n')
        self.assertEqual(self.compile_run('''program test(output);
function overflow(n:integer):integer;
var a:array[0..99]of integer;
begin a[0]:=n;overflow:=a[0]+overflow(n+1) end;
begin writeln(overflow(1):1) end.'''),b'ACK stack overflow\n')

    def test_reproducible_paths_and_crlf(self):
        with tempfile.TemporaryDirectory(prefix='Pascal paths ') as directory:
            a=Path(directory,'different name.p');b=Path(directory,'other.p')
            text="program test(output);\nbegin writeln('OK') end.\n"
            a.write_bytes(text.encode());b.write_bytes(text.replace('\n','\r\n').encode())
            self.assertEqual(compiler.compile_source(a)[0],compiler.compile_source(b)[0])

    def test_errors_preserve_output(self):
        with tempfile.TemporaryDirectory(prefix='Pascal errors ') as directory:
            source=Path(directory,'invalid.p');target=source.with_suffix('.hex')
            target.write_bytes(b'keep me')
            for text in ('program bad;begin broken end.',
                         'program bad(output);var x:real;begin x:=1.0;writeln(x/2.0)end.',
                         'program bad(output);begin writeln(3 mod (-1))end.',
                         'program bad;var a:array[1..8191]of integer;begin a[1]:=2 end.'):
                source.write_text(text)
                result=subprocess.run([sys.executable,str(ROOT/'ack/pascal.py'),str(source),
                                       '-o',str(target)],capture_output=True,timeout=120)
                self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(target.read_bytes(),b'keep me')

def load_tests(loader,tests,pattern):
    suite=loader.loadTestsFromTestCase(Runtime)
    if COMPILE:
        suite.addTests(loader.loadTestsFromTestCase(Compiler))
    return suite

if __name__=='__main__':
    unittest.main()
