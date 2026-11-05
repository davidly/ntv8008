"""Small, freestanding ACK EM22 -> native 8008/A08 code generator.

No EM or C is interpreted by the host at application run time. Unsupported EM
operations fail compilation. The C call stack lives in RAM, not the 8008's
seven saved hardware return addresses.
"""
from pathlib import Path
import re
import sys
if str(Path(__file__).resolve().parents[1]/'tools') not in sys.path:
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native8008 import optimize_functions
from runtime_prune import prune_runtime
from outline8008 import share_return_values, outline_frame_loads
from ack_bytes import lower_bytes, dense_switches
from division import reuse_quotients
from memory import constant_byte_stores, local_updates, fill_loops, strided_loops, global_strided_loops


class CodegenError(ValueError):
    pass


# Startup pushes STOP and jumps to F_MAIN, whose ENTER pushes the old FP.
MAIN_FP = 0x3F00 - 4


def multiply_constant(value):
    """Return an inline multiply for short shift/add sequences, else None."""
    value &= 65535
    if value in (0, 65535):
        return '@MUL_CONST ' + str(value)
    if value & (value-1) == 0 and value <= 8:
        return '@DOUBLE ' + str(value.bit_length()-1)
    if value.bit_length()-1 + bin(value).count('1')-1 <= 8:
        return '@MUL_CONST ' + str(value)
    return None


def split_args(text):
    return re.findall(r"'(?:\\.|[^'\\])*'|[^,]+", text)


def em_string(text):
    # EM uses octal escapes, unlike Python's interpretation of some literals.
    raw = text[1:-1]
    result = bytearray()
    i = 0
    while i < len(raw):
        if raw[i] == '\\':
            i += 1
            match = re.match(r'[0-7]{1,3}', raw[i:])
            if match:
                result.append(int(match[0], 8))
                i += len(match[0])
                continue
        result.append(ord(raw[i]))
        i += 1
    return result


