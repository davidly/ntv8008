#!/usr/bin/env python3
"""Run native Occam examples; --compile exercises frontend and ABI regressions."""
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
spec=importlib.util.spec_from_file_location('ack_occam',ROOT/'ack/occam.py')
compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler)
COMPILE='--compile' in sys.argv
if COMPILE:sys.argv.remove('--compile')


class Runtime(unittest.TestCase):
    def app(self,name,budget=10_000_000_000):
        result=run(f'-n:{budget}',ROOT/f'ack/occam/examples/{name}.hex',timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        return result.stdout

    def test_hello(self):
        self.assertEqual(self.app('hello'),b'HELLO, ACK OCCAM!\n')

    def test_arithmetic(self):
        self.assertEqual(self.app('arithmetic'),b'20 checks\n')

    def test_sieve(self):
        count=sum(all(n%d for d in range(2,int(n**0.5)+1)) for n in range(3,16384,2))
        self.assertEqual(count,1899)
        self.assertEqual(self.app('sieve'),b'1899 primes.\n')

    def test_e(self):
        with localcontext() as ctx:
            ctx.prec=220
            digits=str(Decimal(1).exp()).replace('.','')[:192]
        self.assertEqual(self.app('e'),(digits+'\ndone.\n').encode())

    def test_ttt(self):
        scores,nodes=integration.Integration.minimax_reference()
        self.assertEqual(scores,[5,5,5]);self.assertEqual(nodes,6493)
        self.assertEqual(self.app('ttt'),f'{nodes} moves\n10 iterations\n'.encode())


@unittest.skipUnless(COMPILE,'use --compile after building ACK Occam host tools')
class Compiler(unittest.TestCase):
    def execute(self,text,data=b'',optimize_arrays=True):
        with tempfile.TemporaryDirectory(prefix='Occam regression ') as directory:
            source=Path(directory,'program.ocm');source.write_text(text)
            image,_,_=compiler.compile_source(source,optimize_arrays=optimize_arrays)
            target=source.with_suffix('.hex');target.write_text(image)
            result=run('-n:200000000',target,data=data,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            return result.stdout

    def test_rebuild(self):
        for name in ('hello','arithmetic','sieve','e','ttt'):
            with self.subTest(name=name):
                source=ROOT/f'ack/occam/examples/{name}.ocm'
                image,_,_=compiler.compile_source(source)
                self.assertEqual(image,source.with_suffix('.hex').read_text())

    def test_array_lowering_matches_generic(self):
        text=(ROOT/'ack/occam/examples/arithmetic.ocm').read_text()
        for optimize in (False,True):
            self.assertEqual(self.execute(text,optimize_arrays=optimize),b'20 checks\n')
        source=ROOT/'ack/occam/examples/arithmetic.ocm'
        optimized=compiler.compile_source(source)
        generic=compiler.compile_source(source,optimize_arrays=False)
        self.assertNotIn(' lar 2',optimized[2]);self.assertIn(' lar 2',generic[2])

    def test_lexical_links_and_reference_arguments(self):
        text='''var total:
proc outer(value n) =
  var local:
  proc middle =
    proc inner(var target) =
      seq
        target := target + local
        total := total + n
    :
    inner(total)
  :
  seq
    local := 7
    middle
:
seq
  total := 30
  outer(5)
  putu(total)
'''
        self.assertEqual(self.execute(text),b'42')

    def test_copy_slices_and_array_parameters(self):
        text='''var a[byte 8], b[byte 4], w[4]:
proc word(var data[], value index, number) =
  data[index] := number
:
seq
  seq i = [0 for 8]
    a[byte i] := i + '0'
  a[byte 4 for 4] := a[byte 0 for 4]
  b := a[byte 4 for 4]
  output ! b
  word(w, 3, 1234)
  putu(w[3])
'''
        for optimize in (False,True):
            self.assertEqual(self.execute(text,optimize_arrays=optimize),b'01231234')
            five=text.replace('a[byte 8]', 'a[byte 12]').replace('b[byte 4]', 'b[byte 5]').replace('[0 for 8]', '[0 for 12]').replace('[byte 4 for 4]', '[byte 6 for 5]').replace('[byte 0 for 4]', '[byte 0 for 5]')
            self.assertEqual(self.execute(five,optimize_arrays=optimize),b'012341234')

    def test_input_channels_and_exit(self):
        self.assertEqual(self.execute('''var ch:
seq
  input ? ch
  output ! ch
  error ! 'E'
  exit(0)
  puts("FAIL")
''',b'Q'),b'QE')
        self.assertEqual(self.execute("input ! 'X'\n"),b'Occam invalid output channel\n')

    def test_replicators_zero_dynamic_and_signed_boundary(self):
        self.assertEqual(self.execute('''var total, count:
seq
  total := 0
  count := 0
  seq i = [4 for count]
    total := total + 100
  seq i = [32766 for 2]
    total := total + 1
  putu(total)
'''),b'2')

    def test_signed_constant_and_variable_arithmetic(self):
        self.assertEqual(self.execute('''var x, y:
seq
  x := -32768
  y := -1
  if
    ((x / y) = ((-32768) / (-1))) and (((32767 + 1) < 0))
      puts("K")
    true
      puts("FAIL")
'''),b'K')

    def test_runtime_guard_trap(self):
        self.assertEqual(self.execute('''var x:
seq
  x := 2
  if
    x = 1
      puts("FAIL")
'''),b'Occam runtime trap\n')

    def test_benchmark_variants(self):
        sieve=(ROOT/'ack/occam/examples/sieve.ocm').read_text().replace('size = 8191','size = 31')
        self.assertEqual(self.execute(sieve),b'17 primes.\n')
        e=(ROOT/'ack/occam/examples/e.ocm').read_text().replace('200','16').replace('198','14')
        self.assertEqual(self.execute(e),b'27182818\ndone.\n')

    def test_unsupported_concurrency_and_invalid_sources(self):
        texts=('par\n  skip\n  skip\n', 'chan c:\nskip\n',
               'var x:\nx := now\n', 'puts(\n',
               'proc again = again:\nagain\n',
               'var a[2]:\noutput ! a[2]\n',
               'output ! 1 / 0\n','output ! 1 \\ 0\n')
        for text in texts:
            with self.subTest(text=text),tempfile.TemporaryDirectory() as directory:
                source=Path(directory,'bad.ocm');source.write_text(text)
                with self.assertRaises(compiler.CodegenError):compiler.compile_source(source)

    def test_frontend_patches_repeat_from_verified_archive(self):
        import runpy
        import hashlib
        root=ROOT/'ack/build/src/ack'
        if not root.is_dir():root=ROOT/'ack/build/msvc/src/ack'
        if not root.is_dir():self.skipTest('ACK_TOOLS has no local source build')
        apply=runpy.run_path(str(ROOT/'ack/occam/patch.py'))['apply']
        apply(root)
        files=[p for p in (root/'lang/occam/comp').iterdir() if p.is_file()]
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        apply(root)
        self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files})

    def test_main_frame_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory,'big.ocm')
            source.write_text('var big[byte 16000]:\nbig[byte 0] := 1\n')
            with self.assertRaisesRegex(compiler.CodegenError,'stack'):
                compiler.compile_source(source)

    def test_cli_paths_and_failed_compile_preserves_output(self):
        with tempfile.TemporaryDirectory(prefix='Occam paths ') as directory:
            source=Path(directory,'source with spaces.ocm');source.write_text('puts("K")\n')
            image=source.with_suffix('.hex')
            result=subprocess.run([sys.executable,str(ROOT/'ack/occam.py'),str(source),
                                   '--em',str(source.with_suffix('.e')),
                                   '--assembly',str(source.with_suffix('.asm'))],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(run(image).stdout,b'K')
            old=image.read_bytes();source.write_text('puts(\n')
            result=subprocess.run([sys.executable,str(ROOT/'ack/occam.py'),str(source)],capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn(b'syntax error',result.stderr)
            self.assertNotIn(b'Traceback',result.stderr)
            self.assertEqual(image.read_bytes(),old)


def load_tests(loader,tests,pattern):
    suite=loader.loadTestsFromTestCase(Runtime)
    if COMPILE:suite.addTests(loader.loadTestsFromTestCase(Compiler))
    return suite


if __name__=='__main__':unittest.main()
