"""Truth-only control-flow threading and unsigned byte comparison fusion."""
import re


def thread_booleans(text):
    lines=[s.split(';')[0].strip() for s in text.splitlines() if s.split(';')[0].strip()]
    serial=0
    for iteration in range(4):
        labels={s.split(':')[0]:i for i,s in enumerate(lines) if s.endswith(':')}
        inserts={};changed=False
        def overwritten(index):
            seen=set()
            while index<len(lines) and index not in seen:
                seen.add(index);f=lines[index].split()
                if lines[index].endswith(':') or f[0] in ('TEXT','ADJSP'):index+=1;continue
                if f[0] in ('IMM','ADDRSP','CALL'): return True
                if f[0]=='JUMP' and f[1] in labels:index=labels[f[1]];continue
                return False
            return False
        for i,line in enumerate(lines):
            f=line.split()
            if f[0] not in ('JTRUE','JFALSE'):continue
            value=f[0]=='JTRUE';cursor=labels.get(f[1]);seen=set()
            if cursor is None:continue
            while cursor<len(lines) and cursor not in seen:
                seen.add(cursor);g=lines[cursor].split()
                if lines[cursor].endswith(':') or g[0]=='BOOL':cursor+=1
                elif g[0]=='NOT':value=not value;cursor+=1
                elif g[0]=='JUMP' and g[1] in labels:cursor=labels[g[1]]
                elif g[0] in ('JTRUE','JFALSE'):
                    if value==(g[0]=='JTRUE'):cursor=labels.get(g[1],len(lines))
                    else:cursor+=1
                else:break
            if cursor not in seen or not overwritten(cursor):continue
            # Only bypass truth operations if there was an actual extra test/jump.
            if not any(lines[j].split()[0] in ('BOOL','NOT','JTRUE','JFALSE','JUMP') for j in seen):continue
            label=inserts.get(cursor)
            if label is None:
                serial+=1;label='$BYTEBOOL'+str(serial)
                while label in labels or label in inserts.values():
                    serial+=1;label='$BYTEBOOL'+str(serial)
                inserts[cursor]=label
            lines[i]=f[0]+' '+label;changed=True
        output=[]
        for i,line in enumerate(lines):
            if i in inserts:output.append(inserts[i]+':')
            f=line.split()
            if f[0]=='BOOL' and i+1<len(lines):
                g=lines[i+1].split()
                if g[0] in ('JTRUE','JFALSE') and overwritten(i+2) and overwritten(labels.get(g[1],len(lines))):
                    changed=True;continue
            output.append(line)
        # Drop only unreferenced internal labels, never functions or data symbols.
        references=set(re.findall(r'\$[\w$]+','\n'.join(s for s in output if not s.endswith(':'))))
        lines=[s for s in output if not(s.startswith('$') and s.endswith(':') and s[:-1] not in references)]
        if not changed:break
    return '\n'.join(lines)


def byte_comparisons(text):
    lines=text.splitlines();folded=[];i=0
    while i<len(lines):
        f=lines[i].split(None,1)
        if len(f)==2 and f[0]=='IMM' and i+2<len(lines):
            arithmetic=lines[i+1].split(None,1)
            load=lines[i+2].split()
            if (len(arithmetic)==2 and arithmetic[0]=='ARITH_CONST' and
                    arithmetic[1].startswith('ADD,') and len(load)==2 and load[0]=='LOAD' and
                    re.fullmatch(r'[$A-Za-z_][\w$]*',f[1])):
                offset=int(arithmetic[1].split(',')[1])
                if not -16383<=offset<=16383:
                    folded.append(lines[i]);i+=1;continue
                address=f[1]+(f'{offset:+d}' if offset else '')
                folded.append('DIRECT_LOAD '+address+','+load[1]);i+=3;continue
        folded.append(lines[i]);i+=1
    lines=folded;output=[];i=0
    def operand(line,adjust=0):
        f=line.split(None,1)
        if len(f)!=2:return None
        if f[0]=='STACK_LOAD':
            offset,width=f[1].split(',')
            if width=='1':return 'l~'+str(int(offset)-adjust)
        if f[0]=='DIRECT_LOAD':
            name,width=f[1].rsplit(',',1)
            if width=='1':return 'g~'+name
        if f[0]=='IMM' and re.fullmatch(r'\d+',f[1]) and int(f[1])<=255:return 'i~'+f[1]
        return None
    while i<len(lines):
        left=operand(lines[i]);right=None;cursor=i+1
        if left and cursor+2<len(lines) and lines[cursor]=='PUSH':
            right=operand(lines[cursor+1],2);cursor+=2
        if left and cursor<len(lines):
            f=lines[cursor].split(None,1)
            if len(f)==2 and f[0] in ('COMPARE','CMPBRANCH'):
                args=f[1].split(',');constant=args[1] if f[0]=='COMPARE' else args[3]
                if right and constant=='-':pass
                elif right is None and constant!='-' and 0<=int(constant)<=255:right='i~'+constant
                else:right=None
                if right:
                    if f[0]=='COMPARE':args=[args[0],'-','-','-', '1']
                    output.append('BYTE_CMP '+','.join((*args,left,right)))
                    i=cursor+1;continue
        output.append(lines[i]);i+=1
    return '\n'.join(output)


