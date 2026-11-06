"""Conservative native-target lowering for ACK BASIC assignments."""
import re


def lower_assignments(program):
    """Eliminate dummy3 address spills for independent, pure expressions.

    Never cross labels, calls, branches, or stores. Compute each matched
    expression's stack effect so it cannot consume surrounding operands.
    Other assignments keep the frontend's original temporary convention.
    """
    lines=program.splitlines()
    binary={'adi','adu','sbi','sbu','ads','mli','mlu','dvi','dvu','rmi','rmu',
            'and','ior','xor','sli','slu','sri','sru','cmi','cmu','cms'}
    unary={'inc','dec','ngi','com','loi'}
    def expression(index):
        depth=0
        while index<len(lines):
            line=lines[index]
            if not line.startswith(' '): break
            fields=line.strip().split()
            op=fields[0] if fields else ''
            arg=fields[1] if len(fields)==2 else ''
            if op=='loe' and arg=='dummy3': break
            if op in ('loc','lae','loe'):
                depth+=1
            elif op=='dup' and arg=='2' and depth>=1:
                depth+=1
            elif op in binary and arg=='2' and depth>=2:
                depth-=1
            elif op in unary and depth>=1 and (not arg or arg=='2'):
                pass
            else:
                break
            index+=1
        return index,depth
    output=[];index=0
    while index<len(lines):
        end,depth=expression(index)
        if depth==1 and end<len(lines) and lines[end]==' ste dummy3':
            # Scalar destination: lae target / spill / expression / reload /
            # store becomes expression / ste target.
            scalar=re.fullmatch(r' lae (\S+)',lines[index]) if end==index+1 else None
            if scalar:
                finish,result=expression(end+1)
                if result==1 and lines[finish:finish+2]==[' loe dummy3',' sti 2']:
                    output+=lines[end+1:finish]+[' ste '+scalar[1]]
                    index=finish+2
                    continue
            # For a constant RHS, place the value below the destination. This
            # exposes array address + store to the shared backend's fusion.
            value=re.fullmatch(r' loc (-?\d+)',lines[end+1]) if end+1<len(lines) else None
            if value and lines[end+2:end+4]==[' loe dummy3',' sti 2']:
                output+=[lines[end+1]]+lines[index:end]+[' sti 2']
                index=end+4
                continue
        output.append(lines[index]);index+=1
    return '\n'.join(output)+'\n'


def constant_for_steps(program):
    """Fold FOR steps that are constants into their uses.

    With -8 the frontend stores the step in a temporary and tests its sign
    on every iteration. A temporary stored once from a literal, with no other
    reference than loads, is that literal: the sign tests become nothing or a
    branch, and the code they made unreachable is removed.
    """
    lines=program.split('\n');index=-1
    while index+4<len(lines):
        index+=1
        value=re.fullmatch(r' loc (-?\d+)',lines[index])
        store=re.fullmatch(r' ste (\.\d+)',lines[index+2])
        test=re.fullmatch(r' zlt (\*\d+)',lines[index+3])
        if not (value and store and test and lines[index+1]==' dup 2'):
            continue
        name=store[1]
        uses=[i for i,line in enumerate(lines) if re.search(r'\s'+re.escape(name)+r'$',line)]
        if any(lines[i]!=' loe '+name for i in uses if i!=index+2):
            continue
        for i in uses:
            lines[i]=' loc '+value[1]
        lines[index:index+4]=[' loc '+value[1],' zlt '+test[1]]
    program='\n'.join(lines)
    program=re.sub(r'^ loc (-?\d+)\n zlt (\*\d+)$',
                   lambda m:' bra '+m[2] if int(m[1])<0 else '',program,flags=re.M)
    program=re.sub(r'\n\n+','\n',program)
    # Put the variable first so the backend steps it in place.
    program=re.sub(r'^ loc (-?\d+)\n loe (\S+)\n adi 2\n ste \2$',
                   r' loe \2\n loc \1\n adi 2\n ste \2',program,flags=re.M)
    return unreachable_code(program)


def unreachable_code(program):
    """Remove code after an unconditional branch until a referenced label,
    and branches to the label that immediately follows them."""
    pseudo=('end','pro','exa','exp','ina','inp','con','rom','bss','hol','mes')
    while True:
        lines=program.split('\n');output=[];dead=False
        referenced=set(re.findall(r'\*(\d+)\b',program))
        for line in lines:
            if re.fullmatch(r'\d+',line) and line not in referenced:
                continue
            if (line and not line.startswith(' ')) or line.split()[:1] and line.split()[0] in pseudo:
                dead=False
            elif dead and line:
                continue
            output.append(line)
            if line.startswith((' bra ',' ret ')):
                dead=True
        result=[]
        for i,line in enumerate(output):
            target=re.fullmatch(r' bra \*(\d+)',line)
            following=next((n for n in output[i+1:] if not n.startswith(' lin ')),None)
            if target and following==target[1]:
                continue
            result.append(line)
        result='\n'.join(result)
        if result==program:
            return result
        program=result


