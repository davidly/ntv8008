#!/usr/bin/env python3
"""Exercise the original b8008 integer BASIC and its full benchmark workloads."""
from decimal import Decimal, localcontext
import importlib.util
from pathlib import Path
import random
import re
import subprocess
import tempfile
import unittest

import integration
from integration import ROOT, ASSEMBLER, run

spec = importlib.util.spec_from_file_location('b8008_prepare', ROOT/'b8008/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def signed(n):
    return ((n + 32768) & 65535) - 32768


class B8008(unittest.TestCase):
    def execute(self, source, errors=False, file_input=False, limit=50000000000, image=None):
        with tempfile.TemporaryDirectory(prefix='b8008 BASIC ') as directory:
            args = ['-p', '-n:'+str(limit)]
            data = source.encode('ascii')
            if file_input:
                session = Path(directory)/'input file.bas'
                session.write_bytes(data)
                args.append('-l:'+str(session))
                data = b''
            result = run(*args, image or ROOT/'a08/b8008.hex', data=data, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'input EOF', result.stderr)
        self.assertTrue(result.stdout.endswith(b'>'), result.stdout[-300:])
        if not errors:
            self.assertNotRegex(result.stdout, rb'\?(SYNTAX|BOUNDS|STACK|LINE|MEMORY|DIVIDE)')
        return result.stdout.decode('ascii')

    def values(self, expressions):
        source = ''.join('PRINT "@";'+expr+'\n' for expr in expressions)
        output = self.execute(source)
        return [int(n) for n in re.findall(r'^@(-?\d+)\n', output, re.M)]

    def test_rebuild(self):
        self.assertEqual(prepare.adapt(), (ROOT/'a08/b8008.asm').read_text())
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'b8008.hex'
            result = subprocess.run([str(ASSEMBLER), str(ROOT/'a08/b8008.asm'),
                                     '-o'+str(target)], capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertEqual(target.read_text(), (ROOT/'a08/b8008.hex').read_text())
            # The full 8191-byte sieve array plus program must fit below workspace.
            records = target.read_text().splitlines()
            end = max(int(r[3:7],16)+int(r[1:3],16) for r in records if r[7:9]=='00')
            self.assertLess(end+8191+512, 0x3b00)

    def test_arithmetic(self):
        cases = {'2+3*4':14, '(2+3)*4':20, '20-7-2':11,
                 '-17/5':-3, '17/-5':-3, '-17/-5':3, '-17 MOD -5':-2,
                 '32767+1':-32768, '-32768/-1':-32768, '30000*3':24464,
                 '5 AND 3':1, '5 OR 2':7, 'ABS(-123)':123,
                 '1+(2*(3+4))':15, '+17':17}
        self.assertEqual(self.values(cases), list(cases.values()))

    def test_random_integer_math(self):
        rng = random.Random(8008)
        expressions, expected = [], []
        for _ in range(80):
            a, b = rng.randrange(-32768,32768), rng.randrange(-32768,32768)
            if b == 0:
                b = 1
            quotient = abs(a)//abs(b) * (-1 if (a<0)!=(b<0) else 1)
            for op, value in [('+',a+b), ('-',a-b), ('*',a*b),
                              ('/',quotient), (' MOD ',a-quotient*b)]:
                expressions.append(f'({a}){op}({b})')
                expected.append(signed(value))
        self.assertEqual(self.values(expressions), expected)

    def test_signed_comparisons(self):
        expressions, expected = [], []
        for a in (-32768,-257,-1,0,255,256,32767):
            for b in (-32768,-1,0,256,32767):
                for op, value in [('<',a<b), ('>',a>b), ('=',a==b),
                                  ('<=',a<=b), ('>=',a>=b), ('<>',a!=b)]:
                    expressions.append(f'({a}){op}({b})')
                    expected.append(int(value))
        self.assertEqual(self.values(expressions), expected)

    def test_arrays(self):
        output = self.execute('DIM BYTE B(8190)\nB(0)=257\nB(8190)=255\n'
                              'PRINT "@";B(0);",";B(8190)\nNEW\n'
                              'DIM A(256),BYTE B(3)\nA(256)=-1234\nB(2)=A(256)\n'
                              'A(0)=2\nPRINT "@";B(A(0));",";A(256)\n')
        self.assertIn('@1,255\n', output)
        self.assertIn('@46,-1234\n', output)

    def test_edit_and_list(self):
        source = ('30 PRINT "old"\n10 PRINT 256\n20 PRINT "middle"\n'
                  '30 PRINT "replacement"\n40 PRINT "deleted"\n40\nLIST\nRUN\n')
        output = self.execute(source)
        listing = output.split('>LIST\n')[1].split('>RUN\n')[0]
        self.assertEqual(listing, '10 PRINT 256\n20 PRINT "middle"\n30 PRINT "replacement"\n')
        self.assertTrue(output.endswith('>RUN\n256\nmiddle\nreplacement\n>'))
        self.assertIn('>NEW\n>RUN\n>', self.execute(source+'NEW\nRUN\n'))

    def test_random_editing(self):
        rng=random.Random(8080)
        lines={}
        commands=[]
        for _ in range(160):
            line=rng.randrange(1,2000)
            value=rng.randrange(-32768,32768)
            commands.append(f'{line} PRINT "@";{value}')
            lines[line]=value
        for line in list(lines)[::4]:
            commands.append(str(line))
            del lines[line]
        commands.append('RUN')
        output=self.execute('\n'.join(commands)+'\n')
        actual=[int(n) for n in re.findall(r'^@(-?\d+)$',output,re.M)]
        self.assertEqual(actual,[value for _,value in sorted(lines.items())])

    def test_control_flow(self):
        source = ('10 S=0\n20 FOR I=1 TO 5\n30 FOR J=3 TO -1 STEP -2\n'
                  '40 S=S+I*J\n50 NEXT J\n60 NEXT I\n70 GOSUB 200\n'
                  '80 IF S<>45 THEN PRINT "BAD":PRINT 0\n'
                  '90 IF S=45 THEN PRINT "@";S\n100 GOTO 300\n'
                  '200 PRINT "SUB"\n210 RETURN\n300 END\nRUN\n')
        output = self.execute(source)
        self.assertTrue(output.endswith('>RUN\nSUB\n@45\n>'), output[-300:])

    def test_literal_branches_without_runtime_lookup(self):
        # Trap runtime searches: literal targets must bypass them, even when
        # numerous destinations collide in the old 64-entry cache.
        with tempfile.TemporaryDirectory() as directory:
            asm=Path(directory)/'no-lookup.asm'
            image=asm.with_suffix('.hex')
            source=(ROOT/'a08/b8008.asm').read_text().replace(
                'FINDLINE:\n','FINDLINE:\n        JMP LINEERR\n',1)
            asm.write_text(source)
            result=subprocess.run([str(ASSEMBLER),str(asm),'-o'+str(image)],
                                  capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            program=('10 S=0\n20 FOR I=1 TO 3\n'
                     '30 GOSUB 200:IF I<3 THEN 60\n40 IF 1 THEN 80\n'
                     '50 PRINT "BAD"\n60 GOTO 90\n70 PRINT "BAD"\n'
                     '80 S=S+10\n90 NEXT I\n95 IF 0 THEN 32767\n'
                     '96 FOR J=1 TO 0\n97 GOTO 90\n98 NEXT J\n'
                     '100 PRINT "@";S\n110 END\n200 S=S+1:RETURN\nRUN\n')
            self.assertTrue(self.execute(program,image=image).endswith('>RUN\n@13\n>'))
            ttt=(ROOT/'b8008/examples/ttt.bas').read_text()
            self.assertTrue(self.execute(ttt,image=image).endswith(
                '>RUN\n1 ITERATIONS\nFINAL MOVE COUNT 6493\n>'))
            # A literal prefix of a computed expression must not be bound.
            computed='10 GOTO 100+0\n20 END\n100 PRINT "BAD"\nRUN\n'
            output=self.execute(computed,image=image,errors=True)
            self.assertTrue(output.endswith('>RUN\n?LINE\n>'))

    def test_computed_branches_and_missing_targets(self):
        program=('10 A=100\n20 GOSUB A\n30 IF 1 THEN 200+0\n'
                 '40 PRINT "BAD"\n50 END\n100 PRINT "SUB"\n110 RETURN\n'
                 '200 GOTO 300-10\n290 PRINT "COMPUTED"\n300 END\nRUN\n')
        self.assertTrue(self.execute(program).endswith('>RUN\nSUB\nCOMPUTED\n>'))
        missing=('10 PRINT "BEFORE"\n20 IF 0 THEN 9999\n'
                 '30 PRINT "AFTER"\n40 GOTO 9999\nRUN\nLIST\n')
        output=self.execute(missing,errors=True)
        self.assertIn('>RUN\nBEFORE\nAFTER\n?LINE\n>LIST\n',output)
        self.assertIn('40 GOTO 9999\n',output.split('>LIST\n')[1])

    def test_branch_rebinding_after_run_edit_and_delete(self):
        source=('10 GOSUB 100\n20 GOTO 200\n100 PRINT "A"\n110 RETURN\n'
                '200 PRINT "END"\n210 END\nRUN\nLIST\n'
                '5 REM MOVE THE TARGET ADDRESSES\n100 PRINT "B"\nRUN\n'
                '200\nRUN\n200 PRINT "C"\nRUN\n')
        output=self.execute(source,errors=True)
        parts=output.split('>RUN\n')[1:]
        self.assertEqual(len(parts),4)
        self.assertTrue(parts[0].startswith('A\nEND\n>LIST\n'))
        self.assertIn('10 GOSUB 100\n20 GOTO 200\n',parts[0])
        self.assertTrue(parts[1].startswith('B\nEND\n>'))
        self.assertTrue(parts[2].startswith('B\n?LINE\n>'))
        self.assertEqual(parts[3],'B\nC\n>')
        # LIST can also be a stored command, before returning to the prompt.
        listed=self.execute('10 GOTO 30\n20 END\n30 LIST\nRUN\n')
        self.assertTrue(listed.endswith('>RUN\n10 GOTO 30\n20 END \n30 LIST \n>'))

    def test_zero_trip_and_overflow_loops(self):
        source = ('10 FOR I=2 TO 1\n20 FOR J=1 TO 3\n'
                  '30 PRINT "BAD"\n40 NEXT J\n50 NEXT I\n'
                  '60 FOR I=32767 TO 32767\n70 PRINT "MAX"\n80 NEXT I\n'
                  '90 FOR J=-32768 TO -32768 STEP -1\n100 PRINT "MIN"\n'
                  '110 NEXT J\n120 END\nRUN\n')
        self.assertTrue(self.execute(source).endswith('>RUN\nMAX\nMIN\n>'))

    def test_input_and_console(self):
        source = ('10 DIM A(2)\n20 FOR I=0 TO 2\n30 INPUT A(I)\n'
                  '40 GOSUB 100\n50 NEXT I\n60 END\n'
                  '100 PRINT "@";A(I)\n110 RETURN\nRUN\n-321\n42\n0\n')
        output = self.execute(source, file_input=True)
        self.assertEqual(re.findall(r'^@(-?\d+)$', output, re.M), ['-321','42','0'])
        self.assertIn('@6\n', self.execute('print "@";4X\x08+2\n'))
        self.assertIn('@65\n', self.execute('POKE 14000,65\nPRINT "@";PEEK(14000)\n'))
        self.assertIn('@AB\n', self.execute('PRINT "@";CHR(65);CHR(66)\n'))
        output = self.execute('10 PRINT "OK"\r\nRUN\r\n', file_input=True)
        self.assertIn('OK\n', output.split('>RUN\n')[1])

    def test_parser_fast_and_recursive_paths(self):
        source=('A=123:B=7\nDIM C(3),BYTE D(3)\n'
                'C(2)=-321:D(1)=2\n')
        cases={'A+B*B':172, 'C(D(1))':-321, 'ABS(-C(D(1)))':321,
               'C(1+A MOD 2)':-321, '-A*B+C(2)':-1182,
               'C(2)/B':-45, 'C(2) MOD B':-6, '+(A+B)*(-B)':-910}
        source+=''.join('PRINT "@";'+expr+'\n' for expr in cases)
        # Close to the existing 126-word limit: retain room for both values
        # and return addresses, and balance the stack over long expressions.
        source+='PRINT "@";'+'('*30+'42'+')'*30+'\n'
        source+='PRINT "@";'+'+'.join(['1']*50)+'\n'
        output=self.execute(source)
        actual=[int(n) for n in re.findall(r'^@(-?\d+)$',output,re.M)]
        self.assertEqual(actual,list(cases.values())+[42,50])

    def test_unit_and_general_for_steps(self):
        cases=[(-32768,-32765,1),(-257,-255,1),(-2,2,1),(254,258,1),
               (32765,32767,1),(-1,-2,1),(2,-2,-1),(32767,32767,2),
               (-32768,-32768,-2),(1,5,257),(258,254,-1),(-2,2,2)]
        lines=[]
        expected=[]
        for start,limit,step in cases:
            count=0
            value=start
            while value<=limit if step>0 else value>=limit:
                count+=1
                updated=signed(value+step)
                overflow=(step>0 and updated<value) or (step<0 and updated>value)
                value=updated
                if overflow:
                    break
            expected.append((count,value))
            for statement in ('S=0',f'FOR I={start} TO {limit} STEP {step}',
                              'S=S+1','NEXT I','PRINT "@";S;",";I'):
                lines.append(f'{10*(len(lines)+1)} {statement}')
        source='\n'.join(lines)+'\nRUN\n'
        output=self.execute(source)
        actual=[(int(a),int(b)) for a,b in re.findall(r'^@(-?\d+),(-?\d+)$',output,re.M)]
        self.assertEqual(actual,expected)

    def test_errors_recover(self):
        cases = [('PRINT 1/0','DIVIDE BY ZERO'), ('PRINT (2+3','SYNTAX'),
                 ('DIM A(3):PRINT A(4)','BOUNDS'), ('PRINT B(0)','BOUNDS'),
                 ('DIM A(3):PRINT A(-1)','BOUNDS'), ('DIM BYTE B(16000)','MEMORY'),
                 ('GOTO 12345','LINE'), ('RETURN','STACK'), ('NEXT I','STACK'),
                 ('PRINT '+'('*40+'1'+')'*40,'STACK'),
                 ('X'*245,'SYNTAX')]
        for source, error in cases:
            with self.subTest(source=source[:60]):
                output = self.execute(source+'\nPRINT "@";42\n', errors=True)
                self.assertIn('?'+error+'\n', output)
                self.assertTrue(output.endswith('@42\n>'), output[-300:])

    def benchmark(self, name):
        source = (ROOT/'b8008/examples'/(name+'.bas')).read_text()
        output = self.execute(source, file_input=True)
        return output.split('>RUN\n',1)[1][:-1]

    def test_sieve(self):
        limit=16383
        flags=bytearray(b'\1')*(limit+1)
        flags[:2]=b'\0\0'
        for n in range(2,int(limit**0.5)+1):
            if flags[n]:
                for multiple in range(n*n,limit+1,n):
                    flags[multiple]=0
        self.assertEqual(self.benchmark('sieve'), f'{sum(flags[3:])} PRIMES\n10 ITERATIONS\n')

    def test_e(self):
        with localcontext() as context:
            context.prec=220
            digits=str(Decimal(1).exp()).replace('.','')[:192]
        self.assertEqual(self.benchmark('e'), digits+'\nDONE\n')

    def test_ttt(self):
        scores,nodes=integration.Integration.minimax_reference()
        self.assertEqual(scores,[5,5,5])
        self.assertEqual(self.benchmark('ttt'),f'1 ITERATIONS\nFINAL MOVE COUNT {nodes}\n')


if __name__=='__main__':
    unittest.main()
