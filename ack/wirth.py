"""Shared freestanding ACK Wirth-language runtime linker."""
import re
from codegen import CodegenError

def trim_runtime(program, units):
    """Link only reachable support procedures; don't pull a hosted libpc in."""
    pattern = re.compile(r'^ pro ([^,]+),[^\n]*\n.*?^ end[^\n]*(?:\n|$)', re.M | re.S)
    functions = {}
    for unit in units:
        for match in pattern.finditer(unit):
            if match[1] in functions:
                raise CodegenError('duplicate support function: ' + match[1])
            functions[match[1]] = match[0]
    needed = set(re.findall(r'\b(?:cal|lpi) (\$[^\s,]+)', program))
    # Array operations lower to these ordinary C support functions.
    for op in ('aar','lar','sar'):
        if re.search(r'^ ' + op + r' ', program, re.M):
            needed.add('$_pc_' + op)
    visited = set()
    while needed - visited:
        name = (needed-visited).pop()
        visited.add(name)
        if name in functions:
            needed.update(re.findall(r'\b(?:cal|lpi) (\$[^\s,]+)', functions[name]))
    return [pattern.sub(lambda m: m[0] if m[1] in visited else '', unit) for unit in units]


def lower_fixed_arrays(program):
    """Specialize array operations whose descriptor is an immutable EM ROM.

    The EM stack contains [value,] base, index, descriptor. With checks
    disabled, the address is base + (index - lower_bound) * element_size.
    Leave dynamic descriptors and unsupported scalar widths to the runtime.
    """
    lines = program.splitlines()
    descriptors = {}
    for index, label in enumerate(lines):
        if not label or label.startswith(' ') or label.isdigit():
            continue
        words = []
        for line in lines[index+1:]:
            match = re.fullmatch(r' rom (.*)', line)
            if not match:
                break
            for item in match[1].split(','):
                word = re.fullmatch(r'(-?\d+)(?:[IU]2)?', item.strip())
                if not word:
                    break
                words.append(int(word[1]) & 65535)
            else:
                continue
            break
        if len(words) == 3 and words[2] > 0:
            descriptors[label] = words
    output = []
    index = 0
    while index < len(lines):
        address = re.fullmatch(r' lae (\S+)', lines[index])
        operation = (re.fullmatch(r' (aar|lar|sar) 2', lines[index+1])
                     if index+1 < len(lines) else None)
        descriptor = descriptors.get(address[1]) if address else None
        if descriptor and operation and (operation[1] == 'aar' or descriptor[2] in (1,2)):
            lower, _, stride = descriptor
            if lower:
                output += [f' loc {lower}', ' sbu 2']
            if stride == 2:
                output += [' dup 2', ' adu 2']
            elif stride != 1:
                output += [f' loc {stride}', ' mlu 2']
            output.append(' ads 2')
            if operation[1] != 'aar':
                output.append((' loi ' if operation[1] == 'lar' else ' sti ') + str(stride))
            index += 2
        else:
            output.append(lines[index])
            index += 1
    return '\n'.join(output) + '\n'
