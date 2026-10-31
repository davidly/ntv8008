"""Conservative native 8008 leaf-register and frame-address optimizations.

The emitters mark exact, unescaped byte slots. C is allocated only when CFG
liveness proves it does not interfere with any existing register/flag use.
Unknown calls, pointer exposure and computed destinations retain the old code.
"""
import re

ALL=15


def flags(text):
    op=text.split()[0] if text.split() else ''
    if op in ('JTC','JFC','RTC','RFC'):return 1,0
    if op in ('JTZ','JFZ','RTZ','RFZ'):return 2,0
    if op in ('JTS','JFS','RTS','RFS'):return 4,0
    if op in ('JTP','JFP','RTP','RFP'):return 8,0
    if op in ('RAL','RAR'):return 1,1
    if op in ('RLC','RRC'):return 0,1
    if re.fullmatch(r'(IN|DC)[BCDEHL]',op):return 0,14
    if re.fullmatch(r'(AC|SB)[ABCDEHLMI]',op):return 1,ALL
    if re.fullmatch(r'(AD|SU|ND|XR|OR|CP)[ABCDEHLMI]',op):return 0,ALL
    if op=='CAL':return 0,ALL
    return 0,0


def c_touch(text):
    op=text.split()[0] if text.split() else ''
    if re.fullmatch(r'L[ABCDEHLM][ABCDEHLMI]',op):return op[1]=='C' or op[2]=='C'
    return op in ('ADC','ACC','SUC','SBC','NDC','XRC','ORC','CPC','INC','DCC')


def graph(nodes, data):
    labels={text.strip()[:-1]:i for i,(text,_) in enumerate(nodes) if text.strip().endswith(':')}
    table_targets=set()
    for line in data:
        if line.strip().startswith('DW '):
            table_targets.update(re.findall(r'[A-Za-z_$][\w$]*',line.strip()[3:]))
    successors=[]
    for i,(line,_) in enumerate(nodes):
        parts=line.strip().split();op=parts[0] if parts else ''
        following=[i+1] if i+1<len(nodes) else []
        if op=='JMP':
            target=parts[1]
            following=([labels[target]] if target in labels else
                       [labels[t] for t in table_targets if t in labels] if target=='JUMPAB' else [])
        elif op in ('RET','HLT'):following=[]
        elif op.startswith('J') and len(parts)==2:
            following+=([labels[parts[1]]] if parts[1] in labels else [])
        successors.append(following)
    return successors


def liveness(nodes, successors, slot=None):
    before=[0]*len(nodes);after=[0]*len(nodes)
    changed=True
    while changed:
        changed=False
        for i in range(len(nodes)-1,-1,-1):
            text,group=nodes[i]
            if slot is None:
                use=define=0
                for line in reversed(group or [text]):
                    read,write=flags(line.strip())
                    use=read|(use&~write);define|=write
            else:
                use=int(text=='; local byte load '+slot)
                define=int(text=='; local byte store '+slot)
            out=0
            for j in successors[i]:out|=before[j]
            value=use|(out&~define)
            if value!=before[i] or out!=after[i]:changed=True;before[i]=value;after[i]=out
    return before,after


def allocate_leaf(lines,data):
    groups=[];i=0
    while i<len(lines):
        line=lines[i].strip()
        if line.startswith('; local byte '):
            end=i+1
            while end<len(lines) and lines[end].strip()!='; end local byte':end+=1
            if end==len(lines):return lines
            groups.append((line,lines[i:end+1]));i=end+1
        else:groups.append((lines[i],None));i+=1
    slots={text.rsplit(' ',1)[1] for text,g in groups if text.startswith('; local byte load ')}
    slots={s for s in slots if re.fullmatch(r'-\d+',s) and int(s)<0 and any(t=='; local byte store '+s for t,g in groups)}
    if not slots or any('escaped frame' in line for line in lines):return lines
    entry=next((text.strip()[:-1] for text,g in groups if text.strip().endswith(':')),None)
    preserving={'PUSH','POP','LOADSP','ADDSP','ENTER','LOCAL','LD1','LD2','DUP2','SX1','ZX1','NEG'}
    for text,group in groups:
        p=text.strip().split()
        if p and p[0]=='CAL' and p[1] not in preserving:return lines
        if p and p[0]=='JMP' and p[1]==entry:return lines
        if p and p[0]=='JMP' and (p[1]=='CSA' or p[1] in ('F_MAIN','SC_6D61696E')):return lines
        # A software call jumps to another function after pushing its return word.
        if p and p[0]=='JMP' and p[1] not in {t.strip()[:-1] for t,g in groups if t.strip().endswith(':')} and p[1] not in ('JUMPAB','LEAVE','SCRETURN','STACKFAULT'):
            return lines
    successors=graph(groups,data)
    live_flags=liveness(groups,successors)[1]
    for slot in sorted(slots,key=lambda s:-sum(t=='; local byte load '+s for t,g in groups)):
        live_in,live_out=liveness(groups,successors,slot)
        # A local must be initialized on every reachable path before reading it.
        initialized=[None]*len(groups);initialized[0]=False
        changed=True
        while changed:
            changed=False
            for i,(text,group) in enumerate(groups):
                if initialized[i] is None:continue
                state=initialized[i] or text=='; local byte store '+slot
                for j in successors[i]:
                    value=state if initialized[j] is None else initialized[j] and state
                    if value!=initialized[j]:initialized[j]=value;changed=True
        valid=True
        for i,(text,group) in enumerate(groups):
            own=text in ('; local byte load '+slot,'; local byte store '+slot)
            if own:
                if live_flags[i] or (text.endswith('load '+slot) and initialized[i] is not True):valid=False
            elif live_in[i] or live_out[i]:
                if any(c_touch(s.strip()) for s in (group or [text])):valid=False
            # Other accesses to an overlapping word/escaped frame reject allocation.
            if text.strip().startswith('; local word '):
                offset=int(text.strip().rsplit(' ',1)[1])
                if offset<=int(slot)<offset+2:valid=False
        if not valid:continue
        result=['        ; leaf register C holds byte local '+slot]
        for text,group in groups:
            if text=='; local byte store '+slot:result+=['        LCA']
            elif text=='; local byte load '+slot:
                result+=['        LAC']
                if any(s.strip()=='LBI 0' for s in group):result+=['        LBI 0']
            else:result+=group or [text]
        return result
    return lines


