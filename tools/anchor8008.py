"""Register-anchored frames for self-recursive functions.

Small C addresses locals from the RAM stack pointer and ACK from its frame
pointer; each access loads that 16-bit pointer and adds an offset with carry.
When an activation's frame lies in the stack's first page (3Eh), the same
address is `LAD; ADI k; LLA; LHI 3EH`, with the anchor's low byte in D. The
anchor is the stack pointer at entry (Small C) or the frame pointer (ACK).

A function containing a self-call gets a fast copy using that form. The
original entry checks the pointer page and the byte range of every anchored
address and enters the copy only when all stay in the page; otherwise the
original code runs unchanged. In the copy, D is reloaded before an access
wherever any path may have changed it. An access is converted only where the
original sequence's other results are dead and a reload would not overwrite
a live D.

The stack depth below the anchor is followed through explicit stack-pointer
adjustments, argument blocks and call returns; where it is unknown, sequences
stay unchanged. Within the page, an adjustment stores only the pointer's low
byte and needs no stack-floor check: 3E00h is above any program image. ACK's
ENTER, argument stores and LEAVE use the same page-local forms.
"""
import re

def _control(op):
    """True for calls, jumps, returns and halts (not RAL/RAR/RLC/RRC)."""
    return (op in ('CAL', 'HLT') or op.startswith(('J', 'RST')) or
            (op[0] == 'R' and op not in ('RAL', 'RAR', 'RLC', 'RRC')))


PAGE = 0x3E
A, B, C, D, E, H, L = 1, 2, 4, 8, 16, 32, 64
UNSET = object()


def _executable(text):
    text = text.strip()
    return bool(text) and not text.startswith(';') and not text.endswith(':')


def _codes(lines, i, count):
    """Next `count` instructions from lines[i] without crossing a label."""
    code = [];j = i
    while j < len(lines) and len(code) < count:
        text = lines[j].strip()
        if text.endswith(':'):
            return None, j
        if _executable(text):
            code.append(text)
        j += 1
    return (code, j) if len(code) == count else (None, j)


def _signed(value):
    return value - 65536 if value & 32768 else value


def _form(lines, i, base):
    """Classify a frame sequence at lines[i]: (kind, value, end) or None.

    address: HL = base+value. zero: HL = RSP. adjust: RSP += value (inline
    or ADDSP). args/slot: stored-argument block of `value` bytes, or slot
    `value` within it. enter/leave: ACK frame entry and exit. other: an
    unrecognized stack-pointer use.
    """
    text = lines[i].strip()
    head = lambda name: ['LHI HIGH ' + name, 'LLI LOW ' + name]
    if text in ('LHI HIGH RSP', 'LHI HIGH FP'):
        name = text.split()[-1]
        code, end = _codes(lines, i, 10)
        if code and code[:3] == head(name) + ['LAM']:
            low = re.fullmatch(r'ADI (\d+)D', code[3]);high = re.fullmatch(r'ACI (\d+)D', code[7])
            temp = re.fullmatch(r'L([CE])A', code[4])
            if (name == base and low and high and temp and code[5:7] == ['INL', 'LAM'] and
                    code[8] == 'LHA' and code[9] == 'LL' + temp[1]):
                return 'address', _signed(int(low[1]) | int(high[1]) << 8), end
            if (name == 'RSP' and low and high and code[4] == 'LMA' and
                    code[5:7] == ['INL', 'LAM'] and code[8] == 'LMA'):
                _, stop = _codes(lines, i, 9)
                check, after = _codes(lines, stop, 2)
                if check == ['CPI HIGH STACKMIN', 'JTC STACKFAULT']:
                    stop = after
                return 'adjust', _signed(int(low[1]) | int(high[1]) << 8), stop
        code, end = _codes(lines, i, 6)
        if name == base == 'RSP' and code == head('RSP') + ['LEM', 'INL', 'LHM', 'LLE']:
            return 'zero', 0, end
        return ('other', None, i + 1) if name == 'RSP' else None
    match = re.fullmatch(r'; argument (block|slot) (\d+)', text)
    if match and base == 'FP':
        if match[1] == 'block':
            # The page-crossing label sits between JFC/INH and the stores.
            code, end = _codes(lines, i + 1, 10)
            rest, end = _codes(lines, end + 1, 6) if code else (None, end)
            if (code and rest and code[:2] == ['LCA', 'LDB'] and code[4] == 'CAL ADDSP' and
                    rest == ['LMC', 'INL', 'LMD', 'DCL', 'LCL', 'LDH']):
                return 'args', int(match[2]), end
            return None
        code, end = _codes(lines, i + 1, 11)
        if code and code[0] == 'LEA' and code[7:11] == ['LME', 'INL', 'LMB', 'DCL']:
            extra, after = _codes(lines, end, 2)
            if extra == ['LCL', 'LDH']:
                end = after
            return 'slot', int(match[2]), end
        code, end = _codes(lines, i + 1, 10)
        if code and code[0] == 'LEA' and code[7:10] == ['LME', 'INL', 'LMB']:
            return 'slot', int(match[2]), end
        return None
    if base == 'FP':
        code, end = _codes(lines, i, 3)
        if code and code[2] == 'CAL ADDSP':
            low = re.fullmatch(r'LAI (\d+)D', code[0]);high = re.fullmatch(r'LBI (\d+)D', code[1])
            if low and high:
                return 'adjust', _signed(int(low[1]) | int(high[1]) << 8), end
        if text == 'CAL ENTER':
            return 'enter', 0, i + 1
        if text == 'JMP LEAVE':
            return 'leave', 0, i + 1
    return None


