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
        match=re.fullmatch(r'; local byte (load|store|update) (-?\d+)',text)
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
        if match and match[1] in ('store','update'):state={r:s for r,s in state.items() if s!=slot}
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


def defer_byte_updates(lines,data):
    """Keep a cached byte local's +constant update in its register (Small C).

    A deferred update leaves the RAM slot stale ("dirty"). Before anything
    that reads the slot from RAM, overwrites its last register copy, stores
    through an unmarked address, or calls out, a write-back reuses the
    update's own address sequence: SP cannot move in between, because every
    SP change is one of those events. The write-back is placed at the latest
    earlier point in the same basic block where its scratch registers and
    flags are dead. Dirtiness merges as "may": rewriting an unchanged value
    is harmless. Any unplaceable write-back reverts its updates to RAM stores.
    Returning through SCRETURN discards the frame, so no write-back is needed.
    """
    from native8008 import graph, registers, flags, register_liveness, liveness
    if any('escaped frame' in line for line in lines):return lines
    original=[];i=0
    while i<len(lines):
        text=lines[i].strip()
        if text.startswith('; local byte '):
            end=i+1
            while end<len(lines) and lines[end].strip()!='; end local byte':end+=1
            if end==len(lines):return lines
            original.append((text,lines[i:end+1]));i=end+1
        else:original.append((lines[i],None));i+=1
    HL=32|64

    def step(k):
        text,group=original[k]
        match=re.fullmatch(r'; local byte update (-?\d+)',text)
        if not match:return None
        body=[s.strip() for s in group[1:-1] if s.strip() and not s.strip().startswith(';')]
        last=max([n for n,s in enumerate(body) if registers(s)[1]&HL],default=-1)
        if body[last+1:last+2]!=['LAM'] or len(body)!=last+4:return None
        if not re.fullmatch(r'ADI \d+D',body[last+2]) or body[last+3]!='LMA':return None
        if any(s.split()[0].startswith('LM') or s.split()[0].endswith('M') for s in body[:last+1]
               if s.split()[0] not in ('LAM',)):return None
        return int(match[1]),body[:last+1],body[last+2]

    updates={k:step(k) for k in range(len(original))}
    updates={k:v for k,v in updates.items() if v}
    if not updates:return lines
    duplicated=False

    def materialize(deferred,writebacks):
        nodes=[];meta=[]
        for k,(text,group) in enumerate(original):
            for r,slot,prefix in writebacks.get(k,[]):
                body=['        ; deferred byte store '+str(slot)]+['        '+s for s in prefix]+['        LM'+r,'        ; end deferred byte']
                nodes.append((body[0].strip(),body));meta.append(('wb',k,r,slot))
            if k in deferred:
                slot,prefix,add=updates[k];r=deferred[k]
                body=['        ; deferred byte update '+str(slot),'        LA'+r,'        '+add,'        L'+r+'A','        ; end deferred byte']
                nodes.append((body[0].strip(),body));meta.append(('upd',k,r,slot))
            else:
                nodes.append((text,group));meta.append(('orig',k,None,None))
        return nodes,meta

    def analyze(nodes,meta):
        successors=graph(nodes,data)
        labels={t.strip()[:-1] for t,g in nodes if t.strip().endswith(':')}
        live_out=register_liveness(nodes,successors);flag_in=liveness(nodes,successors)[0]
        live_in=[]
        for i,(text,group) in enumerate(nodes):
            use=define=0
            for line in reversed(group or [text]):
                read,write=registers(line.strip());p=line.strip().split()
                if p and p[0]=='JMP' and p[1] not in labels and p[1] not in ('SCRETURN','JUMPAB','LEAVE','STACKFAULT'):read=127
                use=read|(use&~write);define|=write
            live_in.append(use|(live_out[i]&~define))
        destinations={j for edges in successors for j in edges}
        roots={0}|{i for i,(t,g) in enumerate(nodes) if t.strip().endswith(':') and i not in destinations}
        # A recursive call jumps to the entry label; the callee has a new frame.
        entry=next((i for i,(t,g) in enumerate(nodes) if t.strip().endswith(':')),None)
        if entry is not None:roots.add(entry)
        entry_label=nodes[entry][0].strip()[:-1] if entry is not None else None

        def transfer(i,state):
            holders,dirty=dict(state[0]),{s:set(o) for s,o in state[1]}
            needs=set();bad=False
            def lose(reg):
                if reg in holders:
                    slot=holders.pop(reg)
                    if slot in dirty and slot not in holders.values():needs.add(slot)
            kind,k,r,slot=meta[i];text,group=nodes[i]
            if kind=='upd':
                if holders.get(r)!=slot:bad=True
                for reg in [x for x,s in holders.items() if s==slot]:holders.pop(reg)
                holders[r]=slot;holders['A']=slot
                dirty[slot]=dirty.get(slot,set())|{k}
            elif kind=='wb':
                if holders.get(r)!=slot:bad=True
                dirty.pop(slot,None)
                for line in group:lose_all=[x for x in 'ABCDEHL' if registers(line.strip())[1]&(1<<'ABCDEHL'.index(x))];[lose(x) for x in lose_all]
            else:
                match=re.fullmatch(r'; local byte (load|store|update) (-?\d+)',text.strip())
                if match:
                    slot=int(match[2])
                    if match[1] in ('load','update') and slot in dirty:needs.add(slot)
                    if match[1] in ('store','update'):
                        dirty.pop(slot,None)
                        for reg in [x for x,s in holders.items() if s==slot]:holders.pop(reg)
                    executable=[s.strip() for s in group if s.strip() and not s.strip().startswith(';')]
                    for line in executable:
                        for x in 'ABCDEHL':
                            if registers(line)[1]&(1<<'ABCDEHL'.index(x)):lose(x)
                    if executable and executable[-1] in ('LAM','LMA'):holders['A']=slot
                else:
                    line=text.strip();p=line.split();op=p[0] if p and not line.startswith(';') and not line.endswith(':') else ''
                    if op=='JMP' and p[1] in ('SCRETURN','LEAVE','STACKFAULT'):holders,dirty={},{}
                    elif op=='JMP' and (p[1] not in labels or p[1]==entry_label) and p[1]!='JUMPAB':
                        needs|=set(dirty);holders,dirty={},{}
                    elif op:
                        if op.startswith('LM'):needs|=set(dirty)
                        copy=re.fullmatch(r'L([ACD])([ACD])',op)
                        if copy:
                            value=holders.get(copy[2]);lose(copy[1])
                            if value is not None:holders[copy[1]]=value
                        else:
                            for x in 'ABCDEHL':
                                if registers(line)[1]&(1<<'ABCDEHL'.index(x)):lose(x)
            # A needed write-back precedes this node, so the slot leaves clean.
            for slot in needs:dirty.pop(slot,None)
            return (tuple(sorted(holders.items())),tuple(sorted((s,tuple(sorted(o))) for s,o in dirty.items()))),needs,bad

        empty=((),())
        incoming={i:empty for i in roots};queue=list(roots)
        def merge(a,b):
            holders=tuple(sorted(set(a[0])&set(b[0])))
            dirty={}
            for s,o in a[1]+b[1]:dirty[s]=tuple(sorted(set(dirty.get(s,()))|set(o)))
            return (holders,tuple(sorted(dirty.items())))
        guard=0
        while queue:
            guard+=1
            if guard>200000:return None
            i=queue.pop();out=transfer(i,incoming[i])[0]
            for j in successors[i]:
                value=empty if j in roots else out if j not in incoming else merge(incoming[j],out)
                if j not in incoming or value!=incoming[j]:incoming[j]=value;queue.append(j)
        def slot_live(slot):
            # Live-in: a RAM read of the slot (load or RAM update) may follow.
            before=[False]*len(nodes);changed=True
            use='; local byte load '+str(slot);update='; local byte update '+str(slot)
            while changed:
                changed=False
                for i in range(len(nodes)-1,-1,-1):
                    text=nodes[i][0].strip()
                    words=text.split()
                    if text in (use,update):value=True
                    elif (len(words)==2 and words[0]=='JMP' and words[1] not in ('SCRETURN','LEAVE','STACKFAULT','JUMPAB') and
                          (words[1] not in labels or words[1]==entry_label)):
                        value=True  # a software call resumes in this frame
                    elif text=='; local byte store '+str(slot):value=False
                    else:value=any(before[j] for j in successors[i] if j not in roots)
                    if value!=before[i]:before[i]=value;changed=True
            return before
        return successors,incoming,transfer,live_in,flag_in,roots,slot_live

    deferred={};writebacks={};disabled=set()
    first=True
    for _ in range(64):
        nodes,meta=materialize(deferred,writebacks)
        result=analyze(nodes,meta)
        if result is None:return lines
        successors,incoming,transfer,live_in,flag_in,roots,slot_live=result
        live_slots={}
        if not duplicated:
            # A step usually starts at a join. Where a JMP to it arrives with
            # the slot in a register, copy the step and its short tail
            # (ending in a JMP) in place of that JMP, so the copy can defer.
            # A conditional jump is retargeted to an out-of-line copy placed
            # after the final unconditional transfer.
            duplicated=True;copies={};appended=[]
            final=[t.strip() for t,g in original if g is None and t.strip() and not t.strip().startswith(';')]
            closed=bool(final) and final[-1].split()[0] in ('JMP','RET')
            for k in updates:
                labels=[];j=k-1
                while j>=0 and original[j][1] is None and original[j][0].strip().endswith(':'):
                    labels.append(original[j][0].strip()[:-1]);j-=1
                tail=[];j=k+1
                while j<len(original) and len(tail)<3 and original[j][1] is None:
                    line=original[j][0].strip();tail.append(original[j])
                    if line.endswith(':') or (line.split()[0][0] in 'JR' and line.split()[0] not in ('RAL','RAR','RLC','RRC') and not line.startswith('JMP ')):tail=None;break
                    if line.startswith('JMP '):break
                    j+=1
                if not labels or not tail or not tail[-1][0].strip().startswith('JMP '):continue
                for i,(kind,n,r,slot) in enumerate(meta):
                    line=nodes[i][0].strip()
                    if not(kind=='orig' and nodes[i][1] is None and i in incoming and
                           len(line.split())==2 and line.split()[1] in labels and
                           updates[k][0] in dict(incoming[i][0]).values()):continue
                    if line.startswith('JMP '):
                        copies[n]=[original[k]]+tail
                    elif closed and re.fullmatch(r'J[TF][CZSP]',line.split()[0]):
                        name=line.split()[1]+'_DEFER%d'%len(appended)
                        copies[n]=[('        '+line.split()[0]+' '+name,None)]
                        appended+=[(name+':',None),original[k]]+tail
            if copies:
                original=[node for n,node in enumerate(original) for node in (copies.get(n) or [node])]+appended
                updates={k:step(k) for k in range(len(original))}
                updates={k:v for k,v in updates.items() if v}
                continue
        if first:
            # Defer each step whose slot a cache register holds on entry.
            first=False
            for i,(kind,k,r,slot) in enumerate(meta):
                if k in updates and i in incoming:
                    held=dict(incoming[i][0]);slot=updates[k][0]
                    register=next((x for x in 'CD' if held.get(x)==slot),None)
                    if register:deferred[k]=register
            if not deferred:return lines
            continue
        revert=set();added=False;reset=False
        for i in range(len(nodes)):
            if i not in incoming:continue
            out,needs,bad=transfer(i,incoming[i])
            dirty_in=dict(incoming[i][1])
            if bad:
                if meta[i][0]=='upd':revert.add(meta[i][1])
                else:reset=True
            requests=[(i,s,set(dirty_in.get(s,()))) for s in needs]
            for j in successors[i]:
                if j in roots or j not in incoming:continue
                held=set(dict(incoming[j][0]).values())
                for s,o in out[1]:
                    if s not in held:
                        line=nodes[i][0].strip()
                        if meta[i][0]=='orig' and nodes[i][1] is None and line.startswith('JMP ') and line.split()[1] in {t.strip()[:-1] for t,g in nodes if t.strip().endswith(':')}:
                            requests.append((i,s,set(o)))
                        else:revert|=set(o)
            for at,s,origins in requests:
                if not origins:continue
                if s not in live_slots:live_slots[s]=slot_live(s)
                if not live_slots[s][at]:continue  # never read again in this frame
                prefixes={tuple(updates[o][1]) for o in origins}
                if len(prefixes)!=1:revert|=origins;continue
                prefix=list(prefixes.pop())
                clobber=0;flag_clobber=0
                for line in prefix:clobber|=registers(line)[1];flag_clobber|=flags(line)[1]
                q=at;placed=False
                while True:
                    held=dict(incoming.get(q,((),()))[0]);dirty=dict(incoming.get(q,((),()))[1])
                    register=next((x for x in 'CD' if held.get(x)==s),None)
                    if (meta[q][0]=='orig' and register and s in dirty and
                            not(live_in[q]&clobber) and not(flag_in[q]&flag_clobber)):
                        entries=writebacks.setdefault(meta[q][1],[])
                        if (register,s,prefix) not in entries:entries.append((register,s,prefix));added=True
                        placed=True;break
                    if nodes[q][0].strip().endswith(':') or q==0:break
                    previous=[s2.strip() for s2 in (nodes[q-1][1] or [nodes[q-1][0]]) if s2.strip() and not s2.strip().startswith(';')]
                    if previous and previous[-1].split()[0][0] in 'JR' and previous[-1].split()[0] not in ('RAL','RAR','RLC','RRC'):break
                    q-=1
                    if q not in incoming:break
                if not placed:revert|=origins
        if revert or reset:
            disabled|=revert
            deferred={k:r for k,r in deferred.items() if k not in disabled}
            writebacks={}
            if not deferred:return lines
            continue
        if not added:
            return [line for text,group in nodes for line in (group or [text])]
    return lines