def stack_depths(text,function_names):
    """Exact transient stack depths at each IR line; joins must agree."""
    lines=text.splitlines();labels={s[:-1]:i for i,s in enumerate(lines) if s.endswith(':')}
    data_targets=set()
    for s in lines:
        if s.startswith('DW '):data_targets.update(re.findall(r'[$A-Za-z_][\w$]*',s[3:]))
    depths={i:0 for label,i in labels.items() if label in function_names}
    queue=list(depths)
    binary={'ADD','SUB','MUL','DIVI','DIVU','MODI','MODU','RMISAVE','RMUSAVE','BAND','BOR','BXOR','LSHIFT','SHRI','SHRU','ADDLOAD','CALLIND','POPSECOND','STIND','SWITCH'}
    bad=set()
    while queue:
        i=queue.pop();f=lines[i].split(None,1);op=f[0];arg=f[1] if len(f)>1 else ''
        depth=depths[i]
        if op=='ADJSP':depth-=int(arg)
        elif op=='PUSH':depth+=2
        elif op=='CALL_STORED':depth-=2       # the callee pops its stored return word
        elif op in binary:depth-=2
        elif op in ('COMPARE','CMPBRANCH'):
            fields=arg.split(',')
            if fields[1 if op=='COMPARE' else 3]=='-':depth-=2
        successors=[i+1] if i+1<len(lines) else []
        if op=='JUMP':successors=[labels[arg]] if arg in labels else []
        elif op in ('JTRUE','JFALSE'):successors+=([labels[arg]] if arg in labels else [])
        elif op=='BYTE_CMP':
            fields=arg.split(',')
            if fields[1] in ('JTRUE','JFALSE') and fields[2] in labels:successors.append(labels[fields[2]])
        elif op=='CMPBRANCH':
            fields=arg.split(',')
            if fields[2] in labels:successors.append(labels[fields[2]])
        elif op in ('RETURN','DATA'):successors=[]
        elif op in ('DENSE_SWITCH','SWITCH'):
            successors=[labels[t] for t in data_targets if t in labels]
            if op=='DENSE_SWITCH':
                default=arg.split(',')[3]
                if default in labels:successors.append(labels[default])
        for j in successors:
            if j in depths:
                if depths[j]!=depth:bad.add(j)
            else:depths[j]=depth;queue.append(j)
    # An inconsistent join prevents register allocation, not ordinary lowering.
    if bad:return {}
    return depths


def local_stores(text):
    """Keep a local assignment address off the expression stack.

    Only closed, call-free expression regions are accepted. Branches may join
    inside the expression, but cannot enter or leave it through another edge.
    """
    lines=text.splitlines();output=[];i=0
    references={}
    for j,line in enumerate(lines):
        f=line.split()
        if f and f[0] in ('JUMP','JTRUE','JFALSE'):references.setdefault(f[1],set()).add(j)
    allowed={'STACK_LOAD','IMM','ARITH_CONST','JUMP','JTRUE','JFALSE','OFFSET','BOOL','NOT','NEGATE','COMPLEMENT'}
    while i<len(lines):
        f=lines[i].split()
        if len(f)!=2 or f[0]!='ADDRSP' or i+1>=len(lines) or lines[i+1]!='PUSH':
            output.append(lines[i]);i+=1;continue
        end=i+2
        if end<len(lines) and lines[end].startswith('LOAD '):end+=1
        while end<len(lines) and (lines[end].endswith(':') or lines[end].split()[0] in allowed):end+=1
        body=lines[i+2:end];labels={s[:-1] for s in body if s.endswith(':')}
        closed=bool(body) and body[0].split()[0] in ('LOAD','STACK_LOAD','IMM')
        closed=closed and all(not(references.get(label,set())-set(range(i+2,end))) for label in labels)
        closed=closed and all(s.split()[1] in labels for s in body if s.split()[0] in ('JUMP','JTRUE','JFALSE'))
        if end>=len(lines) or lines[end] not in ('STIND 1','STIND 2') or not closed:
            output.append(lines[i]);i+=1;continue
        offset=int(f[1]);rewritten=[]
        for j,s in enumerate(body):
            if j==0 and s.startswith('LOAD '):s='STACK_LOAD '+str(offset)+','+s.split()[1]
            elif s.startswith('STACK_LOAD '):
                address,width=s.split()[1].split(',');s='STACK_LOAD '+str(int(address)-2)+','+width
            rewritten.append(s)
        output+=rewritten+['STACK_STORE '+str(offset)+','+lines[end].split()[1]]
        i=end+1
    return '\n'.join(output)