def anchor_frames(block, data):
    from native8008 import graph, register_liveness, liveness, registers
    function = next((l.strip().split()[2] for l in block if l.strip().startswith('; function ')), None)
    if not function or not any(l.strip() == 'JMP ' + function for l in block):
        return block
    entry = next((i for i, l in enumerate(block) if l.strip() == function + ':'), None)
    if entry is None:
        return block
    first = next(i for i in range(entry + 1, len(block)) if _executable(block[i]))
    base = 'FP' if block[first].strip() == 'CAL ENTER' else 'RSP'
    nodes = [(line, None) for line in block]
    successors = graph(nodes, data)
    live = register_liveness(nodes, successors)
    block = _byte_holders(block, live, registers)
    nodes = [(line, None) for line in block]
    successors = graph(nodes, data)
    live = register_liveness(nodes, successors)
    flags = liveness(nodes, successors)[1]
    # The entry check writes A, D, H, L and flags before the first
    # instruction; ACK's inline ENTER also writes C and E. A self-recursive
    # function receives its arguments on the RAM stack, so registers carry
    # nothing in (helper calls modeled as reading everything make them
    # appear live); only the first instruction must not read them.
    if base == 'RSP' and registers(block[first].strip())[0] & (A | D | H | L):
        return block
    labels = {l.strip()[:-1] for l in block if l.strip().endswith(':')}
    preds = [[] for _ in block]
    for p, targets in enumerate(successors):
        for target in targets:
            preds[target].append(p)
    forms = {};covered = set()
    for i in range(len(block)):
        if i in covered:
            continue
        found = _form(block, i, base)
        if found:
            forms[i] = found
            if found[0] in ('args', 'slot', 'adjust'):
                covered.update(range(i + 1, found[2]))

    # Depth of RSP below the anchor. ACK's anchor is the FP set by ENTER.
    start = first + 1 if base == 'FP' else first
    returns = {}
    for i, line in enumerate(block):
        match = re.search(r'LAI LOW \(([^)]+)\)', line)
        if match and match[1] in labels:
            call = next((k for k in range(i + 1, min(i + 24, len(block)))
                         if block[k].strip().startswith('JMP ') and
                         (block[k].strip().split()[1] not in labels or
                          block[k].strip().split()[1] == function)), None)
            if call is not None:
                returns[match[1]] = call
    depth = [UNSET] * len(block);out = [UNSET] * len(block)
    changed = True
    while changed:
        changed = False
        for i in range(len(block)):
            text = block[i].strip()
            if i == start:
                value = 0
            elif text.endswith(':') and text[:-1] in returns:
                # The callee pops the return word: two bytes shallower.
                before = depth[returns[text[:-1]]]
                value = before - 2 if isinstance(before, int) else before
            elif i <= first or not preds[i]:
                value = None if i <= first or text.endswith(':') else UNSET
            else:
                incoming = [out[p] for p in preds[i] if out[p] is not UNSET]
                value = (UNSET if not incoming else None if None in incoming or
                         len(set(incoming)) > 1 else incoming[0])
            result = value
            if isinstance(value, int):
                kind = forms[i][0] if i in forms else None
                if kind == 'adjust':
                    result = value - forms[i][1]
                elif kind == 'args':
                    result = value + forms[i][1]
                elif kind == 'other':
                    result = None
                elif text == 'CAL PUSH':
                    result = value + 2
                elif text == 'CAL POP':
                    result = value - 2
                elif _executable(text) and text.split()[0] == 'CAL' and i not in covered:
                    result = None
            if (depth[i], out[i]) != (value, result):
                changed = True
                depth[i], out[i] = value, result

    sites = {}
    for i, (kind, value, end) in forms.items():
        d = depth[i]
        if kind in ('other', 'enter'):
            continue
        if not isinstance(d, int) and not (kind == 'address' and base == 'FP') and kind not in ('slot', 'leave'):
            continue
        last = end - 1
        while not _executable(block[last]):
            last -= 1
        if kind == 'address':
            r = value - d if base == 'RSP' else value
            dead, spans = A | E, [r, r + 1]
        elif kind == 'zero':
            dead, spans = A | E, [-d, -d + 1]
        elif kind == 'adjust':
            dead, spans = A | H | L, [-d, value - d]
        elif kind == 'args':
            # Stored-argument sequences (ack/codegen.py) leave only scratch in
            # A, C/D (the slot pointer, replaced in every slot), H and L.
            dead, spans = 0, [-d, -d - value]
        elif kind == 'slot':
            dead, spans = 0, []
        else:  # leave
            dead, spans = 0, [0, 4]
        if live[last] & dead or (flags[last] and kind not in ('leave', 'args', 'slot')):
            continue
        sites[i] = (kind, value, d, end, spans)
    # A slot converts only with its block, whose depth fixes its address.
    block_of = {};members = {};current = None
    for i, line in enumerate(block):
        text = line.strip()
        if text.startswith('; argument block'):
            current = i if forms.get(i, ('',))[0] == 'args' else None
            if current is not None:
                members[i] = []
        elif text.startswith('; argument slot') and current is not None:
            # An unrecognized slot (no form) blocks its whole block.
            block_of[i] = current;members[current].append(i)
    for head, slots in members.items():
        # All or nothing: unconverted slots would still read the CD pointer.
        if head not in sites or any(slot not in sites for slot in slots) or not slots:
            for index in [head] + slots:
                sites.pop(index, None)
    for i in [i for i in sites if sites[i][0] == 'slot' and i not in block_of]:
        sites.pop(i)
    if not any(kind in ('address', 'zero') for kind, *_ in sites.values()):
        return block
    if base == 'FP':
        sites[first] = ('enter', 0, 0, first + 1, [0, 1, 2, 3])

    uses = {}
    for line in block:
        parts = line.strip().split()
        if len(parts) == 2 and parts[0][0] == 'J':
            uses[parts[1]] = uses.get(parts[1], 0) + 1
    drop = set();spans = [s for site in sites.values() for s in site[4]]
    def following(k, count):
        found = []
        while k < len(block) and len(found) < count:
            if block[k].strip() and not block[k].strip().startswith(';'):
                found.append(k)
            k += 1
        return found
    def fixup(k):
        # Indices of a JFC/JFZ + INH/DCH page fix-up starting at k, if any.
        index = following(k, 3)
        if len(index) < 3:
            return None
        jump, step, label = (block[x].strip() for x in index)
        parts = jump.split()
        if (len(parts) == 2 and parts[0] in ('JFC', 'JFZ') and step in ('INH', 'DCH') and
                label == parts[1] + ':' and uses.get(parts[1]) == 1 and not flags[index[2]]):
            return index[:2]
        return None
    # Page fix-ups after in-page addresses are dead weight in the copy:
    # INL/JFZ/INH after a word's low byte, and register-cached frame steps.
    for i, (kind, value, d, end, _) in sites.items():
        if kind != 'address':
            continue
        for k in following(end, 5):
            text = block[k].strip()
            if text == 'INL':
                found = fixup(k + 1)
                if found:
                    drop.update(found)
                break
            if registers(text)[1] & (H | L) or text.endswith(':') or _control(text.split()[0]):
                break
    for i, line in enumerate(block):
        match = re.fullmatch(r'; cached frame address (RSP|FP)\+(\d+)', line.strip())
        if not match or match[1] != base or not isinstance(depth[i], int):
            continue
        offset = _signed(int(match[2])) - (depth[i] if base == 'RSP' else 0)
        index = following(i + 1, 3)
        texts = [block[k].strip() for k in index]
        if len(texts) == 3 and texts[0] == 'LAL' and re.fullmatch(r'(ADI|SUI) \d+D', texts[1]) and texts[2] == 'LLA':
            found = fixup(index[2] + 1)
        elif texts and texts[0] == 'INL':
            k = index[0]
            while block[k].strip() == 'INL':
                k += 1
            found = fixup(k)
        else:
            found = None
        if found:
            drop.update(found)
            spans += [offset, offset + 1]
    low, high = min(spans), max(spans)
    if high - low > 220 or high > 254 or low < -255:
        return block

    # D validity in the copy: a must analysis over the original CFG.
    def kills(i):
        text = block[i].strip()
        if not _executable(text):
            return False
        if registers(text)[1] & D:
            return True
        parts = text.split()
        return parts[0] == 'JMP' and (parts[1] not in labels | {'JUMPAB'} or parts[1] == function)
    roots = {i for i in range(len(block)) if block[i].strip().endswith(':') and not preds[i]}
    # Lines inside a converted site are replaced; unconverted forms keep
    # their own D writes.
    inside = {k for i, site in sites.items() for k in range(i + 1, site[3])}
    # Greatest fixed point: start valid everywhere and only remove validity.
    valid = [True] * len(block);incoming = [True] * len(block)
    changed = True
    while changed:
        changed = False
        for i in range(len(block)):
            if i == first or i == start:
                value = True
            elif i in roots or not preds[i]:
                value = False
            else:
                value = all(valid[p] for p in preds[i])
            if i in sites:
                kind = sites[i][0]
                if kind == 'slot':
                    value_out = True  # inside its converted block
                elif kind == 'args':
                    value_out = True
                elif kind == 'leave':
                    value_out = False
                else:
                    value_out = value or not live[i] & D  # a reload makes it valid
            elif i in inside:
                value_out = value
            else:
                value_out = value and not kills(i)
            if incoming[i] != value or valid[i] != value_out:
                incoming[i], valid[i], changed = value, value_out, True

    tables = {}
    referenced = set(re.findall(r'(?:LOW|HIGH) \(([A-Za-z_$][\w$]*)', '\n'.join(block)))
    for index, line in enumerate(data):
        name = line.strip()[:-1] if line.strip().endswith(':') else None
        if name not in referenced or name in labels:
            continue
        end = index + 1
        while end < len(data) and data[end].strip().startswith(('DW ', 'DB ')):
            end += 1
        entries = data[index + 1:end]
        if any(set(re.findall(r'[A-Za-z_$][\w$]*', e.strip()[3:])) & labels for e in entries):
            tables[name] = entries
    renamed = labels | set(tables)
    pattern = re.compile(r'\b(' + '|'.join(map(re.escape, sorted(renamed, key=len, reverse=True))) + r')\b')
    rename = lambda text: pattern.sub(lambda m: m[1] + '_A' if m[1] != function else m[1], text)
    page = '        LHI %dD' % PAGE

    def reload(d):
        code = ['        LHI HIGH ' + base, '        LLI LOW ' + base, '        LAM']
        if base == 'RSP' and d & 255:
            code.append('        ADI %dD' % (d & 255))
        return code + ['        LDA']

    copy = [];i = 0;blocks = {}
    while i < len(block):
        line = block[i]
        if i in sites:
            kind, value, d, end, _ = sites[i]
            if kind == 'enter':
                # D holds the new FP's low byte from the entry check.
                copy += ['        ; anchored ENTER', '        LHI HIGH FP', '        LLI LOW FP',
                         '        LCM', '        INL', '        LEM', '        LHI HIGH RSP',
                         '        LLI LOW RSP', '        LAD', '        LMA', '        LLD', page,
                         '        LMC', '        INL', '        LME', '        LHI HIGH FP',
                         '        LLI LOW FP', '        LMD', '        INL', '        LMI %dD' % PAGE]
                i = end;continue
            if kind == 'slot':
                r = blocks[block_of[i]] + value
                copy += ['        ; anchored argument slot %+d' % r, '        LEA', '        LAD',
                         '        ADI %dD' % (r & 255), '        LLA', page, '        LME',
                         '        INL', '        LMB']
                i = end;continue
            if kind == 'leave':
                code = [] if incoming[i] else reload(0)
                copy += ['        ; anchored LEAVE'] + code + [
                    '        LAD', '        ADI 4D', '        LHI HIGH RSP', '        LLI LOW RSP',
                    '        LMA', '        INL', '        LMI %dD' % PAGE, '        LLD', page,
                    '        LCM', '        INL', '        LEM', '        INL', '        LAM',
                    '        INL', '        LBM', '        LHI HIGH FP', '        LLI LOW FP',
                    '        LMC', '        INL', '        LME', '        JMP JUMPAB']
                i = end;continue
            if kind == 'args':
                r = -d - value;blocks[i] = r
                code = [] if incoming[i] else reload(d)
                copy += ['        ; anchored argument block %+d' % r, '        LEA'] + code + [
                    '        LAD', '        ADI %dD' % (r & 255), '        LHI HIGH RSP',
                    '        LLI LOW RSP', '        LMA', '        LAD',
                    '        ADI %dD' % ((r + value - 2) & 255), '        LLA', page,
                    '        LME', '        INL', '        LMB']
                i = end;continue
            if not incoming[i] and live[i] & D:
                copy += [rename(l) for l in block[i:end]];i = end;continue
            code = [] if incoming[i] else reload(d if isinstance(d, int) else 0)
            if kind == 'adjust':
                r = value - d
                copy += ['        ; anchored stack adjust %+d' % r] + code + [
                    '        LAD', '        ADI %dD' % (r & 255), '        LHI HIGH RSP',
                    '        LLI LOW RSP', '        LMA']
                if base == 'FP':
                    copy += ['        LLA', page]  # ADDSP returns HL = RSP
            else:
                r = (value - d if base == 'RSP' else value) if kind == 'address' else -d
                copy += ['        ; anchored frame address %+d' % r] + code + [
                    '        LAD', '        ADI %dD' % (r & 255), '        LLA', page]
            i = end;continue
        if line.strip().startswith('; function ') or i in drop:
            i += 1;continue
        copy.append(function + '_A:' if line.strip() == function + ':' else rename(line));i += 1
    copy = _saved_addresses(copy, registers)

    fast, slow = function + '_A', function + '_S'
    check = ['        LHI HIGH RSP', '        LLI LOW RSP', '        LAM']
    if base == 'FP':
        # ENTER will push the old FP: the new FP is RSP-2.
        check += ['        SUI 2', '        JTC ' + slow]
    if low < 0:
        check += ['        CPI %dD' % -low, '        JTC ' + slow]
    check += ['        CPI %dD' % (255 - high), '        JFC ' + slow,
              '        LDA', '        INL', '        LAM', '        CPI %dD' % PAGE,
              '        JTZ ' + fast, slow + ':']
    output = []
    for i, line in enumerate(block):
        if i == first:
            output += check
        output.append(line)
    for name, entries in tables.items():
        data += [name + '_A_ALIGN:', '        ORG (%s_A_ALIGN+1) AND 0FFFEH' % name, name + '_A:']
        data += [rename(entry) for entry in entries]
    return output + copy