class Generator:
    def __init__(self, pascal=False, optimize=True):
        self.pascal = pascal
        self.optimize = optimize
        self.code = []
        self.data = []
        self.function = ''
        self.serial = 0
        self.unit = 0
        self.definitions = set()
        self.references = set()
        self.exports = set()
        self.locals = set()
        self.data_definitions = set()
        # A main reached only from startup has the constant frame MAIN_FP.
        self.static_main = False

    def emit(self, *lines):
        self.code += ['        ' + line for line in lines]

    def label(self, name):
        self.code.append(name + ':')

    def unique(self):
        self.serial += 1
        return 'ACKL%d' % self.serial

    def symbol(self, text):
        text = text.strip()
        if text.startswith('$'):
            name = text[1:]
            if self.pascal and name in ('_m_a_i_n', '_hlt'):
                return 'F_MAIN' if name == '_m_a_i_n' else 'F_PCHALT'
            return {'main': 'F_MAIN', 'putchar': 'F_PUTCHAR',
                    'getchar': 'F_GETCHAR', 'puts': 'F_PUTS'}.get(
                        name, 'F_' + ('' if text not in self.locals else 'U%d_' % self.unit) +
                        name.encode('ascii').hex().upper())
        if text.startswith('*'):
            return self.function + '_L' + text[1:]
        if text.startswith('.'):
            return 'U%d_D%s' % (self.unit, text[1:])
        return ('G_' + ('' if text not in self.locals else 'U%d_' % self.unit) +
                text.encode('ascii').hex().upper())

    def address(self, text):
        match = re.fullmatch(r'([.*$A-Za-z_][\w.$]*)([+-]\d+)?', text)
        if not match:
            raise CodegenError('unsupported address: ' + text)
        return self.symbol(match[1]) + ((match[2] + 'D') if match[2] else '')

    def immediate(self, value):
        if isinstance(value, int):
            self.emit(f'LAI {value & 255}D', f'LBI {(value >> 8) & 255}D')
        else:
            self.emit('LAI LOW (' + value + ')', 'LBI HIGH (' + value + ')')

    def constant(self, value):
        self.immediate(value)
        self.emit('CAL PUSH')

    def static_frame(self, function, offset):
        """Return HL loads for a constant main frame address, else None."""
        if not self.static_main or function != 'F_MAIN':
            return None
        address = (MAIN_FP + offset + (4 if offset >= 0 else 0)) & 65535
        return [f'LHI {address >> 8}D', f'LLI {address & 255}D']

    def local(self, offset):
        static = self.static_frame(self.function, offset)
        if static:
            self.emit(*static)
            return
        self.immediate(offset + (4 if offset >= 0 else 0))
        self.emit('CAL LOCAL')

    def frame_address(self, offset):
        # HL = FP + displacement. CD survive for native local updates.
        static = self.static_frame(self.function, offset)
        if static:
            self.emit(*static)
            return
        offset = (offset+(4 if offset>=0 else 0)) & 65535
        self.emit('LHI HIGH FP','LLI LOW FP','LAM',f'ADI {offset & 255}D',
                  'LEA','INL','LAM',f'ACI {offset >> 8}D','LHA','LLE')

    def branch(self, condition, target):
        # AB is already popped. Sign is taken from B, never from the low byte.
        if condition in ('eq', 'ne'):
            self.emit('ORB', ('JTZ ' if condition == 'eq' else 'JFZ ') + target)
        elif condition in ('lt', 'ge'):
            self.emit('LAB', 'NDI 80H', ('JFZ ' if condition == 'lt' else 'JTZ ') + target)
        elif condition in ('gt', 'le'):
            skip = self.unique()
            self.emit('ORB', 'JTZ ' + (skip if condition == 'gt' else target),
                      'LAB', 'NDI 80H', ('JTZ ' if condition == 'gt' else 'JFZ ') + target)
            self.label(skip)
        else:
            raise CodegenError('unsupported branch: ' + condition)

    def compare_branch(self, condition, target, signed, constant=None):
        """Consume operands and branch directly, without a comparison result."""
        self.emit('CAL POP')
        if constant is None:
            self.emit('LCA', 'LDB', 'CAL POP')
        elif constant & 65535 == 0:
            if signed or condition in ('eq','ne'):
                self.branch(condition, target)
            elif condition in ('gt','le'):
                self.branch('ne' if condition == 'gt' else 'eq', target)
            elif condition == 'ge':
                self.emit('JMP ' + target)
            return
        done = self.unique()
        self.emit('LEA', 'LAB')
        if signed and condition not in ('eq', 'ne'):
            # Bias only the high bytes to compare signed words as unsigned.
            # E retains the left low byte for the equal-high-byte case.
            if constant is None:
                self.emit('XRI 80H', 'LBA', 'LAD', 'XRI 80H', 'LDA', 'LAB')
            else:
                self.emit('XRI 80H')
        high = ('CPD' if constant is None else
                'CPI %dD' % (((constant >> 8) & 255) ^
                            (128 if signed and condition not in ('eq','ne') else 0)))
        self.emit(high)
        if condition not in ('eq','ne'):
            self.emit('JTC ' + (target if condition in ('lt','le') else done))
        self.emit('JFZ ' + (target if condition in ('gt','ge','ne') else done),
                  'LAE', 'CPC' if constant is None else 'CPI %dD' % (constant & 255))
        if condition == 'eq':
            self.emit('JTZ ' + target)
        elif condition == 'ne':
            self.emit('JFZ ' + target)
        elif condition == 'lt':
            self.emit('JTC ' + target)
        elif condition == 'ge':
            self.emit('JFC ' + target)
        elif condition == 'le':
            self.emit('JTC ' + target, 'JTZ ' + target)
        elif condition == 'gt':
            self.emit('JTC ' + done, 'JFZ ' + target)
        else:
            raise CodegenError('unsupported comparison: ' + condition)
        self.label(done)

    def indexed_access(self, lines, index, base):
        """Fuse a constant base, scalar index, scaling, and memory access.

        Match only straight-line, side-effect-free index expressions. Labels,
        calls, and other expressions retain the ordinary stack lowering.
        """
        if index >= len(lines):
            return None
        load = lines[index].strip().split()
        if len(load) != 2 or load[0] not in ('lol','llb','loe','loc'):
            return None
        cursor = index+1
        actions = []
        while cursor < len(lines):
            current = lines[cursor].strip().split()
            following = lines[cursor+1].strip().split() if cursor+1 < len(lines) else []
            if current == ['ads','2']:
                constant = len(following)==2 and following[0]=='stc'
                if not constant and following not in (['loi','1'],['loi','2'],['sti','1'],['sti','2']):
                    return None
                if load[0] in ('lol','llb'):
                    if self.optimize:
                        self.emit('@LOCAL_'+('LOAD1 ' if load[0]=='llb' else 'LOAD2 ')+load[1])
                    else:
                        self.local(int(load[1]))
                        self.emit('LAM', 'INL', 'LBM', 'CAL PUSH')
                elif load[0] == 'loe':
                    self.emit('@GLOBAL_LOAD2 ' + self.address(load[1]))
                else:
                    self.constant(int(load[1]))
                self.emit(*actions)
                if constant:
                    self.emit('@INDEX_CONST1 '+self.address(base)+','+following[1])
                else:
                    operation = 'LOAD' if following[0] == 'loi' else 'STORE'
                    self.emit('@INDEX_' + operation + following[1] + ' ' + self.address(base))
                return cursor+2
            if current == ['dup','2'] and following in (['adu','2'],['adi','2']):
                actions.append('@DOUBLE 1')
                cursor += 2
            elif (current == ['loc','2'] and following == ['loc','2'] and
                  cursor+2 < len(lines) and
                  lines[cursor+2].strip() in ('cii','ciu','cui','cuu')):
                cursor += 3
            elif len(current) == 2 and current[0] == 'loc' and following in (
                    ['adu','2'],['adi','2'],['sbu','2'],['sbi','2']):
                value = int(current[1]) * (-1 if following[0].startswith('sb') else 1)
                actions.append('@ADD_CONST ' + str(value & 65535))
                cursor += 2
            elif (len(current) == 2 and current[0] == 'loc' and
                  following in (['mlu','2'],['mli','2']) and multiply_constant(int(current[1]))):
                actions.append(multiply_constant(int(current[1])))
                cursor += 2
            else:
                return None
        return None

    def unit_code(self, text):
        self.unit += 1
        lines = (dense_switches(lower_bytes(constant_byte_stores(local_updates(fill_loops(strided_loops(global_strided_loops(reuse_quotients(text)))))))) if self.optimize else text).splitlines()
        self.exports = {line.strip().split()[1] for line in lines
                        if line.strip().startswith(('exp ', 'exa '))}
        self.locals = ({line.strip().split()[1].split(',')[0] for line in lines
                        if line.strip().startswith(('pro ', 'inp ', 'ina '))} |
                       {line.strip() for line in lines if line and not line.startswith(' ')
                        and not line.isdigit()}) - self.exports
        index = 0
        while index < len(lines):
            line = lines[index]
            index += 1
            if not line.strip():
                continue
            if not line.startswith(' '):
                symbol = (self.function + '_L' + line if line.isdigit() else self.symbol(line))
                # Data labels can be interspersed in a procedure. The next
                # EM directive distinguishes them from instruction labels.
                nextop = lines[index].strip().split()[0] if index < len(lines) else ''
                if nextop in ('rom', 'con', 'bss', 'hol'):
                    if symbol in self.data_definitions:
                        raise CodegenError('duplicate data: ' + line)
                    self.data_definitions.add(symbol)
                    self.data += [symbol + '_ALIGN:',
                                  '        ORG (' + symbol + '_ALIGN+1) AND 0FFFEH',
                                  symbol + ':']
                else:
                    self.label(symbol)
                continue
            fields = line.strip().split(None, 1)
            op, arg = fields[0], fields[1] if len(fields) > 1 else ''
            # ACK represents conversion sizes as two pushed constants. They
            # are static in C output, so fold these three EM operations here.
            if op == 'loc' and index + 1 < len(lines):
                second = lines[index].strip().split()
                third = lines[index + 1].strip().split()
                if len(second) == 2 and second[0] == 'loc' and third and third[0] in (
                        'cii', 'ciu', 'cui', 'cuu'):
                    old, new = int(arg), int(second[1])
                    if old not in (1, 2) or new not in (1, 2):
                        raise CodegenError('only 8/16-bit integer conversions are supported')
                    if old == 1 or new == 1:
                        signed = third[0].endswith('i') if new == 1 else third[0].startswith('ci')
                        self.emit('CAL ' + ('SX1' if signed else 'ZX1'))
                    index += 2
                    continue
            if self.optimize:
                following = lines[index].strip().split() if index < len(lines) else []
                third = lines[index+1].strip().split() if index+1 < len(lines) else []
                branches = ('zeq','zne','zlt','zle','zgt','zge')
                comparisons = ('cmi','cmu','cms')
                if op == 'lae':
                    consumed = self.indexed_access(lines, index, arg)
                    if consumed is not None:
                        index = consumed
                        continue
                if op == 'ads' and arg == '2' and following in (
                        ['loi','1'],['loi','2'],['sti','1'],['sti','2']):
                    self.emit('CAL A' + ('LD' if following[0] == 'loi' else 'ST') + following[1])
                    index += 1
                    continue
                if op in comparisons and arg == '2' and len(following) == 2 and following[0] in branches:
                    self.compare_branch(following[0][1:], self.symbol(following[1]), op == 'cmi')
                    index += 1
                    continue
                if op == 'loc' and len(following) == 2:
                    value = int(arg)
                    if following[0] in ('beq','bne','blt','ble','bgt','bge'):
                        self.compare_branch(following[0][1:], self.symbol(following[1]), True, value)
                        index += 1
                        continue
                    if (following[0] in comparisons and following[1] == '2' and
                            len(third) == 2 and third[0] in branches):
                        self.compare_branch(third[0][1:], self.symbol(third[1]), following[0] == 'cmi', value)
                        index += 2
                        continue
                    if following[1] == '2':
                        arithmetic = following[0]
                        if arithmetic in ('adi','adu','ads','sbi','sbu'):
                            if arithmetic in ('sbi','sbu'):
                                value = -value
                            self.emit('@ADD_CONST ' + str(value & 65535))
                            index += 1
                            continue
                        if arithmetic in ('and','ior','xor'):
                            self.emit('@' + arithmetic.upper() + '_CONST ' + str(value & 65535))
                            index += 1
                            continue
                        if arithmetic in ('mli','mlu') and multiply_constant(value):
                            self.emit(multiply_constant(value))
                            index += 1
                            continue
                        if (arithmetic in ('dvi','dvu','rmi','rmu') and
                                0 < value <= 256 and value & (value-1) == 0):
                            if arithmetic in ('rmi','rmu'):
                                operation = '@SMOD_MASK' if arithmetic == 'rmi' and value > 1 else '@AND_CONST'
                                self.emit(operation + ' ' + str(value-1))
                            else:
                                operation = '@SDIV_SHIFT' if arithmetic == 'dvi' else '@UDIV_SHIFT'
                                self.emit(operation + ' ' + str(value.bit_length()-1))
                            index += 1
                            continue
                if op == 'dup' and arg == '2' and following in (['adi','2'],['adu','2']):
                    self.emit('@DOUBLE 1')
                    index += 1
                    continue
            if op=='ubinc':
                self.emit('@BYTE_INC '+arg)
                continue
            if (self.optimize and op == 'lol' and index < len(lines) and
                    lines[index].strip() in ('adi 2','adu 2','ads 2')):
                self.emit('@ADD_LOCAL '+arg)
                index += 1
                continue
            # A byte stored through a simple index waits in D instead of
            # taking a RAM-stack round trip under the address.
            if (self.optimize and op in ('llb','lol') and index+3 < len(lines) and
                    lines[index].strip().startswith('lae ') and
                    lines[index+1].strip().split()[0] in ('llb','lol') and
                    lines[index+2].strip() == 'ads 2' and lines[index+3].strip() == 'sti 1'):
                source = lines[index+1].strip().split()
                self.emit('@LOCAL_'+('LOAD1 ' if op == 'llb' else 'LOAD2 ')+arg, '@SAVE_BYTE 0',
                          '@LOCAL_'+('LOAD1 ' if source[0] == 'llb' else 'LOAD2 ')+source[1],
                          '@INDEX_STORED1 '+self.address(lines[index].strip().split()[1]))
                index += 4
                continue
            if op in ('llb','slb'):
                self.emit('@LOCAL_'+('LOAD1 ' if op=='llb' else 'STORE1 ')+arg)
                continue
            if op == 'dcsa':
                table,low,count,default=arg.split(',')
                self.emit('@DENSE_SWITCH '+','.join((self.address(table),low,count,self.symbol(default))))
                continue
            if op == 'bcmp':
                condition,target,left,right=arg.split(',')
                operands=[('g:'+self.address(value[2:]) if value.startswith('g:') else value)
                          for value in (left,right)]
                self.emit('@BYTE_CMP '+','.join((condition,self.symbol(target),*operands)))
                continue
            if op in ('mes', 'exp', 'exa', 'ina', 'inp', 'fil', 'lin', 'lni'):
                if (op == 'mes' and self.function == 'F_MAIN' and
                        arg.startswith('9,') and arg != '9,0'):
                    raise CodegenError('startup requires main(void), without arguments')
                continue
            if op in ('con', 'rom'):
                for item in split_args(arg):
                    item = item.strip()
                    if item.startswith("'"):
                        data = em_string(item)
                        for start in range(0, len(data), 16):
                            self.data.append('        DB ' + ','.join(f'{v}D' for v in data[start:start+16]))
                    elif re.fullmatch(r'-?\d+(?:[IU][12])?', item):
                        match = re.fullmatch(r'(-?\d+)(?:[IU]([12]))?', item)
                        value, size = int(match[1]), int(match[2] or 2)
                        self.data.append(('        DB ' if size == 1 else '        DW ') +
                                         str(value & ((1 << (size * 8)) - 1)) + 'D')
                    else:
                        self.data.append('        DW ' + self.address(item))
                continue
            if op in ('bss', 'hol'):
                size, value, *_ = map(int, arg.split(','))
                if size < 0 or size > 16384 or value:
                    raise CodegenError('unsupported storage reservation: ' + line)
                for start in range(0, size, 16):
                    self.data.append('        DB ' + ','.join('0' for _ in range(min(16, size-start))))
                continue
            if op == 'pro':
                name, size = arg.split(',')
                self.function = self.symbol(name)
                if self.function in self.definitions:
                    raise CodegenError('duplicate function: ' + name)
                self.definitions.add(self.function)
                self.emit('; function '+self.function)
                self.label(self.function)
                self.emit('CAL ENTER')
                if int(size):
                    self.immediate(-int(size))
                    self.emit('CAL ADDSP')
            elif op == 'end':
                self.function = ''
            elif op in ('loc', 'lae', 'lpi'):
                self.constant(int(arg) if op == 'loc' else self.address(arg))
            elif op in ('lxl', 'lxa') and self.pascal:
                level = int(arg)
                if not 0 <= level <= 255:
                    raise CodegenError('unsupported lexical nesting level')
                self.immediate(level)
                self.emit('CAL PCLEX')
                if op == 'lxa':
                    self.emit('LAL', 'ADI 4', 'LLA', 'LAH', 'ACI 0', 'LHA')
                self.emit('LAL', 'LBH', 'CAL PUSH')
            elif op in ('lim', 'sim') and self.pascal:
                if op == 'sim':
                    self.emit('CAL POP')
                self.emit('LHI HIGH PCMASK', 'LLI LOW PCMASK')
                self.emit(*(['LAM','INL','LBM','CAL PUSH'] if op == 'lim' else
                            ['LMA','INL','LMB']))
            elif op in ('aar', 'lar', 'sar') and self.pascal:
                if arg != '2':
                    raise CodegenError('only 16-bit array indices are supported')
                function, resume = self.symbol('$_pc_' + op), self.unique()
                self.references.add(function)
                self.constant(resume)
                self.emit('JMP ' + function)
                self.label(resume)
                self.immediate(8 if op == 'sar' else 6)
                self.emit('CAL ADDSP')
                if op != 'sar':
                    self.emit('LHI HIGH RV','LLI LOW RV','LAM','INL','LBM','CAL PUSH')
            elif op == 'lal':
                self.emit('; escaped frame')
                self.local(int(arg))
                self.emit('LAL', 'LBH', 'CAL PUSH')
            elif op in ('lil', 'sil'):
                self.local(int(arg))
                self.emit('LAM', 'INL', 'LBM', 'CAL PUSH',
                          'CAL ' + ('LD2' if op == 'lil' else 'ST2'))
            elif op in ('lol', 'stl', 'zrl', 'inl', 'del'):
                if self.optimize and op in ('lol','stl'):
                    self.emit('@LOCAL_'+('LOAD2 ' if op == 'lol' else 'STORE2 ')+arg)
                    continue
                self.emit('; local word access '+arg)
                self.local(int(arg))
                if op == 'lol':
                    self.emit('LAM', 'INL', 'LBM', 'CAL PUSH')
                elif op == 'zrl':
                    self.emit('LMI 0', 'INL', 'LMI 0')
                elif self.optimize and op in ('inl','del'):
                    done = self.unique()
                    self.emit('LAM', 'ADI 1' if op == 'inl' else 'SUI 1', 'LMA',
                              'JFC '+done, 'INL', 'LAM',
                              'ACI 0' if op == 'inl' else 'SBI 0', 'LMA')
                    self.label(done)
                else:
                    # Preserve the destination across POP in C/D.
                    self.emit('LCL', 'LDH')
                    if op == 'stl':
                        self.emit('CAL POP', 'LHD', 'LLC', 'LMA', 'INL', 'LMB')
                    else:
                        self.emit('LAM', 'INL', 'LBM', 'CAL PUSH')
                        self.constant(1)
                        self.emit('CAL ' + ('ADD' if op == 'inl' else 'SUB'))
                        self.local(int(arg))
                        self.emit('LCL', 'LDH', 'CAL POP', 'LHD', 'LLC', 'LMA', 'INL', 'LMB')
            elif op in ('loe', 'ste', 'zre', 'ine', 'dee'):
                if self.optimize and op in ('loe','ste'):
                    self.emit('@GLOBAL_' + ('LOAD2 ' if op == 'loe' else 'STORE2 ') + self.address(arg))
                    continue
                if self.optimize and op in ('ine','dee'):
                    address = self.address(arg)
                    done = self.unique()
                    self.emit('LHI HIGH (' + address + ')', 'LLI LOW (' + address + ')',
                              'LAM', 'ADI 1' if op == 'ine' else 'SUI 1', 'LMA', 'JFC '+done, 'INL',
                              'LAM', 'ACI 0' if op == 'ine' else 'SBI 0', 'LMA')
                    self.label(done)
                    continue
                self.constant(self.address(arg))
                if op in ('loe', 'ste'):
                    self.emit('CAL ' + ('LD2' if op == 'loe' else 'ST2'))
                elif op == 'zre':
                    self.emit('CAL POP', 'LHB', 'LLA', 'LMI 0', 'INL', 'LMI 0')
                else:
                    self.emit('CAL LD2')
                    self.constant(1)
                    self.emit('CAL ' + ('ADD' if op == 'ine' else 'SUB'))
                    self.constant(self.address(arg))
                    self.emit('CAL ST2')
            elif op in ('lof', 'stf'):
                if int(arg):
                    self.constant(int(arg))
                    self.emit('CAL ADD')
                self.emit('CAL ' + ('LD2' if op == 'lof' else 'ST2'))
            elif op in ('loi', 'sti'):
                if arg not in ('1', '2'):
                    raise CodegenError('only byte/word memory operations are supported')
                self.emit('CAL ' + ('LD' if op == 'loi' else 'ST') + arg)
            elif op in ('adi','adu','sbi','sbu','mli','mlu','dvi','dvu','rmi','rmu','pmod','rmisave','rmusave','pmodsave',
                        'and','ior','xor','cmi','cmu','cms','sli','slu','sri','sru','ads'):
                if arg != '2':
                    raise CodegenError('only 16-bit operations are supported: ' + line)
                routine = dict(adi='ADD', adu='ADD', ads='ADD', sbi='SUB', sbu='SUB',
                               mli='MUL', mlu='MUL', dvi='DIVI', dvu='DIVU',
                               rmi='MODI', rmu='MODU', pmod='PMODI', rmisave='RMISAVE', rmusave='RMUSAVE', pmodsave='PMODSAVE', and_='BAND', ior='BOR',
                               xor='BXOR', cmi='CMI', cmu='CMU', cms='CMU', sli='LSHIFT', slu='LSHIFT',
                               sri='SHRI', sru='SHRU').get(op, 'BAND')
                self.emit('CAL ' + routine)
            elif op == 'gstride':
                index_address,stride,count,byte,base,fallback,exit = arg.split(',')
                count = int(count)
                index_address,stride,base = map(self.address,(index_address,stride,base))
                self.emit('LHI HIGH ('+stride+')','LLI LOW ('+stride+')',
                          'LCM','INL','LBM','LHI HIGH ('+index_address+')',
                          'LLI LOW ('+index_address+')','LEM','INL','LDM')
                loop,body,done,slow = (self.unique() for _ in range(4))
                self.label(loop)
                self.emit('LAD','NDI 128D','JFZ '+slow,
                          'LAD',f'CPI {count>>8}D','JTC '+body,'JFZ '+done,
                          'LAE',f'CPI {count&255}D','JFC '+done)
                self.label(body)
                self.emit('LAE','ADI LOW ('+base+')','LLA','LAD',
                          'ACI HIGH ('+base+')','LHA',f'LMI {int(byte)&255}D',
                          'LAE','ADC','LEA','LAD','ACB','LDA','JMP '+loop)
                for label,target in ((done,exit),(slow,fallback)):
                    self.label(label)
                    self.emit('LHI HIGH ('+index_address+')','LLI LOW ('+index_address+')',
                              'LME','INL','LMD','JMP '+self.symbol('*'+target))
            elif op == 'stride':
                offset,stride,count,byte,base = arg.split(',')
                count = int(count)
                # DE starts as the index and BC holds the stride. Keep an
                # index-based fallback for potentially wrapping addresses.
                self.frame_address(int(stride))
                self.emit('LCM','INL','LBM')
                self.frame_address(int(offset))
                self.emit('LEM','INL','LDM')
                loop,body,done = self.unique(),self.unique(),self.unique()
                base = self.address(base)
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
                    # Test at the bottom: each mark costs no extra jump.
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
                self.frame_address(int(offset))
                self.emit('LAC','LMA','INL','LMB')
            elif op == 'fill':
                offset,count,byte,base = arg.split(',')
                count,byte = int(count),int(byte)&255
                if count:
                    loop,advance = self.unique(),self.unique()
                    base = self.address(base)
                    self.emit('LHI HIGH ('+base+')','LLI LOW ('+base+')',
                              f'LBI {((count+255)//256)&255}D',f'LCI {count&255}D')
                    self.label(loop)
                    self.emit(f'LMI {byte}D','INL','JFZ '+advance,'INH')
                    self.label(advance)
                    self.emit('DCC','JFZ '+loop,'DCB','JFZ '+loop)
                self.constant(count)
                self.emit('@LOCAL_STORE2 '+offset)
            elif op == 'ladd':
                destination,source = map(int,arg.split(','))
                self.frame_address(source)
                self.emit('LCM','INL','LDM')
                self.frame_address(destination)
                self.emit('LAM','ADC','LMA','INL','LAM','ACD','LMA')
            elif op == 'stc':
                self.emit('CAL POP','LHB','LLA','LMI '+str(int(arg)&255)+'D')
            elif op == 'qreuse':
                self.emit('@GLOBAL_LOAD2 DQUOT')
            elif op == 'adp':
                if int(arg):
                    if self.optimize:
                        self.emit('@ADD_CONST ' + str(int(arg) & 65535))
                    else:
                        self.constant(int(arg))
                        self.emit('CAL ADD')
            elif op in ('inc', 'dec'):
                if self.optimize:
                    self.emit('@ADD_CONST ' + ('1' if op == 'inc' else '65535'))
                else:
                    self.constant(1)
                    self.emit('CAL ' + ('ADD' if op == 'inc' else 'SUB'))
            elif op in ('ngi', 'com'):
                if arg != '2':
                    raise CodegenError('only 16-bit unary operations are supported')
                self.emit('CAL ' + ('NEGI' if op == 'ngi' else 'COM'))
            elif op == 'dup' and arg == '2':
                self.emit('CAL DUP2')
            elif op == 'zer' and arg == '2':
                self.constant(0)
            elif op == 'asp':
                self.immediate(int(arg))
                self.emit('CAL ADDSP')
            elif op == 'cmp':
                self.emit('CAL CMU')
            elif op == 'csa' and arg == '2':
                self.emit('JMP CSA')
            elif op == 'cai':
                resume = self.unique()
                self.emit('CAL POP', 'LCA', 'LDB')
                self.constant(resume)
                self.emit('LAC', 'LBD', 'JMP JUMPAB')
                self.label(resume)
            elif op == 'cal':
                function, resume = self.symbol(arg), self.unique()
                self.references.add(function)
                self.constant(resume)
                self.emit('JMP ' + function)
                self.label(resume)
            elif op == 'lfr' and arg == '2':
                self.emit('LHI HIGH RV', 'LLI LOW RV', 'LAM', 'INL', 'LBM', 'CAL PUSH')
            elif op == 'ret' and arg in ('0', '2'):
                if arg == '2':
                    self.emit('CAL POP', 'LHI HIGH RV', 'LLI LOW RV', 'LMA', 'INL', 'LMB')
                self.emit('JMP LEAVE')
            elif op == 'bra':
                self.emit('JMP ' + self.symbol(arg))
            elif op in ('zeq','zne','zlt','zle','zgt','zge'):
                self.emit('CAL POP')
                self.branch(op[1:], self.symbol(arg))
            elif op in ('beq','bne','blt','ble','bgt','bge'):
                if self.optimize:
                    self.compare_branch(op[1:], self.symbol(arg), True)
                else:
                    self.emit('CAL CMI', 'CAL POP')
                    self.branch(op[1:], self.symbol(arg))
            elif op in ('teq','tne','tlt','tle','tgt','tge'):
                yes, done = self.unique(), self.unique()
                self.emit('CAL POP')
                self.branch(op[1:], yes)
                self.immediate(0)
                self.emit('JMP ' + done)
                self.label(yes)
                self.immediate(1)
                self.label(done)
                self.emit('CAL PUSH')
            elif op == 'nop':
                continue
            else:
                raise CodegenError('unsupported EM instruction: ' + line.strip())

    def cached_code(self):
        """Keep the EM stack's top word in AB between compatible operations.

        Labels, calls, branches, and ordinary instructions are conservative
        barriers: spill before them so every control-flow join and C call uses
        the existing RAM-stack convention. Runtime expression helpers accept
        their top operand in AB and leave results there.

        @ operations are atomic native sequences with declared stack effects.
        Expand them here so their internal instructions don't spill the cached
        value. Global loads produce a new top; indexed stores consume an index
        and the stored value; other stores consume one word.
        """
        helpers = {'LD1', 'LD2', 'ST1', 'ST2', 'NEGI', 'COM', 'SX1', 'ZX1',
                   'MUL', 'DIVI', 'DIVU', 'MODI', 'MODU', 'CMI', 'CMU',
                   'ADD', 'SUB', 'BAND', 'BOR', 'BXOR', 'LSHIFT', 'SHRI', 'SHRU',
                   'ALD1', 'ALD2', 'AST1', 'AST2', 'PMODI', 'RMISAVE', 'RMUSAVE', 'PMODSAVE'}
        pending = False
        output = []
        function = ''
        for line in self.code:
            instruction = line.strip()
            if instruction.startswith('; function '):
                function = instruction.split()[2]
            if instruction.startswith('@'):
                operation, argument = instruction.split(None, 1)
                if operation in ('@BYTE_CMP','@BYTE_INC'):
                    if pending: output.append('        CAL PUSH')
                elif operation in ('@GLOBAL_LOAD2','@LOCAL_LOAD2','@LOCAL_LOAD1'):
                    if pending:
                        output.append('        CAL PUSH')
                elif not pending:
                    output.append('        CAL POP')
                if operation=='@BYTE_INC':
                    offset=int(argument)
                    address=self.static_frame(function,offset)
                    offset=(offset+(4 if offset>=0 else 0))&65535
                    address=address or ['LHI HIGH FP','LLI LOW FP','LAM',
                            f'ADI {offset&255}D','LEA','INL','LAM',f'ACI {offset>>8}D',
                            'LHA','LLE']
                    native=['; local byte update '+argument,*address,'LAM','ADI 1D','LMA','; end local byte']
                    output+=['        '+s for s in native];pending=False
                    continue
                if operation == '@DENSE_SWITCH':
                    table,low,count,default=argument.split(',')
                    low=int(low);native=[]
                    if low:native+=['SUI %dD'%(low&255),'LEA','LAB','SBI %dD'%(low>>8),'LBA','LAE']
                    native+=['LEA','LAB','NDA','JFZ '+default,'LAE','CPI '+count+'D',
                             'JFC '+default,'ADA','ADI LOW ('+table+'+6D)','LLA',
                             'LAI HIGH ('+table+'+6D)','ACI 0','LHA','LAM','INL','LBM','JMP JUMPAB']
                    output+=['        '+item for item in native]
                    pending=False;continue
                if operation == '@BYTE_CMP':
                    condition,target,left,right=argument.split(',')
                    native=[]
                    for operand_number,operand in enumerate((right,left)):
                        kind,value=operand.split(':',1)
                        if kind=='i': native+=['LAI '+value+'D']
                        elif kind=='g':
                            address=value
                            native+=['LHI HIGH ('+address+')','LLI LOW ('+address+')','LAM']
                        else:
                            offset=int(value)
                            address=self.static_frame(function,offset)
                            offset=(offset+(4 if offset>=0 else 0))&65535
                            address=address or ['LHI HIGH FP','LLI LOW FP','LAM',
                                     f'ADI {offset&255}D','LEA','INL','LAM',f'ACI {offset>>8}D',
                                     'LHA','LLE']
                            native+=['; local byte load '+value,*address,'LAM','; end local byte']
                        if operand_number==0: native+=['LDA']
                    native+=['CPD']
                    if condition in ('eq','ne','lt','ge'):
                        native+=[{'eq':'JTZ','ne':'JFZ','lt':'JTC','ge':'JFC'}[condition]+' '+target]
                    elif condition=='le': native+=['JTC '+target,'JTZ '+target]
                    else:
                        done=self.unique();native+=['JTC '+done,'JFZ '+target,done+':']
                    output+=[item if item.endswith(':') else '        '+item for item in native]
                    pending=False
                    continue
                if operation == '@SAVE_BYTE':
                    output.append('        LDA')
                    pending = False
                    continue
                if operation == '@INDEX_STORED1':
                    native = ['ADI LOW ('+argument+')','LLA','LAB','ACI HIGH ('+argument+')','LHA','LMD']
                    output += ['        '+item for item in native]
                    pending = False
                    continue
                if operation == '@ADD_LOCAL':
                    offset = int(argument)
                    address = self.static_frame(function, offset)
                    if not address:
                        # Keep the low byte in C while forming FP+offset.
                        offset = (offset+(4 if offset >= 0 else 0)) & 65535
                        address = ['LCA','LHI HIGH FP','LLI LOW FP','LAM',f'ADI {offset&255}D',
                                   'LEA','INL','LAM',f'ACI {offset>>8}D','LHA','LLE','LAC']
                    native = ['; local word add '+argument,*address,
                              'ADM','LEA','INL','LAB','ACM','LBA','LAE']
                    output += ['        '+item for item in native]
                    pending = True
                    continue
                if operation.startswith(('@INDEX_', '@GLOBAL_', '@LOCAL_')):
                    if operation == '@INDEX_CONST1':
                        argument,byte = argument.rsplit(',',1)
                    if operation.startswith('@INDEX_'):
                        native = ['ADI LOW ('+argument+')', 'LLA', 'LAB',
                                  'ACI HIGH ('+argument+')', 'LHA']
                    elif operation.startswith('@LOCAL_'):
                        # Form FP+constant without destroying a cached store value.
                        offset = int(argument)
                        static = self.static_frame(function, offset)
                        offset = (offset+(4 if offset >= 0 else 0)) & 65535
                        if static:
                            native = static
                        elif 'LOAD' in operation or operation.endswith('1'):
                            native = ([] if 'LOAD' in operation else ['LBA']) + [
                                'LHI HIGH FP','LLI LOW FP','LAM',f'ADI {offset&255}D',
                                'LEA','INL','LAM',f'ACI {offset>>8}D','LHA','LLE']
                            if 'LOAD' not in operation: native+=['LAB']
                        else:
                            native = ['LEA','LHI HIGH FP','LLI LOW FP','LAM',
                                      f'ADI {offset&255}D','LCA','INL','LAM',f'ACI {offset>>8}D',
                                      'LHA','LLC','LAE']
                        native=['; local '+('byte' if operation.endswith('1') else 'word')+' '+('load ' if 'LOAD' in operation else 'store ')+argument]+native
                    else:
                        native = ['LHI HIGH ('+argument+')', 'LLI LOW ('+argument+')']
                    if operation == '@INDEX_CONST1':
                        native += ['LMI '+str(int(byte)&255)+'D']
                    elif 'LOAD' in operation:
                        native += ['LAM', 'LBI 0'] if operation.endswith('1') else ['LAM','INL','LBM']
                    else:
                        if operation.startswith('@INDEX_'):
                            native += ['LCL','LDH','CAL POP','LHD','LLC']
                        native += ['LMA'] if operation.endswith('1') else ['LMA','INL','LMB']
                    if operation.startswith('@LOCAL_') and operation.endswith('1'):
                        native+=['; end local byte']
                    output += ['        '+item for item in native]
                    pending = 'LOAD' in operation
                    continue
                value = int(argument)
                if operation == '@ADD_CONST':
                    if value:
                        output += ['        ADI %dD' % (value & 255), '        LEA',
                                   '        LAB', '        ACI %dD' % (value >> 8),
                                   '        LBA', '        LAE']
                elif operation == '@DOUBLE':
                    output += ['        ' + item for _ in range(value) for item in
                               ('ADA','LEA','LAB','RAL','LBA','LAE')]
                elif operation == '@MUL_CONST':
                    # Shift and add from the top bit; CD keeps the multiplicand.
                    native = []
                    if value == 0:
                        native = ['LAI 0','LBI 0']
                    elif value == 65535:
                        native = ['CAL NEG']
                    elif value != 1:
                        bits = bin(value)[3:]
                        if '1' in bits:
                            native = ['LCA','LDB']
                        for bit in bits:
                            native += ['ADA','LEA','LAB','RAL','LBA','LAE']
                            if bit == '1':
                                native += ['ADC','LEA','LAB','ACD','LBA','LAE']
                    output += ['        '+item for item in native]
                elif operation in ('@SDIV_SHIFT','@UDIV_SHIFT'):
                    if value and operation == '@SDIV_SHIFT':
                        # Bias negative dividends before arithmetic shifting:
                        # division truncates toward zero, unlike signed >>.
                        positive = self.unique()
                        mask = (1 << value)-1
                        output += ['        LEA','        LAB','        NDI 80H',
                                   '        JTZ '+positive,'        LAE',
                                   '        ADI %dD' % (mask & 255),'        LEA','        LAB',
                                   '        ACI %dD' % (mask >> 8),'        LBA',
                                   positive+':','        LAE']
                    step = (('LEA','LAB','RLC','LAB','RAR','LBA','LAE','RAR')
                            if operation == '@SDIV_SHIFT' else
                            ('LEA','LAB','NDA','RAR','LBA','LAE','RAR'))
                    output += ['        '+item for _ in range(value) for item in step]
                elif operation == '@SMOD_MASK':
                    positive, done = self.unique(), self.unique()
                    mask = ['        NDI %dD' % (value & 255),'        LEA','        LAB',
                            '        NDI %dD' % (value >> 8),'        LBA','        LAE']
                    output += ['        LEA','        LAB','        NDI 80H',
                               '        JTZ '+positive,'        LAE','        CAL NEG']
                    output += mask+['        CAL NEG','        JMP '+done,positive+':','        LAE']
                    output += mask+[done+':']
                else:
                    mnemonic = {'@AND_CONST':'NDI', '@IOR_CONST':'ORI', '@XOR_CONST':'XRI'}[operation]
                    output += ['        '+mnemonic+' %dD' % (value & 255), '        LEA',
                               '        LAB', '        '+mnemonic+' %dD' % (value >> 8),
                               '        LBA', '        LAE']
                pending = True
            elif instruction == 'CAL PUSH':
                if pending:
                    # Two pushes duplicate AB: materialize the older copy.
                    output.append(line)
                pending = True
            elif instruction == 'CAL POP':
                if not pending:
                    output.append(line)
                pending = False
            elif instruction == 'CAL DUP2':
                # A cached top is duplicated with one spill; otherwise DUP2
                # loads the existing RAM top while leaving that copy intact.
                output.append('        CAL PUSH' if pending else line)
                pending = True
            elif instruction.startswith('CAL ') and instruction[4:] in helpers:
                if not pending:
                    output.append('        CAL POP')
                helper = instruction[4:]
                if self.optimize and helper in ('LD1','LD2','ST1','ST2'):
                    native = ['LHB','LLA'] if helper.startswith('LD') else [
                        'LCA','LDB','CAL POP','LHD','LLC']
                    native += {'LD1':['LAM','LBI 0'], 'LD2':['LAM','INL','LBM'],
                               'ST1':['LMA'], 'ST2':['LMA','INL','LMB']}[helper]
                    output += ['        '+item for item in native]
                else:
                    output.append(line)
                pending = helper not in ('ST1', 'ST2', 'AST1', 'AST2')
            else:
                if pending:
                    output.append('        CAL PUSH')
                    pending = False
                output.append(line)
        if pending:
            output.append('        CAL PUSH')
        # A zero-extended byte tests as its low byte; branches consume AB.
        for i in range(2, len(output)):
            # Signed gt/le tests read B's sign after the zero test.
            if (output[i].strip().split()[:1] in (['JTZ'],['JFZ']) and
                    output[i-1].strip() == 'ORB' and
                    (i+1 == len(output) or output[i+1].strip() != 'LAB')):
                j = i-2
                while j >= 0 and output[j].strip().startswith('; end local byte'):
                    j -= 1
                if j >= 0 and output[j].strip() == 'LBI 0':
                    output[j] = None
                    output[i-1] = '        NDA'
        return [line for line in output if line is not None]

    def finish(self):
        builtins = {'F_PUTCHAR', 'F_GETCHAR', 'F_PUTS'}
        if self.pascal:
            builtins.add('F_PCHALT')
        missing = (self.references | {'F_MAIN'}) - self.definitions - builtins
        if missing:
            raise CodegenError('unresolved functions: ' + ', '.join(sorted(missing)))
        runtime = Path(__file__).with_name('runtime.asm').read_text()
        if self.pascal:
            runtime += '\n' + Path(__file__).with_name('pascal').joinpath('runtime.asm').read_text()
        helpers = []
        used = {line.strip() for line in self.code}
        for name in ('ALD1','ALD2','AST1','AST2'):
            if 'CAL ' + name not in used:
                continue
            helpers += [name+':'] + ['        '+item for item in (
                'LCA','LDB','CAL POP','ADC','LEA','LAB','ACD','LHA','LLE')]
            if name.startswith('ALD'):
                native = ['LAM','LBI 0'] if name.endswith('1') else ['LAM','INL','LBM']
            else:
                native = ['LCL','LDH','CAL POP','LHD','LLC','LMA']
                if name.endswith('2'):
                    native += ['INL','LMB']
            helpers += ['        '+item for item in native+['RET']]
        for name, low, high in [('ADD','ADC','ACD'),('SUB','SUC','SBD'),
                                ('BAND','NDC','NDD'),('BOR','ORC','ORD'),('BXOR','XRC','XRD')]:
            helpers += [name + ':', '        LCA', '        LDB', '        CAL POP',
                        '        ' + low, '        LEA', '        LAB', '        ' + high,
                        '        LBA', '        LAE', '        RET']
        for name in ('LSHIFT','SHRI','SHRU'):
            helpers += [name + ':', '        LCA', '        CAL POP', name+'LOOP:',
                        '        LEA', '        LAC', '        NDA', '        JTZ '+name+'DONE',
                        '        DCC', '        LAE']
            if name == 'LSHIFT':
                helpers += ['        ADA', '        LEA', '        LAB', '        RAL',
                            '        LBA', '        LAE']
            else:
                helpers += ['        LAB', '        NDA']
                if name == 'SHRI':
                    # Copy the sign into carry, then rotate through carry.
                    helpers += ['        RLC', '        LAB']
                helpers += ['        RAR', '        LBA', '        LAE', '        RAR']
            helpers += ['        JMP '+name+'LOOP', name+'DONE: LAE', '        RET']
        application = '\n'.join((optimize_functions(self.cached_code(),self.data,aligned=True,defer=True) if self.optimize else self.cached_code()) + self.data)
        application = share_return_values(application)
        if self.optimize:
            application, frame_helpers = outline_frame_loads(application, 'FP')
            runtime += '\n' + frame_helpers
        runtime = prune_runtime(runtime + '\n' + '\n'.join(helpers), application)
        return runtime + '\n' + application + '\nACKEND:\nSTACKMIN EQU (ACKEND+255D) AND 0FF00H\n        END\n'


def generate(units, *, pascal=False, optimize=True):
    generator = Generator(pascal=pascal, optimize=optimize)
    generator.static_main = optimize and not any(
        re.search(r'^\s*(?:cal|lpi)\s+\$(?:main|_m_a_i_n)\s*$', unit, re.M) for unit in units)
    for unit in units:
        generator.unit_code(unit)
    return generator.finish()
