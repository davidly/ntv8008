"""Liveness-guarded native byte comparisons and zero-offset pointer loads."""
import re

def _control(op):
    """True for calls, jumps, returns and halts (not RAL/RAR/RLC/RRC)."""
    return (op in ('CAL', 'HLT') or op.startswith(('J', 'RST')) or
            (op[0] == 'R' and op not in ('RAL', 'RAR', 'RLC', 'RRC')))



def shorten(code,data):
    from native8008 import graph,register_liveness,liveness
    nodes=[(s,None) for s in code];edges=graph(nodes,data)
    regs=register_liveness(nodes,edges);flag_live=liveness(nodes,edges)[1]
    output=[];i=0
    while i<len(code):
        if not code[i].strip() or code[i].strip().startswith(';'):
            output.append(code[i]);i+=1;continue
        positions=[j for j in range(i,min(i+24,len(code)))
                   if code[j].strip() and not code[j].strip().startswith(';')][:10]
        seq=[code[j].strip() for j in positions]
        def comments(end):
            return [s for s in code[i:end+1] if not s.strip() or s.strip().startswith(';')]
        # FP/SP+0 needs a pointer load, not a 16-bit addition. The old E
        # result is retained; A and arithmetic flags must be dead.
        if (len(seq)==10 and seq[0] in ('LHI HIGH FP','LHI HIGH RSP') and
            seq[1]=='LLI LOW '+seq[0].split()[-1] and
            seq[2:]==['LAM','ADI 0D','LEA','INL','LAM','ACI 0D','LHA','LLE'] and
            not(regs[positions[9]]&1) and not flag_live[positions[9]]):
            output+=comments(positions[9])+[code[positions[0]],code[positions[1]],'        LEM','        INL','        LHM','        LLE']
            i=positions[9]+1;continue
        # A register/immediate left operand can precede a static right
        # address without being overwritten. Keep both operand order and flags.
        if (len(seq)>=6 and seq[0].startswith('LHI HIGH (') and
            seq[1].startswith('LLI LOW (') and seq[0][9:]==seq[1][8:] and
            seq[2:4]==['LAM','LDA'] and
            (re.fullmatch(r'LA[BCE]',seq[4]) or seq[4].startswith('LAI ')) and seq[5]=='CPD' and
            not(regs[positions[5]]&8)):
            output+=comments(positions[5])+[code[positions[4]],code[positions[0]],code[positions[1]],'        CPM']
            i=positions[5]+1;continue
        output.append(code[i]);i+=1
    return output


INVERT = {'JTC': 'JFC', 'JFC': 'JTC', 'JTZ': 'JFZ', 'JFZ': 'JTZ',
          'JTS': 'JFS', 'JFS': 'JTS', 'JTP': 'JFP', 'JFP': 'JTP'}


def _tail(lines, labels, name, limit):
    """Instructions after label `name` up to a JMP/RET (at most `limit`)."""
    tail = [];k = labels[name] + 1
    while k < len(lines) and len(tail) <= limit:
        text = lines[k].strip()
        if text.endswith(':'):
            return None
        if text and not text.startswith(';'):
            tail.append(lines[k])
            if text.split()[0] in ('JMP', 'RET'):
                break
        k += 1
    if tail and len(tail) <= limit and tail[-1].strip().split()[0] in ('JMP', 'RET'):
        return tail
    return None


def _test(lines, labels, name):
    """(instructions, branch index) for a short test ending in Jcc, else None."""
    test = [];k = labels[name] + 1
    while k < len(lines) and len(test) <= 3:
        text = lines[k].strip()
        if text.endswith(':'):
            return None
        if text and not text.startswith(';'):
            op = text.split()[0]
            if op in INVERT and len(text.split()) == 2:
                return (test, k) if k + 1 < len(lines) else None
            if _control(op):
                return None
            test.append(lines[k])
        k += 1
    return None


def thread_jumps(lines, limit=4):
    """Shorten jumps into short code that ends in a jump.

    A JMP to a tail of at most `limit` instructions ending in JMP/RET becomes
    a copy of the tail. A JMP to a short test ending in a conditional jump
    becomes the test with the condition inverted, jumping into the code after
    the original test, then a JMP to the original target. The originals stay
    for their other entries. An `LAr` right after `LrA` is dropped.
    """
    labels = {line.strip()[:-1]: i for i, line in enumerate(lines) if line.strip().endswith(':')}
    continuation = {}
    for line in lines:
        parts = line.strip().split()
        if (len(parts) == 2 and parts[0] == 'JMP' and parts[1] in labels and
                not _tail(lines, labels, parts[1], limit)):
            found = _test(lines, labels, parts[1])
            if found:
                continuation[found[1]] = parts[1] + '_T'
    if continuation:
        lines = [item for index, line in enumerate(lines)
                 for item in ([line, continuation[index] + ':'] if index in continuation else [line])]
        labels = {line.strip()[:-1]: i for i, line in enumerate(lines) if line.strip().endswith(':')}
    output = []
    for index, line in enumerate(lines):
        parts = line.strip().split()
        if len(parts) == 2 and parts[0] == 'JMP' and parts[1] in labels:
            # A jump to a label directly below is a fall-through.
            k = index + 1
            while k < len(lines) and (not lines[k].strip() or lines[k].strip().startswith(';')
                                      or lines[k].strip().endswith(':')):
                if lines[k].strip() == parts[1] + ':':
                    break
                k += 1
            if k < len(lines) and lines[k].strip() == parts[1] + ':':
                continue
            tail = _tail(lines, labels, parts[1], limit)
            if tail and tail[-1].strip() != line.strip():
                output += tail
                continue
            found = _test(lines, labels, parts[1])
            if found and lines[found[1] + 1].strip().endswith('_T:'):
                test, branch = found
                op, target = lines[branch].strip().split()
                after = lines[branch + 1].strip()[:-1]
                output += test + ['        ' + INVERT[op] + ' ' + after, '        JMP ' + target]
                continue
        output.append(line)
    cleaned = []
    for line in output:
        if (cleaned and re.fullmatch(r'LA([BCDEHL])', line.strip()) and
                cleaned[-1].strip() == 'L' + line.strip()[2] + 'A'):
            continue
        cleaned.append(line)
    return cleaned