REGS='ABCDEHL'


def registers(text):
    op=text.split()[0] if text.split() else ''
    bit=lambda r:1<<REGS.index(r) if r in REGS else 0
    hl=bit('H')|bit('L')
    if re.fullmatch(r'L[ABCDEHLM][ABCDEHLMI]',op):
        return (hl if op[1]=='M' or op[2]=='M' else 0)|bit(op[2]),bit(op[1])
    if re.fullmatch(r'(IN|DC)[BCDEHL]',op):return bit(op[-1]),bit(op[-1])
    if op in ('RAL','RAR','RLC','RRC'):return bit('A'),bit('A')
    if re.fullmatch(r'(AD|AC|SU|SB|ND|XR|OR|CP)[ABCDEHLMI]',op):
        return bit('A')|(hl if op[-1]=='M' else bit(op[-1])),0 if op.startswith('CP') else bit('A')
    if op=='OUT':return bit('A'),0
    if op=='INP':return 0,bit('A')
    if op=='CAL':
        name=text.split()[1]
        if name=='PUSH':return bit('A')|bit('B'),bit('E')|hl
        if name=='POP':return 0,bit('A')|bit('B')|bit('E')|hl
        if name=='LOADSP':return 0,bit('E')|hl
        if name in ('ENTER','ADDSP','LOCAL'):return bit('A')|bit('B'),bit('A')|bit('E')|hl
        return 127,127
    if op=='RET':return bit('A')|bit('B'),0
    if op=='JMP' and text.split()[1] in ('SCRETURN','JUMPAB'):return bit('A')|bit('B'),0
    return 0,0


def register_liveness(nodes,successors):
    before=[0]*len(nodes);after=[0]*len(nodes)
    labels={text.strip()[:-1] for text,group in nodes if text.strip().endswith(':')}
    changed=True
    while changed:
        changed=False
        for i,(text,group) in reversed(list(enumerate(nodes))):
            use=define=0
            for line in reversed(group or [text]):
                read,write=registers(line.strip())
                p=line.strip().split()
                if p and p[0]=='JMP' and p[1] not in labels and p[1] not in ('SCRETURN','JUMPAB','LEAVE','STACKFAULT'):
                    read=127
                use=read|(use&~write);define|=write
            out=0
            for j in successors[i]:out|=before[j]
            value=use|(out&~define)
            if before[i]!=value or after[i]!=out:before[i]=value;after[i]=out;changed=True
    return after


