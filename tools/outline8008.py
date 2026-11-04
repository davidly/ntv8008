"""Selective post-optimization outlining with unchanged register/flag results."""
import re
from collections import Counter

RETURN_STORE = ('        LHI HIGH RV\n        LLI LOW RV\n        LMA\n'
                '        INL\n        LMB\n        JMP LEAVE')


def share_return_values(application):
    # One occurrence only moves seven bytes rather than saving any space.
    if application.count(RETURN_STORE) < 2:
        return application
    return application.replace(RETURN_STORE, '        JMP LEAVEVALUE')


def outline_frame_loads(application, base, minimum_sites=8):
    """Outline long loads only outside back-edge spans and recursive functions.

    This is a conservative static selection, not a claim of measured coldness.
    Eight 17-byte sites replaced by seven-byte call sites cover the 15-byte
    helper with at least 65 bytes saved for each selected width.
    """
    functions = list(re.finditer(r'^\s*; function (\S+)\s*$', application, re.M))
    bodies = {}
    for i, match in enumerate(functions):
        end = functions[i + 1].start() if i + 1 < len(functions) else len(application)
        bodies[match[1]] = (match.start(), application[match.start():end])
    calls = {name: set(re.findall(r'^\s*JMP (\S+)', body, re.M)) & bodies.keys()
             for name, (_, body) in bodies.items()}
    recursive = set()
    for name in bodies:
        pending = list(calls[name]); seen = set()
        while pending:
            target = pending.pop()
            if target == name:
                recursive.add(name)
                break
            if target not in seen:
                seen.add(target); pending.extend(calls[target] - seen)
    pattern = re.compile(
        r'        LHI HIGH '+base+r'\n        LLI LOW '+base+
        r'\n        LAM\n        ADI ([^\n]+)\n        LEA\n        INL\n'
        r'        LAM\n        ACI ([^\n]+)\n        LHA\n        LLE\n'
        r'        LAM\n        (LBI 0|INL\n        LBM)')
    candidates = []
    for name, (start, body) in bodies.items():
        if name in recursive:
            continue
        labels = {m[1]: m.start() for m in re.finditer(r'^([\w.$?]+):', body, re.M)}
        spans = []
        for branch in re.finditer(r'^\s*(?:JMP|J[TF][CZSP]) (\S+)', body, re.M):
            target = labels.get(branch[1])
            if target is not None and target <= branch.start():
                spans.append((target, branch.end()))
        for match in pattern.finditer(body):
            if any(lo <= match.start() <= hi for lo, hi in spans):
                continue
            width = 1 if match[3] == 'LBI 0' else 2
            candidates.append((start + match.start(), start + match.end(),
                               width, match[1], match[2]))
    counts = Counter(item[2] for item in candidates)
    selected = [item for item in candidates if counts[item[2]] >= minimum_sites]
    for start, end, width, low, high in sorted(selected, reverse=True):
        application = (application[:start] + f'        LAI {low}\n        LBI {high}\n'
                       f'        CAL NATIVE_FRAME_LOAD{width}' + application[end:])
    helpers = []
    for width in sorted({item[2] for item in selected}):
        helpers.append(f'''NATIVE_FRAME_LOAD{width}: LHI HIGH {base}
        LLI LOW {base}
        ADM
        LEA
        INL
        LAB
        ACM
        LHA
        LLE
        LAM
'''+('        LBI 0\n' if width == 1 else '        INL\n        LBM\n')+'        RET\n')
    return application, '\n'.join(helpers)
