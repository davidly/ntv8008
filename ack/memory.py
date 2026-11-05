"""Conservative native memory-operation lowering for ACK EM."""
import re


def constant_byte_stores(text):
    # A literal below a pure address expression can become a memory-immediate
    # store. Neither expression evaluation order nor any memory read changes.
    address = r' lae [^\n]+\n(?:(?: (?:lol|loe|loc) [^\n]+| lal -?\d+\n loi 1)\n ads 2\n)?'
    return re.sub(r'^ loc (-?\d+)\n('+address+r') sti 1$',
                  lambda m:m[2]+' stc '+m[1], text, flags=re.M)


def local_updates(text):
    def add(match):
        left,right,kind,destination=match.groups()
        if destination not in (left,right) or int(left)%2 or int(right)%2:
            return match[0]
        source=right if destination==left else left
        return ' ladd '+destination+','+source
    text=re.sub(r'^ lol (-?\d+)\n lol (-?\d+)\n (adi|adu) 2\n stl (-?\d+)$',
                add,text,flags=re.M)
    # The C frontend also spells ++local as 1+local followed by a store.
    text=re.sub(r'^ loc 1\n lol (-?\d+)\n adu 2\n stl \1$',
                lambda m:' inl '+m[1],text,flags=re.M)
    # Likewise ++global, possibly with ACK's ina declaration in between.
    return re.sub(r'^ loc 1\n( ina [^\n]+\n)? loe ([^\n]+)\n adu 2\n ste \2$',
                  lambda m:(m[1] or '')+' ine '+m[2],text,flags=re.M)


def fill_loops(text):
    """Recognize a zero-based unsigned byte-fill loop with no other entries."""
    allocations={m[1]:int(m[2]) for m in re.finditer(r'^([^ \n]+)\n bss (\d+),',text,re.M)}
    pattern=re.compile(
        r'^ zrl (?P<index>-?\d+)\n(?P<test>\d+)\n'
        r' lol (?P=index)\n loc (?P<count>\d+)\n cmu 2\n zge \*(?P<exit>\d+)\n'
        r' loc (?P<byte>-?\d+)\n(?P<metadata>(?: ina [^\n]+\n)?)'
        r' lae (?P<base>[^,\n]+)\n lol (?P=index)\n ads 2\n sti 1\n'
        r'(?: loc 1\n lol (?P=index)\n adu 2\n stl (?P=index)| inl (?P=index))\n'
        r' bra \*(?P=test)\n(?=(?P=exit)(?:\n|$))',re.M)
    def procedure(match):
        body=match[0]
        def lower(loop):
            base=re.fullmatch(r'([A-Za-z_.$][\w.$]*)(?:\+(\d+))?',loop['base'])
            if (not base or base[1] not in allocations or
                    int(base[2] or 0)+int(loop['count'])>allocations[base[1]]):
                return loop[0]
            if (int(loop['count'])>65535 or int(loop['index'])%2 or
                    len(re.findall(r'\*'+loop['test']+r'(?!\d)',body))!=1):
                return loop[0]
            return (loop['metadata']+' fill '+','.join(
                loop[name] for name in ('index','count','byte','base'))+'\n')
        return pattern.sub(lower,body)
    return re.sub(r'^ pro [^\n]+\n.*?^ end[^\n]*(?:\n|$)',procedure,text,flags=re.M|re.S)


