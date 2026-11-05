#!/usr/bin/env python3
"""Execute ACK/8008 examples; --compile also exercises the real C toolchain."""
from decimal import Decimal, localcontext
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import integration
from integration import ROOT, run

sys.path.insert(0, str(ROOT / 'ack'))
from codegen import CodegenError, generate
spec = importlib.util.spec_from_file_location('ack_compile', ROOT / 'ack/compile.py')
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)
COMPILE = '--compile' in sys.argv
if COMPILE:
    sys.argv.remove('--compile')


class Runtime(unittest.TestCase):
    def app(self, name, budget=100_000_000):
        result = run(f'-n:{budget}', ROOT / f'ack/examples/{name}.hex', timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_hello(self):
        self.assertEqual(self.app('hello'), b'HELLO, ACK C!\n')

    def test_arithmetic(self):
        self.assertEqual(self.app('arithmetic'), b'22 checks\n')

    def test_sieve(self):
        count = sum(all(n % d for d in range(2, int(n ** 0.5) + 1))
                    for n in range(3, 16384, 2))
        self.assertEqual(count, 1899)
        self.assertEqual(self.app('sieve', 5_000_000_000), f'{count} primes.\n'.encode())

    def test_e(self):
        with localcontext() as context:
            context.prec = 220
            digits = str(Decimal(1).exp()).replace('.', '')[:192]
        self.assertEqual(self.app('e', 1_000_000_000), (digits + '\ndone.\n').encode())

    def test_ttt(self):
        scores, nodes = integration.Integration.minimax_reference()
        self.assertEqual(scores, [5, 5, 5])
        self.assertEqual(nodes, 6493)
        self.assertEqual(self.app('ttt', 11_000_000_000),
                         f'{nodes} moves\n10 iterations\n'.encode())

    def test_cached_stack_across_joins_and_calls(self):
        # A value lives across both a branch join and a native console call.
        # Direct EM also guarantees DUP2 and indirect stores survive frontend
        # optimizations, exercising both cached and materialized operands.
        for condition, total in ((0,12),(1,106)):
            em = f""" pro $main,0
 loc 7
 loc {condition}
 zeq *1
 loc 99
 bra *2
1
 loc 5
2
 adi 2
 loc 75
 cal $putchar
 asp 2
 loc {total}
 cmi 2
 zeq *3
 loc 33
 cal $putchar
 asp 2
3
 loc 300
 dup 2
 adu 2
 dup 2
 sbu 2
 zeq *4
 loc 33
 cal $putchar
 asp 2
4
 loc 123
 lae counter
 sti 2
 lae counter
 loi 2
 loc 123
 cmi 2
 zeq *5
 loc 33
 cal $putchar
 asp 2
5
 loc 0
 ret 2
 end 0
counter
 bss 2,0,0
"""
            with self.subTest(condition=condition), tempfile.TemporaryDirectory() as directory:
                source = Path(directory, 'cache.asm')
                image = source.with_suffix('.hex')
                source.write_text(generate([em]))
                result = subprocess.run([str(integration.ASSEMBLER), str(source),
                                         '-o'+str(image)], capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                result = run('-n:1000000', image)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, b'K')

    def test_unsupported_em(self):
        for instruction in (' adf 4', ' loc 1\n loc 4\n cii', ' mlu 4', ' mon'):
            with self.subTest(instruction=instruction), self.assertRaises(CodegenError):
                generate([' pro $main,0\n' + instruction + '\n end 0\n'])
        with self.assertRaises(CodegenError):
            generate([' pro $main,0\n cal $unknown\n ret 0\n end 0\n'])


class Compiler(unittest.TestCase):
    def compile_run(self, texts, data=b'', expected=None, budget=200_000_000):
        with tempfile.TemporaryDirectory(prefix='ack C test ') as directory:
            sources = []
            for index, text in enumerate(texts):
                path = Path(directory, f'unit{index}.c')
                path.write_text(text)
                sources.append(path)
            image, assembly, em = compiler.compile_sources(sources)
            if expected is not None:
                self.assertEqual(image, expected)
            path = Path(directory, 'compiled.hex')
            path.write_text(image)
            result = run(f'-n:{budget}', path, data=data, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_examples_rebuild(self):
        # Execution of the large benchmarks is checked by Runtime above.
        for name in ('hello', 'arithmetic', 'sieve', 'e', 'ttt'):
            with self.subTest(name=name):
                image, _, _ = compiler.compile_sources([ROOT / f'ack/examples/{name}.c'])
                self.assertEqual(image, (ROOT / f'ack/examples/{name}.hex').read_text())

    def test_deferred_byte_updates(self):
        # ++i reached through a conditional skip stays in a register. RAM
        # must be current before calls, recursion, and exits that read i.
        source = '''#include <stdio.h>
static unsigned char hits[12];
static unsigned char mask[5];
static int noise(int n) { unsigned char z; z = n; return z + 1; }
static int scan(void)
{
    unsigned char i, n;
    n = 0;
    for (i = 0; i < 12; ++i) {
        if (hits[i]) continue;
        noise(99);
        n = n + i;
    }
    return n;
}
static int first(void)
{
    unsigned char i;
    for (i = 0; i < 12; ++i) {
        if (hits[i]) continue;
        break;
    }
    return i;
}
static int rec(unsigned char d)
{
    unsigned char i, sum;
    sum = 0;
    for (i = 0; i < 5; ++i) {
        if (mask[i]) continue;
        mask[i] = 1;
        if (d) sum = sum + rec(d - 1) + i; else sum = sum + i;
        mask[i] = 0;
    }
    return sum;
}
int main(void)
{
    unsigned char k;
    for (k = 0; k < 12; ++k) hits[k] = k % 3 != 1;
    putu(scan()); putchar(',');
    putu(first()); putchar(',');
    for (k = 0; k < 12; ++k) hits[k] = 1;
    putu(first()); putchar(',');
    mask[2] = 1;
    putu(rec(3));
    return 0;
}
'''
        mask = [0, 0, 1, 0, 0]

        def rec(d):
            total = 0
            for i in range(5):
                if mask[i]:
                    continue
                mask[i] = 1
                total = (total + (rec(d - 1) if d else 0) + i) & 255
                mask[i] = 0
            return total

        with tempfile.TemporaryDirectory(prefix='ack C test ') as directory:
            path = Path(directory, 'program.c')
            path.write_text(source)
            image, assembly, _ = compiler.compile_sources([path])
            # ACK's byte cache holds i on entry to first's step only.
            self.assertGreaterEqual(assembly.count('; deferred byte update'), 1)
            path = path.with_suffix('.hex')
            path.write_text(image)
            result = run('-n:200000000', path, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f'22,1,12,{rec(3)}'.encode())

    def test_stored_arguments_and_spill_slots(self):
        # Argument blocks are reserved once and stored in place; short-lived
        # expression words use scratch slots. Nested calls inside arguments,
        # recursion and older stack words must keep their values.
        source = '''#include <stdio.h>
static int one(int a) { return a + 1; }
static int six(int a, int b, int c, int d, int e, int f)
{ return a - 2*b + 3*c - 4*d + 5*e - 6*f; }
static int mix(int a, int b, int c) { return a * 100 + b * 10 + c; }
static int depth(int n, int total) { return n ? depth(n - 1, total + n) : total; }
static unsigned char cells[12];
int main(void)
{
    int i, k = 7, sum = 0;
    for (i = 0; i < 12; ++i) cells[i] = i * 3;
    for (i = 0; i < 6; ++i) {
        sum += six(i, k, i + k, cells[i], cells[i + 1] + 1, one(i) * 2);
        sum += mix(one(i), cells[(i * 5) % 12], mix(1, i, 2));
        sum ^= 1000 - (cells[i] + (cells[i + 2] - (k - cells[i + 4])));
    }
    putu(sum & 32767); putchar(','); putu(depth(30, 5));
    return 0;
}
'''
        def six(a,b,c,d,e,f): return a-2*b+3*c-4*d+5*e-6*f
        cells=[i*3 for i in range(12)];k=7;total=0
        wrap=lambda v:((v+32768)&65535)-32768
        for i in range(6):
            total=wrap(total+six(i,k,i+k,cells[i],cells[i+1]+1,(i+1)*2))
            total=wrap(total+(i+1)*100+cells[(i*5)%12]*10+(100+i*10+2))
            total=wrap(total^(1000-(cells[i]+(cells[i+2]-(k-cells[i+4])))))
        with tempfile.TemporaryDirectory(prefix='ack C test ') as directory:
            path = Path(directory, 'program.c')
            path.write_text(source)
            image, assembly, _ = compiler.compile_sources([path])
            self.assertIn('ARGS', assembly)
            self.assertIn('SPILL', assembly)
            path = path.with_suffix('.hex')
            path.write_text(image)
            result = run('-n:200000000', path, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f'{total & 32767},{5 + sum(range(31))}'.encode())

    def test_calls_switch_and_input(self):
        text = '''#include <stdio.h>
static int deep(int n) { int local = n; return n ? local + deep(n-1) : 0; }
static int pick(int n) {
  switch(n) { case -1:return 2; case 0:return 4; case 1:return 8;
              default:return 16; }
}
static int square(int n) { return n*n; }
int main(void) {
  int (*fp)(int) = square;
  if (deep(20) != 210 || fp(7) != 49) puts("FAIL");
  if (pick(-1)+pick(0)+pick(1)+pick(2) != 30) puts("FAIL");
  putchar(getchar()); putchar(getchar());
  return 0;
}
'''
        self.assertEqual(self.compile_run([text], data=b'K\n'), b'K\n')

    def test_cached_expressions_and_side_effects(self):
        text = """#include <stdio.h>
static unsigned calls;
static int value(int n) { ++calls; return n; }
static int pick(int n) { return n < 0 ? value(256-n) : value(n+1); }
int main(void) {
 int i, a, b, c, buffer[3];
 unsigned char byte;
 int *p;
 for(i=-5;i<=5;++i) {
  a=pick(i)+value(3)*value(7);
  b=i ? (i<0 ? value(100) : value(200)) : value(300);
  c=(i<0 && value(1)) || (i>0 && value(0));
  p=buffer; *p++=a; *p++=b; *p=c;
  a=b=c=17;
  byte=(unsigned char)(buffer[0]+256);
  putu(buffer[0]);putchar(',');putu(buffer[1]);putchar(',');
  putu(buffer[2]);putchar(',');putu(a+b+c);putchar(',');
  putu(byte);putchar(';');
 }
 putu(calls);return 0;
}
"""
        expected = ''
        for i in range(-5,6):
            a = (256-i if i<0 else i+1) + 21
            b = 100 if i<0 else 200 if i>0 else 300
            expected += f'{a},{b},{int(i<0)},51,{a&255};'
        self.assertEqual(self.compile_run([text]), (expected+'54').encode())

    def test_multiple_units(self):
        self.assertEqual(self.compile_run(['''#include <stdio.h>
static int value = 9;
int Value = 12;
extern int other(int);
int main(void) { if (other(value) == 42 && Value == 12) puts("OK");
                else puts("FAIL"); return 0; }
''', '''static int value = 33;
int other(int n) { return n+value; }
''']), b'OK\n')

    def test_integer_boundaries(self):
        values = [0, 1, 127, 128, 255, 256, 32767, 32768, 65535]
        unsigned = [(a, b) for a in values for b in values if b]
        signed_values = [-32768, -32767, -257, -1, 0, 1, 127, 256, 32767]
        signed = [(a, b) for a in signed_values for b in signed_values
                  if b and (a, b) != (-32768, -1)]
        def records(items):
            rows = []
            for a, b in items:
                q = (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)
                r = a - q*b
                row = [a, b, (a+b)&65535, (a-b)&65535, (a*b)&65535,
                       q & 65535, r & 65535, (a>b)-(a<b)]
                rows.append(','.join(f'{x & 65535}U' for x in row))
            return ',\n'.join(rows)
        text = '''#include <stdio.h>
static unsigned u[] = {''' + records(unsigned) + '''};
static unsigned s[] = {''' + records(signed) + '''};
static int test(unsigned *p, unsigned count, int sign) {
 unsigned i,a,b; int x,y;
 for(i=0;i<count;++i,p+=8) {
  a=p[0]; b=p[1]; x=(int)a; y=(int)b;
  if(a+b != p[2] || a-b != p[3] || a*b != p[4]) return 0;
  if(sign) {
   if((unsigned)(x/y)!=p[5] || (unsigned)(x%y)!=p[6]) return 0;
   if((x>y)-(x<y) != (int)p[7]) return 0;
  } else {
   if(a/b!=p[5] || a%b!=p[6]) return 0;
   if((a>b)-(a<b) != (int)p[7]) return 0;
  }
 }
 return 1;
}
int main(void) {
 if(test(u,sizeof(u)/16,0) && test(s,sizeof(s)/16,1)) puts("OK");
 else puts("FAIL");
 return 0;
}
'''
        self.assertEqual(self.compile_run([text], budget=10_000_000_000), b'OK\n')

    def test_runtime_traps(self):
        self.assertEqual(self.compile_run(['''#include <stdio.h>
unsigned zero;
int main(void) { putu(17/zero); return 0; }
''']), b'ACK division by zero\n')
        self.assertEqual(self.compile_run(['''#include <stdio.h>
int overflow(int n) { int locals[100]; locals[0]=n;
  return locals[0]+overflow(n+1); }
int main(void) { putu(overflow(1)); return 0; }
''']), b'ACK stack overflow\n')

    def test_cli_failure_preserves_output(self):
        with tempfile.TemporaryDirectory(prefix='ack paths ') as directory:
            source = Path(directory, 'invalid.c')
            image = source.with_suffix('.hex')
            image.write_bytes(b'original')
            for text in ('int main(void) { return ; broken }',
                         'long main(void) { volatile long x=123456L; return x*x; }'):
                source.write_text(text)
                result = subprocess.run([sys.executable, str(ROOT / 'ack/compile.py'),
                                         str(source), '-o', str(image)], capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(image.read_bytes(), b'original')


def load_tests(loader, tests, pattern):
    suite = loader.loadTestsFromTestCase(Runtime)
    if COMPILE:
        suite.addTests(loader.loadTestsFromTestCase(Compiler))
    return suite


if __name__ == '__main__':
    unittest.main()
