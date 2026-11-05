"""Render SmallC-85 backend operations as native 8008/A08 instructions.

The operation stream exists only during compilation. Target programs contain
8008 code and runtime helpers, with all C call frames on the RAM stack.
"""
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
import sys
if str(HERE) not in sys.path: sys.path.insert(0,str(HERE))
from smallc_bytes import thread_booleans, byte_comparisons, stack_depths, local_stores
if str(HERE.parent/'tools') not in sys.path: sys.path.insert(0,str(HERE.parent/'tools'))
from native8008 import optimize_functions
from runtime_prune import prune_runtime
from outline8008 import outline_frame_loads

class CodegenError(ValueError):
    pass

# runtime.asm starts the RAM stack at RSP EQU 3F00H and pushes STOP before
# jumping to main.
MAIN_SP = 0x3F00 - 2

class Generator:
    def __init__(self, optimize=True, compact=False):
        self.optimize = optimize
        # Compact output keeps PUSHes: each stored argument is ~20 bytes inline.
        self.compact = compact
        self.code = []
        self.data = []
        self.output = self.code
        self.serial = 0
        self.defined = set()
        self.references = set()
        self.function = None
        self.static_main = False
        self.frame_depth = None
        self.hl_address = None
        self.paged = {}

    def emit(self, *lines):
        for line in lines:
            op = line.split()[0] if line.split() else ''
            if op[:2] in ('LH','LL') or op in ('INH','INL','DCH','DCL','CAL','JMP'):
                self.hl_address = None
        self.output.extend('        ' + line for line in lines)

    def label(self, name):
        self.hl_address = None
        self.output.append(name + ':')

    def unique(self):
        self.serial += 1
        return 'SCL' + str(self.serial)

    def symbol(self, name):
        return 'SC_' + name.strip().encode('ascii').hex().upper()

    def value(self, text):
        text = text.strip()
        if re.fullmatch(r'-?\d+', text):
            return str(int(text) & 65535) + 'D'
        offset = re.fullmatch(r'([$A-Za-z_][\w$]*)([+-]\d+)', text)
        if offset:
            return self.value(offset[1]) + offset[2] + 'D'
        if not re.fullmatch(r'[$A-Za-z_][\w$]*', text):
            raise CodegenError('unsupported constant: ' + text)
        self.references.add(text)
        return self.symbol(text)

    def immediate(self, value):
        self.emit('LAI LOW (' + value + ')', 'LBI HIGH (' + value + ')')

    def inc_hl(self):
        if self.hl_address is not None and self.hl_address & 255 != 255:
            # A known address that cannot carry into H needs no page check.
            self.output.append('        INL')
            self.hl_address += 1
            return
        done = self.unique()
        self.emit('INL', 'JFZ ' + done, 'INH')
        self.label(done)

    def load(self, width, address=True):
        if address:
            self.emit('LHB', 'LLA')
        self.emit('LAM')
        if width == 2:
            self.inc_hl()
            self.emit('LBM')
        else:
            self.emit('LBI 0')
            if width == -1:
                done = self.unique()
                self.emit('NDA', 'JFS ' + done, 'LBI 0FFH')
                self.label(done)

    def stack_address(self, offset):
        # Constant SP-relative addresses need neither a general 16-bit add
        # helper nor its register shuffling. Preserve CD for callers.
        if (self.static_main and self.function == 'main' and
                self.frame_depth is not None):
            # main is entered once, with SP = MAIN_SP; the exact transient
            # depth makes every SP-relative address a constant.
            address = (MAIN_SP - self.frame_depth + offset) & 65535
            self.emit(f'LHI {address >> 8}D', f'LLI {address & 255}D')
            self.hl_address = address
            return
        offset &= 65535
        self.emit('LHI HIGH RSP','LLI LOW RSP','LAM',
                  f'ADI {offset & 255}D','LEA','INL','LAM',
                  f'ACI {offset >> 8}D','LHA','LLE')

    def boolean(self, condition):
        yes, done = self.unique(), self.unique()
        if condition in ('eq', 'ne'):
            self.emit('ORB', ('JTZ ' if condition == 'eq' else 'JFZ ') + yes)
        elif condition in ('lt', 'ge'):
            self.emit('LAB', 'NDI 80H', ('JFZ ' if condition == 'lt' else 'JTZ ') + yes)
        else:
            self.emit('ORB', 'JTZ ' + (done if condition == 'gt' else yes),
                      'LAB', 'NDI 80H', ('JTZ ' if condition == 'gt' else 'JFZ ') + yes)
            # gt with zero must still construct false below.
            if condition == 'gt':
                self.label(done)
                done = self.unique()
        self.immediate('0')
        self.emit('JMP ' + done)
        self.label(yes)
        self.immediate('1')
        self.label(done)

    def binary(self, name):
        # The frontend has already pushed the left operand. Keep the right
        # operand and result in AB rather than making two stack round trips.
        self.emit('CAL ' + name)

    def add_constant(self, value):
        value = self.value(value)
        self.emit('ADI LOW ('+value+')', 'LEA', 'LAB',
                  'ACI HIGH ('+value+')', 'LBA', 'LAE')

    def compare_branch(self, relation, target, constant=None):
        """Compare AB against a constant, or RAM left against AB right."""
        signed = not relation.startswith('U')
        condition = relation.lstrip('U').lower()
        if constant is None:
            self.emit('LCA', 'LDB', 'CAL POP')
        elif constant & 65535 == 0:
            if condition in ('eq','ne') or not signed:
                if condition in ('ge','lt'):
                    if condition == 'ge':
                        self.emit('JMP '+target)
                else:
                    zero = condition in ('eq','le')
                    self.emit('ORB', ('JTZ ' if zero else 'JFZ ')+target)
                return
        done = self.unique()
        self.emit('LEA','LAB')
        if signed and condition not in ('eq','ne'):
            if constant is None:
                self.emit('XRI 80H','LBA','LAD','XRI 80H','LDA','LAB')
            else:
                self.emit('XRI 80H')
        self.emit('CPD' if constant is None else 'CPI %dD' % (
            ((constant >> 8) & 255) ^ (128 if signed and condition not in ('eq','ne') else 0)))
        if condition not in ('eq','ne'):
            self.emit('JTC '+(target if condition in ('lt','le') else done))
        self.emit('JFZ '+(target if condition in ('gt','ge','ne') else done),
                  'LAE', 'CPC' if constant is None else 'CPI %dD' % (constant & 255))
        if condition in ('eq','ne','lt','ge'):
            self.emit({'eq':'JTZ ','ne':'JFZ ','lt':'JTC ','ge':'JFC '}[condition]+target)
        elif condition == 'le':
            self.emit('JTC '+target,'JTZ '+target)
        else:
            self.emit('JTC '+done,'JFZ '+target)
        self.label(done)

    def compare_boolean(self, relation, constant=None, jump=None, target=None):
        # Short-circuit expression joins can read the comparison's boolean AB
        # after branching, so retain canonical 0/1 on both paths when needed.
        yes, done = self.unique(), self.unique()
        self.compare_branch(relation, yes, constant)
        self.immediate('0')
        self.emit('JMP '+(target if jump == 'JFALSE' else done))
        self.label(yes)
        self.immediate('1')
        if jump == 'JTRUE':
            self.emit('JMP '+target)
        self.label(done)

    def optimized_ir(self, text):
        lines = [raw.split(';')[0].strip() for raw in text.splitlines()]
        lines = [line for line in lines if line]
        labels = {line.split(':',1)[0]:i for i,line in enumerate(lines) if ':' in line}
        def parts(index):
            return lines[index].split(None,1) if index < len(lines) else []
        def dead(index):
            # Prove AB is overwritten before its next use on this successor.
            # Unknown operations and loops conservatively keep the boolean.
            seen = set()
            while index < len(lines) and index not in seen:
                seen.add(index)
                line = lines[index].split(':',1)[-1].strip()
                fields = line.split(None,1)
                if not fields:
                    index += 1
                    continue
                op = fields[0]
                if op in ('IMM','ADDRSP','CALL'):
                    return True
                if op == 'JUMP' and fields[1] in labels:
                    index = labels[fields[1]]
                elif op in ('ADJSP','TEXT','SECOND'):
                    index += 1
                else:
                    return False
            return False
        relations = ('EQ','NE','LT','LE','GT','GE','ULT','ULE','UGT','UGE')
        output = []
        index = 0
        while index < len(lines):
            first, second, third, fourth = [parts(index+n) for n in range(4)]
            if len(first)==2 and first[0]=='ADJSP':
                amount,cursor = int(first[1]),index+1
                while parts(cursor) and parts(cursor)[0]=='ADJSP':
                    following = int(parts(cursor)[1])
                    if amount*following < 0 or abs(amount+following) >= 16384:
                        break
                    amount += following
                    cursor += 1
                if cursor > index+1:
                    output.append('ADJSP '+str(amount))
                    index = cursor
                    continue
            constant = None
            if (len(first)==2 and first[0]=='IMM' and
                    re.fullmatch(r'[$A-Za-z_][\w$]*',first[1]) and
                    second==['LOAD','2'] and third in (['OFFSET','1'],['OFFSET','-1']) and
                    fourth==['STORE',first[1]+',2'] and dead(index+4)):
                output.append('GLOBAL_STEP '+first[1]+','+third[1])
                index += 4
                continue
            if (len(first)==2 and first[0]=='ADDRSP' and int(first[1])>=0 and
                    second==['LOAD','2'] and third==['PUSH'] and
                    fourth==['ADDRSP',str(int(first[1])+2)] and
                    parts(index+4)==['LOAD','2'] and parts(index+5)==['ADD']):
                # The pushed word shifts the second address by two bytes.
                # Read an unchanged local once when computing x + x.
                output.extend((lines[index], 'LOAD 2', 'DOUBLE'))
                index += 6
                continue
            if (first==['PUSH'] and len(second)==2 and second[0]=='ADDRSP' and
                    int(second[1])>=2 and third==['LOAD','2'] and fourth==['ADD']):
                output.append('ADD_LOCAL '+str(int(second[1])-2))
                index += 4
                continue
            relation = first[0] if first[0] in relations else None
            count = 1
            if first == ['PUSH'] and len(second) == 2 and second[0] == 'IMM' and re.fullmatch(r'-?\d+',second[1]) and third:
                value = int(second[1])
                if third[0] in relations:
                    relation, constant, count = third[0], value, 3
                elif third[0] in ('ADD','SUB','BAND','BOR','BXOR') or (
                        third[0] == 'MUL' and value in (0,1,2,3,4,5,8,10,16,32,64,128,256,-1)) or (
                        third[0] == 'LSHIFT' and value in (0,1,2,3)):
                    output.append('ARITH_CONST '+third[0]+','+str(value))
                    index += 3
                    continue
            if relation:
                following = parts(index+count)
                if following and following[0] in ('JTRUE','JFALSE'):
                    keep = not (dead(index+count+1) and dead(labels.get(following[1],len(lines))))
                    output.append('CMPBRANCH '+','.join((relation,following[0],following[1],
                                  str(constant) if constant is not None else '-',str(int(keep)))))
                    index += count+1
                else:
                    output.append('COMPARE '+relation+','+(str(constant) if constant is not None else '-'))
                    index += count
                continue
            if (first==['PUSH'] and len(second)==2 and second[0]=='IMM' and
                    re.fullmatch(r'-?\d+',second[1]) and
                    third in (['STIND','1'],['STIND','-1'])):
                output.append('CONST_STORE1 '+second[1])
                index += 3
                continue
            if (len(first)==2 and first[0]=='ADDRSP' and int(first[1])>=0 and second==['PUSH'] and
                    third==['LOAD','2'] and fourth==['PUSH'] and
                    len(parts(index+4))==2 and parts(index+4)[0]=='ADDRSP' and
                    int(parts(index+4)[1])>=4 and parts(index+5)==['LOAD','2'] and
                    parts(index+6)==['ADD'] and parts(index+7)==['STIND','2']):
                output.append('LOCAL_ADD '+first[1]+','+str(int(parts(index+4)[1])-4))
                index += 8
                continue
            if (len(first)==2 and first[0]=='ADDRSP' and second==['PUSH'] and
                    third==['LOAD','1'] and len(fourth)==2 and fourth[0]=='OFFSET' and
                    parts(index+4)==['STIND','1']):
                operation = 'LOCAL_BYTE_STEP' if dead(index+5) else 'LOCAL_BYTE_UPDATE'
                output.append(operation+' '+first[1]+','+fourth[1])
                index+=5
                continue
            if (len(first) == 2 and first[0] == 'ADDRSP' and second == ['PUSH'] and
                    int(first[1]) >= 0 and
                    third == ['LOAD','2'] and len(fourth) == 2 and fourth[0] == 'OFFSET' and
                    parts(index+4) == ['STIND','2']):
                operation = ('LOCAL_STEP' if int(fourth[1]) in (-1,1) and dead(index+5)
                             else 'LOCAL_UPDATE')
                output.append(operation+' '+first[1]+','+fourth[1])
                index += 5
                continue
            if (len(first) == 2 and first[0] == 'ADDRSP' and second == ['PUSH'] and
                    len(third) == 2 and third[0] == 'IMM' and fourth and fourth[0] == 'STIND'):
                output.append('LOCAL_CONST '+','.join((first[1],third[1],fourth[1])))
                index += 4
                continue
            if (len(first) == 2 and first[0] == 'IMM' and second == ['PUSH'] and
                    len(third) == 2 and third[0] == 'ADDRSP' and int(third[1]) >= 2 and
                    fourth in (['LOAD','2'],['LOAD','1'],['LOAD','-1'])):
                cursor = index+4
                scaling = []
                while parts(cursor) and parts(cursor)[0] in ('DOUBLE','OFFSET','SCALE'):
                    scaling.append(lines[cursor])
                    cursor += 1
                if parts(cursor) == ['ADD']:
                    following = parts(cursor+1)
                    if (fourth in (['LOAD','2'],['LOAD','1']) and not scaling and
                            following in (['LOAD','1'],['LOAD','-1'],['LOAD','2'])):
                        output.append('INDEX_LOAD '+','.join((
                            str(int(third[1])-2),first[1],following[1]))+
                            (',byte' if fourth==['LOAD','1'] else ''))
                        index = cursor+2
                        continue
                    # The old index was addressed after pushing the base. The
                    # fused sequence removes that push, so compensate by -2.
                    output += ['ADDRSP '+str(int(third[1])-2),'LOAD '+fourth[1]]+scaling
                    output.append('ADD_CONST '+first[1])
                    index = cursor+1
                    continue
            if len(first) == 2 and first[0] == 'IMM' and second and second[0] == 'LOAD':
                output.append('DIRECT_LOAD '+first[1]+','+second[1])
                index += 2
                continue
            if first == ['ADD'] and second and second[0] == 'LOAD':
                output.append('ADDLOAD '+second[1])
                index += 2
                continue
            output.append(lines[index])
            index += 1
        return '\n'.join(output)

    def allocations(self, text):
        """Sizes of statically allocated byte buffers in the IR data section."""
        allocations={}
        section,current=False,None
        for line in text.splitlines():
            if line in ('DATA','TEXT'):
                section,current=line=='DATA',None
                continue
            if not section:
                continue
            if ':' in line:
                current,line=line.split(':',1)
                current,line=current.strip(),line.strip()
                allocations[current]=0
                if not line:
                    continue
            fields=line.split(None,1)
            if current and len(fields)==2:
                if fields[0]=='DS' and fields[1].isdigit():
                    allocations[current]+=int(fields[1])
                    continue
                values=fields[1].split(',')
                if fields[0] in ('DB','DW') and all(re.fullmatch(r'-?\d+',v.strip()) for v in values):
                    allocations[current]+=len(values)*(1 if fields[0]=='DB' else 2)
                    continue
            current=None
        return allocations

    def saved_addresses(self, text):
        """Hold an indirect store's address in SADDR instead of the RAM stack.

        The value expression between PUSH and its STIND must be straight-line,
        call-free and store-free, so nothing else can reuse SADDR meanwhile.
        Its SP-relative operands move down by the removed word.
        """
        lines = [x.split(';')[0].strip() for x in text.splitlines()]
        lines = [x for x in lines if x]
        binary = {'ADD','SUB','MUL','DIVI','DIVU','MODI','MODU','BOR','BXOR',
                  'BAND','SHRI','SHRU','LSHIFT','EQ','NE','LT','LE','GT','GE',
                  'ULT','ULE','UGT','UGE','RMISAVE','RMUSAVE','ADDLOAD'}
        pure = {'IMM','LOAD','LOADQUOT','OFFSET','DOUBLE','HALF','SCALE','NEGATE',
                'COMPLEMENT','BOOL','NOT','ARITH_CONST','ADD_CONST','DIRECT_LOAD'}
        shifted = {'STACK_LOAD','INDEX_LOAD','ADD_LOCAL'}
        index = 0
        while index < len(lines):
            if lines[index] != 'PUSH':
                index += 1
                continue
            depth, cursor, adjusted, matched = 0, index+1, [], False
            while cursor < len(lines):
                fields = lines[cursor].split(None, 1)
                op = fields[0]
                if op == 'STIND' and depth == 0:
                    matched = True
                    break
                if op == 'PUSH':
                    depth += 1
                elif op in binary:
                    if not depth:
                        break
                    depth -= 1
                elif op in shifted:
                    values = fields[1].split(',')
                    if int(values[0]) < 2:
                        break
                    values[0] = str(int(values[0])-2)
                    adjusted.append(op+' '+','.join(values))
                    cursor += 1
                    continue
                elif op not in pure:
                    break
                adjusted.append(lines[cursor])
                cursor += 1
            if matched:
                lines[index:cursor+1] = (['SAVE_ADDRESS']+adjusted+
                                         ['STIND_SAVED '+lines[cursor].split()[1]])
            index += 1
        return '\n'.join(lines)

    def stored_arguments(self, text):
        """Reserve a direct call's trailing argument words with one ADJSP.

        Straight-line argument pushes before CALL become stores into their
        final slots, and the call stores its return word at SP+0. Operands
        between pushes see the lower SP, so their offsets grow accordingly.
        """
        lines = [x.split(';')[0].strip() for x in text.splitlines()]
        lines = [x for x in lines if x]
        pure = {'IMM','LOAD','LOADQUOT','OFFSET','DOUBLE','COMPLEMENT',
                'ARITH_CONST','ADD_CONST','DIRECT_LOAD'}
        shifted = {'STACK_LOAD','INDEX_LOAD'}
        index = 0
        while index < len(lines):
            fields = lines[index].split()
            if fields[0] != 'CALL' or index == 0 or lines[index-1] != 'PUSH':
                index += 1
                continue
            start = index-1
            while start > 0 and (lines[start-1] == 'PUSH' or
                                 lines[start-1].split()[0] in pure|shifted):
                start -= 1
            pushes = [i for i in range(start, index) if lines[i] == 'PUSH']
            total = 2*len(pushes)+2
            output, done = [], 0
            for i in range(start, index):
                op = lines[i].split(None, 1)
                if lines[i] == 'PUSH':
                    if not done:
                        output.append('ADJSP -'+str(total))
                    done += 1
                    output.append('STACK_STORE '+str(total-2*done)+',2')
                elif op[0] in shifted and done:
                    values = op[1].split(',')
                    values[0] = str(int(values[0])+total-2*done)
                    output.append(op[0]+' '+','.join(values))
                else:
                    output.append(lines[i])
            output.append('CALL_STORED '+fields[1])
            lines[start:index+1] = output
            index = start+len(output)
        return '\n'.join(lines)

    def paged_arrays(self, text):
        """Byte arrays of at most one page that unsigned byte indices address.

        The data section pads each so it cannot cross a page; its indexed
        addresses then need no carry into the high byte.
        """
        sizes=self.allocations(text);lines=text.splitlines();paged={}
        for i,line in enumerate(lines):
            f=line.split(None,1);name=None
            if f and f[0]=='INDEX_LOAD':
                fields=f[1].split(',')
                if fields[2]=='1' and fields[3:]==['byte']:name=fields[1]
            elif (f and f[0]=='ADD_CONST' and i and
                  re.fullmatch(r'STACK_LOAD -?\d+,1',lines[i-1].strip())):
                name=f[1].strip()
            if name and 1<sizes.get(name,0)<=256:paged[name]=sizes[name]
        return paged

    def fill_loops(self, text):
        """Replace canonical unsigned byte fills; keep live final indices."""
        text='\n'.join(line.split(';')[0].strip() for line in text.splitlines())
        text='\n'.join(line for line in text.splitlines() if line)
        allocations=self.allocations(text)
        pattern=re.compile(
            r'^ADDRSP (?P<index>\d+)\nPUSH\nIMM 0\nSTIND 2\n'
            r'(?P<test>\$\d+):\nADDRSP (?P=index)\nLOAD 2\nPUSH\n'
            r'IMM (?P<count>\d+)\nULT\nJTRUE (?P<body>\$\d+)\nJUMP (?P<exit>\$\d+)\n'
            r'(?P<increment>\$\d+):\nADDRSP (?P=index)\nPUSH\nLOAD 2\nOFFSET 1\n'
            r'STIND 2\nJUMP (?P=test)\n(?P=body):\n'
            r'IMM (?P<base>[^,\n]+)\nPUSH\nADDRSP (?P<adjusted>\d+)\nLOAD 2\nADD\n'
            r'PUSH\nIMM (?P<byte>-?\d+)\nSTIND 1\nJUMP (?P=increment)\n'
            r'(?=(?P=exit):(?:\n|$))',re.M)
        def lower(loop):
            base=re.fullmatch(r'([A-Za-z_$][\w$]*)(?:\+(\d+))?',loop['base'])
            if (not base or base[1] not in allocations or
                    int(base[2] or 0)+int(loop['count'])>allocations[base[1]]):
                return loop[0]
            if int(loop['count'])>65535 or int(loop['adjusted'])!=int(loop['index'])+2:
                return loop[0]
            for name in ('test','body','increment'):
                references=re.findall(r'(?<![\w$])'+re.escape(loop[name])+r'(?![\w$])',text)
                if len(references)!=2:
                    return loop[0]
            return 'FILL '+','.join(loop[name] for name in ('index','count','byte','base'))+'\n'
        return pattern.sub(lower,text)

    def loop_entries(self, text):
        """Bypass a proven-true first test; retain the original loop back edge."""
        lines = text.splitlines()
        labels = {line[:-1]:i for i,line in enumerate(lines) if line.endswith(':')}
        pattern = re.compile(
            r'^ADDRSP (?P<slot>\d+)\nPUSH\nIMM (?P<initial>-?\d+)\n'
            r'STIND (?P<store>1)\n(?P<test>[$\w]+):\n'
            r'ADDRSP (?P=slot)\nLOAD (?P<load>-1|1)\nPUSH\n'
            r'IMM (?P<bound>-?\d+)\n(?P<relation>U?(?:EQ|NE|LT|LE|GT|GE))\n'
            r'(?P<branch>JTRUE|JFALSE) (?P<body>[$\w]+)\nJUMP (?P<exit>[$\w]+)$', re.M)

        def lower(loop):
            width = int(loop['load'])
            if abs(width) != int(loop['store']):
                return loop[0]
            left = int(loop['initial']) & (255 if abs(width)==1 else 65535)
            if width == -1 and left >= 128:
                left |= 0xff00
            right = int(loop['bound']) & 65535
            relation = loop['relation']
            if not relation.startswith('U'):
                left = (left+32768)%65536-32768
                right = (right+32768)%65536-32768
            truth = {'EQ':left==right, 'NE':left!=right, 'LT':left<right,
                     'LE':left<=right, 'GT':left>right, 'GE':left>=right}[relation.lstrip('U')]
            if truth != (loop['branch']=='JTRUE'):
                return loop[0]
            # Skipping the comparison also discards its boolean AB result.
            # Accept only a body that immediately overwrites AB, even if other
            # predecessors enter the test or body labels.
            cursor = labels.get(loop['body'], len(lines)) + 1
            while cursor < len(lines) and lines[cursor].endswith(':'):
                cursor += 1
            if cursor >= len(lines) or lines[cursor].split()[0] not in ('IMM','ADDRSP'):
                return loop[0]
            initialization, test = loop[0].split(loop['test']+':', 1)
            return initialization+'JUMP '+loop['body']+'\n'+loop['test']+':'+test

        return pattern.sub(lower, text)

    def strided_loops(self, text):
        # fill_loops has already normalized whitespace and comments.
        allocations=self.allocations(text)
        pattern=re.compile(
            r'^(?P<test>\$\d+):\nADDRSP (?P<index>\d+)\nLOAD 2\nPUSH\n'
            r'IMM (?P<count>\d+)\nULT\nJTRUE (?P<body>\$\d+)\nJUMP (?P<exit>\$\d+)\n'
            r'(?P<increment>\$\d+):\nADDRSP (?P=index)\nPUSH\nLOAD 2\nPUSH\n'
            r'ADDRSP (?P<adjusted_stride>\d+)\nLOAD 2\nADD\nSTIND 2\nJUMP (?P=test)\n'
            r'(?P=body):\nIMM (?P<base>[^,\n]+)\nPUSH\nADDRSP (?P<adjusted>\d+)\n'
            r'LOAD 2\nADD\nPUSH\nIMM (?P<byte>-?\d+)\nSTIND 1\nJUMP (?P=increment)\n'
            r'(?=(?P=exit):(?:\n|$))',re.M)
        def lower(loop):
            index,stride=int(loop['index']),int(loop['adjusted_stride'])-4
            base=re.fullmatch(r'([A-Za-z_$][\w$]*)(?:\+(\d+))?',loop['base'])
            if (not base or base[1] not in allocations or
                    int(base[2] or 0)+int(loop['count'])>allocations[base[1]] or
                    int(loop['count'])>65535 or stride<0 or abs(index-stride)<2 or
                    int(loop['adjusted'])!=index+2):
                return loop[0]
            for name in ('test','body','increment'):
                if len(re.findall(r'(?<![\w$])'+re.escape(loop[name])+r'(?![\w$])',text))!=2:
                    return loop[0]
            return f'STRIDE {index},{stride},'+','.join(loop[n] for n in ('count','byte','base'))+'\n'
        return pattern.sub(lower,text)

    def dense_switches(self, text):
        """Specialize compact constant switch tables; retain sparse fallback."""
        lines = [x.split(';')[0].strip() for x in text.splitlines()]
        lines = [x for x in lines if x]
        tables = {}
        for index,line in enumerate(lines):
            if not line.endswith(':'):
                continue
            words, cursor = [], index+1
            while cursor < len(lines) and lines[cursor].startswith('DW '):
                words += [x.strip() for x in lines[cursor][3:].split(',')]
                cursor += 1
            if len(words)<8 or len(words)%2 or words[-1]!='0':
                continue
            pairs = list(zip(words[:-2:2],words[1:-2:2]))
            if not all(re.fullmatch(r'-?\d+',x) and y!='0' for x,y in pairs):
                continue
            cases = {((int(x)+32768)&65535)-32768:y for x,y in pairs}
            if len(cases)!=len(pairs):
                continue
            low,high = min(cases),max(cases)
            if high-low > 127 or high-low+1 > 2*len(cases):
                continue
            tables[line[:-1]] = (low,high,words[-2],cases)
        binary = {'ADD','SUB','MUL','DIVI','DIVU','MODI','MODU','BOR','BXOR',
                  'BAND','SHRI','SHRU','LSHIFT','EQ','NE','LT','LE','GT','GE',
                  'ULT','ULE','UGT','UGE'}
        pure = {'IMM','ADDRSP','LOAD','OFFSET','DOUBLE','HALF','SCALE',
                'NEGATE','COMPLEMENT','BOOL','NOT'}
        extra = []
        index = 0
        while index+2 < len(lines):
            first = lines[index].split()
            if (len(first)!=2 or first[0]!='IMM' or first[1] not in tables or
                    lines[index+1]!='PUSH' or
                    lines[index+2].split()[0] not in ('IMM','ADDRSP')):
                index += 1
                continue
            depth, cursor, adjusted = 0,index+2,[]
            fused = False
            while cursor < len(lines):
                fields = lines[cursor].split()
                op = fields[0]
                if op=='SWITCH' and not depth:
                    low,high,default,cases = tables[first[1]]
                    name = '$'+self.unique()
                    while name+':' in lines:
                        name = '$'+self.unique()
                    extra += ['DATA',name+':','DW '+','.join(
                        cases.get(x,default) for x in range(low,high+1))]
                    # LOAD 1 zero-extends AB. Restrict the shortcut to tables
                    # starting at zero: subtracting a nonzero low case could
                    # otherwise borrow into the high byte.
                    byte = low==0 and adjusted[-1:] == ['LOAD 1']
                    lines[index:cursor+1] = adjusted+[
                        'DENSE_SWITCH '+','.join((name,str(low),str(high),default))+
                        (',byte' if byte else '')]
                    fused = True
                    break
                if op=='PUSH':
                    depth += 1
                elif op in binary:
                    if not depth:
                        break
                    depth -= 1
                elif op not in pure:
                    break
                if op=='ADDRSP':
                    if int(fields[1]) < 2:
                        break
                    adjusted.append('ADDRSP '+str(int(fields[1])-2))
                else:
                    adjusted.append(lines[cursor])
                cursor += 1
            if not fused:
                index += 1
        return '\n'.join(lines+extra)

    def fold_expressions(self, text):
        """Remove saved local destinations and small constant left factors.

        Only straight-line expressions with balanced temporary stacks qualify.
        Direct calls may occur; assignments and control-flow joins stop folding.
        Removing a saved word requires adjusting every SP-relative operand in
        that expression, including operands below nested expression pushes.
        """
        lines = [x.split(';')[0].strip() for x in text.splitlines()]
        lines = [x for x in lines if x]
        binary = {'ADD','SUB','MUL','DIVI','DIVU','MODI','MODU','BOR','BXOR',
                  'BAND','SHRI','SHRU','LSHIFT','EQ','NE','LT','LE','GT','GE',
                  'ULT','ULE','UGT','UGE','RMISAVE','RMUSAVE'}
        pure = {'IMM','ADDRSP','LOAD','LOADQUOT','OFFSET','DOUBLE','HALF','SCALE',
                'NEGATE','COMPLEMENT','BOOL','NOT','CALL'}
        index = 0
        while index+2 < len(lines):
            first = lines[index].split()
            if (len(first)!=2 or first[0] not in ('ADDRSP','IMM') or
                    not re.fullmatch(r'-?\d+',first[1]) or lines[index+1]!='PUSH' or
                    lines[index+2].split()[0] not in ('IMM','ADDRSP','LOADQUOT','CALL')):
                index += 1
                continue
            local = first[0]=='ADDRSP'
            factor = int(first[1])
            if not local and factor not in (0,1,2,3,4,5,8,10,16,32,64,128,256,-1):
                index += 1
                continue
            depth, cursor, adjusted = 0, index+2, []
            fused = False
            while cursor < len(lines):
                fields = lines[cursor].split()
                op = fields[0]
                if (depth==0 and ((local and op=='STIND') or
                                 (not local and op=='MUL'))):
                    replacement = ('STACK_STORE '+first[1]+','+fields[1] if local
                                   else 'ARITH_CONST MUL,'+first[1])
                    lines[index:cursor+1] = adjusted+[replacement]
                    fused = True
                    break
                if op=='PUSH':
                    depth += 1
                elif op=='ADJSP':
                    amount = int(fields[1])
                    if amount < 0 or amount % 2 or amount//2 > depth:
                        break
                    depth -= amount//2
                elif op in binary:
                    if not depth:
                        break
                    depth -= 1
                elif op not in pure:
                    break
                if op=='ADDRSP':
                    offset = int(fields[1])
                    if offset < 2:
                        break
                    adjusted.append('ADDRSP '+str(offset-2))
                else:
                    adjusted.append(lines[cursor])
                cursor += 1
            if not fused:
                index += 1
        return '\n'.join(lines)

    def multiply_constant(self, value):
        if value == 0:
            self.immediate('0')
        elif value == -1:
            self.emit('CAL NEG')
        elif value != 1:
            bits = bin(value)[3:]
            if '1' in bits:
                self.emit('LCA','LDB')
            for bit in bits:
                self.emit('ADA','LEA','LAB','RAL','LBA','LAE')
                if bit == '1':
                    self.emit('ADC','LEA','LAB','ACD','LBA','LAE')

    def reuse_quotients(self, text):
        """Reuse MOD's quotient for matching local loads in one basic block.

        Track the original PUSH depth so SP-relative operands have stable
        identities. Disable this pass for the entire unit if a local address
        escapes or the abstract stack cannot be followed conservatively.
        """
        lines = [x.split(';')[0].strip() for x in text.splitlines()]
        lines = [x for x in lines if x]
        output = list(lines)
        stack, value, depth, candidate = [], None, 0, None
        binary = {'ADD','SUB','MUL','DIVI','DIVU','MODI','MODU','BOR','BXOR',
                  'BAND','SHRI','SHRU','LSHIFT','EQ','NE','LT','LE','GT','GE',
                  'ULT','ULE','UGT','UGE'}
        def address(v):
            return v is not None and v[0] == 'address'
        for index,line in enumerate(lines):
            fields = line.split(None,1)
            op,arg = fields[0],fields[1] if len(fields)>1 else ''
            if re.match(r'^[^:]+:\s*(DB|DW|DS)\b',line):
                continue
            if line.endswith(':') or op in ('TEXT','DATA'):
                if stack or address(value):
                    return text
                stack, value, candidate = [], None, None
                if line.endswith(':') and not line.startswith('$'):
                    depth = 0
            elif op == 'ADDRSP':
                value = ('address',depth+int(arg))
            elif op == 'IMM':
                value = ('constant',int(arg)&65535) if re.fullmatch(r'-?\d+',arg) else None
            elif op == 'LOAD':
                value = ('local',value[1]) if address(value) and arg=='2' else None
            elif op == 'PUSH':
                stack.append(value)
                depth -= 2
            elif op == 'ADJSP':
                amount = int(arg)
                if any(address(v) for v in stack) or address(value):
                    return text
                if amount > 0:
                    del stack[max(0,len(stack)-amount//2):]
                else:
                    stack = []
                depth += amount
                candidate = None
            elif op in binary:
                if not stack:
                    return text
                left = stack.pop()
                depth += 2
                if address(left) or address(value):
                    # Pointer arithmetic on a local could expose an alias.
                    return text
                if op in ('DIVI','DIVU','MODI','MODU'):
                    key = (left,value,op.endswith('I'))
                    pattern = [x.split() for x in lines[max(0,index-5):index]]
                    simple = (len(pattern)==5 and pattern[0][0]=='ADDRSP' and
                              pattern[1]==['LOAD','2'] and pattern[2]==['PUSH'] and
                              pattern[3][0]=='ADDRSP' and pattern[4]==['LOAD','2'])
                    valid = simple and left and value and left[0]=='local' and value[0]=='local'
                    if valid and op.startswith('DIV') and candidate and candidate[0]==key:
                        output[candidate[1]] = 'RMISAVE' if key[2] else 'RMUSAVE'
                        output[index-5:index+1] = ['']*5+['LOADQUOT']
                        candidate = None
                    elif valid and op.startswith('MOD'):
                        candidate = (key,index)
                    else:
                        candidate = None
                value = None
            elif op == 'STIND':
                if not stack or address(value):
                    return text
                target = stack.pop()
                depth += 2
                if candidate and address(target):
                    lo,hi = target[1],target[1]+abs(int(arg))
                    if any(lo < v[1]+2 and v[1] < hi for v in candidate[0][:2]):
                        candidate = None
                # Unknown pointers cannot reach unescaped frame locals.
            elif op == 'STORE':
                if address(value):
                    return text
            elif op in ('JTRUE','JFALSE','JUMP','SWITCH','CALL','CALLIND','RETURN'):
                if any(address(v) for v in stack) or address(value):
                    return text
                candidate = None
                value = None
            elif op in ('OFFSET','DOUBLE','HALF','SCALE','NEGATE','COMPLEMENT','BOOL','NOT'):
                if address(value):
                    return text
                value = None
            elif op not in ('GLOBAL','EXTERN','DB','DW','DS','SECOND'):
                return text
        return '\n'.join(output)

    def render(self, text):
        function_names={'main'} | set(re.findall(r'(?m)^\s*;\s*FUNCTION\s+(\w+)',text))
        function_names.update(re.findall(r'(?m)^\s*CALL\s+(\w+)',text))
        if self.optimize:
            text = self.strided_loops(self.fill_loops(self.reuse_quotients(text)))
            text = self.loop_entries(text)
            text = self.optimized_ir(thread_booleans(self.fold_expressions(self.dense_switches(text))))
            # Also catches loads exposed by indexed-address folding.
            text = re.sub(r'(?m)^ADDRSP (-?\d+)\nLOAD (-?\d+)$',
                          r'STACK_LOAD \1,\2', text)
            text=self.saved_addresses(byte_comparisons(local_stores(text)))
            if not self.compact:
                text=self.stored_arguments(text)
        depths=stack_depths(text,function_names) if self.optimize else {}
        # Startup reaches main through one pushed return word; nothing else
        # may call it or take its address.
        self.static_main = (self.optimize and bool(depths) and
                            len(re.findall(r'(?m)\bmain\b', text)) ==
                            len(re.findall(r'(?m)^main:|^\s*;\s*FUNCTION\s+main\b', text)))
        self.paged = self.paged_arrays(text) if self.optimize else {}
        previous = ''
        for line_number,raw in enumerate(text.splitlines()):
            self.frame_depth=depths.get(line_number)
            if raw.split(';')[0].strip():
                previous, current = raw.split(';')[0].strip(), previous
            else:
                current = previous
            line = raw.split(';')[0].strip()
            if not line:
                continue
            if ':' in line:
                name, line = line.split(':', 1)
                name = name.strip()
                if name in self.defined:
                    raise CodegenError('duplicate symbol: ' + name)
                self.defined.add(name)
                if name in self.paged and self.output is self.data:
                    # Keep the array within one page: pad to the next page
                    # only when it would otherwise cross.
                    size = self.paged[name]
                    self.emit(f'DS (((LOW ($))+{size-1}D) SHR 8D)*(256D-(LOW ($)))')
                if name in function_names and self.output is self.code:
                    self.function = name
                    self.emit('; function '+self.symbol(name))
                self.label(self.symbol(name))
                line = line.strip()
                if not line:
                    continue
            parts = line.split(None, 1)
            op, arg = parts[0], parts[1] if len(parts) == 2 else ''
            if op in ('TEXT', 'DATA'):
                self.output = self.code if op == 'TEXT' else self.data
            elif op == 'ADD_CONST':
                if arg in self.paged and re.fullmatch(r'STACK_LOAD -?\d+,1', current):
                    # Unsigned byte index into a single-page array.
                    base = self.value(arg)
                    self.emit('ADI LOW ('+base+')','LBI HIGH ('+base+')')
                else:
                    self.add_constant(arg)
            elif op == 'ARITH_CONST':
                operation, value = arg.split(',')
                value = int(value)
                if operation in ('ADD','SUB'):
                    self.add_constant(str(value if operation == 'ADD' else -value))
                elif operation == 'MUL':
                    self.multiply_constant(value)
                elif operation == 'LSHIFT':
                    count = value
                    for _ in range(count):
                        self.emit('ADA','LEA','LAB','RAL','LBA','LAE')
                else:
                    mnemonic = {'BAND':'NDI','BOR':'ORI','BXOR':'XRI'}[operation]
                    self.emit(mnemonic+' %dD' % (value & 255),'LEA','LAB',
                              mnemonic+' %dD' % ((value >> 8) & 255),'LBA','LAE')
            elif op == 'BYTE_CMP':
                relation,jump,target,constant,keep,left,right=arg.split(',')
                right_kind,right_value=right.split('~',1)
                direct = right_kind in ('i','g')
                for number,operand in enumerate((left,) if direct else (right,left)):
                    kind,value=operand.split('~',1)
                    if kind=='i': self.emit('LAI '+value+'D')
                    elif kind=='g':
                        address=self.value(value)
                        self.emit('LHI HIGH ('+address+')','LLI LOW ('+address+')','LAM')
                    else:
                        slot=int(value)-(self.frame_depth if self.frame_depth is not None else -65536)
                        self.emit('; local byte load '+str(slot))
                        self.stack_address(int(value));self.emit('LAM','; end local byte')
                    if number==0 and not direct:self.emit('LDA')
                condition=relation.lstrip('U').lower()
                if jump=='JFALSE' and keep=='0':
                    condition={'eq':'ne','ne':'eq','lt':'ge','le':'gt','gt':'le','ge':'lt'}[condition]
                yes=self.unique() if keep=='1' else self.value(target)
                if right_kind=='i':
                    self.emit('CPI '+right_value+'D')
                elif right_kind=='g':
                    address=self.value(right_value)
                    self.emit('LHI HIGH ('+address+')','LLI LOW ('+address+')','CPM')
                else:
                    self.emit('CPD')
                if condition in ('eq','ne','lt','ge'):
                    self.emit({'eq':'JTZ','ne':'JFZ','lt':'JTC','ge':'JFC'}[condition]+' '+yes)
                elif condition=='le': self.emit('JTC '+yes,'JTZ '+yes)
                else:
                    done=self.unique();self.emit('JTC '+done,'JFZ '+yes);self.label(done)
                if keep=='1':
                    done=self.unique();self.immediate('0')
                    self.emit('JMP '+(self.value(target) if jump=='JFALSE' else done))
                    self.label(yes);self.immediate('1')
                    if jump=='JTRUE':self.emit('JMP '+self.value(target))
                    self.label(done)
            elif op in ('COMPARE','CMPBRANCH'):
                fields = arg.split(',')
                relation = fields[0]
                value = fields[3] if op == 'CMPBRANCH' else fields[1]
                constant = None if value == '-' else int(value)
                if op == 'COMPARE':
                    self.compare_boolean(relation, constant)
                else:
                    _, jump, target, _, keep = fields
                    target = self.value(target)
                    if keep == '1':
                        self.compare_boolean(relation,constant,jump,target)
                    else:
                        if jump == 'JFALSE':
                            prefix = 'U' if relation.startswith('U') else ''
                            relation = prefix+{'EQ':'NE','NE':'EQ','LT':'GE','LE':'GT',
                                               'GT':'LE','GE':'LT'}[relation.lstrip('U')]
                        self.compare_branch(relation,target,constant)
            elif op == 'STRIDE':
                offset,stride,count,byte,base = arg.split(',')
                count = int(count)
                self.stack_address(int(stride))
                self.emit('LCM')
                self.inc_hl()
                self.emit('LBM')
                self.stack_address(int(offset))
                self.emit('LEM')
                self.inc_hl()
                self.emit('LDM')
                loop,body,done = self.unique(),self.unique(),self.unique()
                base = self.value(base)
                if count:
                    pointer,mark,finish = self.unique(),self.unique(),self.unique()
                    # Use an absolute pointer when the stride cannot wrap it.
                    # Reject the boundary high byte conservatively, keeping
                    # the index-based loop for large/wrapping strides.
                    self.emit('LAB',f'CPI HIGH (65535D-(({base})+{count-1}D))',
                              'JFC '+loop,
                              'LAD',f'CPI {count>>8}D','JTC '+pointer,'JFZ '+done,
                              'LAE',f'CPI {count&255}D','JFC '+done)
                    self.label(pointer)
                    self.emit('LAE','ADI LOW ('+base+')','LLA','LAD',
                              'ACI HIGH ('+base+')','LHA','JMP '+mark)
                    # Test at the bottom: each store needs no loop-back JMP.
                    self.label(mark+'BODY')
                    self.emit(f'LMI {int(byte)&255}D','LAL','ADC','LLA',
                              'LAH','ACB','LHA')
                    self.label(mark)
                    self.emit('LAH',f'CPI HIGH (({base})+{count}D)',
                              'JTC '+mark+'BODY','JFZ '+finish,
                              'LAL',f'CPI LOW (({base})+{count}D)','JTC '+mark+'BODY')
                    self.label(finish)
                    self.emit('LAL','SUI LOW ('+base+')','LEA','LAH',
                              'SBI HIGH ('+base+')','LDA','JMP '+done)
                self.label(loop)
                self.emit('LAD',f'CPI {count>>8}D','JTC '+body,'JFZ '+done,
                          'LAE',f'CPI {count&255}D','JFC '+done)
                self.label(body)
                self.emit('LAE','ADI LOW ('+base+')','LLA','LAD',
                          'ACI HIGH ('+base+')','LHA',f'LMI {int(byte)&255}D',
                          'LAE','ADC','LEA','LAD','ACB','LDA','JMP '+loop)
                self.label(done)
                self.emit('LBD','LCE')
                self.stack_address(int(offset))
                self.emit('LAC','LMA')
                self.inc_hl()
                self.emit('LMB')
                self.immediate('0')
            elif op == 'FILL':
                offset,count,byte,base = arg.split(',')
                count,byte = int(count),int(byte)&255
                if count:
                    loop,advance = self.unique(),self.unique()
                    base = self.value(base)
                    self.emit('LHI HIGH ('+base+')','LLI LOW ('+base+')',
                              f'LBI {((count+255)//256)&255}D',f'LCI {count&255}D')
                    self.label(loop)
                    self.emit(f'LMI {byte}D','INL','JFZ '+advance,'INH')
                    self.label(advance)
                    self.emit('DCC','JFZ '+loop,'DCB','JFZ '+loop)
                self.immediate(str(count)+'D')
                self.emit('LCA')
                self.stack_address(int(offset))
                self.emit('LAC','LMA')
                self.inc_hl()
                self.emit('LMB')
                self.immediate('0')
            elif op == 'LOCAL_ADD':
                destination,source = map(int,arg.split(','))
                self.stack_address(source)
                self.emit('LCM')
                self.inc_hl()
                self.emit('LDM')
                self.stack_address(destination)
                self.emit('LAM','ADC','LMA','LEA')
                self.inc_hl()
                self.emit('LAM','ACD','LMA','LBA','LAE')
            elif op == 'ADD_LOCAL':
                # Retain the left value in CD while reading the right local;
                # no temporary RAM-stack word or PUSH/POP helper is needed.
                self.emit('LCA','LDB')
                self.stack_address(int(arg))
                self.emit('LAM','ADC','LEA')
                self.inc_hl()
                self.emit('LAM','ACD','LBA','LAE')
            elif op in ('LOCAL_BYTE_UPDATE','LOCAL_BYTE_STEP'):
                offset,value=map(int,arg.split(','));value&=65535
                slot=offset-(self.frame_depth if self.frame_depth is not None else -65536)
                self.emit('; local byte update '+str(slot))
                self.stack_address(offset)
                if op=='LOCAL_BYTE_STEP':
                    self.emit('LAM',f'ADI {value&255}D','LMA','; end local byte')
                    continue
                # Retain the full promoted result in AB, including byte wrap.
                self.emit('LAM',f'ADI {value&255}D','LMA','LEA','LAI 0D',
                          f'ACI {value>>8}D','LBA','LAE','; end local byte')
            elif op == 'GLOBAL_STEP':
                name,value = arg.split(',')
                address = self.value(name)
                self.emit('LHI HIGH ('+address+')','LLI LOW ('+address+')')
                done = self.unique()
                self.emit('LAM',('ADI' if value=='1' else 'SUI')+' 1D','LMA','JFC '+done)
                self.inc_hl()
                self.emit('LAM',('ACI' if value=='1' else 'SBI')+' 0D','LMA')
                self.label(done)
            elif op == 'LOCAL_STEP':
                offset,value = map(int,arg.split(','))
                slot=offset-(self.frame_depth if self.frame_depth is not None else -65536)
                self.emit('; local word store '+str(slot))
                self.stack_address(offset)
                done = self.unique()
                self.emit('LAM',('ADI' if value==1 else 'SUI')+' 1D','LMA','JFC '+done)
                self.inc_hl()
                self.emit('LAM',('ACI' if value==1 else 'SBI')+' 0D','LMA')
                self.label(done)
            elif op in ('LOCAL_UPDATE','LOCAL_CONST'):
                fields = arg.split(',')
                slot=int(fields[0])-(self.frame_depth if self.frame_depth is not None else -65536)
                if op=='LOCAL_UPDATE' or fields[2]!='1':
                    self.emit('; local word store '+str(slot))
                self.stack_address(int(fields[0]))
                if op == 'LOCAL_UPDATE':
                    value = int(fields[1]) & 65535
                    self.emit('LAM',f'ADI {value & 255}D','LMA','LEA')
                    self.inc_hl()
                    self.emit('LAM',f'ACI {value >> 8}D','LMA','LBA','LAE')
                else:
                    self.immediate(self.value(fields[1]))
                    if fields[2]=='1':self.emit('; local byte store '+str(slot))
                    self.emit('LMA')
                    if fields[2]=='1':self.emit('; end local byte')
                    if fields[2] == '2':
                        self.inc_hl()
                        self.emit('LMB')
            elif op == 'SAVE_ADDRESS':
                self.emit('LHI HIGH SADDR','LLI LOW SADDR','LMA','INL','LMB')
            elif op == 'STIND_SAVED':
                # Like STIND, leave the stored value in AB.
                self.emit('LCA','LHI HIGH SADDR','LLI LOW SADDR','LEM','INL',
                          'LHM','LLE','LAC','LMA')
                if int(arg) == 2:
                    self.inc_hl()
                    self.emit('LMB')
            elif op == 'CONST_STORE1':
                self.emit('LHB','LLA','LMI '+str(int(arg)&255)+'D')
                self.immediate(self.value(arg))
            elif op == 'STACK_STORE':
                offset,width = map(int,arg.split(','))
                slot=offset-(self.frame_depth if self.frame_depth is not None else -65536)
                self.emit('; local '+('byte' if width==1 else 'word')+' store '+str(slot))
                self.emit('LCA')
                self.stack_address(offset)
                self.emit('LAC','LMA')
                if abs(width)==2:
                    self.inc_hl()
                    self.emit('LMB')
                if width==1:self.emit('; end local byte')
            elif op == 'STACK_LOAD':
                offset,width = map(int,arg.split(','))
                slot=offset-(self.frame_depth if self.frame_depth is not None else -65536)
                self.emit('; local '+('byte' if width==1 else 'word')+' load '+str(slot))
                self.stack_address(offset)
                self.load(width,address=False)
                if width==1:self.emit('; end local byte')
            elif op == 'INDEX_LOAD':
                fields = arg.split(',')
                offset,base,width = fields[:3]
                base = self.value(base)
                byte = fields[3:] == ['byte']
                if byte:
                    slot=int(offset)-(self.frame_depth if self.frame_depth is not None else -65536)
                    self.emit('; local byte load '+str(slot))
                self.stack_address(int(offset))
                self.emit('LAM')
                if byte:
                    self.emit('; end local byte')
                if byte and fields[1] in self.paged:
                    self.emit('ADI LOW ('+base+')','LLA','LHI HIGH ('+base+')')
                    self.load(int(width),address=False)
                    continue
                self.emit('ADI LOW ('+base+')','LEA')
                if byte:
                    self.emit('LAI HIGH ('+base+')','ACI 0D','LHA','LLE')
                else:
                    self.inc_hl()
                    self.emit('LAM','ACI HIGH ('+base+')','LHA','LLE')
                self.load(int(width),address=False)
            elif op == 'LOADQUOT':
                self.emit('LHI HIGH DQUOT','LLI LOW DQUOT','LAM','INL','LBM')
            elif op in ('RMISAVE','RMUSAVE'):
                self.binary(op)
            elif op == 'ADDLOAD':
                self.emit('LCA','LDB','CAL POP','ADC','LEA','LAB','ACD','LHA','LLE')
                self.load(int(arg),address=False)
            elif op == 'DIRECT_LOAD':
                name, width = arg.split(',')
                address = self.value(name)
                self.emit('LHI HIGH ('+address+')','LLI LOW ('+address+')')
                self.load(int(width),address=False)
            elif op == 'IMM':
                self.immediate(self.value(arg))
            elif op == 'SECOND':
                v = self.value(arg)
                self.emit('LCI LOW (' + v + ')', 'LDI HIGH (' + v + ')')
            elif op in ('DB', 'DW'):
                self.emit(op + ' ' + ','.join(self.value(v) for v in arg.split(',')))
            elif op == 'DS':
                self.emit('DS ' + self.value(arg))
            elif op == 'PUSH':
                self.emit('CAL PUSH')
            elif op == 'POPSECOND':
                self.emit('LCA', 'LDB', 'CAL POP', 'CAL SWAP')
            elif op == 'SWAP':
                self.emit('CAL SWAP')
            elif op == 'SWAPSTACK':
                self.emit('LCA', 'LDB', 'CAL POP', 'CAL SWAP', 'CAL PUSH', 'LAC', 'LBD')
            elif op == 'ADDRSP':
                self.emit('; escaped frame')
                if self.optimize:
                    self.stack_address(int(arg))
                    self.emit('LAL','LBH')
                else:
                    self.immediate(self.value(arg))
                    self.emit('CAL SPADDR')
            elif op == 'ADJSP':
                if self.optimize:
                    value = int(arg) & 65535
                    if value:
                        self.emit('LCA','LHI HIGH RSP','LLI LOW RSP','LAM',
                                  f'ADI {value & 255}D','LMA','INL','LAM',
                                  f'ACI {value >> 8}D','LMA','CPI HIGH STACKMIN',
                                  'JTC STACKFAULT','LAC')
                else:
                    self.emit('LCA', 'LDB')
                    self.immediate(self.value(arg))
                    self.emit('CAL ADDSP', 'LAC', 'LBD')
            elif op == 'LOAD':
                self.load(int(arg))
            elif op in ('STORE', 'STIND'):
                if op == 'STORE':
                    name, width = arg.split(',')
                    dest = self.value(name)
                    self.emit('LHI HIGH ' + dest, 'LLI LOW ' + dest)
                else:
                    width = arg
                    self.emit('LCA', 'LDB', 'CAL POP', 'LHB', 'LLA', 'LAC', 'LBD')
                self.emit('LMA')
                if int(width) == 2:
                    self.inc_hl()
                    self.emit('LMB')
            elif op in ('ADD','SUB','MUL','DIVI','DIVU','MODI','MODU','BOR','BXOR','BAND','SHRI','SHRU','LSHIFT'):
                self.binary(op)
            elif op in ('EQ','NE','LT','LE','GT','GE','ULT','ULE','UGT','UGE'):
                self.binary('CMU' if op.startswith('U') else 'CMI')
                self.boolean(op.lstrip('U').lower())
            elif op == 'NEGATE':
                self.emit('CAL NEG')
            elif op == 'COMPLEMENT':
                self.emit('LEA', 'LAB', 'XRI 0FFH', 'LBA', 'LAE', 'XRI 0FFH')
            elif op in ('BOOL','NOT'):
                self.boolean('ne' if op == 'BOOL' else 'eq')
            elif op in ('OFFSET','DOUBLE','HALF','SCALE'):
                if op == 'DOUBLE':
                    self.emit('ADA', 'LEA', 'LAB', 'RAL', 'LBA', 'LAE')
                elif op == 'OFFSET':
                    # Offset is a compile-time integer; no RAM-stack operand.
                    value = int(arg) & 65535
                    self.emit(f'ADI {value & 255}D', 'LEA', 'LAB',
                              f'ACI {value >> 8}D', 'LBA', 'LAE')
                else:
                    self.emit('CAL PUSH')
                    self.immediate(self.value(arg if op == 'SCALE' else '1'))
                    self.binary('MUL' if op == 'SCALE' else 'SHRI')
            elif op == 'SCALESECOND':
                self.emit('LCA', 'LDB', 'CAL POP', 'ADA', 'LEA', 'LAB', 'RAL',
                          'LBA', 'LAE', 'CAL PUSH', 'LAC', 'LBD')
            elif op == 'CALL_STORED':
                # Arguments are already in place; store the return word at
                # SP+0 as PUSH would have, then enter the function.
                resume = self.unique()
                self.immediate(resume)
                self.emit('LCA')
                self.stack_address(0)
                self.emit('LAC','LMA')
                self.inc_hl()
                self.emit('LMB')
                self.references.add(arg)
                self.emit('JMP ' + self.symbol(arg))
                self.label(resume)
            elif op in ('CALL','CALLIND'):
                resume = self.unique()
                if op == 'CALLIND':
                    self.emit('CAL POP', 'LCA', 'LDB')
                self.immediate(resume)
                self.emit('CAL PUSH')
                if op == 'CALLIND':
                    self.emit('LAC', 'LBD', 'JMP JUMPAB')
                else:
                    self.references.add(arg)
                    self.emit('JMP ' + self.symbol(arg))
                self.label(resume)
            elif op == 'RETURN':
                self.emit('JMP SCRETURN')
            elif op == 'JUMP':
                self.emit('JMP ' + self.value(arg))
            elif op in ('JTRUE','JFALSE'):
                if self.output[-1].strip() == 'LBI 0':
                    # A zero-extended byte: test A alone, and leave LBI 0
                    # for dead-load removal when B is unused.
                    self.output[-1] = '        NDA'
                    self.emit('LBI 0')
                else:
                    self.emit('ORB')
                self.emit(('JFZ ' if op == 'JTRUE' else 'JTZ ') + self.value(arg))
            elif op == 'DENSE_SWITCH':
                fields = arg.split(',')
                name,low,high,default = fields[:4]
                byte = fields[4:] == ['byte']
                table,target = self.value(name),self.value(default)
                if int(low):
                    self.add_constant(str(-int(low)))
                if not byte:
                    self.emit('LEA','LAB','NDA','JFZ '+target,'LAE')
                self.emit(f'CPI {int(high)-int(low)+1}D','JFC '+target,
                          'ADA','ADI LOW ('+table+')','LLA',
                          'LAI HIGH ('+table+')','ACI 0','LHA','LAM')
                self.inc_hl()
                self.emit('LBM','JMP JUMPAB')
            elif op == 'SWITCH':
                # Table is [value,target]...,default,0; target addresses are nonzero.
                self.emit('JMP SCSWITCH')
            else:
                raise CodegenError('unsupported backend operation: ' + line)
        builtins = {'putchar','getchar','puts','kbhit','waitkey'}
        missing = (self.references | {'main'}) - self.defined - builtins
        if missing:
            raise CodegenError('unresolved symbols: ' + ', '.join(sorted(missing)))
        runtime = (HERE / 'runtime.asm').read_text()
        application = '\n'.join((optimize_functions(self.code,self.data,defer=True,anchor=not self.compact) if self.optimize else self.code) + self.data)
        if self.optimize:
            application, frame_helpers = outline_frame_loads(application, 'RSP')
            runtime += '\n' + frame_helpers
        runtime = prune_runtime(runtime, application)
        return (runtime + '\n' + application +
                '\nSCEND: DB 0\nSTACKMIN EQU (SCEND+255D) AND 0FF00H\n        END\n')


def generate(text, *, optimize=True, compact=False):
    return Generator(optimize=optimize, compact=compact).render(text)