def strided_loops(text):
    """Retain unsigned index/stride for a call-free constant byte-store loop."""
    allocations={m[1]:int(m[2]) for m in re.finditer(r'^([^ \n]+)\n bss (\d+),',text,re.M)}
    pattern=re.compile(
        r'^(?P<test>\d+)\n lol (?P<index>-?\d+)\n loc (?P<count>\d+)\n'
        r' cmu 2\n zge \*(?P<exit>\d+)\n loc (?P<byte>-?\d+)\n'
        r' lae (?P<base>[^,\n]+)\n lol (?P=index)\n ads 2\n sti 1\n'
        r' lol (?P<stride>-?\d+)\n lol (?P=index)\n adu 2\n stl (?P=index)\n'
        r' bra \*(?P=test)\n(?=(?P=exit)(?:\n|$))',re.M)
    def procedure(match):
        body=match[0]
        def lower(loop):
            base=re.fullmatch(r'([A-Za-z_.$][\w.$]*)(?:\+(\d+))?',loop['base'])
            if (not base or base[1] not in allocations or
                    int(base[2] or 0)+int(loop['count'])>allocations[base[1]] or
                    int(loop['count'])>65535 or
                    any(int(loop[n])%2 for n in ('index','stride')) or
                    loop['index']==loop['stride'] or
                    len(re.findall(r'\*'+loop['test']+r'(?!\d)',body))!=1):
                return loop[0]
            return ' stride '+','.join(loop[n] for n in ('index','stride','count','byte','base'))+'\n'
        return pattern.sub(lower,body)
    return re.sub(r'^ pro [^\n]+\n.*?^ end[^\n]*(?:\n|$)',procedure,text,flags=re.M|re.S)


def global_strided_loops(text):
    """Retain signed global index/stride, falling back for negative indices.

    Pascal uses a test at the top; Modula-2 branches to a test after the body.
    Keep the original loop for negative indices, where unchecked array stores
    could alias the retained variables. Nonnegative indices are proven to stay
    within a separate static allocation before each native store.
    """
    allocations={m[1]:int(m[2]) for m in re.finditer(r'^([^ \n]+)\n bss (\d+),',text,re.M)}
    name=r'[A-Za-z_.$][\w.$]*'
    store=(r' loc (?P<byte>-?\d+)\n lae (?P<base>'+name+r')\n'
           r' loe (?P<index>'+name+r')\n(?: loc 2\n loc 2\n ciu ?\n)?'
           r' ads 2\n sti 1\n loe (?P<stride>'+name+r')\n'
           r' loe (?P=index)\n adi 2\n ste (?P=index)\n')
    top=re.compile(r'^(?P<test>\d+)\n loe (?P<checked>'+name+r')\n'
                   r' loc (?P<bound>\d+)\n bgt \*(?P<exit>\d+)\n'+store+
                   r' bra \*(?P=test)\n(?=(?P=exit)(?:\n|$))',re.M)
    bottom=re.compile(r'^ bra \*(?P<test>\d+)\n(?P<body>\d+)\n'+store+
                      r'(?P=test)\n loe (?P<checked>'+name+r')\n'
                      r' loc (?P<bound>\d+)\n ble \*(?P=body)(?:\n|$)',re.M)
    serial=max([int(n) for n in re.findall(r'^(\d+)$',text,re.M)]+[0])
    def procedure(match):
        nonlocal serial
        body=re.sub(r'^ (?:lin [^\n]+|lni ?)\n','',match[0],flags=re.M)
        def lower(loop):
            nonlocal serial
            index,stride,base=(loop[n] for n in ('index','stride','base'))
            if (index!=loop['checked'] or len({index,stride,base})!=3 or
                    allocations.get(index)!=2 or allocations.get(stride)!=2 or
                    not 0<=int(loop['bound'])<32767 or
                    allocations.get(base,0)<=int(loop['bound'])):
                return loop[0]
            # Every removed header must have only the canonical internal edge.
            for label in ('test','body') if 'body' in loop.groupdict() else ('test',):
                if len(re.findall(r'\*'+loop[label]+r'(?!\d)',body))!=1:
                    return loop[0]
            serial+=1
            exit=str(serial)
            return (' gstride '+','.join((index,stride,str(int(loop['bound'])+1),
                    loop['byte'],base,loop['test'],exit))+'\n'+loop[0]+
                    ('' if loop[0].endswith('\n') else '\n')+exit+'\n')
        return bottom.sub(lower,top.sub(lower,body))
    return re.sub(r'^ pro [^\n]+\n.*?^ end[^\n]*(?:\n|$)',procedure,text,flags=re.M|re.S)


