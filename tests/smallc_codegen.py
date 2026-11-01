#!/usr/bin/env python3
"""Differential tests for Small C native optimizations, without host tools."""
import importlib.util
import operator
from pathlib import Path
import subprocess
import tempfile
import unittest
from integration import ROOT, ASSEMBLER, run
spec=importlib.util.spec_from_file_location('smallc_codegen',ROOT/'smallc/codegen.py')
codegen=importlib.util.module_from_spec(spec);spec.loader.exec_module(codegen)

class Codegen(unittest.TestCase):
    def differential(self,ir,expected,table_offset=None):
        for optimize in (False,True):
            with self.subTest(optimize=optimize), tempfile.TemporaryDirectory() as directory:
                source=Path(directory,'test.asm');image=source.with_suffix('.hex')
                assembly=codegen.generate(ir,optimize=optimize)
                if table_offset is not None:
                    symbol=codegen.Generator().symbol('$SCL1' if optimize else 'table')
                    self.assertIn(symbol+':',assembly)
                    assembly=assembly.replace(symbol+':',
                        '_SC_TABLE_PAGE:\n        ORG ((_SC_TABLE_PAGE+255D) AND 0FF00H)+'+
                        str(table_offset)+'D\n'+symbol+':')
                source.write_text(assembly)
                result=subprocess.run([str(ASSEMBLER),str(source),'-o'+str(image)],capture_output=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                result=run('-n:200000000',image,timeout=30)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(result.stdout,expected)

    def test_byte_updates_keep_promoted_result_and_older_stack(self):
        body=[]
        for offset in (0,255,256):
            for value in (0,1,127,254,255):
                for delta in (-257,-1,0,1,257):
                    expected=(value+delta)&65535
                    body.append(f"""IMM 7
PUSH
ADDRSP {offset+2}
PUSH
IMM {value}
STIND 1
ADDRSP {offset+2}
PUSH
LOAD 1
OFFSET {delta}
STIND 1
PUSH
IMM {expected}
NE
JTRUE fail
ADDRSP {offset+2}
LOAD 1
PUSH
IMM {expected&255}
NE
JTRUE fail
IMM 7
NE
JTRUE fail
""")
        ir='TEXT\nmain:\nADJSP -258\n'+''.join(body)+"""IMM 75
JUMP print
fail:
IMM 33
print:
ADJSP 258
PUSH
CALL putchar
ADJSP 2
IMM 0
RETURN
"""
        self.assertIn('LOCAL_BYTE_UPDATE',codegen.Generator().optimized_ir(ir))
        self.differential(ir,b'K')

    def test_memory_immediate_byte_store_result_and_live_stack(self):
        for width in (1,-1):
            body=[]
            for byte in (-32768,-257,-1,0,255,256,305,32767):
                loaded=byte&255
                if width==-1 and loaded>=128: loaded-=256
                body.append(f'''IMM 1234
PUSH
IMM buffer+255
PUSH
IMM {byte}
STIND {width}
PUSH
IMM {byte}
NE
JTRUE fail
IMM 1234
NE
JTRUE fail
IMM buffer+255
LOAD {width}
PUSH
IMM {loaded}
NE
JTRUE fail
''')
            ir='TEXT\nmain:\n'+''.join(body)+'''IMM 75
JUMP print
fail:
IMM 33
print:
PUSH
CALL putchar
ADJSP 2
IMM 0
RETURN
DATA
buffer:
DS 258
'''
            self.assertIn('CONST_STORE1',codegen.Generator().optimized_ir(ir))
            self.differential(ir,b'K')

    def test_variable_local_updates_alias_and_odd_page(self):
        body=[]
        for left,right in ((0,0),(255,1),(65535,1),(32768,32768),(65280,255)):
            for alias in (False,True):
                source=0 if alias else 2
                answer=(left+(left if alias else right))&65535
                body.append(f'''ADDRSP 0
PUSH
IMM {left}
STIND 2
ADDRSP 2
PUSH
IMM {right}
STIND 2
ADDRSP 0
PUSH
LOAD 2
PUSH
ADDRSP {source+4}
LOAD 2
ADD
STIND 2
PUSH
IMM {answer}
NE
JTRUE fail
ADDRSP 0
LOAD 2
PUSH
IMM {answer}
NE
JTRUE fail
''')
        # The source overlaps the destination by one byte. Both words must be
        # read before storing either result byte, including on a page boundary.
        body.append('''ADDRSP 0
PUSH
IMM 33279
STIND 2
ADDRSP 2
PUSH
IMM 127
STIND 1
ADDRSP 0
PUSH
LOAD 2
PUSH
ADDRSP 5
LOAD 2
ADD
STIND 2
PUSH
IMM 384
NE
JTRUE fail
''')
        ir='TEXT\nmain:\nADJSP -255\n'+''.join(body)+'''IMM 75
JUMP print
fail:
IMM 33
print:
PUSH
CALL putchar
ADJSP 2
ADJSP 255
IMM 0
RETURN
'''
        self.assertEqual(codegen.Generator().optimized_ir(ir).count('LOCAL_ADD '),len(body))
        self.differential(ir,b'K')

    def test_register_strided_loops(self):
        for start,stride,bound in ((0,1,0),(512,3,255),(1,3,513),
                                   (250,257,1024),(100,65500,101),(255,32768,256)):
            final=start
            touched=set()
            while final<bound:
                touched.add(final)
                final=(final+stride)&65535
            checks=''.join(f'IMM buffer+{i}\nLOAD 1\nPUSH\nIMM {49 if i in touched else 0}\nNE\nJTRUE fail\n'
                           for i in sorted({0,bound,*list(sorted(touched))[:12]}))
            ir=f'''TEXT
main:
ADJSP -255
IMM 1234
PUSH
ADDRSP 2
PUSH
IMM {start}
STIND 2
ADDRSP 4
PUSH
IMM {stride}
STIND 2
$10:
ADDRSP 2
LOAD 2
PUSH
IMM {bound}
ULT
JTRUE $12
JUMP $13
$11:
ADDRSP 2
PUSH
LOAD 2
PUSH
ADDRSP 8
LOAD 2
ADD
STIND 2
JUMP $10
$12:
IMM buffer
PUSH
ADDRSP 4
LOAD 2
ADD
PUSH
IMM 305
STIND 1
JUMP $11
$13:
JTRUE fail
ADDRSP 2
LOAD 2
PUSH
IMM {final}
NE
JTRUE fail
ADDRSP 4
LOAD 2
PUSH
IMM {stride}
NE
JTRUE fail
IMM 1234
NE
JTRUE fail
{checks}IMM 75
JUMP print
fail:
IMM 33
print:
PUSH
CALL putchar
ADJSP 2
ADJSP 255
IMM 0
RETURN
DATA
buffer: DS {bound+1}
'''
            generator=codegen.Generator()
            lower=lambda text:generator.strided_loops(generator.fill_loops(text))
            self.assertIn('STRIDE ',lower(ir))
            self.differential(ir,b'K')
            for bad in (ir.replace('JUMP $10','JUMP $10\nJUMP $10'),
                        ir.replace('ULT','LT'),
                        ir.replace('ADDRSP 8','ADDRSP 6'),
                        ir.replace('IMM buffer\n','IMM unknown\n')):
                self.assertNotIn('STRIDE ',lower(bad))

    def fill_program(self,count,byte):
        return f'''TEXT
main:
ADJSP -255
IMM buffer
PUSH
IMM 17
STIND 1
IMM buffer+1
PUSH
IMM 17
STIND 1
IMM buffer+{count+1}
PUSH
IMM 17
STIND 1
IMM 1234
PUSH
ADDRSP 2
PUSH
IMM 0
STIND 2
$6:
ADDRSP 2
LOAD 2
PUSH
IMM {count}
ULT
JTRUE $8
JUMP $9
$7:
ADDRSP 2
PUSH
LOAD 2
OFFSET 1
STIND 2
JUMP $6
$8:
IMM buffer+1
PUSH
ADDRSP 4
LOAD 2
ADD
PUSH
IMM {byte}
STIND 1
JUMP $7
$9:
JTRUE fail
ADDRSP 2
LOAD 2
PUSH
IMM {count}
NE
JTRUE fail
IMM 1234
NE
JTRUE fail
ADDRSP 2
PUSH
IMM 0
STIND 2
$20:
ADDRSP 2
LOAD 2
PUSH
IMM {count}
ULT
JFALSE $21
IMM buffer+1
PUSH
ADDRSP 4
LOAD 2
ADD
LOAD 1
PUSH
IMM {byte&255}
NE
JTRUE fail
ADDRSP 2
PUSH
LOAD 2
OFFSET 1
STIND 2
JUMP $20
$21:
IMM buffer
LOAD 1
PUSH
IMM 17
NE
JTRUE fail
IMM buffer+{count+1}
LOAD 1
PUSH
IMM 17
NE
JTRUE fail
IMM 75
JUMP print
fail:
IMM 33
print:
PUSH
CALL putchar
ADJSP 2
ADJSP 255
IMM 0
RETURN
DATA
buffer:
DS {count+2}
'''

    def test_native_fill_counts_pages_stack_and_final_index(self):
        for count in (0,1,2,255,256,257,511,512,8191):
            byte=0 if count==511 else (-1 if count%2 else 305)
            ir=self.fill_program(count,byte)
            self.assertIn('FILL ',codegen.Generator().fill_loops(ir))
            with self.subTest(count=count,byte=byte):
                self.differential(ir,b'K')

    def test_native_fill_initialized_static_buffer(self):
        ir=self.fill_program(257,1).replace('DS 259',
            '\n'.join('DB '+','.join('17' for _ in range(min(16,259-offset)))
                      for offset in range(0,259,16)))
        self.assertIn('FILL ',codegen.Generator().fill_loops(ir))
        self.differential(ir,b'K')

    def test_fill_rejects_other_entries_bounds_and_dynamic_addresses(self):
        ir=self.fill_program(257,1)
        variants=(ir.replace('IMM 1234\nPUSH','JUMP $6\nIMM 1234\nPUSH'),
                  ir.replace('IMM buffer+1\nPUSH\nADDRSP','IMM 16128\nPUSH\nADDRSP'),
                  ir.replace('DS 259','DS 256'),
                  ir.replace('IMM 257\nULT\nJTRUE $8','IMM 65536\nULT\nJTRUE $8'),
                  ir.replace('ULT\nJTRUE $8','LT\nJTRUE $8'),
                  ir.replace('STIND 1\nJUMP $7','STIND 1\nCALL other\nJUMP $7'),
                  ir+'DATA\npointer:\nDW $6\n')
        for variant in variants:
            self.assertNotIn('FILL ',codegen.Generator().fill_loops(variant))

    def test_constant_left_multiplication(self):
        for constant in (0,3,5,10,256,-1):
            body=[]
            for value in (0,1,255,256,32767,32768,65535):
                body.append(f"""IMM {constant}
PUSH
IMM {value}
MUL
PUSH
IMM {(constant*value)&65535}
NE
JTRUE fail
""")
            ir='TEXT\nmain:\n'+''.join(body)+"""IMM 75
JUMP print
fail:
IMM 33
print:
PUSH
CALL putchar
ADJSP 2
IMM 0
RETURN
"""
            self.differential(ir,b'K')

    def test_local_store_with_nested_calls_and_alias(self):
        ir="""TEXT
main:
ADJSP -127
ADJSP -128
ADDRSP 4
PUSH
IMM 7
STIND 2
ADDRSP 0
PUSH
IMM 10
PUSH
ADDRSP 8
LOAD 2
MUL
PUSH
CALL twice
ADJSP 2
STIND 2
PUSH
IMM 140
NE
JTRUE fail
ADDRSP 0
PUSH
ADDRSP 2
PUSH
CALL bump
ADJSP 2
STIND 2
PUSH
IMM 141
NE
JTRUE fail
ADDRSP 0
LOAD 2
PUSH
IMM 141
NE
JTRUE fail
IMM 0
PUSH
IMM 3
PUSH
CALL counted
ADJSP 2
MUL
PUSH
IMM 0
NE
JTRUE fail
IMM counter
LOAD 2
PUSH
IMM 1
NE
JTRUE fail
IMM 75
JUMP print
fail:
IMM 33
print:
PUSH
CALL putchar
ADJSP 2
ADJSP 128
ADJSP 127
IMM 0
RETURN
twice:
ADDRSP 2
LOAD 2
DOUBLE
RETURN
bump:
ADDRSP 2
LOAD 2
PUSH
LOAD 2
OFFSET 1
STIND 2
RETURN
counted:
IMM counter
PUSH
LOAD 2
OFFSET 1
STIND 2
IMM 3
RETURN
DATA
counter:
DW 0
"""
        lowered=codegen.Generator().fold_expressions(ir)
        self.assertIn('STACK_STORE 0,2',lowered)
        self.assertIn('ARITH_CONST MUL,10',lowered)
        self.assertIn('ARITH_CONST MUL,0',lowered)
        self.differential(ir,b'K')

    def test_dense_switch_table_crosses_byte_page(self):
        for offset in (254,255):
            for selector in (-1,0,1,2,3,4,256,65535):
                ir=f"""TEXT
main:
IMM table
PUSH
IMM {selector}
SWITCH
case0:
IMM 65
JUMP print
case2:
IMM 66
JUMP print
case3:
IMM 67
JUMP print
default:
IMM 33
print:
PUSH
CALL putchar
ADJSP 2
IMM 0
RETURN
DATA
table:
DW 0,case0,2,case2,3,case3,default,0
"""
                expected=bytes([{0:65,2:66,3:67}.get(selector,33)])
                with self.subTest(offset=offset,selector=selector):
                    self.differential(ir,expected,offset)

    def test_dense_switch_signed_holes_and_fallback(self):
        tables=((-3,-2,0,2),(32765,32766,32767),(-32768,-32767,-32765),
                (0,64,127),(0,1000,2000))
        for cases in tables:
            targets=','.join(f'{v},case{i}' for i,v in enumerate(cases))
            dispatch=''.join(f'case{i}:\nIMM {65+i}\nJUMP print\n' for i in range(len(cases)))
            for selector in set(cases)|{min(cases)-1,max(cases)+1,-1,0,1,32767,32768,65535}:
                ir=f"""TEXT
main:
ADJSP -3
ADDRSP 0
PUSH
IMM {selector}
STIND 2
IMM table
PUSH
ADDRSP 2
LOAD 2
SWITCH
"""+dispatch+"""default:
IMM 33
print:
PUSH
CALL putchar
ADJSP 2
ADJSP 3
IMM 0
RETURN
DATA
padding:
DB 17
table:
DW """+targets+",default,0\n"
                normalized=((selector+32768)&65535)-32768
                expected=bytes([65+cases.index(normalized)]) if normalized in cases else b'!'
                lowered=codegen.Generator().dense_switches(ir)
                if max(cases)-min(cases)<=127 and max(cases)-min(cases)+1<=2*len(cases):
                    self.assertIn('DENSE_SWITCH',lowered)
                else:
                    self.assertNotIn('DENSE_SWITCH',lowered)
                with self.subTest(cases=cases,selector=selector):
                    self.differential(ir,expected)

    def test_quotient_reuse(self):
        for signed in (False,True):
            body=[]
            for left,right in ((0,3),(255,7),(65535,255),(32768,1),
                               (32768,65535),(65535,7),(12345,257)):
                a=left-65536 if signed and left>=32768 else left
                b=right-65536 if signed and right>=32768 else right
                q=abs(a)//abs(b)*(-1 if (a<0)!=(b<0) else 1)
                r=a-q*b
                body.append(f"""ADDRSP 0
PUSH
IMM {left}
STIND 2
ADDRSP 2
PUSH
IMM {right}
STIND 2
ADDRSP 4
PUSH
ADDRSP 2
LOAD 2
PUSH
ADDRSP 6
LOAD 2
{'MODI' if signed else 'MODU'}
STIND 2
ADDRSP 0
LOAD 2
PUSH
ADDRSP 4
LOAD 2
{'DIVI' if signed else 'DIVU'}
PUSH
IMM {q & 65535}
NE
JTRUE fail
ADDRSP 4
LOAD 2
PUSH
IMM {r & 65535}
NE
JTRUE fail
""")
            ir='TEXT\nmain:\nADJSP -6\n'+''.join(body)+"""IMM 75
JUMP print
fail:
IMM 33
print:
PUSH
CALL putchar
ADJSP 2
ADJSP 6
IMM 0
RETURN
"""
            lowered=codegen.Generator().reuse_quotients(ir)
            self.assertEqual(lowered.count('LOADQUOT'),len(body))
            self.differential(ir,b'K')

    def test_quotient_reuse_barriers(self):
        prefix="""TEXT
main:
ADJSP -4
ADDRSP 0
LOAD 2
PUSH
ADDRSP 4
LOAD 2
MODU
"""
        suffix="""ADDRSP 0
LOAD 2
PUSH
ADDRSP 4
LOAD 2
DIVU
ADJSP 4
RETURN
"""
        middles=('ADDRSP 0\nPUSH\nIMM 3\nSTIND 2\n',
                 'ADDRSP 1\nPUSH\nIMM 3\nSTIND 1\n',
                 'ADDRSP 0\nSTORE pointer,2\n',
                 '$1:\n','CALL other\n',
                 'ADDRSP 0\nLOAD 2\nPUSH\nIMM 3\nDIVU\n')
        for middle in middles:
            with self.subTest(middle=middle):
                self.assertNotIn('LOADQUOT',codegen.Generator().reuse_quotients(prefix+middle+suffix))
        # Escape discovered after a candidate also cancels the optimization.
        text=prefix+suffix.replace('ADJSP 4','ADDRSP 0\nSTORE pointer,2\nADJSP 4')
        self.assertNotIn('LOADQUOT',codegen.Generator().reuse_quotients(text))

    def test_comparison_values_and_branches(self):
        values=[0,1,255,256,32767,32768,65280,65535]
        relations={'EQ':operator.eq,'NE':operator.ne,'LT':operator.lt,
                   'LE':operator.le,'GT':operator.gt,'GE':operator.ge}
        for signed in (False,True):
            for constant in (False,True):
                for form in ('value','dead_branch','live_join'):
                    for left in values:
                        body=[];expected=bytearray()
                        for right in values:
                            for relation,compare in relations.items():
                                suffix=str(len(body));yes='yes'+suffix;done='done'+suffix
                                a=left-65536 if signed and left>=32768 else left
                                b=right-65536 if signed and right>=32768 else right
                                expected.append(48+compare(a,b))
                                operation=relation if signed or relation in ('EQ','NE') else 'U'+relation
                                if constant:
                                    expression=f'IMM {left}\nPUSH\nIMM {right}\n{operation}\n'
                                else:
                                    expression=f'IMM {right}\nSTORE right,2\nIMM {left}\nPUSH\nIMM right\nLOAD 2\n{operation}\n'
                                if form == 'dead_branch':
                                    expression+=f'JTRUE {yes}\nIMM 48\nJUMP {done}\n{yes}:\nIMM 49\n{done}:\n'
                                elif form == 'live_join':
                                    expression+=f'JFALSE {done}\nJUMP {done}\n{done}:\nBOOL\nOFFSET 48\n'
                                else:
                                    expression+='OFFSET 48\n'
                                body.append(expression+'PUSH\nCALL putchar\nADJSP 2\n')
                        ir='TEXT\nmain:\n'+''.join(body)+'IMM 0\nRETURN\nDATA\nright:\nDW 0\n'
                        with self.subTest(signed=signed,constant=constant,form=form,left=left):
                            self.differential(ir,bytes(expected))

    def test_constant_arithmetic(self):
        operations={'ADD':lambda a,b:a+b,'SUB':lambda a,b:a-b,
                    'BAND':operator.and_,'BOR':operator.or_,'BXOR':operator.xor,
                    'MUL':operator.mul,'LSHIFT':operator.lshift}
        for operation,calculate in operations.items():
            constants=(0,1,2,3) if operation=='LSHIFT' else ((0,1,2,3,4,5,8,10,16,32,64,128,256,-1) if operation=='MUL' else (0,1,-1,255,256,32768,65535))
            for constant in constants:
                body=[]
                for value in (0,1,255,256,32767,32768,65535):
                    answer=calculate(value,constant)&65535
                    body.append(f'IMM {value}\nPUSH\nIMM {constant}\n{operation}\nPUSH\nIMM {answer}\nNE\nJTRUE fail\n')
                ir='TEXT\nmain:\n'+''.join(body)+'''IMM 75
JUMP print
fail:
IMM 33
print:
PUSH
CALL putchar
ADJSP 2
IMM 0
RETURN
'''
                self.differential(ir,b'K')

    def test_unaligned_updates_and_indexed_memory(self):
        ir='''TEXT
main:
ADJSP -255
ADDRSP 0
PUSH
IMM 255
STIND 2
ADDRSP 0
PUSH
LOAD 2
OFFSET 1
STIND 2
PUSH
IMM 256
NE
JTRUE fail
ADDRSP 0
PUSH
LOAD 2
OFFSET -1
STIND 2
PUSH
IMM 255
NE
JTRUE fail
ADDRSP 0
PUSH
IMM 2
STIND 2
IMM buffer+254
PUSH
ADDRSP 2
LOAD 2
ADD
PUSH
IMM 255
STIND 1
IMM buffer+254
PUSH
ADDRSP 2
LOAD 2
ADD
LOAD -1
PUSH
IMM -1
NE
JTRUE fail
IMM buffer+254
PUSH
ADDRSP 2
LOAD 2
DOUBLE
ADD
PUSH
IMM 33059
STIND 2
IMM buffer+254
PUSH
ADDRSP 2
LOAD 2
SCALE 2
ADD
LOAD 2
PUSH
IMM 33059
NE
JTRUE fail
IMM buffer+254
PUSH
IMM index
LOAD 2
ADD
LOAD 1
PUSH
IMM 255
NE
JTRUE fail
IMM 75
JUMP print
fail:
IMM 33
print:
PUSH
CALL putchar
ADJSP 2
ADJSP 255
IMM 0
RETURN
DATA
index:
DW 2
buffer:
DS 512
'''
        self.differential(ir,b'K')

if __name__=='__main__': unittest.main()