def cache_frame_addresses(lines,data,aligned,serial):
    nodes=[];addresses={};increments=set();i=0
    uses={}
    for line in lines:
        p=line.strip().split()
        if len(p)==2 and p[0].startswith('J'):uses[p[1]]=uses.get(p[1],0)+1
    while i<len(lines):
        seq=[s.strip() for s in lines[i:i+10]]
        if (len(seq)==10 and seq[0] in ('LHI HIGH FP','LHI HIGH RSP') and
                seq[1]=='LLI LOW '+seq[0].split()[-1] and seq[2]=='LAM' and
                re.fullmatch(r'ADI \d+D',seq[3]) and seq[4:7]==['LEA','INL','LAM'] and
                re.fullmatch(r'ACI \d+D',seq[7]) and seq[8:]==['LHA','LLE']):
            low=int(seq[3][4:-1]);high=int(seq[7][4:-1]);offset=(high<<8)|low
            addresses[len(nodes)]=(seq[0].split()[-1],offset)
            nodes.append(('; frame address',lines[i:i+10]));i+=10;continue
        if (len(seq)>=4 and seq[0]=='INL' and seq[1].startswith('JFZ ') and
                seq[2]=='INH' and seq[3]==seq[1].split()[1]+':' and uses.get(seq[1].split()[1])==1):
            increments.add(len(nodes));nodes.append(('; increment pointer',lines[i:i+4]));i+=4;continue
        nodes.append((lines[i],None));i+=1
    if not addresses:return lines
    successors=graph(nodes,data)
    destinations={j for edges in successors for j in edges}
    roots={0}|{i for i,(text,group) in enumerate(nodes)
               if text.strip().endswith(':') and i not in destinations}
    # Software-call return labels have no explicit CFG predecessor. Their
    # incoming pointer state is unknown, just like function entry.
    incoming={i:None for i in roots};queue=list(roots)
    while queue:
        i=queue.pop();state=incoming[i]
        if i in addresses:state=addresses[i]
        elif i in increments:
            if state:state=(state[0],(state[1]+1)&65535)
        else:
            op=nodes[i][0].strip().split();op=op[0] if op else ''
            if op=='INL' and aligned and state and state[1]%2==0:state=(state[0],(state[1]+1)&65535)
            elif op=='DCL' and aligned and state and state[1]%2==1:state=(state[0],(state[1]-1)&65535)
            elif op=='CAL' or op.startswith('LM') or registers(nodes[i][0].strip())[1]&96:state=None
        for j in successors[i]:
            value=state if j not in incoming else state if state==incoming[j] else None
            if j not in incoming or value!=incoming[j]:incoming[j]=value;queue.append(j)
    regs=register_liveness(nodes,successors);flag_live=liveness(nodes,successors)[1]
    result=[]
    for i,(text,group) in enumerate(nodes):
        state=incoming.get(i)
        if i not in addresses or not state or state[0]!=addresses[i][0] or regs[i]&17 or flag_live[i]:
            result+=group or [text];continue
        delta=((addresses[i][1]-state[1]+32768)&65535)-32768
        if abs(delta)>2:result+=group;continue
        native=[];offset=state[1]
        for step in range(abs(delta)):
            if delta>0:
                native+=['INL']
                if not(aligned and offset%2==0):
                    serial[0]+=1;label='NATIVEFRAME'+str(serial[0]);native+=['JFZ '+label,'INH',label+':']
                offset+=1
            else:
                if aligned and offset%2==1:native+=['DCL']
                else:
                    serial[0]+=1;label='NATIVEFRAME'+str(serial[0]);native+=['LEA','DCL','LAL','CPI 255D','JFZ '+label,'DCH',label+':','LAE']
                offset-=1
        # Two guarded decrements cost more than the original address formation.
        if sum(1 for s in native if not s.endswith(':'))>=10:result+=group;continue
        result.append('        ; cached frame address '+addresses[i][0]+f'+{addresses[i][1]}')
        result+=[s if s.endswith(':') else '        '+s for s in native]
    return result


# Keep the public entry point small: every function is independently analyzed.
def optimize_functions(code,data,aligned=False):
    result=[];block=[];serial=[0]
    def finish(block):
        return simplify_values(cache_frame_addresses(allocate_leaf(block,data),data,aligned,serial),data)
    for line in code:
        if line.strip().startswith('; function '):
            if block:result+=finish(block)
            block=[line]
        elif block:block.append(line)
        else:result.append(line)
    if block:result+=finish(block)
    return result


def simplify_values(lines,data):
    """Drop redundant promotions and loads using register/flag liveness."""
    for iteration in range(3):
        nodes=[(s,None) for s in lines];successors=graph(nodes,data)
        regs=register_liveness(nodes,successors);flag_live=liveness(nodes,successors)[1]
        result=[];i=0;changed=False
        while i<len(lines):
            seq=[s.strip() for s in lines[i:i+6]]
            if (len(seq)==6 and re.fullmatch(r'(NDI|ORI|XRI) \d+D',seq[0]) and
                    seq[1:3]==['LEA','LAB'] and re.fullmatch(r'(NDI|ORI|XRI) \d+D',seq[3]) and
                    seq[4:]==['LBA','LAE'] and seq[0][:3]==seq[3][:3] and
                    not(regs[i+5]&16) and not flag_live[i+5]):
                high=int(seq[3][4:-1]);op=seq[3][:3]
                if (op=='NDI' and high in (0,255)) or (op in ('ORI','XRI') and high==0):
                    if seq[0]!='NDI 255D':result.append(lines[i])
                    if op=='NDI' and high==0:result.append('        LBI 0')
                    i+=6;changed=True;continue
            op=seq[0].split()[0] if seq[0].split() else ''
            read,write=registers(seq[0]);fr,fw=flags(seq[0])
            pure=(re.fullmatch(r'L[ABCDEHL][ABCDEHLMI]',op) or
                  re.fullmatch(r'(AD|AC|SU|SB|ND|XR|OR|CP)[ABCDEHLMI]',op) or
                  re.fullmatch(r'(IN|DC)[BCDEHL]',op) or op in ('RAL','RAR','RLC','RRC'))
            if pure and not(write&regs[i]) and not(fw&flag_live[i]):
                changed=True;i+=1;continue
            if re.fullmatch(r'L([ABCDEHL])\1',op):changed=True;i+=1;continue
            result.append(lines[i]);i+=1
        lines=result
        if not changed:break
    return lines
