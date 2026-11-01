"""Liveness-guarded native byte comparisons and zero-offset pointer loads."""
import re


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
