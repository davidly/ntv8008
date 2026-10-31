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
