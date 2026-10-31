"""Conservative native register caches and expression-stack join elimination.

RAM remains authoritative at stores and calls. Control-flow joins retain only
values proved identical on every incoming edge; call continuations start empty.
"""
import re


def cache_bytes(lines, data):
    from native8008 import graph, registers, register_liveness, liveness
    if any('escaped frame' in line for line in lines):return lines
    if any(re.search(r'; local byte (?:load|store) (-?\d+)',line) and
           abs(int(line.strip().rsplit(' ',1)[1]))>=32768 for line in lines):return lines
    nodes=[];i=0
    while i<len(lines):
        text=lines[i].strip()
        if text.startswith('; local byte '):
            end=i+1
            while end<len(lines) and lines[end].strip()!='; end local byte':end+=1
            if end==len(lines):return lines
            nodes.append((text,lines[i:end+1]));i=end+1
        else:nodes.append((lines[i],None));i+=1
    successors=graph(nodes,data)
    live=register_liveness(nodes,successors);flive=liveness(nodes,successors)[1]
    labels={t.strip()[:-1] for t,g in nodes if t.strip().endswith(':')}
    destinations={j for edges in successors for j in edges}
    roots={0}|{i for i,(t,g) in enumerate(nodes) if t.strip().endswith(':') and i not in destinations}
    incoming={i:{} for i in roots};queue=list(roots)

    def transfer(i,state):
        text,group=nodes[i];state=state.copy();replacement=None;extra=[]
        match=re.fullmatch(r'; local byte (load|store) (-?\d+)',text)
        slot=int(match[2]) if match else None
        old=next((r for r,s in state.items() if s==slot),None) if match else None
        # Address calculations leave A, E, HL and flags behind. Replacing a
        # load must not erase any of those effects if subsequently observed.
        reuse=(match and match[1]=='load' and old and not flive[i] and not(live[i]&112))
        if reuse:
            replacement=['        ; cached byte local '+str(slot),'        LA'+old]
            if any(s.strip()=='LBI 0' for s in group):replacement+=['        LBI 0']
        for line in (replacement if reuse else group or [text]):
            p=line.strip().split();op=p[0] if p else ''
            writes=registers(line.strip())[1]
            state={r:s for r,s in state.items() if not(writes & (1<<'ABCDEHL'.index(r)))}
            if op=='JMP' and p[1] not in labels and p[1] not in ('LEAVE','SCRETURN','STACKFAULT'):
                state={}
            if op.startswith('LM') and not match:
                # Unmarked stores can be local word writes or alias stores.
                state={}
        if match and match[1]=='store':state={r:s for r,s in state.items() if s!=slot}
        if match:
            # Deterministic allocation makes this a monotone must analysis:
            # dropping an incoming fact cannot select a different register.
            available=[r for r in 'CD' if not(live[i]&(1<<'ABCDEHL'.index(r)))]
            if available:
                r=available[0]
                if state.get(r)!=slot:extra=['        L'+r+'A']
                state[r]=slot
        return state,replacement,extra

    while queue:
        i=queue.pop();state,_,_=transfer(i,incoming[i])
        for j in successors[i]:
            merged=state.copy() if j not in incoming else {r:s for r,s in state.items() if incoming[j].get(r)==s}
            if j in roots:merged={}
            if j not in incoming or merged!=incoming[j]:incoming[j]=merged;queue.append(j)
    result=[]
    for i,(text,group) in enumerate(nodes):
        _,replacement,extra=transfer(i,incoming.get(i,{}))
        result+=(replacement if replacement is not None else (group or [text]))+extra
    return result


