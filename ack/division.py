"""Conservative quotient reuse within straight-line EM code."""
import re


def reuse_quotients(text):
    """Keep the quotient of MOD for a later DIV of unchanged scalar operands.

    Calls, control flow, another division, and ambiguous writes are barriers.
    An indirect store cannot reach this frame's locals if no local address is
    ever taken. Internal globals whose addresses never escape are also safe;
    other global operands are invalidated by indirect stores.
    The saved quotient is private runtime scratch, never live across calls.
    """
    lines = text.splitlines()
    # An internal word whose address is never materialized cannot alias an
    # indirect store. Check the whole unit, including data initializers.
    private = set(re.findall(r'^([^ \n]+)\n bss 2,',text,re.M))
    for name in tuple(private):
        token = re.compile(r'(?<![\w.$])'+re.escape(name)+r'(?![\w.$])')
        for line in lines:
            if token.search(line) and line != name and not re.fullmatch(
                    r' (loe|ste|zre|ine|dee|ina) '+re.escape(name),line):
                private.remove(name)
                break
    start = 0
    while start < len(lines):
        if not lines[start].startswith(' pro '):
            start += 1
            continue
        end = start+1
        while end < len(lines) and not lines[end].startswith(' end'):
            end += 1
        escaped = any(re.match(r' (lal|lxa|lxl)\b', line) for line in lines[start:end])
        candidate = None
        for index in range(start+1,end):
            fields = lines[index].strip().split()
            if not fields:
                continue
            op = fields[0]
            if op in ('rmi','rmu','dvi','dvu','pmod'):
                operands = tuple(lines[index-2:index])
                simple = all(re.fullmatch(r' (lol -?\d+|loe \S+|loc -?\d+)', x)
                             for x in operands)
                signed = op in ('rmi','dvi','pmod')
                key = (operands,signed)
                if simple and op in ('dvi','dvu') and candidate and candidate[0] == key:
                    previous = candidate[1]
                    previous_op = lines[previous].split()[0]
                    helper = 'pmodsave' if previous_op=='pmod' else ('rmisave' if signed else 'rmusave')
                    lines[previous] = ' '+helper+' 2'
                    lines[index-2:index+1] = ['', '', ' qreuse 2']
                    candidate = None
                elif simple and op in ('rmi','rmu','pmod'):
                    # Preserve the cheaper existing power-of-two lowering.
                    divisor = operands[1].split()
                    power = int(divisor[1]) if divisor[0]=='loc' else 0
                    candidate = None if 0 < power <= 256 and power & (power-1)==0 else (key,index)
                else:
                    candidate = None
                continue
            if not candidate:
                continue
            operands = candidate[0][0]
            if not lines[index].startswith(' ') or op in (
                    'cal','cai','bra','ret','pro','end','sil','bls','sts','sar',
                    'beq','bne','blt','ble','bgt','bge','zeq','zne','zlt','zle','zgt','zge'):
                candidate = None
            elif op in ('stl','zrl','inl','del'):
                written = int(fields[1])
                if any(x.startswith(' lol ') and abs(int(x.split()[1])-written)<2 for x in operands):
                    candidate = None
            elif op in ('ste','zre','ine','dee'):
                if any(x.startswith(' loe ') for x in operands):
                    candidate = None
            elif op == 'sti':
                if any((x.startswith(' lol ') and escaped) or
                       (x.startswith(' loe ') and x.split()[1] not in private)
                       for x in operands):
                    candidate = None
            elif op not in ('loc','lol','loe','lae','loi','lal','ads','adi','adu','sbi','sbu',
                            'mli','mlu','and','ior','xor','dup','inc','dec','adp',
                            'lin','mes','cii','ciu','cui','cuu','sli','slu','sri','sru'):
                candidate = None
        start = end+1
    return '\n'.join(lines)+'\n'