# Side-effect-free EM operations: (words popped, words pushed) for size 2.
PURE_OPERATIONS = {'loc':(0,1),'lol':(0,1),'loe':(0,1),'lal':(0,1),'lae':(0,1),'lil':(0,1),
                   'loi':(1,1),'inc':(1,1),'dec':(1,1),'ngi':(1,1),'com':(1,1),'dup':(1,2),
                   'adp':(1,1),'adi':(2,1),'adu':(2,1),'ads':(2,1),'sbi':(2,1),'sbu':(2,1),
                   'mli':(2,1),'mlu':(2,1),'and':(2,1),'ior':(2,1),'xor':(2,1),
                   'sli':(2,1),'slu':(2,1),'sri':(2,1),'sru':(2,1),'lin':(0,0)}
SIZED = {'loi','dup','ngi','com','adi','adu','ads','sbi','sbu','mli','mlu','and','ior',
         'xor','sli','slu','sri','sru'}
COMMUTATIVE = ('mli','mlu','and','ior','xor')


def commute_constants(text):
    """Move a leading literal after a pure operand of a commutative operation.

    Some frontends emit `loc 10; <a[i]>; mli 2`. The literal and the operand
    are free of side effects, so `<a[i]>; loc 10; mli 2` is equivalent and
    exposes the constant to the native constant-operation lowering. Every
    operation in the operand must take its inputs from the operand itself.
    Additions are left alone; other passes match their literal-first form.
    """
    lines = text.split('\n')
    output = [];i = 0
    while i < len(lines):
        fields = lines[i].split()
        if len(fields) == 2 and fields[0] == 'loc' and lines[i].startswith(' '):
            depth = 0;j = i+1
            while j < len(lines) and lines[j].startswith(' '):
                parts = lines[j].split()
                if depth == 1 and parts[0] in COMMUTATIVE and parts[1:] == ['2']:break
                effect = PURE_OPERATIONS.get(parts[0])
                if (effect is None or depth < effect[0] or
                        (parts[0] in SIZED and parts[1:] not in (['2'],['1'] if parts[0] == 'loi' else ['2']))):
                    break
                depth += effect[1]-effect[0];j += 1
            if (j < len(lines) and depth == 1 and lines[j].startswith(' ') and
                    lines[j].split()[0] in COMMUTATIVE and lines[j].split()[1:] == ['2']):
                output += lines[i+1:j]+[lines[i]];i = j;continue
        output.append(lines[i]);i += 1
    return '\n'.join(output)


def variable_steps(text):
    """Turn load/step/store of one variable into EM's in-place increments."""
    def step(match):
        kind,name,operation,store=match[1],match[2],match[3],match[4]
        if {'lol':'stl','loe':'ste'}[kind]!=store:return match[0]
        down=operation in ('dec','sbu','sbi')
        return ' '+{(False,'lol'):'inl',(True,'lol'):'del',(False,'loe'):'ine',
                     (True,'loe'):'dee'}[down,kind]+' '+name
    text=re.sub(r'^ (lol|loe) ([^\n]+)\n (inc|dec) ?\n (stl|ste) \2$',step,text,flags=re.M)
    return re.sub(r'^ (lol|loe) ([^\n]+)\n loc 1\n (adi|adu|sbi|sbu) 2\n (stl|ste) \2$',
                  step,text,flags=re.M)


