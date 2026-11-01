#!/usr/bin/env python3
"""Refresh native build metadata from the pinned, completed Unix ACK build.

Only build metadata is published. Native Windows setup uses this recipe and
regenerates all C/parser/table outputs itself; it never runs this exporter.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import shlex
from bootstrap import REVISION

HERE = Path(__file__).resolve().parent
TARGETS = {
    'em_cemcom.ansi': '.obj/lang/cem/cemcom.ansi/+cemcom/cemcom',
    'cpp.ansi': '.obj/lang/cem/cpp.ansi/+cpp.ansi/cpp.ansi',
    'em_opt': '.obj/util/opt/+em_opt/em_opt',
    'em_opt2': '.obj/util/opt/+em_opt2/em_opt2',
    'em_decode': '.obj/util/misc/+em_decode/em_decode',
    'em_pc': '.obj/lang/pc/comp/+em_pc/em_pc',
    'em_m2': '.obj/lang/m2/comp/+em_m2/em_m2',
    'em_bem': '.obj/lang/basic/src/+em_bem/em_bem',
    'em_occam': '.obj/lang/occam/comp/+em_occam/em_occam',
    'LLgen': '.obj/util/LLgen/+LLgen/LLgen',
    'tabgen': '.obj/util/cmisc/+tabgen/tabgen',
    'mktab': '.obj/util/opt/+mktab/mktab',
}


def export(source, destination):
    graph, records = {}, []
    lines = (source / '.obj/build.ninja').read_text().splitlines()
    for index, line in enumerate(lines):
        if not line.startswith('build '):
            continue
        left, right = line[6:].split(' :', 1)
        outputs = [str(PurePosixPath(p)) for p in left.split()]
        dependencies = [str(PurePosixPath(p)) for p in right.split()[1:]]
        for output in outputs:
            graph[output] = dependencies
        if ':rule' in line:
            command = lines[index + 1].strip().split('command=', 1)[1].strip()
            if command.startswith('sh '):
                command = (source / command[3:]).read_text()
            commands = [c for c in re.findall(r'\(cd [^ ]+ && (.*?) \)', command, re.S)
                        if not c.startswith('mkdir ')]
            records.append({'outs': outputs, 'deps': dependencies, 'commands': commands})
    needed = set()

    def visit(node):
        if node not in needed:
            needed.add(node)
            for dependency in graph.get(node, []):
                visit(dependency)

    for node in TARGETS.values():
        visit(node)
    groups, group_ids, units = [], {}, {}
    for entry in json.loads((source / '.obj/compile_commands.json').read_text()):
        args = shlex.split(entry['command'])
        if '-o' not in args or '-c' not in args:
            continue
        target = args[args.index('-o') + 1]
        if target not in needed:
            continue
        includes = [a[2:] for a in args if a.startswith('-I')]
        defines = [a[2:].replace('\\"', '"') for a in args if a.startswith('-D')]
        key = json.dumps([includes, defines])
        if key not in group_ids:
            group_ids[key] = len(groups)
            groups.append({'includes': includes, 'defines': defines, 'deps': set()})
        group = group_ids[key]
        groups[group]['deps'].update(d for d in graph[target] if not d.endswith('.c'))
        units[target] = [entry['file'], group]
    for group in groups:
        group['deps'] = sorted(group['deps'])
    libraries = {p: [d for d in graph[p] if d.endswith('.o')]
                 for p in sorted(needed) if p.endswith('.a')}
    programs = {p: [d for d in graph[p] if d.endswith(('.o', '.a'))] for p in TARGETS.values()}
    rules = [r for r in records if any(p in needed for p in r['outs'])
             and not r['outs'][0].endswith(('.o', '.a'))
             and not any(p in TARGETS.values() for p in r['outs'])]
    if not all(r['commands'] for r in rules):
        raise ValueError('unrecognized generator rule; review upstream build changes')
    plan = {'revision': REVISION, 'groups': groups, 'units': units,
            'libraries': libraries, 'programs': programs, 'targets': TARGETS, 'rules': rules}
    destination.write_text(json.dumps(plan, indent=2) + '\n')
    print('Recorded', len(units), 'C units and', len(rules), 'generator rules.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=HERE / 'build/src/ack')
    parser.add_argument('--output', type=Path, default=HERE / 'msvc/recipe.json')
    args = parser.parse_args()
    export(args.source, args.output)