def _byte_holders(block, live, registers):
    """Hold a stored byte in E rather than D, keeping D for the anchor.

    `LDA; Y; LMD` where straight-line Y neither reads nor writes D or E,
    with E dead after LDA and D dead after LMD, becomes `LEA; Y; LME`.
    """
    block = list(block)
    uses = {}
    for line in block:
        parts = line.strip().split()
        if len(parts) == 2 and parts[0][0] == 'J':
            uses[parts[1]] = uses.get(parts[1], 0) + 1
    for i, line in enumerate(block):
        if line.strip() != 'LDA' or live[i] & E:
            continue
        j = i + 1;pending = set()
        while j < len(block):
            text = block[j].strip()
            if text == 'LMD':
                break
            if text.endswith(':'):
                # Only the target of a single forward jump inside the span.
                if text[:-1] not in pending:
                    j = len(block);break
                pending.discard(text[:-1])
            elif text and not text.startswith(';'):
                read, write = registers(text)
                parts = text.split()
                if (len(parts) == 2 and parts[0][0] == 'J' and parts[0] != 'JMP' and
                        uses.get(parts[1]) == 1):
                    pending.add(parts[1])
                elif _control(parts[0]) or (read | write) & (D | E):
                    j = len(block);break
            j += 1
        if pending:
            continue
        if j < len(block) and not live[j] & D:
            block[i] = line.replace('LDA', 'LEA');block[j] = block[j].replace('LMD', 'LME')
    return block