def stacked_for_loops(text):
    """Keep Pascal's for-loop value in its variable rather than the EM stack.

    `dup; <limit>; bgt X; L: st v; body; lo v; dup; <limit>; beq X; inc;
    bra L; X: asp 2` carries v on the stack across the back edge, forcing a
    RAM push and pop per iteration. Store v once before L; the back edge
    tests and steps v in memory and leaves through a new label after X's pop.
    The zero-trip test and the final value of v are unchanged.
    """
    numbers=[int(n) for n in re.findall(r'^(\d+)$',text,re.M)]
    fresh=[max(numbers,default=0)]
    pattern=re.compile(
        r'^ dup 2\n (?P<limit>(?:loc|lol|loe) [^\n]+)\n (?P<test>bgt|blt) \*(?P<exit>\d+)\n'
        r'(?P<loop>\d+)\n (?P<store>ste|stl) (?P<v>[^\n]+)\n(?P<body>(?:[^\n]*\n)*?)'
        r' (?P<load>loe|lol) (?P=v)\n dup 2\n (?P=limit)\n beq \*(?P=exit)\n'
        r' (?P<step>inc|dec) ?\n bra \*(?P=loop)\n(?P=exit)\n asp 2$',re.M)
    def rewrite(match):
        body=match['body']
        if ({'ste':'loe','stl':'lol'}[match['store']]!=match['load'] or
                (match['test']=='bgt')!=(match['step']=='inc') or
                re.search(r'\*(?:'+match['loop']+'|'+match['exit']+r')\b',body) or
                re.search(r'^(?:'+match['loop']+'|'+match['exit']+r')$',body,re.M)):
            return match[0]
        fresh[0]+=1;done=str(fresh[0])
        step={('inc','ste'):'ine',('dec','ste'):'dee',('inc','stl'):'inl',
              ('dec','stl'):'del'}[match['step'],match['store']]
        return (' dup 2\n '+match['limit']+'\n '+match['test']+' *'+match['exit']+'\n '+
                match['store']+' '+match['v']+'\n'+match['loop']+'\n'+body+
                ' '+match['load']+' '+match['v']+'\n '+match['limit']+'\n beq *'+done+'\n '+
                step+' '+match['v']+'\n bra *'+match['loop']+'\n'+match['exit']+'\n asp 2\n'+done)
    # A match spans its inner loops without rewriting them; repeat for those.
    while True:
        changed=pattern.sub(rewrite,text)
        if changed==text:return text
        text=changed


TESTS = {'teq':'eq','tne':'ne','tlt':'lt','tle':'le','tgt':'gt','tge':'ge'}
NEGATE = {'eq':'ne','ne':'eq','lt':'ge','ge':'lt','gt':'le','le':'gt'}


def branching_conditions(text):
    """Branch on pure and/or conditions instead of building 0/1 words.

    Pascal evaluates `(a=b) and (c=d) or ...` completely, combining test
    results with word and/or before a zero branch. When every operand is a
    side-effect-free value, testing each comparison with a direct branch and
    skipping the rest is equivalent, and avoids stack traffic and helpers.
    """
    lines=text.split('\n')
    numbers=[int(n) for n in re.findall(r'^(\d+)$',text,re.M)]
    fresh=[max(numbers,default=0)]
    effects=dict(PURE_OPERATIONS)
    effects.update({'cms':(2,1),'cmi':(2,1),'cmu':(2,1)})
    effects.update({name:(1,1) for name in TESTS})

    def parse(region):
        stack=[]
        for line in region:
            parts=line.split();op=parts[0]
            if op in ('cms','cmi','cmu'):
                if parts[1:]!=['2'] or len(stack)<2 or stack[-1][0]!='value' or stack[-2][0]!='value':return None
                right=stack.pop();left=stack.pop();stack.append(('compare',op,left[1],right[1]))
            elif op in TESTS:
                if not stack:return None
                top=stack.pop()
                if top[0]=='compare':stack.append(('test',TESTS[op],top))
                elif top[0]=='value':stack.append(('test',TESTS[op],('zero',top[1])))
                else:return None
            elif op in ('and','ior') and parts[1:]==['2'] and len(stack)>=2 and \
                    stack[-1][0] in ('test','and','ior') and stack[-2][0] in ('test','and','ior'):
                right=stack.pop();left=stack.pop();stack.append((op,left,right))
            elif op in PURE_OPERATIONS and op not in ('and','ior'):
                pops,pushes=PURE_OPERATIONS[op]
                if len(stack)<pops or any(item[0]!='value' for item in stack[len(stack)-pops:]):return None
                code=[];[code.extend(item[1]) for item in stack[len(stack)-pops:]]
                del stack[len(stack)-pops:]
                if pushes==1:stack.append(('value',code+[line]))
                elif pushes==2:return None
            else:return None
        return stack[0] if len(stack)==1 and stack[0][0] in ('and','ior') else None

    def jump(node,value,target,out):
        kind=node[0]
        if kind=='test':
            condition=node[1] if value else NEGATE[node[1]]
            operand=node[2]
            if operand[0]=='zero':out+=operand[1]
            else:out+=operand[2]+operand[3]+[' '+operand[1]+' 2']
            out.append(' z'+condition+' *'+target);return
        if (kind=='and')!=value:
            # and→false or ior→true: either operand decides alone.
            jump(node[1],value,target,out);jump(node[2],value,target,out);return
        fresh[0]+=1;skip=str(fresh[0])
        jump(node[1],not value,skip,out);jump(node[2],value,target,out);out.append(skip)

    output=[];i=0
    while i<len(lines):
        parts=lines[i].split()
        if len(parts)==2 and parts[0] in ('zeq','zne') and lines[i].startswith(' '):
            needed=1;start=i
            while start>0 and needed>0:
                previous=lines[start-1]
                if not previous.startswith(' '):break
                effect=effects.get(previous.split()[0])
                if effect is None:break
                needed+=effect[0]-effect[1];start-=1
            if needed==0 and start<i:
                tree=parse([line for line in lines[start:i] if line.split()[0]!='lin'])
                if tree:
                    code=[]
                    jump(tree,parts[0]=='zne',parts[1][1:],code)
                    del output[len(output)-(i-start):]
                    output+=code;i+=1;continue
        output.append(lines[i]);i+=1
    return '\n'.join(output)


