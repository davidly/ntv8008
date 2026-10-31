#!/usr/bin/env python3
"""Validate SmallC-85/8008 examples; --compile also checks the C toolchain."""
from decimal import Decimal, localcontext
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import integration
from integration import ROOT, run

# Avoid colliding with ACK's module named codegen when run by a test collector.
spec = importlib.util.spec_from_file_location('smallc_codegen', ROOT / 'smallc/codegen.py')
codegen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codegen)
sys.modules['codegen'] = codegen
spec = importlib.util.spec_from_file_location('smallc_compile', ROOT / 'smallc/compile.py')
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)
COMPILE = '--compile' in sys.argv
if COMPILE:
    sys.argv.remove('--compile')

class Runtime(unittest.TestCase):
    def app(self, name, budget=300_000_000):
        result = run(f'-n:{budget}', ROOT / f'smallc/examples/{name}.hex', timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_hello(self):
        self.assertEqual(self.app('hello'), b'HELLO, SMALL C!\n')

    def test_arithmetic(self):
        self.assertEqual(self.app('arithmetic'), b'24 checks\n')

    def test_sieve(self):
        primes = sum(all(n % d for d in range(2, int(n ** 0.5) + 1))
                     for n in range(3, 16384, 2))
        self.assertEqual(primes, 1899)
        self.assertEqual(self.app('sieve', 7_000_000_000), f'{primes} primes.\n'.encode())

    def test_e(self):
        with localcontext() as ctx:
            ctx.prec = 220
            digits = str(Decimal(1).exp()).replace('.', '')[:192]
        self.assertEqual(self.app('e', 2_000_000_000), (digits + '\ndone.\n').encode())

    def test_ttt(self):
        scores, nodes = integration.Integration.minimax_reference()
        self.assertEqual(scores, [5, 5, 5])
        self.assertEqual(nodes, 6493)
        self.assertEqual(self.app('ttt', 14_000_000_000),
                         f'{nodes} moves\n10 iterations\n'.encode())

class Compiler(unittest.TestCase):
    def compile_run(self, text, data=b'', budget=300_000_000):
        with tempfile.TemporaryDirectory(prefix='smallc C test ') as directory:
            source = Path(directory, 'program.c')
            source.write_text(text)
            image, _, _ = compiler.compile_source(source)
            target = source.with_suffix('.hex')
            target.write_text(image)
            result = run(f'-n:{budget}', target, data=data, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_rebuild(self):
        for name in ('hello','arithmetic','sieve','e','ttt','snake'):
            with self.subTest(name=name):
                image, _, _ = compiler.compile_source(ROOT / f'smallc/examples/{name}.c')
                self.assertEqual(image, (ROOT / f'smallc/examples/{name}.hex').read_text())

    def test_comparison_boundaries(self):
        for typ, values in [('int', [-32768,-256,-1,0,1,255,256,32767]),
                            ('unsigned int', [0,1,255,256,32767,32768,65535])]:
            text = '''#include <stdio.h>
%s values[%d] = {%s};
main() {
 int i, j;
 for (i=0; i<%d; ++i) for (j=0; j<%d; ++j) {
  putchar('0'+(values[i]<values[j]));
  putchar('0'+(values[i]<=values[j]));
  putchar('0'+(values[i]>values[j]));
  putchar('0'+(values[i]>=values[j]));
  putchar('0'+(values[i]==values[j]));
  putchar('0'+(values[i]!=values[j]));
 }
 return 0;
}
''' % (typ,len(values),','.join(map(str,values)),len(values),len(values))
            expected = ''.join(str(int(v)) for a in values for b in values
                               for v in (a<b,a<=b,a>b,a>=b,a==b,a!=b)).encode()
            with self.subTest(typ=typ):
                self.assertEqual(self.compile_run(text), expected)

    def test_arithmetic_boundaries(self):
        # Cross-check the register/stack helper ABI with full-width operands,
        # signed division/remainders, and values carrying across byte boundaries.
        for typ, left, right in [
                ('int', [-32768,-256,-1,0,1,256,32767], [-257,-1,0,1,255,256]),
                ('unsigned int', [0,1,255,256,32767,32768,65535], [0,1,255,256,65535])]:
            text = """%s left[%d]={%s}, right[%d]={%s};
main() {
 int i,j;
 for(i=0;i<%d;++i) for(j=0;j<%d;++j) {
  putu(left[i]+right[j]);putchar(',');
  putu(left[i]-right[j]);putchar(',');
  putu(left[i]*right[j]);putchar(',');
  if(right[j]) {
   putu(left[i]/right[j]);putchar(',');
   putu(left[i]%%right[j]);putchar(',');
  }
  putu(left[i]&right[j]);putchar(',');
  putu(left[i]|right[j]);putchar(',');
  putu(left[i]^right[j]);putchar(',');
  putu(left[i]<<1);putchar(',');
  putu(left[i]>>8);putchar(',');
  putu(~left[i]);putchar(';');
 }
 return 0;
}
""" % (typ,len(left),','.join(map(str,left)),len(right),
       ','.join(map(str,right)),len(left),len(right))
            expected = ''
            for a in left:
                for b in right:
                    values = [a+b,a-b,a*b]
                    if b:
                        q = abs(a)//abs(b) * (-1 if (a<0) != (b<0) else 1)
                        values += [q,a-q*b]
                    values += [a&b,a|b,a^b,a<<1,a>>8,~a]
                    expected += ','.join(str(v & 65535) for v in values) + ';'
            with self.subTest(typ=typ):
                self.assertEqual(self.compile_run(text, budget=3_000_000_000), expected.encode())

    def test_short_circuit_values_and_side_effects(self):
        text="""int calls;
touch(n) int n; { ++calls; return n; }
main() {
 int a,i,r; int values[7];
 values[0]=-32768;values[1]=-1;values[2]=0;values[3]=1;
 values[4]=255;values[5]=256;values[6]=32767;
 for(i=0;i<7;++i) {
  a=values[i];calls=0;
  r=(a<0)&&touch(1);putchar(r+48);
  r=(a>=0)||touch(0);putchar(r+48);
  r=((a==-1)&&touch(2))||touch(3);putchar(r+48);
  r=(a>255)&&((a!=256)||touch(0));putchar(r+48);
  putu(calls);putchar(';');
 }
 return 0;
}"""
        expected=''
        for a in (-32768,-1,0,1,255,256,32767):
            calls=0
            def touch(n):
                nonlocal calls
                calls+=1
                return n
            results=[a<0 and touch(1),a>=0 or touch(0),
                     (a==-1 and touch(2)) or touch(3),a>255 and (a!=256 or touch(0))]
            expected+=''.join(str(int(bool(r))) for r in results)+str(calls)+';'
        self.assertEqual(self.compile_run(text),expected.encode())

    def test_indexed_stores_preserve_calls_and_order(self):
        self.assertEqual(self.compile_run("""int calls; unsigned char data[260];
index() { ++calls; return 256; }
value() { ++calls; return 231; }
main() {
 int i; char pad; pad=7; i=256;calls=0;
 data[index()]=value();
 putu(data[i]);putchar(',');putu(calls);putchar(',');putu(pad);
 return 0;
}"""),b'231,2,7')

    def test_nested_calls_and_unaligned_locals(self):
        self.assertEqual(self.compile_run("""
value(n) int n; { char odd; odd=1; return n+odd-1; }
main() {
 char pad;
 int n;
 pad=7;
 n=value(1000)+value(2)*value(3)-value(4);
 putu(n);putchar(',');
 n=256;--n;putu(n);putchar(',');
 n=0;--n;putu(n);putchar(',');
 n=-1;++n;putu(n);putchar(',');putu(pad);
 return 0;
}
"""), b'1002,255,65535,0,7')

    def test_console_and_ansi_arguments(self):
        self.assertEqual(self.compile_run('''
add(int a, int b) { return a+b; }
main() {
 putu(add(12, 30)); putchar(getchar()); putchar(getchar());
 return 0;
}''', b'X\n'), b'42X\n')

    def test_switch_fallthrough_and_loops(self):
        self.assertEqual(self.compile_run('''
main() {
 int i, n;
 n=0;
 for(i=-2;i<5;++i) {
  switch(i) {
   case -2:n+=1;break;
   case -1:n+=2;
   case 0:n+=4;break;
   case 3:n+=8;break;
   default:n+=16;break;
  }
 }
 putu(n); return 0;
}'''), b'67')

    def test_traps(self):
        self.assertEqual(self.compile_run('main(){int n;n=0;return 4/n;}'),
                         b'Small C division by zero\n')
        self.assertEqual(self.compile_run('''
recurse(n) int n; { char buffer[128];buffer[0]=n;return recurse(n+1)+buffer[0]; }
main(){return recurse(0);}
'''), b'Small C stack overflow\n')

    def test_errors_preserve_output(self):
        with tempfile.TemporaryDirectory(prefix='smallc invalid ') as directory:
            source = Path(directory, 'bad.c')
            target = Path(directory, 'old.hex')
            target.write_bytes(b'keep me')
            for text in ('main(){float n;return 0;}', 'main(){return unknown();}',
                         'char huge[16000];main(){return huge[0];}'):
                source.write_text(text)
                result = subprocess.run([sys.executable, str(ROOT / 'smallc/compile.py'),
                                         str(source), '-o', str(target)], capture_output=True,
                                        timeout=120)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(target.read_bytes(), b'keep me')

def load_tests(loader, tests, pattern):
    suite = loader.loadTestsFromTestCase(Runtime)
    if COMPILE:
        suite.addTests(loader.loadTestsFromTestCase(Compiler))
    return suite

if __name__ == '__main__':
    unittest.main()