def _saved_addresses(lines, registers):
    """Keep a saved store address in E/B instead of SADDR across a load.

    `LHI HIGH SADDR; LLI LOW SADDR; LMA; INL; LMB; Y; LCA; LHI HIGH SADDR;
    LLI LOW SADDR; LEM; INL; LHM; LLE; LAC; LMA` with straight-line Y that
    writes neither B nor E is `LEA; Y; LCA; LHB; LLE; LMA`.
    """
    store = ['LHI HIGH SADDR', 'LLI LOW SADDR', 'LMA', 'INL', 'LMB']
    load = ['LCA', 'LHI HIGH SADDR', 'LLI LOW SADDR', 'LEM', 'INL', 'LHM', 'LLE', 'LAC', 'LMA']
    output = [];i = 0
    while i < len(lines):
        if [l.strip() for l in lines[i:i + 5]] == store:
            j = i + 5;ok = True
            while j < len(lines) and [l.strip() for l in lines[j:j + 9]] != load:
                text = lines[j].strip()
                if text and not text.startswith(';'):
                    if (text.endswith(':') or _control(text.split()[0]) or 'SADDR' in text or
                            registers(text)[1] & (B | E)):
                        ok = False;break
                j += 1
            if ok and j < len(lines):
                output += ['        LEA'] + lines[i + 5:j] + ['        LCA', '        LHB', '        LLE', '        LMA']
                i = j + 9;continue
        output.append(lines[i]);i += 1
    return output