def fold_addresses(text):
    """Fold constant scaling and offsets into static addresses.

    `lae X; loc 1; dup 2; adu 2; ads 2; loi 2` reads board[1] of a word array
    in Modula-2; it is `loe X+2`. Rules repeat until nothing changes.
    """
    def offset(name,delta):
        match=re.fullmatch(r'(.*?)([+-]\d+)?',name)
        total=int(match[2] or 0)+delta
        return match[1]+('' if not total else '%+d'%total)
    rules=((r'^ loc (-?\d+)\n dup 2\n ad[iu] 2$',lambda m:' loc %d'%(int(m[1])*2)),
           (r'^ loc (-?\d+)\n loc (-?\d+)\n ad[iu] 2$',lambda m:' loc %d'%(int(m[1])+int(m[2]))),
           (r'^ loc 2\n loc 2\n ci[iu]\n?$',None),
           (r'^ lae ([^\n]+)\n loc (-?\d+)\n ads 2$',lambda m:' lae '+offset(m[1],int(m[2]))),
           (r'^ lae ([^\n]+)\n (loi|sti) 2$',lambda m:(' loe ' if m[2]=='loi' else ' ste ')+m[1]))
    while True:
        previous=text
        for pattern,replacement in rules:
            if replacement is None:continue
            text=re.sub(pattern,replacement,text,flags=re.M)
        if text==previous:return text


def indexed_operands(text):
    """Address static arrays after computing a complex index.

    `lae B; E; ads 2; loi w` pushes B while E is computed. For a pure E
    containing a load, emit `E; addr B; loi w` so the base is added in
    registers. `A; loi w; inc; A; sti w` on one pure address becomes
    `E; addr B; inci w` (dec: `deci`), updating memory in place.
    """
    effects=dict(PURE_OPERATIONS);effects['llb']=(0,1)
    lines=text.split('\n');output=[];i=0

    def operand(start):
        # Pure lines from start up to a top-level ads 2; returns that index.
        depth=0;j=start
        while j<len(lines) and lines[j].startswith(' '):
            parts=lines[j].split()
            if depth==1 and parts==['ads','2']:return j
            effect=effects.get(parts[0])
            if (effect is None or depth<effect[0] or parts[0] in ('lin','lae') and j==start and False or
                    (parts[0] in SIZED and parts[1:] not in (['2'],['1'] if parts[0]=='loi' else ['2']))):
                return None
            depth+=effect[1]-effect[0];j+=1
        return None

    while i<len(lines):
        parts=lines[i].split()
        if len(parts)==2 and parts[0]=='lae' and lines[i].startswith(' '):
            end=operand(i+1)
            if end is not None and end>i+1 and end+1<len(lines):
                index=lines[i+1:end];access=lines[end+1].split()
                if access in (['loi','1'],['loi','2']) and end+2<len(lines):
                    step=lines[end+2].split()
                    width=access[1];size=end+2-i
                    if (step and step[0] in ('inc','dec') and len(step)==1 and
                            lines[end+3:end+3+size-1]==lines[i:end+1] and
                            lines[end+3+size-1].split()==['sti',width]):
                        output+=index+[' addr '+parts[1],' '+step[0]+'i '+width]
                        i=end+3+size;continue
                if access[:1] in (['loi'],['sti']) and access[1:] in (['1'],['2']) and \
                        any(line.split()[0]=='loi' for line in index):
                    output+=index+[' addr '+parts[1],lines[end+1]]
                    i=end+2;continue
        output.append(lines[i]);i+=1
    return '\n'.join(output)


