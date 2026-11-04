"""Conservatively retain reachable 8008 assembly runtime blocks.

Application code/data is never removed. Its symbolic references seed the runtime
graph, including addresses stored in tables or loaded for indirect calls.
"""
import re

LABEL = re.compile(r'^\s*([A-Za-z_.$?][A-Za-z_0-9.$?]*):')
EQU = re.compile(r'^\s*[A-Za-z_.$?][A-Za-z_0-9.$?]*\s+EQU\b', re.I)
TOKEN = re.compile(r'[A-Za-z_.$?][A-Za-z_0-9.$?]*')
DATA = {'DB', 'DW', 'DATA', 'DS'}
TERMINAL = {'JMP', 'RET', 'HLT'}


def statement(line):
    # Ignore comments and literal contents when finding symbolic references.
    return re.sub(r'"[^"\n]*"|\'[^\'\n]*\'|;.*', ' ', line)


def prune_runtime(runtime, application):
    blocks = [('', [])]
    for line in runtime.splitlines():
        match = LABEL.match(statement(line))
        if match:
            blocks.append((match[1], []))
        blocks[-1][1].append(line)
    labels = {name.upper(): index for index, (name, _) in enumerate(blocks) if name}

    def references(text):
        return {labels[token.upper()] for token in TOKEN.findall(text)
                if token.upper() in labels}

    # EQU declarations occupy no bytes and remain available even when the code
    # surrounding their original position is removed. Retain their dependencies.
    roots = {0} | references('\n'.join(map(statement, application.splitlines())))
    edges = []
    for index, (_, lines) in enumerate(blocks):
        statements = [statement(line) for line in lines]
        for line, text in zip(lines, statements):
            if EQU.match(text):
                roots.update(references(text))
        refs = references('\n'.join(statements))
        operations = []
        for text in statements:
            if EQU.match(text):
                continue
            text = LABEL.sub('', text, count=1).strip()
            if text:
                operations.append(text.split()[0].upper())
        # Conditional returns and calls can fall through. A data object does
        # not execute its following object, but consecutive data blocks stay
        # together to accommodate tables with interior labels/offset accesses.
        following_data = False
        if index + 1 < len(blocks):
            for line in blocks[index + 1][1]:
                text = LABEL.sub('', statement(line), count=1).strip()
                if text and not EQU.match(text):
                    following_data = text.split()[0].upper() in DATA
                    break
        if index + 1 < len(blocks) and (
                not operations or operations[-1] not in TERMINAL | DATA or
                operations[-1] in DATA and following_data):
            refs.add(index + 1)
        edges.append(refs)
    live = set()
    pending = list(roots)
    while pending:
        index = pending.pop()
        if index in live:
            continue
        live.add(index)
        pending.extend(edges[index] - live)
    return '\n'.join(line for index, (_, lines) in enumerate(blocks)
                     for line in lines if index in live or EQU.match(statement(line))) + '\n'
