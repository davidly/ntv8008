"""Relocate provably non-reentrant sequential Occam workspaces to static RAM."""
import re


def static_workspaces(program, mode='all'):
    if mode not in ('all', 'main', 'stack'):
        raise ValueError('invalid Occam storage mode')
    if mode == 'stack' or re.search(r'^ (?:cai|lpi|lxa)\b', program, re.M):
        return program
    pattern = re.compile(r'^ pro ([^,]+),(\d+)\n.*?^ end \d+', re.M | re.S)
    procedures = {m[1]: m for m in pattern.finditer(program)}
    if '$main' not in procedures:
        return program
    calls = {name: set(re.findall(r'^ cal (\S+)', m[0], re.M)) & procedures.keys()
             for name, m in procedures.items()}
    if any('$main' in targets for targets in calls.values()):
        return program
    parents = {'$main': None}

    def ancestor(name, depth):
        for _ in range(depth):
            if name not in parents or parents[name] is None:
                return None
            name = parents[name]
        return name

    changed = True
    while changed:
        changed = False
        for caller, m in procedures.items():
            if caller not in parents:
                continue
            for depth, callee in re.findall(r'^ lxl (\d+)\n cal (\S+)', m[0], re.M):
                if callee not in procedures:
                    continue
                parent = ancestor(caller, int(depth))
                if parent is None:
                    return program
                if callee in parents and parents[callee] != parent:
                    return program
                if callee not in parents:
                    parents[callee] = parent; changed = True
    recursive = set()
    for name in procedures:
        seen = set(); pending = list(calls[name])
        while pending:
            target = pending.pop()
            if target == name:
                recursive.add(name); break
            if target not in seen:
                seen.add(target); pending.extend(calls[target] - seen)
    candidates = {name for name, m in procedures.items()
                  if name in parents and name not in recursive and int(m[2])}
    if mode == 'main':
        candidates &= {'$main'}
    # A bare lexical frame pointer may escape. Static links passed to known
    # Occam procedures and constant displacements preserve the stack headers.
    for caller, m in procedures.items():
        lines = m[0].splitlines()
        for i, line in enumerate(lines):
            match = re.fullmatch(r' lxl (\d+)', line)
            if not match:
                continue
            target = ancestor(caller, int(match[1]))
            following = lines[i + 1] if i + 1 < len(lines) else ''
            allowed = (re.fullmatch(r' adp -?\d+', following) or
                       following.startswith(' cal ') and following[5:] in procedures)
            if target is None:
                return program
            if not allowed:
                candidates.discard(target)
    sizes = {name: int(procedures[name][2]) for name in candidates}
    labels = {name: 'occam_workspace_'+str(i) for i, name in enumerate(procedures) if name in candidates}

    def address(name, offset, width=1):
        size = sizes[name]
        if not -size <= offset or offset + width > 0:
            raise ValueError('Occam local access outside workspace')
        return labels[name]+'+'+str(size+offset)

    def rewrite(m):
        name = m[1]; text = m[0]
        def lexical(match):
            target = ancestor(name, int(match[1])); offset = int(match[2])
            return ' lae '+address(target, offset) if target in candidates and offset < 0 else match[0]
        text = re.sub(r'^ lxl (\d+)\n adp (-?\d+)$', lexical, text, flags=re.M)
        if name not in candidates:
            return text
        def local(match):
            op, value = match.groups(); offset = int(value)
            if offset >= 0:
                return match[0]
            symbol = address(name, offset, 1 if op in ('lal','llb','slb') else 2)
            return {'lal':' lae '+symbol, 'lol':' loe '+symbol,
                    'stl':' ste '+symbol, 'llb':' lae '+symbol+'\n loi 1',
                    'slb':' lae '+symbol+'\n sti 1',
                    'zrl':' loc 0\n ste '+symbol,
                    'inl':' loe '+symbol+'\n inc \n ste '+symbol,
                    'del':' loe '+symbol+'\n dec \n ste '+symbol,
                    'lil':' loe '+symbol+'\n loi 2',
                    'sil':' loe '+symbol+'\n sti 2'}[op]
        text = re.sub(r'^ (lal|lol|stl|llb|slb|zrl|inl|del|lil|sil) (-?\d+)$', local, text, flags=re.M)
        # Reject unknown frame-relative operations rather than partially moving
        # a frame. Debug MES records are not executable references.
        if re.search(r'^ (?:ldl|sdl|lfl|sfl) -\d+', text, re.M):
            raise ValueError('unsupported Occam workspace reference')
        text = re.sub(r'^( pro [^,]+),\d+', r'\g<1>,0', text, count=1)
        return re.sub(r'^ end \d+', ' end 0', text, flags=re.M)
    if not candidates:
        return program
    try:
        result = pattern.sub(rewrite, program)
    except ValueError:
        return program
    return result+'\n'+'\n'.join(labels[name]+'\n bss '+str(sizes[name])+',0,0' for name in procedures if name in candidates)+'\n'
