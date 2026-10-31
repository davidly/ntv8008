"""Conservative native memory-operation lowering for ACK EM."""
import re


def constant_byte_stores(text):
    # A literal below a pure address expression can become a memory-immediate
    # store. Neither expression evaluation order nor any memory read changes.
    address = r' lae [^\n]+\n(?: (?:lol|loe|loc) [^\n]+\n ads 2\n)?'
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
    return re.sub(r'^ loc 1\n lol (-?\d+)\n adu 2\n stl \1$',
                  lambda m:' inl '+m[1],text,flags=re.M)


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
