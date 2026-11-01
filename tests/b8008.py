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

    @staticmethod
    def image_memory():
        memory={}
        for record in (ROOT/'a08/b8008.hex').read_text().splitlines():
            if record[7:9]!='00':
                continue
            start=int(record[3:7],16)
            for i,value in enumerate(bytes.fromhex(record[9:-2])):
                if start+i in memory:
                    raise AssertionError('overlapping interpreter HEX records')
                memory[start+i]=value
        return memory

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
            end = max(int(r[3:7],16)+int(r[1:3],16) for r in records if r[7:9]=='00' and int(r[3:7],16)<0x3b00)
            self.assertLess(end+8191+512, 0x3b00)
            # Fixed helpers reuse only explicitly reserved variable-page tail.
            memory=self.image_memory()
            reserved=set(range(0x3ca4,0x3ccb))|set(range(0x3cd0,0x3cfd))
            self.assertEqual({a for a in memory if a>=0x3b00},reserved)
            workspace=prepare.addresses((ROOT/'b8008/basic.src').read_text())
            self.assertLessEqual(max(v for v in workspace.values()
                                     if isinstance(v,int) and 0x3c00<=v<0x3d00),0x3ca3)


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
               (-32768,-32768,-2),(1,5,257),(258,254,-1),(-2,2,2),(-32768,-32768,-1),
               (-255,-258,-1),(1,-1,-1),(-32765,-32768,-1),
               (3,4,-1),(32767,32765,-1),(-1,-1,-257)]
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

    def test_simple_values_offsets_and_fallback(self):
        source=('DIM A(300),BYTE B(300)\nI=255:J=1\n'
                'A(I)=12345:B(I+1)=257\nA(65535+1)=7:A(I-254)=8\n'
                'A(1+1)=9\nPRINT "@";A(I);",";B(I+1);",";A(0);",";A(1);",";A(2)\n'
                'C=32767:C=C+1:PRINT "@";C\n'
                'C=C-1:C=C+65535:C=C-65535:PRINT "@";C\n'
                'A(I)=A(I)+1:B(I+1)=B(I+1)-2\n'
                'A((I+J))=11:A(I+J*2)=12:A(I+1+1)=13\n'
                'PRINT "@";A(I);",";B(I+1);",";A(I+1);",";A(I+2)\n'
                'C=I+1*2:PRINT "@";C\nC=I-1-1:PRINT "@";C\n'
                'C=I+(1+1):PRINT "@";C\nC=I+1>250:PRINT "@";C\n'
                'I=-1:A(I+1)=14:A(65535+1)=15:PRINT "@";A(0)\n')
        output=self.execute(source)
        actual=re.findall(r'^@([^\n]+)$',output,re.M)
        self.assertEqual(actual,['12345,1,7,8,9','-32768','32767',
                                 '12346,255,11,13','257','253','257','1','15'])
        for index in ('I+1','65535','32767+1'):
            output=self.execute('DIM A(1)\nI=1\nA('+index+')=7\n'
                                'PRINT "@";A(1)\n',errors=True)
            self.assertIn('?BOUNDS\n',output)
            self.assertTrue(output.endswith('@0\n>'))

    def test_short_arithmetic_boundaries(self):
        values=[0,1,2,7,255,256,32767,-1,-255,-32768]
        divisors=[1,2,7,8,255,256,32767,-1,-2,-32768]
        expressions=[]
        expected=[]
        for a in values:
            for b in divisors:
                q=abs(a)//abs(b)*(-1 if (a<0)!=(b<0) else 1)
                for op,value in [('*',a*b),('/',q),(' MOD ',a-q*b)]:
                    expressions.append(f'({a}){op}({b})')
                    expected.append(signed(value))
        self.assertEqual(self.values(expressions),expected)
        output=self.execute('PRINT 0/0\nPRINT "@";42\n',errors=True)
        self.assertIn('?DIVIDE BY ZERO\n',output)
        self.assertTrue(output.endswith('@42\n>'))

    def test_division_reuses_both_results(self):
        # Count real signed divisions. Printing uses unsigned formatting, and
        # multiplication overwrites scratch results; neither may poison cache.
        with tempfile.TemporaryDirectory() as directory:
            asm=Path(directory)/'division-count.asm'
            image=asm.with_suffix('.hex')
            source=(ROOT/'a08/b8008.asm').read_text().replace('DIVMAIN:\n',
                'DIVMAIN:\n        LHI HIGH VARS\n        LLI 203D\n'
                '        LAM\n        ADI 1D\n        LMA\n',1)
            asm.write_text(source)
            result=subprocess.run([str(ASSEMBLER),str(asm),'-o'+str(image)],
                                  capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            marker='PRINT "@";PEEK(15563)\n'
            program=('POKE 15563,0\nA=1234:B=17\n'
                     'PRINT "Q";A/B;",";A MOD B\nC=10*7\n'
                     'PRINT "R";A MOD B;",";A/B\n'+marker+
                     'A=1235\nPRINT "Q";A/B;",";A MOD B\n'+marker+
                     'A=-1235\nPRINT "Q";A/B;",";A MOD B\n'+marker+
                     'B=-17\nPRINT "Q";A/B;",";A MOD B\n'+marker+
                     'PRINT 0/0\n'+marker+
                     'NEW\nPRINT "Q";(-1235)/(-17);",";(-1235) MOD (-17)\n'+marker+
                     'INPUT A\n-1235\nINPUT B\n-17\n'
                     'PRINT "Q";A/B;",";A MOD B\n'+marker+
                     'PRINT "Q";1234/17;",";1234 MOD 17\n'+marker)
            output=self.execute(program,errors=True,image=image)
            self.assertEqual(re.findall(r'^@([0-9]+)$',output,re.M),
                             ['1','2','3','4','4','4','4','5'])
            self.assertEqual(re.findall(r'^Q([^\n]+)$',output,re.M),
                             ['72,10','72,11','-72,-11','72,-11',
                              '72,-11','72,-11','72,10'])
            self.assertIn('R10,72\n',output)
            self.assertEqual(output.count('?DIVIDE BY ZERO\n'),1)

    def test_address_reload_elimination(self):
        # Execute both versions: register clobbers, low-byte wrap, calls, and
        # flags must behave identically despite eliminated immediate loads.
        source="""VARS EQU 3C00H
LEFT EQU VARS+88D
        ORG 40H
        LHI HIGH VARS
        LHI HIGH LEFT
        LLI 0D
        LMI 66D
        LLI 1D
        LMI 65D
        LHI HIGH VARS
        LLI 1D
        LAM
        OUT 10D
        LLI 255D
        INL
        LLI 0D
        LAM
        OUT 10D
        LLI 2D
        LMI 3DH
        LHM
        LHI HIGH VARS
        LLI 0D
        LAM
        OUT 10D
        LLI 3D
        LMI 1D
        LLM
        LLI 3D
        LAM
        OUT 10D
        CAL CLOBBER
        LHI HIGH VARS
        LLI 0D
        LAM
        OUT 10D
        LAI 1D
        CPI 1D
        LHI HIGH VARS
        LLI 0D
        LHI HIGH VARS
        LLI 0D
        JTZ DONE
        LAI 63D
        OUT 10D
        HLT
DONE:   LAI 33D
        OUT 10D
        HLT
CLOBBER:
        LHI 3DH
        LLI 7D
        RET
        END
"""
        optimized='\n'.join(prepare.address_loads(source.splitlines(),prepare.addresses(source)))+'\n'
        self.assertLess(len(optimized),len(source))
        outputs=[]
        with tempfile.TemporaryDirectory() as directory:
            for name,text in [('original',source),('optimized',optimized)]:
                asm=Path(directory)/(name+'.asm')
                image=asm.with_suffix('.hex')
                asm.write_text(text)
                result=subprocess.run([str(ASSEMBLER),str(asm),'-o'+str(image)],
                                      capture_output=True,timeout=15)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                result=run('-n:100000',image)
                self.assertEqual(result.returncode,0,result.stderr)
                outputs.append(result.stdout)
        self.assertEqual(outputs,[b'ABB\x01B!']*2)

    def test_fast_comparison_rhs(self):
        # Scalars/constants/offsets use the leaf path; compound RHSs fall back.
        expressions=[]
        expected=[]
        for a in (-32768,-1,0,255,32767):
            for b in (-32768,-1,0,256,32767):
                for op, value in [('<',a<b),('>',a>b),('=',a==b),
                                  ('<=',a<=b),('>=',a>=b),('<>',a!=b)]:
                    expressions.append(f'A={a}:B={b}:PRINT "@";A{op}B')
                    expected.append(int(value))
        output=self.execute('\n'.join(expressions)+'\n')
        self.assertEqual([int(n) for n in re.findall(r'^@(-?\d+)$',output,re.M)],expected)
        source=('10 A=3:B=2\n20 IF A=B+1 THEN PRINT "OFFSET"\n'
                '30 IF A=B+1*2 THEN PRINT "BAD"\n'
                '40 IF A=B*2-1 THEN PRINT "FALLBACK"\n'
                '50 IF A>B THEN IF B=2 THEN PRINT "NESTED"\n'
                '60 PRINT "@";A=B+1;",";A=B+1*2;",";A<B<2\nRUN\n')
        output=self.execute(source).split('>RUN\n')[1]
        self.assertEqual(output,'OFFSET\nFALLBACK\nNESTED\n@1,0,1\n>')

    def test_program_header_page_boundary(self):
        # Force PROGRAM to xxFF: NEW must clear both bytes across the page.
        asm=(ROOT/'a08/b8008.asm').read_text()
        records=(ROOT/'a08/b8008.hex').read_text().splitlines()
        end=max(int(r[3:7],16)+int(r[1:3],16) for r in records if r[7:9]=='00' and int(r[3:7],16)<0x3b00)
        padding=(255-end)%256
        fill=''.join('        DATA '+','.join(['0D']*min(16,padding-i))+'\n'
                     for i in range(0,padding,16))
        asm=asm.replace('PROGRAM:',fill+'PROGRAM:')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'boundary.asm'
            image=path.with_suffix('.hex')
            path.write_text(asm)
            result=subprocess.run([str(ASSEMBLER),str(path),'-o'+str(image)],capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            output=self.execute('10 PRINT "FIRST"\n20 END\nRUN\nNEW\n'
                                '20 PRINT "SECOND"\n30 END\nRUN\nLIST\n',image=image)
            self.assertIn('>RUN\nFIRST\n>',output)
            self.assertIn('>RUN\nSECOND\n>',output)
            self.assertTrue(output.endswith('20 PRINT "SECOND"\n30 END \n>'),repr(output))

    def test_word_reader_boundaries(self):
        # Both byte increments can cross a page; preserve GET's final A/flags.
        asm=(ROOT/'a08/b8008.asm').read_text().replace('        JMP START','        JMP WORDTEST',1)
        code=['        ORG 3000H','WORDTEST:']
        expected=bytearray()
        for i,(address,lo,hi) in enumerate([(0x30fe,0x12,0x34),
                                           (0x30ff,0x34,0x56),(0x3100,0x56,0x78)]):
            code += [f'        LBI {address>>8}D',f'        LCI {address&255}D',
                     '        CAL GETWORD','        OUT 10D',
                     '        LAE','        OUT 10D','        LAD','        OUT 10D',
                     '        LAC','        OUT 10D','        LAB','        OUT 10D',
                     '        LAI 0D',f'        JFZ WORDNZ{i}',
                     '        LAI 1D',f'WORDNZ{i}:','        OUT 10D']
            after=address+2
            expected.extend([hi,lo,hi,after&255,after>>8,0])
        code += ['        HLT','        ORG 30FEH','        DATA 12H,34H,56H,78H']
        asm=asm.replace('        END','\n'.join(code)+'\n        END')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'reader.asm'
            image=path.with_suffix('.hex')
            path.write_text(asm)
            result=subprocess.run([str(ASSEMBLER),str(path),'-o'+str(image)],capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=run('-a:0','-n:100000',image)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout,bytes(expected))

    def test_atomic_arithmetic_rhs(self):
        statements=[]
        expected=[]
        for a,b in [(-32768,-1),(-17,5),(0,1),(255,256),(32767,3)]:
            q=abs(a)//abs(b)*(-1 if (a<0)!=(b<0) else 1)
            for op,value in [('+',a+b),('-',a-b),('*',a*b),('/',q),
                             (' MOD ',a-q*b),(' AND ',a&b),(' OR ',a|b)]:
                statements.append(f'A={a}:B={b}:PRINT "@";A{op}B')
                expected.append(signed(value))
        output=self.execute('\n'.join(statements)+'\n')
        self.assertEqual([int(n) for n in re.findall(r'^@(-?\d+)$',output,re.M)],expected)
        cases={'2+3*4':14,'20-3*4':8,'20-12/3':16,'20+12 MOD 5':22,
               '20-6-3':11,'24/3/2':4,'24 MOD 7*3':9,'8 OR 1 AND 3':1,
               '2+3*4-5':9,'2+(-3)*4':-10,'20/(2+3)':4,
               '20 MOD (2+3)':0,'2+ABS(-3)*4':14,'3*(2+4)':18}
        self.assertEqual(self.values(cases),list(cases.values()))
        output=self.execute('DIM A(3),BYTE B(3)\nA(1)=7:B(2)=3\n'
                            'PRINT "@";2+A(1)*B(2);",";A(1)*B(2);",";'
                            '20-A(B(2)-2)*2\n')
        self.assertIn('@23,21,6\n',output)
        for expression in ('7/0','7 MOD 0','7+','7*','7/(2-2)'):
            output=self.execute('PRINT '+expression+'\nPRINT "RECOVERED"\n',errors=True)
            self.assertIn('?',output)
            self.assertTrue(output.endswith('RECOVERED\n>'))

    def test_atomic_rhs_skips_recursive_factor(self):
        # A native marker proves scalar and simple-array RHSs skip FACTOR.
        # A complex array index still enters the full parser. Instrumentation executes on the emulated CPU.
        asm=(ROOT/'a08/b8008.asm').read_text().replace(
            'FACTOR:', 'FACTOR:\n        LAI 33D\n        OUT 10D',1)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'factor.asm'
            image=path.with_suffix('.hex')
            path.write_text(asm)
            result=subprocess.run([str(ASSEMBLER),str(path),'-o'+str(image)],capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            output=self.execute('PRINT 7*3\nPRINT 24/3\nDIM BYTE A(1)\n'
                                'A(1)=4\nPRINT 7*A(1)\nPRINT 7*A(1+0*1)\n',image=image)
            self.assertIn('>PRINT 7*3\n21\n>',output)
            self.assertIn('>PRINT 24/3\n8\n>',output)
            self.assertIn('>PRINT 7*A(1)\n28\n>',output)
            fallback=output.split('>PRINT 7*A(1+0*1)\n')[1]
            self.assertIn('!',fallback)
            self.assertTrue(fallback.endswith('28\n>'))

    def test_fast_if_conditions_and_fallback(self):
        statements=[]
        expected=[]
        for a in (-32768,-1,0,255,32767):
            for b in (-32768,-1,0,256,32767):
                for op,value in [('<',a<b),('>',a>b),('=',a==b),
                                 ('<=',a<=b),('>=',a>=b),('<>',a!=b)]:
                    statements.append(f'A={a}:B={b}:R=0:IF A{op}B THEN R=1')
                    statements.append('PRINT "@";R')
                    expected.append(int(value))
        output=self.execute('\n'.join(statements)+'\n')
        self.assertEqual([int(n) for n in re.findall(r'^@(-?\d+)$',output,re.M)],expected)
        source=('10 A=3:B=2\n20 IF A>B THEN PRINT "SCALARS"\n'
                '30 IF 3>=B THEN PRINT "LEFT CONSTANT"\n'
                '40 IF A<>2 THEN PRINT "RIGHT CONSTANT"\n'
                '50 IF A>B+1 THEN PRINT "BAD"\n'
                '60 IF A>B*2-2 THEN PRINT "FALLBACK"\n'
                '70 IF A<B<2 THEN PRINT "CHAIN"\n'
                '80 IF A THEN IF B=2 THEN PRINT "TRUTH"\n'
                '90 IF (A-B)=1 THEN PRINT "PARENS"\nRUN\n')
        self.assertEqual(self.execute(source).split('>RUN\n')[1],
                         'SCALARS\nLEFT CONSTANT\nRIGHT CONSTANT\nFALLBACK\nCHAIN\nTRUTH\nPARENS\n>')
        for condition in ('A< THEN','A=3','A=>2 THEN','A<2* THEN'):
            output=self.execute('A=3\nIF '+condition+' PRINT 7\nPRINT "RECOVERED"\n',errors=True)
            self.assertIn('?SYNTAX',output)
            self.assertTrue(output.endswith('RECOVERED\n>'))

    def test_fast_if_skips_expression_parser(self):
        asm=(ROOT/'a08/b8008.asm').read_text().replace(
            'EXPR:', 'EXPR:\n        LAI 33D\n        OUT 10D',1)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'condition.asm'
            image=path.with_suffix('.hex')
            path.write_text(asm)
            result=subprocess.run([str(ASSEMBLER),str(path),'-o'+str(image)],capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            output=self.execute('A=7:B=3\nIF A>B THEN PRINT "FAST"\n'
                                'IF A>B+1 THEN PRINT "SLOW"\n',image=image)
            self.assertIn('>IF A>B THEN PRINT "FAST"\nFAST\n>',output)
            self.assertIn('>IF A>B+1 THEN PRINT "SLOW"\n!SLOW\n>',output)

    def test_simple_assignment_sums(self):
        source=('I=7:J=2:K=3\nP=I+I+3:T=1-J:V=I-J-K:W=I+J-K+4\n'
                'PRINT "@";P;",";T;",";V;",";W\n'
                'A=32767:B=1:C=A+B+1:D=0-A-B-1\n'
                'PRINT "@";C;",";D\nDIM A(20),BYTE B(20)\n'
                'A(I+J-K)=1234:B(I+J+K)=257\n'
                'PRINT "@";A(I+J-K);",";B(I+J+K)\n'
                'C=20-J*K+I:D=20-J-K*I\nPRINT "@";C;",";D\n')
        output=self.execute(source)
        for expected in ('@17,-1,2,10\n','@-32767,32767\n','@1234,1\n','@21,-3\n'):
            self.assertIn(expected,output)
        for expression in ('I+J+','I-J*','I++','I+J/(J-J)'):
            output=self.execute('I=7:J=2\nC='+expression+'\nPRINT "RECOVERED"\n',errors=True)
            self.assertIn('?',output)
            self.assertTrue(output.endswith('RECOVERED\n>'))

    def test_general_loop_signed_boundaries(self):
        rng=random.Random(800811)
        cases=[(-32768,-32768,-1),(32767,32767,1),
               (-32768,32767,32767),(32767,-32768,-32768),
               (-32768,32767,1),(32767,-32768,-1)]
        # Avoid the two full-range unit loops: boundaries are covered above.
        cases=cases[:-2]
        for _ in range(60):
            start=rng.choice([-32768,-32767,-257,-1,0,255,32766,32767])
            step=rng.choice([-32768,-32767,-257,-3,-1,1,2,257,32767])
            limit=max(-32768,min(32767,start+rng.randrange(-5,6)))
            cases.append((start,limit,step))
        for offset in range(0,len(cases),8):
            lines=[]
            expected=[]
            for start,limit,step in cases[offset:offset+8]:
                value=start
                count=0
                while value<=limit if step>0 else value>=limit:
                    count+=1
                    updated=signed(value+step)
                    overflow=(step>0 and updated<value) or (step<0 and updated>value)
                    value=updated
                    if overflow:
                        break
                expected.append((count,value))
                for statement in ('C=0',f'FOR I={start} TO {limit} STEP {step}',
                                  'C=C+1','NEXT I','PRINT "@";C;",";I'):
                    lines.append(f'{10*(len(lines)+1)} {statement}')
            output=self.execute('\n'.join(lines)+'\nRUN\n')
            self.assertEqual([(int(a),int(b)) for a,b in re.findall(r'^@(-?\d+),(-?\d+)$',output,re.M)],expected)

    def test_workspace_code_survives_reset(self):
        memory=self.image_memory()
        addresses=sorted(a for a in memory if a>=0x3b00)
        expected=[memory[a] for a in addresses]
        program=('10 FOR I=15524 TO 15562\n20 PRINT "@";PEEK(I)\n30 NEXT I\n'
                 '40 FOR I=15568 TO 15612\n50 PRINT "@";PEEK(I)\n60 NEXT I\n70 END\n')
        output=self.execute(program+'RUN\nNEW\nPRINT 1/0\n'+program+'RUN\n',errors=True)
        self.assertIn('?DIVIDE BY ZERO',output)
        self.assertEqual([int(n) for n in re.findall(r'^@(\d+)$',output,re.M)],expected*2)

    def test_fast_array_operands_and_fallback(self):
        source=('DIM BYTE B(20),A(20)\nI=3:J=1:B(2)=7:B(3)=9:B(4)=11\n'
                'A(2)=-1234:A(3)=32767\n'
                'X=B(2):Y=B(I):Z=B(I+1):W=B(I-1+2-1)\n'
                'PRINT "@";X;",";Y;",";Z;",";W\n'
                'PRINT "@";B(2)+B(3)-B(4);",";A(2);",";A(I)\n'
                'IF B(2)<B(I) THEN PRINT "ARRAYS"\n'
                'IF B(I+1)=11 THEN PRINT "OFFSET"\n'
                'IF 0<B(2)+1 THEN PRINT "PRECEDENCE"\n'
                'B(1)=2\nPRINT "@";B(B(1));",";B(I+J);",";B(I+J*1)\n'
                'PRINT "@";2+B(I)*3;",";20-B(I-1)*2\n')
        output=self.execute(source)
        for expected in ('@7,9,11,9\n','@5,-1234,32767\n','ARRAYS\n','OFFSET\n',
                         'PRECEDENCE\n','@7,11,11\n','@29,6\n'):
            self.assertIn(expected,output)
        for expression,error in [('B(21)','BOUNDS'),('B(0-1)','BOUNDS'),
                                 ('C(0)','BOUNDS'),('B(I+)','SYNTAX'),
                                 ('B(I+1','SYNTAX'),('B(I+J*)','SYNTAX')]:
            output=self.execute('DIM BYTE B(20)\nI=2:J=1\nPRINT '+expression+
                                '\nPRINT "RECOVERED"\n',errors=True)
            self.assertIn('?'+error,output)
            self.assertTrue(output.endswith('RECOVERED\n>'))

    def test_fast_array_skips_expression_parser(self):
        asm=(ROOT/'a08/b8008.asm').read_text().replace(
            'EXPR:', 'EXPR:\n        LAI 33D\n        OUT 10D',1)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'array-parse.asm'
            image=path.with_suffix('.hex')
            path.write_text(asm)
            result=subprocess.run([str(ASSEMBLER),str(path),'-o'+str(image)],capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            output=self.execute('DIM BYTE B(3)\nI=1:J=1:B(1)=7:B(2)=9\n'
                                'X=B(I+1)\nIF X=B(2) THEN PRINT "FAST"\n'
                                'IF X=B(I+J) THEN PRINT "FALLBACK"\n',image=image)
            self.assertIn('>X=B(I+1)\n>',output)
            self.assertIn('>IF X=B(2) THEN PRINT "FAST"\nFAST\n>',output)
            fallback=output.split('>IF X=B(I+J) THEN PRINT "FALLBACK"\n')[1]
            self.assertIn('!',fallback)
            self.assertTrue(fallback.endswith('FALLBACK\n>'))

    def test_multiply_ten_and_general_boundaries(self):
        expressions=[]
        expected=[]
        for a in (0,1,2,10,266,522,-10,-1,-32768,32767):
            for b in (-32768,-257,-1,0,1,255,256,32767):
                expressions.append(f'({a})*({b})')
                expected.append(signed(a*b))
        self.assertEqual(self.values(expressions),expected)
        # A native marker proves the full 16-bit value 10 selects the shift/add
        # path, while 266 (same low byte) still uses general multiplication.
        asm=(ROOT/'a08/b8008.asm').read_text().replace(
            'MULLOOP:', 'MULLOOP:\n        LAI 33D\n        OUT 10D',1)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'multiply.asm'
            image=path.with_suffix('.hex')
            path.write_text(asm)
            result=subprocess.run([str(ASSEMBLER),str(path),'-o'+str(image)],capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            output=self.execute('PRINT 10*7\nPRINT 266*7\n',image=image)
            self.assertIn('>PRINT 10*7\n70\n>',output)
            fallback=output.split('>PRINT 266*7\n')[1]
            self.assertIn('!',fallback)
            self.assertTrue(fallback.endswith('1862\n>'))

    def test_division_small_magnitudes(self):
        expressions=[]
        expected=[]
        for a in (-257,-256,-255,-128,-1,0,1,127,128,255,256,257):
            for b in (-32768,-256,-127,-10,-1,1,2,10,127,256):
                q=abs(a)//abs(b)*(-1 if (a<0)!=(b<0) else 1)
                expressions += [f'({a})/({b})',f'({a}) MOD ({b})']
                expected += [signed(q),a-q*b]
        self.assertEqual(self.values(expressions),expected)

    def test_division_skips_zero_high_byte(self):
        # Emit the native bit count before its store: no numeric PRINT calls
        # are used, so unsigned formatting cannot add unrelated divisions.
        asm=(ROOT/'a08/b8008.asm').read_text().replace(
            'DIVCOUNT:', 'DIVCOUNT:\n        OUT 10D',1)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'division-align.asm'
            image=path.with_suffix('.hex')
            path.write_text(asm)
            result=subprocess.run([str(ASSEMBLER),str(path),'-o'+str(image)],capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            output=self.execute('A=255/2\nA=256/2\nA=-255/2\nA=1/2\nPRINT "DONE"\n',image=image)
            for expression,count in [('255/2',8),('256/2',16),('-255/2',8)]:
                self.assertIn('>A='+expression+'\n'+chr(count)+'>',output)
            self.assertIn('>A=1/2\n>',output)

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