def word_compares(program):
    """Compare two global words with one native operation: wcmp."""
    return re.sub(r'^ loe (\S+)\n loe (\S+)\n(?: cmi 2\n z| b)(eq|ne|lt|le|gt|ge) (\*\d+)$',
                  lambda m:' wcmp '+','.join((m[3],m[4],'g:'+m[1],'g:'+m[2])),program,flags=re.M)


def accumulations(program):
    """Evaluate `x = x + <pure expression>` with x loaded last.

    The backend then adds x from memory instead of saving the expression
    under it on the RAM stack. Addition commutes and nothing is stored.
    """
    effects={'loc':(0,1),'loe':(0,1),'lae':(0,1),'dup':(1,2),'loi':(1,1),
             'adi':(2,1),'adu':(2,1),'ads':(2,1),'sbi':(2,1),'sbu':(2,1)}
    lines=program.split('\n');output=[];index=0
    while index<len(lines):
        first=re.fullmatch(r' loe (\S+)',lines[index])
        cursor=index+1;depth=0
        while first and cursor<len(lines):
            fields=lines[cursor].split()
            effect=effects.get(fields[0]) if len(fields)==2 and (fields[0] not in
                    ('dup','loi','adi','adu','ads','sbi','sbu') or fields[1]=='2') else None
            if not effect or depth<effect[0] or (depth==1 and fields[0] in ('adi','adu') and
                    lines[cursor+1:cursor+2]==[' ste '+first[1]]):
                break
            depth+=effect[1]-effect[0];cursor+=1
        # A lone constant stays second: the backend adds it in place.
        if (first and depth==1 and cursor>index+1 and not
                (cursor==index+2 and lines[index+1].startswith(' loc ')) and
                lines[cursor:cursor+2]==[' adi 2',' ste '+first[1]]):
            output+=lines[index+1:cursor]+[lines[index],' adi 2',' ste '+first[1]]
            index=cursor+2
            continue
        output.append(lines[index]);index+=1
    return '\n'.join(output)


def versioned_steps(program):
    """Test a variable FOR step's sign once, not on every iteration.

    The frontend stores the step in a temporary that nothing else writes and
    tests its sign before each bound check. Give the loop an ascending and a
    descending copy, each with only its own bound check. A body is copied only
    if no label inside it is referenced from outside, such as GOSUB returns.
    """
    serial=[max([int(n) for n in re.findall(r'^(\d+)$',program,re.M)]+[0])]
    pattern=re.compile(
        r'^(?P<inc>\d+)\n loe (?P<s>\.\d+)\n loe (?P<v>\S+)\n adi 2\n ste (?P=v)\n'
        r'(?P<t>\d+)\n loe (?P=s)\n zlt \*(?P<a>\d+)\n'
        r' wcmp gt,\*(?P<exit>\d+),g:(?P=v),g:(?P<limit>\S+)\n bra \*(?P<b>\d+)\n'
        r'(?P=a)\n wcmp lt,\*(?P=exit),g:(?P=v),g:(?P=limit)\n(?P=b)\n'
        r'(?P<body>(?:[^\n]*\n)*?) bra \*(?P=inc)\n(?P=exit)$',re.M)
    def references(label,text):
        return len(re.findall(r'\*'+label+r'\b',text))
    def rewrite(match):
        body=match['body']
        if (len(re.findall(r'^ ste '+re.escape(match['s'])+r'$',program,re.M))!=1 or
                re.search(r'^ lae '+re.escape(match['s'])+r'$',program,re.M) or
                any(references(match[n],program)!=1 for n in ('inc','t','a','b')) or
                any(references(label,body)!=references(label,program)
                    for label in re.findall(r'^(\d+)$',body,re.M))):
            return match[0]
        renamed={}
        for label in re.findall(r'^(\d+)$',body,re.M):
            serial[0]+=1;renamed[label]=str(serial[0])
        copy=re.sub(r'^(\d+)$|\*(\d+)\b',lambda m:(renamed.get(m[1],m[1]) if m[1] else
                    '*'+renamed.get(m[2],m[2])),body,flags=re.M)
        step=' loe '+match['v']+'\n loe '+match['s']+'\n adi 2\n ste '+match['v']+'\n'
        test=' wcmp %s,*'+match['exit']+',g:'+match['v']+',g:'+match['limit']+'\n'
        return (match['t']+'\n loe '+match['s']+'\n zlt *'+match['a']+'\n'+
                match['b']+'\n'+test % 'gt'+body+step+' bra *'+match['b']+'\n'+
                match['a']+'\n'+test % 'lt'+copy+step+' bra *'+match['a']+'\n'+match['exit'])
    return pattern.sub(rewrite,program)