def cache_frame_registers(lines,data):
    """Hold a frame address in CD over regions where both are otherwise dead."""
    from native8008 import graph, registers, register_liveness, liveness
    nodes=[];addresses={};i=0
    while i<len(lines):
        seq=[s.strip() for s in lines[i:i+10]]
        if (len(seq)==10 and seq[0] in ('LHI HIGH FP','LHI HIGH RSP') and
            seq[1]=='LLI LOW '+seq[0].split()[-1] and seq[2]=='LAM' and
            re.fullmatch(r'ADI \d+D',seq[3]) and seq[4:7]==['LEA','INL','LAM'] and
            re.fullmatch(r'ACI \d+D',seq[7]) and seq[8:]==['LHA','LLE']):
            addresses[len(nodes)]=(seq[0].split()[-1],int(seq[3][4:-1])+(int(seq[7][4:-1])<<8))
            nodes.append(('; frame register address',lines[i:i+10]));i+=10
        else:nodes.append((lines[i],None));i+=1
    if not addresses:return lines
    successors=graph(nodes,data);live=register_liveness(nodes,successors);flive=liveness(nodes,successors)[1]
    destinations={j for edges in successors for j in edges}
    roots={0}|{i for i,(t,g) in enumerate(nodes) if t.strip().endswith(':') and i not in destinations}
    incoming={i:None for i in roots};queue=list(roots)
    def transfer(i,state):
        if i in addresses:
            if state and state[:2]==addresses[i]:return state
            if state and state[0]==addresses[i][0] and not flive[i]:return state
            if not(live[i]&12):return (*addresses[i],i)
            return state
        p=nodes[i][0].strip().split();op=p[0] if p else ''
        if registers(nodes[i][0].strip())[1]&12 or op=='CAL' or op.startswith('LM'):return None
        return state
    while queue:
        i=queue.pop();state=transfer(i,incoming[i])
        for j in successors[i]:
            merged=state if j not in incoming or incoming[j]==state else None
            if j in roots:merged=None
            if j not in incoming or merged!=incoming[j]:incoming[j]=merged;queue.append(j)
    used=set();replacements={}
    for i,address in addresses.items():
        state=incoming.get(i)
        if not state or state[0]!=address[0] or flive[i]:continue
        delta=(address[1]-state[1])&65535
        if delta==0:
            native=['LHD','LLC']
            if live[i]&1:native+=['LAD']
            if live[i]&16:native+=['LEC']
        else:native=['LAC',f'ADI {delta&255}D','LEA','LAD',f'ACI {delta>>8}D','LHA','LLE']
        replacements[i]=['        ; register-held frame address']+['        '+s for s in native];used.add(state[2])
    result=[]
    for i,(text,group) in enumerate(nodes):
        result+=replacements.get(i,group or [text])
        if i in used:result+=['        ; cache frame address in CD','        LCL','        LDH']
    return result


def join_values(lines,data):
    """Keep AB across a join whose every incoming edge pushes that same value.

    No executable instruction may intervene between each PUSH and the POP.
    Helpers' flags and scratch outputs must be dead at the join.
    """
    from native8008 import graph, register_liveness, liveness
    nodes=[(s,None) for s in lines];successors=graph(nodes,data)
    predecessors=[[] for s in lines]
    for i,edges in enumerate(successors):
        for j in edges:predecessors[j].append(i)
    regs=register_liveness(nodes,successors);flive=liveness(nodes,successors)[1]
    removed=set()
    entries=set()
    for line in data:
        if line.strip().startswith('DW '):entries.update(re.findall(r'[A-Za-z_$][\w$]*',line.strip()[3:]))
    def transparent(i):
        t=lines[i].strip()
        return not t or t.startswith(';') or (t.endswith(':') and t[:-1] not in entries) or t.startswith('JMP ')
    for i,line in enumerate(lines):
        if line.strip()!='CAL POP' or regs[i]&112 or flive[i]:continue
        pushes=set();seen=set();pending=list(predecessors[i]);valid=bool(pending)
        while pending and valid:
            j=pending.pop()
            if j in seen:continue
            seen.add(j)
            if lines[j].strip()=='CAL PUSH':pushes.add(j)
            elif transparent(j) and predecessors[j]:pending+=predecessors[j]
            else:valid=False
        if not valid or not pushes:continue
        # A PUSH cannot be shared with an alternative consumer or a loop.
        for push in pushes:
            j=push;visited=set()
            while j!=i:
                if j in visited or len(successors[j])!=1:valid=False;break
                visited.add(j);j=successors[j][0]
                if j!=i and not transparent(j):valid=False;break
        if valid:removed|=pushes|{i}
    return [s for i,s in enumerate(lines) if i not in removed]