BRANCH_NEGATE = {'beq':'bne','bne':'beq','blt':'bge','bge':'blt','bgt':'ble','ble':'bgt',
                 'zeq':'zne','zne':'zeq','zlt':'zge','zge':'zlt','zgt':'zle','zle':'zgt'}


def materialized_conditions(text):
    """Branch directly on a condition materialized as -1/0 only to be tested.

    `bXX *a; loc 0; bra *b; a: loc -1; b: zne *T` becomes `bXX *T` (zeq
    negates it) when the labels a and b have no other references.
    """
    pattern=re.compile(r'^ (?P<branch>[bz](?:eq|ne|lt|le|gt|ge)) \*(?P<a>\d+)\n loc 0\n bra \*(?P<b>\d+)\n'
                       r'(?P=a)\n loc -1\n(?P=b)\n (?P<test>zeq|zne) \*(?P<target>\d+)$',re.M)
    def rewrite(match):
        for label in (match['a'],match['b']):
            if len(re.findall(r'\*'+label+r'\b',text))!=1:return match[0]
        branch=match['branch'] if match['test']=='zne' else BRANCH_NEGATE[match['branch']]
        return ' '+branch+' *'+match['target']
    return pattern.sub(rewrite,text)


def stored_address_temporaries(text):
    """Store array elements without parking their address in a temporary.

    ACK BASIC emits `lae B; E; ads 2; ste T; V; loe T; sti w`. With pure E,
    a V that neither reads nor writes T, and T read nowhere else, the store
    is `V; lae B; E; ads 2; sti w`: computing the address later is equivalent.
    """
    effects=dict(PURE_OPERATIONS);effects['llb']=(0,1)
    lines=text.split('\n');matches=[];i=0
    while i<len(lines):
        parts=lines[i].split()
        if len(parts)==2 and parts[0]=='lae' and lines[i].startswith(' '):
            depth=0;j=i+1
            while j<len(lines) and lines[j].startswith(' '):
                p=lines[j].split()
                if depth==1 and p==['ads','2']:break
                effect=effects.get(p[0])
                if effect is None or depth<effect[0]:j=len(lines);break
                depth+=effect[1]-effect[0];j+=1
            if j+1<len(lines) and depth==1 and lines[j].split()==['ads','2'] and \
                    lines[j+1].split()[:1]==['ste']:
                temp=lines[j+1].split()[1];k=j+2
                while k<len(lines) and lines[k].startswith(' ') and temp not in lines[k].split()[1:]:
                    p=lines[k].split()
                    if p==['loe',temp]:break
                    if p[0] not in effects:break
                    k+=1
                if (k+1<len(lines) and lines[k].split()==['loe',temp] and
                        lines[k+1].split()[:1]==['sti']):
                    matches.append((i,j,k,temp));i=k+2;continue
        i+=1
    if not matches:return text
    temps={m[3] for m in matches}
    reads={t:sum(1 for line in lines if line.split()==['loe',t]) for t in temps}
    used={t:sum(1 for m in matches if m[3]==t) for t in temps}
    output=[];cursor=0
    for i,j,k,temp in matches:
        output+=lines[cursor:i]
        if reads[temp]!=used[temp] or any(temp in line.split()[1:] and line.split()[0] not in ('ste','loe','con','ina','exa')
                                         for line in lines):
            output+=lines[i:k+2]
        else:
            output+=lines[j+2:k]+lines[i:j+1]+[lines[k+1]]
        cursor=k+2
    return '\n'.join(output+lines[cursor:])
