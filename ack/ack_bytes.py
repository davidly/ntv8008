"""Fuse unsigned byte accesses and comparisons without changing EM semantics."""
import re


def lower_bytes(text):
    lines=text.splitlines()
    output=[]
    i=0
    while i<len(lines):
        fields=lines[i].strip().split()
        following=lines[i+1].strip().split() if i+1<len(lines) else []
        third=lines[i+2].strip().split() if i+2<len(lines) else []
        if (len(fields)==2 and fields[0]=='lol' and following==['lal',fields[1]] and third==['sti','1']):
            i+=3
            continue
        if len(fields)==2 and fields[0]=='lal' and following in (['loi','1'],['sti','1']):
            output.append(' '+('llb' if following[0]=='loi' else 'slb')+' '+fields[1]);i+=2
            continue
        output.append(lines[i]);i+=1
    text='\n'.join(output)
    # A byte increment consumes and stores the promoted value; no result
    # escapes. Same-size conversions do not alter its low byte.
    text=re.sub(r'^ llb (-?\d+)\n inc ?\n(?: loc 2\n loc 2\n ciu ?\n)? slb \1$',
                lambda m:' ubinc '+m[1],text,flags=re.M)
    lines=text.splitlines()
    def operand(index):
        if index>=len(lines): return None
        f=lines[index].strip().split()
        if len(f)!=2: return None
        if f[0]=='llb': return 'l:'+f[1],index+1
        if f[0]=='loc' and 0<=int(f[1])<=255: return 'i:'+f[1],index+1
        if f[0]=='lae' and index+1<len(lines) and lines[index+1].strip()=='loi 1':
            return 'g:'+f[1],index+2
        return None
    output=[];i=0
    while i<len(lines):
        first=operand(i)
        second=operand(first[1]) if first else None
        if second:
            cursor=second[1]
            f=lines[cursor].strip().split() if cursor<len(lines) else []
            count=1
            if f in (['cmi','2'],['cmu','2']):
                cursor+=1;count+=1
                f=lines[cursor].strip().split() if cursor<len(lines) else []
                condition=f[0][1:] if len(f)==2 and f[0] in ('zeq','zne','zlt','zle','zgt','zge') else None
            else:
                condition=f[0][1:] if len(f)==2 and f[0] in ('beq','bne','blt','ble','bgt','bge') else None
            if condition:
                output.append(' bcmp '+','.join((condition,f[1],first[0],second[0])))
                i=second[1]+count;continue
        output.append(lines[i]);i+=1
    return '\n'.join(output)


def dense_switches(text):
    lines=text.splitlines();tables={}
    for i,line in enumerate(lines):
        if not line or line.startswith(' ') or i+3>=len(lines):continue
        cursor=i+1;values=[]
        while cursor<len(lines) and lines[cursor].strip().startswith('rom '):
            values.extend(v.strip() for v in lines[cursor].strip()[4:].split(','));cursor+=1
        # A zero default (Modula-2 CASE without ELSE) jumps to address 0, as CSA does.
        if len(values)<4 or not re.fullmatch(r'\*\d+|0(?:[IU]2)?',values[0]):continue
        if not values[0].startswith('*'):values[0]='0'
        low=re.fullmatch(r'(-?\d+)(?:I2)?',values[1]);span=re.fullmatch(r'(\d+)(?:I2)?',values[2])
        if not low or not span:continue
        count=int(span[1])+1
        if not 1<=count<=128 or len(values)!=count+3 or not all(re.fullmatch(r'\*\d+',v) for v in values[3:]):continue
        tables[line.strip()]=(int(low[1])&65535,count,values[0])
    output=[];i=0
    while i<len(lines):
        f=lines[i].strip().split()
        if (len(f)==2 and f[0]=='lae' and f[1] in tables and i+1<len(lines) and lines[i+1].strip()=='csa 2'):
            low,count,default=tables[f[1]]
            output.append(' dcsa '+','.join((f[1],str(low),str(count),default)));i+=2
        else:output.append(lines[i]);i+=1
    return '\n'.join(output)
