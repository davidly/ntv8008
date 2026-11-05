#!/usr/bin/env python3
"""Differential native tests for ACK branch, arithmetic, and memory lowering."""
from pathlib import Path
import operator
import subprocess
import sys
import tempfile
import unittest
from integration import ROOT, ASSEMBLER, run
sys.path.insert(0,str(ROOT/'ack'))
from codegen import generate

class Codegen(unittest.TestCase):
    def execute(self,em,optimize,table_offset=None):
        with tempfile.TemporaryDirectory(prefix='ACK codegen ') as directory:
            source=Path(directory,'test.asm');image=source.with_suffix('.hex')
            assembly=generate([em],optimize=optimize)
            if table_offset is not None:
                anchor='G_U1_7461626C65_ALIGN:'
                self.assertIn(anchor,assembly)
                assembly=assembly.replace(anchor,
                    'CSA_PAGE:\n        ORG ((CSA_PAGE+255D) AND 0FF00H)+'+str(table_offset)+'D\n'+anchor)
            source.write_text(assembly)
            result=subprocess.run([str(ASSEMBLER),str(source),'-o'+str(image)],capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=run('-n:200000000',image,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            return result.stdout

    def differential(self,em,expected):
        for optimize in (False,True):
            with self.subTest(optimize=optimize):
                self.assertEqual(self.execute(em,optimize),expected)

    def test_word_steps_preserve_wrap_and_older_operands(self):
        body=[]
        for value in (0,1,255,256,32767,32768,65535):
            for delta in (-1,1):
                for store,load,step in (('stl -2','lol -2','inl -2' if delta==1 else 'del -2'),
                                        ('ste value','loe value','ine value' if delta==1 else 'dee value')):
                    body.append(f""" loc {value}
 {store}
 loc 1234
 {step}
 {load}
 loc {(value+delta)&65535}
 cmi 2
 zne *9
 loc 1234
 cmi 2
 zne *9
""")
        em=' pro $main,2\n'+''.join(body)+""" loc 75
 bra *8
9
 loc 33
8
 cal $putchar
 asp 2
 loc 0
 ret 2
 end 2
value
 bss 2,0,0
"""
        self.differential(em,b'K')

    def test_byte_increment_keeps_older_operands(self):
        from ack_bytes import lower_bytes
        for conversion in ('',' loc 2\n loc 2\n ciu \n'):
            body=[]
            for value in (0,1,127,254,255):
                body.append(f""" loc 7
 loc {value}
 lal -1
 sti 1
 lal -1
 loi 1
 inc
{conversion} lal -1
 sti 1
 lal -1
 loi 1
 loc {(value+1)&255}
 cmi 2
 zne *9
 loc 7
 cmi 2
 zne *9
""")
            em=' pro $main,2\n'+''.join(body)+""" loc 75
 bra *8
9
 loc 33
8
 cal $putchar
 asp 2
 loc 0
 ret 2
 end 2
"""
            self.assertEqual(lower_bytes(em).count(' ubinc '),5)
            self.differential(em,b'K')

    def test_constant_byte_stores_keep_older_values(self):
        body=[]
        for byte in (-32768,-257,-1,0,255,256,305,32767):
            body.append(f''' loc 1234
 loc {byte}
 lae buffer
 loc 255
 ads 2
 sti 1
 loc 1234
 cmi 2
 zne *9
 lae buffer+255
 loi 1
 loc {byte&255}
 cmi 2
 zne *9
''')
        em=' pro $main,0\n'+''.join(body)+''' loc 75
 bra *8
9
 loc 33
8
 cal $putchar
 asp 2
 loc 0
 ret 2
 end 0
buffer
 bss 258,0,1
'''
        from memory import constant_byte_stores
        self.assertEqual(constant_byte_stores(em).count(' stc '),len(body))
        self.differential(em,b'K')

    def test_native_local_add_carry_alias_and_live_stack(self):
        body=[]
        for left,right in ((0,0),(255,1),(65535,1),(32768,32768),(65280,255)):
            for reverse in (False,True):
                for alias in (False,True):
                    first,second=('-4','-2') if reverse else ('-2','-4')
                    if alias: first=second='-2'
                    answer=(left+(left if alias else right))&65535
                    body.append(f''' loc {left}
 stl -2
 loc {right}
 stl -4
 loc 1234
 lol {first}
 lol {second}
 adu 2
 stl -2
 lol -2
 loc {answer}
 cmi 2
 zne *9
 loc 1234
 cmi 2
 zne *9
''')
        em=' pro $main,4\n'+''.join(body)+''' loc 75
 bra *8
9
 loc 33
8
 cal $putchar
 asp 2
 loc 0
 ret 2
 end 4
'''
        from memory import local_updates
        self.assertEqual(local_updates(em).count(' ladd '),len(body))
        self.differential(em,b'K')

    def test_register_strided_loops(self):
        from memory import strided_loops
        for start,stride,bound in ((0,1,0),(512,3,255),(1,3,513),
                                   (250,257,1024),(100,65500,101),(255,32768,256),
                                   (0,255,1024),(1,256,1024),(255,257,1024),
                                   (0,60000,1024),(65535,1,1024),
                                   (1024,32767,1024),(254,1,256)):
            final=start
            touched=set()
            while final<bound:
                touched.add(final)
                final=(final+stride)&65535
            checks=''.join(f' lae buffer+{i}\n loi 1\n loc {49 if i in touched else 0}\n cmi 2\n zne *9\n'
                           for i in sorted({0,bound,*list(sorted(touched))[:12]}))
            em=f''' pro $main,4
 loc {start}
 stl -2
 loc {stride}
 stl -4
 loc 1234
10
 lol -2
 loc {bound}
 cmu 2
 zge *11
 loc 305
 lae buffer
 lol -2
 ads 2
 sti 1
 lol -4
 lol -2
 adu 2
 stl -2
 bra *10
11
 lol -2
 loc {final}
 cmi 2
 zne *9
 lol -4
 loc {stride}
 cmi 2
 zne *9
 loc 1234
 cmi 2
 zne *9
{checks} loc 75
 bra *8
9
 loc 33
8
 cal $putchar
 asp 2
 loc 0
 ret 2
 end 4
buffer
 bss {bound+1},0,1
'''
            self.assertIn(' stride ',strided_loops(em))
            self.differential(em,b'K')
            for bad in (em.replace(' bra *10',' bra *10\n bra *10'),
                        em.replace(' cmu 2',' cmi 2'),
                        em.replace(' lol -4\n lol -2',' lol -2\n lol -2'),
                        em.replace(' lae buffer',' lae unknown')):
                self.assertNotIn(' stride ',strided_loops(bad))

    def global_loop_program(self,start,stride,bound,bottom=False):
        test=f' loe k\n loc {bound}\n'
        store=''' loc 305
 lae buffer
 loe k
 loc 2
 loc 2
 ciu 
 ads 2
 sti 1
 loe prime
 loe k
 adi 2
 ste k
'''
        loop=(' bra *10\n11\n'+store+'10\n'+test+' ble *11\n12\n' if bottom else
              '10\n'+test+' bgt *12\n'+store+' bra *10\n12\n')
        return (f' pro $main,0\n loc {start}\n ste k\n loc {stride}\n ste prime\n'
                ' loc 1234\n'+loop)

    def test_signed_global_strided_loops(self):
        from memory import global_strided_loops
        for bottom in (False,True):
            for start,stride,bound in ((0,1,0),(512,3,254),(1,3,512),
                                       (250,257,1023),(-1,1,3),
                                       (2,32767,3),(2,-32767,3),(32767,1,3)):
                final=start
                touched=set()
                while final<=bound:
                    touched.add(((final+8192)&16383)-8192)
                    final=((final+stride+32768)&65535)-32768
                checks=''.join(f' lae buffer{offset:+d}\n loi 1\n loc {49 if offset in touched else 0}\n cmi 2\n zne *90\n'
                               for offset in sorted({-4,-1,0,bound+1,*list(sorted(touched))[:12]}))
                em=self.global_loop_program(start,stride,bound,bottom)+f''' loe k
 loc {final}
 cmi 2
 zne *90
 loe prime
 loc {stride}
 cmi 2
 zne *90
 loc 1234
 cmi 2
 zne *90
{checks} loc 75
 bra *91
90
 loc 33
91
 cal $putchar
 asp 2
 loc 0
 ret 2
 end 0
guard
 bss 8,0,1
buffer
 bss {bound+2},0,1
k
 bss 2,0,0
prime
 bss 2,0,0
'''
                self.assertEqual(global_strided_loops(em).count(' gstride '),1)
                self.differential(em,b'K')
                for bad in (em.replace(' bss 2,0,0',' bss 4,0,0'),
                            em.replace(f' bss {bound+2},0,1',f' bss {bound},0,1'),
                            em.replace(' loe prime\n loe k',' loe k\n loe k'),
                            em.replace(' sti 1',' sti 1\n cal $effect'),
                            em.replace(' loe k\n loc '+str(bound),
                                       ' loe other\n loc '+str(bound)),
                            em.replace(' ret 2',' bra *10\n ret 2')):
                    self.assertNotIn(' gstride ',global_strided_loops(bad))

    def test_signed_global_negative_index_aliases_stride(self):
        from memory import global_strided_loops
        for bottom in (False,True):
            # buffer[-2] aliases prime's low byte, changing the step from 1
            # to 49. The fallback must read that changed step from memory.
            em=self.global_loop_program(-2,1,3,bottom)+''' loe k
 loc 47
 cmi 2
 zne *90
 loe prime
 loc 49
 cmi 2
 zne *90
 loc 1234
 cmi 2
 zne *90
 loc 75
 bra *91
90
 loc 33
91
 cal $putchar
 asp 2
 loc 0
 ret 2
 end 0
k
 bss 2,0,0
prime
 bss 2,0,0
buffer
 bss 8,0,1
'''
            self.assertIn(' gstride ',global_strided_loops(em))
            self.differential(em,b'K')

    def fill_program(self,count,byte):
        return f''' pro $main,4
 loc 17
 lae buffer
 sti 1
 loc 17
 lae buffer+1
 sti 1
 loc 17
 lae buffer+{count+1}
 sti 1
 loc 1234
 zrl -2
10
 lol -2
 loc {count}
 cmu 2
 zge *11
 loc {byte}
 lae buffer+1
 lol -2
 ads 2
 sti 1
 loc 1
 lol -2
 adu 2
 stl -2
 bra *10
11
 lol -2
 loc {count}
 cmi 2
 zne *9
 loc 1234
 cmi 2
 zne *9
 zrl -4
20
 lol -4
 loc {count}
 cmu 2
 zge *21
 lae buffer+1
 lol -4
 ads 2
 loi 1
 loc {byte&255}
 cmi 2
 zne *9
 inl -4
 bra *20
21
 lae buffer
 loi 1
 loc 17
 cmi 2
 zne *9
 lae buffer+{count+1}
 loi 1
 loc 17
 cmi 2
 zne *9
 loc 75
 bra *8
9
 loc 33
8
 cal $putchar
 asp 2
 loc 0
 ret 2
 end 4
buffer
 bss {count+2},0,1
'''

    def test_native_fill_counts_pages_and_final_index(self):
        from memory import fill_loops
        for count in (0,1,2,255,256,257,511,512,8191):
            byte=0 if count==511 else (-1 if count%2 else 305)
            em=self.fill_program(count,byte)
            self.assertIn(' fill ',fill_loops(em))
            with self.subTest(count=count,byte=byte):
                self.differential(em,b'K')

    def test_fill_rejects_other_entries_bounds_and_dynamic_addresses(self):
        from memory import fill_loops
        em=self.fill_program(257,1)
        variants=(em.replace(' loc 1234\n zrl -2',' bra *10\n loc 1234\n zrl -2'),
                  em.replace(' lae buffer+1\n lol -2',' lae 16128\n lol -2'),
                  em.replace(' bss 259,0,1',' bss 256,0,1'),
                  em.replace(' loc 257\n cmu 2\n zge *11',' loc 65536\n cmu 2\n zge *11'),
                  em.replace(' cmu 2\n zge *11',' cmi 2\n zge *11'),
                  em.replace(' sti 1\n loc 1\n lol -2',' sti 1\n cal $other\n loc 1\n lol -2'))
        for variant in variants:
            self.assertNotIn(' fill ',fill_loops(variant))

    def test_dense_switch_descriptor_crosses_page(self):
        for offset in (250,252,254):
            for selector,expected in ((9,b'!'),(10,b'A'),(11,b'B'),(12,b'C'),(13,b'!')):
                em=f""" pro $main,0
 loc {selector}
 lae table
 csa 2
1
 loc 65
 bra *8
2
 loc 66
 bra *8
3
 loc 67
 bra *8
9
 loc 33
8
 cal $putchar
 asp 2
 loc 0
 ret 2
table
 rom *9,10,2,*1,*2,*3
 end 0
"""
                for optimize in (False,True):
                    with self.subTest(offset=offset,selector=selector,optimize=optimize):
                        self.assertEqual(self.execute(em,optimize,offset),expected)

    def test_quotient_reuse_and_signed_remainders(self):
        from division import reuse_quotients
        calls=[];procedures=[]
        for signed in (False,True):
            for left,right in ((0,3),(255,7),(65535,255),(32768,1),
                               (32768,65535),(65535,7),(12345,257)):
                a=left-65536 if signed and left>=32768 else left
                b=right-65536 if signed and right>=32768 else right
                q=abs(a)//abs(b)*(-1 if (a<0)!=(b<0) else 1)
                r=a-q*b
                name='$check'+str(len(calls))
                calls.append(f' loc {right}\n loc {left}\n cal {name}\n asp 4\n')
                procedures.append(f""" pro {name},2
 lol 0
 lol 2
 {'rmi' if signed else 'rmu'} 2
 stl -2
 lol 0
 lol 2
 {'dvi' if signed else 'dvu'} 2
 loc {q & 65535}
 cmi 2
 zne *9
 lol -2
 loc {r & 65535}
 cmi 2
 zne *9
 loc 75
 bra *8
9
 loc 33
8
 cal $putchar
 asp 2
 ret 0
 end 2
""")
        em=' pro $main,0\n'+''.join(calls)+' loc 0\n ret 2\n end 0\n'+''.join(procedures)
        self.assertEqual(reuse_quotients(em).count(' qreuse 2'),len(calls))
        self.differential(em,b'K'*len(calls))

    def test_quotient_reuse_barriers(self):
        from division import reuse_quotients
        prefix=' pro $main,4\n lol -2\n lol -4\n rmu 2\n'
        suffix=' lol -2\n lol -4\n dvu 2\n ret 2\n end 4\n'
        for middle in (' stl -2\n',' inl -4\n',' cal $other\n',
                       '1\n',' lol -2\n loc 3\n dvu 2\n',
                       ' lal -2\n loc 1\n sti 2\n'):
            with self.subTest(middle=middle):
                self.assertNotIn(' qreuse ',reuse_quotients(prefix+middle+suffix))
        global_em=(prefix+suffix).replace('lol -2','loe x').replace('lol -4','loe y')
        for middle in (' sti 1\n',' ste x+1\n'):
            em=global_em.replace(' rmu 2\n',' rmu 2\n'+middle)
            self.assertNotIn(' qreuse ',reuse_quotients(em))

    def test_quotient_reuse_private_globals(self):
        from division import reuse_quotients
        em=""" pro $main,0
 loc 65535
 ste x
 loc 255
 ste y
 loe x
 loe y
 rmu 2
 lae buffer
 loc 0
 ads 2
 sti 1
 loe x
 loe y
 dvu 2
 loc 257
 cmi 2
 zne *9
 lae buffer
 loi 1
 loc 0
 cmi 2
 zne *9
 loc 75
 bra *8
9
 loc 33
8
 cal $putchar
 asp 2
 loc 0
 ret 2
 end 0
x
 bss 2,0,0
y
 bss 2,0,0
buffer
 bss 4,0,0
"""
        self.assertIn(' qreuse 2',reuse_quotients(em))
        self.differential(em,b'K')
        for escape in (' exa x\n','pointer\n con x\n',
                       ' pro $address,0\n lae x\n ret 2\n end 0\n'):
            self.assertNotIn(' qreuse 2',reuse_quotients(em+escape))

    def test_local_offsets_and_cached_values(self):
        # Cross pages in both directions, with an older expression word live.
        body=[]
        for offset in (-2,-254,-256,-258,-510):
            for value in (0,255,256,32768,65535):
                body.append(f""" loc 1234
 loc {value}
 stl {offset}
 lol {offset}
 loc {value}
 cmi 2
 zne *9
 loc 1234
 cmi 2
 zne *9
""")
        em=' pro $main,512\n'+''.join(body)+""" loc 75
 cal $putchar
 asp 2
 loc 0
 ret 2
9
 loc 33
 cal $putchar
 asp 2
 loc 0
 ret 2
 end 512
"""
        self.differential(em,b'K')

    def test_comparison_boundaries(self):
        values=[0,1,127,128,255,256,32767,32768,32769,65280,65535]
        relations={'eq':operator.eq,'ne':operator.ne,'lt':operator.lt,
                   'le':operator.le,'gt':operator.gt,'ge':operator.ge}
        # Main loops over the left operands. Every right operand/relation has
        # its own procedure, testing both constant and two-operand patterns.
        for signed in (False,True):
            for constant in (False,True):
                functions=[];calls=[];expected=bytearray()
                for right in values:
                    for relation in relations:
                        name=f'$check{right}{relation}'
                        compare=('lol 0\n loc '+str(right)+'\n '+
                                 ('cmi' if signed else 'cmu')+' 2\n z'+relation+' *1')
                        if not constant:
                            # Load the right operand through a local; it can't
                            # be matched as an immediate comparison.
                            compare=('lol 0\n lol 2\n '+
                                     ('b'+relation+' *1' if signed else 'cmu 2\n z'+relation+' *1'))
                        functions.append(f''' pro {name},0
 {compare}
 loc 48
 ret 2
1
 loc 49
 ret 2
 end 0
''')
                        calls.append(f''' loc {right}
 lae values
 lol -2
 loc 2
 mlu 2
 ads 2
 loi 2
 cal {name}
 asp 4
 lfr 2
 cal $putchar
 asp 2
''')
                for left in values:
                    for right in values:
                        a=left-65536 if signed and left>=32768 else left
                        b=right-65536 if signed and right>=32768 else right
                        expected.extend(49 if op(a,b) else 48 for op in relations.values())
                main=''' pro $main,2
 zrl -2
1
'''+''.join(calls)+f''' inl -2
 lol -2
 loc {len(values)}
 blt *1
 loc 0
 ret 2
 end 2
values
 rom '''+','.join(map(str,values))+'\n'
                with self.subTest(signed=signed,constant=constant):
                    self.differential(main+''.join(functions),bytes(expected))

    def test_constant_arithmetic_and_carry(self):
        values=[0,1,255,256,32767,32768,65535]
        constants=[0,1,-1,255,256,32768,65535]
        operations={'adu':lambda a,b:a+b,'sbu':lambda a,b:a-b,
                    'and':operator.and_,'ior':operator.or_,'xor':operator.xor}
        # Each operation/constant gets a small image, leaving a sentinel below
        # the expression to verify its exact stack consumption.
        for instruction,operation in operations.items():
            for constant in constants:
                body=[]
                for value in values:
                    answer=operation(value,constant)&65535
                    body.append(f''' loc 1234
 loc {value}
 loc {constant}
 {instruction} 2
 loc {answer}
 cmi 2
 zne *9
 loc 1234
 cmi 2
 zne *9
''')
                em=' pro $main,0\n'+''.join(body)+''' loc 75
 cal $putchar
 asp 2
 loc 0
 ret 2
9
 loc 33
 cal $putchar
 asp 2
 loc 0
 ret 2
 end 0
'''
                self.differential(em,b'K')

    def test_power_of_two_division_and_remainder(self):
        signed_values=[-32768,-32767,-257,-256,-255,-3,-2,-1,0,1,2,3,255,256,257,32767]
        unsigned_values=[0,1,2,3,127,128,255,256,257,32767,32768,65535]
        for operation in ('dvi','dvu','rmi','rmu'):
            signed=operation.endswith('i')
            for divisor in (1,2,4,8,16,32,64,128,256):
                body=[]
                for value in signed_values if signed else unsigned_values:
                    quotient=abs(value)//divisor*(-1 if value<0 else 1)
                    answer=quotient if operation.startswith('dv') else value-quotient*divisor
                    body.append(f""" loc 1234
 loc {value}
 loc {divisor}
 {operation} 2
 loc {answer}
 cmi 2
 zne *9
 loc 1234
 cmi 2
 zne *9
""")
                em=' pro $main,0\n'+''.join(body)+""" loc 75
 cal $putchar
 asp 2
 loc 0
 ret 2
9
 loc 33
 cal $putchar
 asp 2
 loc 0
 ret 2
 end 0
"""
                with self.subTest(operation=operation,divisor=divisor):
                    self.differential(em,b'K')

    def test_scaling_and_updates(self):
        body=[]
        for value in (0,1,255,32767,32768,65535):
            for factor in (1,2,4,8):
                body.append(f''' loc {value}
 loc {factor}
 mlu 2
 loc {(value*factor)&65535}
 cmi 2
 zne *9
''')
            body.append(f''' loc {value}
 dup 2
 adu 2
 loc {(value*2)&65535}
 cmi 2
 zne *9
 loc {value}
 stl -2
 inl -2
 del -2
 lol -2
 loc {value}
 cmi 2
 zne *9
 loc {value}
 ste counter
 ine counter
 dee counter
 loe counter
 loc {value}
 cmi 2
 zne *9
 loc {value}
 inc
 dec
 adp 257
 adp -257
 loc {value}
 cmi 2
 zne *9
''')
        em=' pro $main,2\n'+''.join(body)+''' loc 75
 cal $putchar
 asp 2
 loc 0
 ret 2
9
 loc 33
 cal $putchar
 asp 2
 loc 0
 ret 2
 end 2
counter
 bss 2,0,0
'''
        self.differential(em,b'K')

    def test_fused_memory_and_side_effects(self):
        # Mix fixed and dynamic bases, stack values across calls, scaled local
        # indices, and indexed stores. Byte offsets cross a page boundary.
        em=''' pro $main,2
 loc 2
 stl -2
 loc 1234
 loc 231
 lae buffer+254
 lol -2
 ads 2
 sti 1
 lae buffer+254
 lol -2
 ads 2
 loi 1
 loc 231
 cmi 2
 zne *9
 loc 33059
 lae buffer+254
 lol -2
 dup 2
 adu 2
 ads 2
 sti 2
 lae buffer+254
 lol -2
 loc 2
 mlu 2
 ads 2
 loi 2
 loc 33059
 cmi 2
 zne *9
 loc 211
 lae buffer
 cal $identity
 asp 2
 lfr 2
 loc 300
 ads 2
 sti 1
 lae buffer
 cal $identity
 asp 2
 lfr 2
 loc 300
 ads 2
 loi 1
 loc 211
 cmi 2
 zne *9
 loc 1234
 cmi 2
 zne *9
 loc 75
 cal $putchar
 asp 2
 loc 0
 ret 2
9
 loc 33
 cal $putchar
 asp 2
 loc 0
 ret 2
 end 2
 pro $identity,0
 lol 0
 ret 2
 end 0
buffer
 bss 512,0,0
'''
        self.differential(em,b'K')

if __name__=='__main__': unittest.main()
