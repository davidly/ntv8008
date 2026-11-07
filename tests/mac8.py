#!/usr/bin/env python3
"""Assemble with the recovered Intel MAC8 assembler, then execute real 8008 code."""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plm8'))
spec = importlib.util.spec_from_file_location('plm8_mac8', ROOT / 'plm8/mac8.py')
mac8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mac8)
import pdp10  # noqa: E402
HOST = ROOT / ('ntv8008.exe' if os.name == 'nt' else 'ntv8008')

REGISTERS = 'ABCDEHLM'
# a08's 1972 condition letters and ALU prefixes, and MAC8's 8080-style names.
CONDITIONS = {'FC': 'NC', 'FZ': 'NZ', 'FS': 'P', 'FP': 'PO', 'TC': 'C', 'TZ': 'Z', 'TS': 'M', 'TP': 'PE'}
ALU = {'AD': 'ADD', 'AC': 'ADC', 'SU': 'SUB', 'SB': 'SBB', 'ND': 'ANA', 'XR': 'XRA', 'OR': 'ORA', 'CP': 'CMP'}
IMMEDIATE = {'ADI': 'ADI', 'ACI': 'ACI', 'SUI': 'SUI', 'SBI': 'SBI', 'NDI': 'ANI', 'XRI': 'XRI', 'ORI': 'ORI', 'CPI': 'CPI'}
FIXED = {'RET': 'RET', 'RLC': 'RLC', 'RRC': 'RRC', 'RAL': 'RAL', 'RAR': 'RAR', 'JMP': 'JMP', 'CAL': 'CALL',
         'INP': 'IN', 'OUT': 'OUT', 'ORG': 'ORG', 'END': 'END', 'DATA': 'DB', 'NOP': 'MOV A,A'}
# Operators and directives; a label named IF would open conditional assembly.
RESERVED = set(REGISTERS) | {'SHR', 'SHL', 'AND', 'OR', 'XOR', 'NOT', 'MOD', 'IF', 'ENDIF', 'MACRO', 'ENDM',
                             'EQU', 'SET', 'ORG', 'END', 'DB', 'DW', 'DS', 'MOV', 'MVI', 'INR', 'DCR', 'RST', 'HLT', 'IN',
                             'CALL'} | set(ALU.values()) | set(IMMEDIATE.values()) | set(FIXED.values()) | {
                             p + c for p in 'JCR' for c in CONDITIONS.values()}


def split_comment(line):
    quote = None
    for index, character in enumerate(line):
        if quote:
            quote = None if character == quote else quote
        elif character in '"\'':
            quote = character
        elif character == ';':
            return line[:index]
    return line


def a08_instruction(op):
    """Return the MAC8 mnemonic and any register operands for an a08 opcode."""
    if op in FIXED:
        return FIXED[op], ''
    if op == 'HLT':
        return 'DB', '0FFH'  # a08 encodes HLT as FF; MAC8 HLT is 00
    if op in IMMEDIATE:
        return IMMEDIATE[op], ''
    if len(op) == 3 and op[0] == 'L' and op[1] in REGISTERS and op[2] in REGISTERS + 'I':
        return ('MVI', op[1]) if op[2] == 'I' else ('MOV', op[1] + ',' + op[2])
    if len(op) == 3 and op[:2] in ('IN', 'DC') and op[2] in REGISTERS:
        return ('INR' if op[:2] == 'IN' else 'DCR'), op[2]
    if len(op) == 3 and op[:2] in ALU and op[2] in REGISTERS:
        return ALU[op[:2]], op[2]
    if len(op) == 3 and op[0] in 'JCR' and op[1:] in CONDITIONS:
        return op[0] + CONDITIONS[op[1:]], ''
    raise ValueError(f'unsupported a08 opcode {op}')


def translate_a08(text):
    """Translate this project's a08 sources (octal default radix) to MAC8."""
    parsed = []
    for line in text.splitlines():
        code = split_comment(line).rstrip()
        label = ''
        if code and not code[0].isspace():
            label, code = re.match(r'([A-Z_][A-Z0-9_]*):?\s*(.*)', code).groups()
        fields = code.split(None, 1)
        parsed.append((label, fields[0] if fields else '', fields[1].strip() if len(fields) > 1 else ''))
    # MAC8 keeps five significant characters; give every symbol a unique short name.
    names, used = {}, set(RESERVED)
    for label in sorted({label for label, _, _ in parsed if label}):
        short, serial = label.replace('_', '')[:5], 0
        while short in used:
            serial += 1
            short = label.replace('_', '')[:5 - len(str(serial))] + str(serial)
        used.add(short)
        names[label] = short

    def number(match):
        token = match.group(0)
        if token[0] == "'":
            return str(ord(token[1]))
        if '#' in token:  # a08's page#offset notation, both octal
            page, offset = token.split('#')
            return str(int(page, 8) * 256 + int(offset, 8))
        if token[-1] == 'D':
            return token[:-1]
        if token[-1] == 'H':
            return str(int(token[:-1], 16))
        return str(int(token, 8))

    def term(text):
        text = re.sub(r"'.'|\b[0-9][0-9A-F]*#[0-7]+|\b[0-9][0-9A-F]*H\b|\b[0-9]+D?\b", number, text)
        return re.sub(r'\b[A-Z_][A-Z0-9_]*\b', lambda m: names.get(m.group(0), m.group(0)), text)

    def expression(text):
        text = text.strip()
        # a08's HIGH and LOW apply to the rest of the expression.
        match = re.search(r'\b(HIGH|LOW)\s+', text)
        if not match:
            return term(text)
        rest = term(text[match.end():])
        return term(text[:match.start()]) + ('((%s) SHR 8)' if match.group(1) == 'HIGH' else '((%s) AND 255)') % rest

    def data(item):
        item = item.strip()
        if len(item) >= 2 and item[0] in '"\'' and item[-1] == item[0]:
            body = item[1:-1]
            if body and all(' ' <= c <= 'Z' and c != "'" for c in body):
                return ["'" + body + "'"]
            return [str(ord(c)) for c in body]
        return [expression(item)]

    lines = []
    for label, op, operands in parsed:
        prefix = (names[label] + ':') if label else ''
        if not op:
            lines.append(prefix)
            continue
        if op == 'EQU':
            lines.append(f'{names[label]:<8}EQU {expression(operands)}')
            continue
        if op == 'DATA':
            items = sum((data(item) for item in re.findall(r'"[^"]*"|\'[^\']*\'|[^,]+', operands)), [])
            group = []
            for item in items:  # MAC8 ignores columns past 72
                if group and len(f'{prefix:<8}DB ' + ','.join(group + [item])) > 72:
                    lines.append(f'{prefix:<8}DB ' + ','.join(group))
                    prefix, group = '', []
                group.append(item)
            lines.append(f'{prefix:<8}DB ' + ','.join(group))
            continue
        if op == 'RST':  # a08 accepts a vector number or address
            value = expression(operands)
            lines.append(f'{prefix:<8}RST ' + (value if re.fullmatch(r'[0-7]', value) else f'({value})/8'))
            continue
        mnemonic, registers = a08_instruction(op)
        if operands:
            operands = expression(operands)
        operand = ','.join(part for part in (registers, operands) if part)
        lines.append(f'{prefix:<8}{mnemonic} {operand}'.rstrip())
    return '\n'.join(lines) + '\n'


def image(text):
    memory = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(':'):
            raw = bytes.fromhex(line[1:])
            if raw[3] == 0:
                address = int.from_bytes(raw[1:3], 'big')
                memory.update((address + i, b) for i, b in enumerate(raw[4:4 + raw[0]]))
    return memory


def opcode_table():
    """Every 8008 instruction in MAC8 syntax, with its encoding."""
    table = []
    for d, destination in enumerate(REGISTERS):
        for s, source in enumerate(REGISTERS):
            if d != 7 or s != 7:
                table.append((f'MOV {destination},{source}', [0o300 | d << 3 | s]))
        table.append((f'MVI {destination},5AH', [0o006 | d << 3, 0x5A]))
    for d in range(1, 7):
        table += [(f'INR {REGISTERS[d]}', [d << 3]), (f'DCR {REGISTERS[d]}', [d << 3 | 1])]
    for p, (register_op, immediate) in enumerate(zip(ALU.values(), IMMEDIATE.values())):
        table += [(f'{register_op} {source}', [0o200 | p << 3 | s]) for s, source in enumerate(REGISTERS)]
        table.append((f'{immediate} 0A5H', [0o004 | p << 3, 0xA5]))
    table += [(name, [0o002 | k << 3]) for k, name in enumerate(('RLC', 'RRC', 'RAL', 'RAR'))]
    table += [('JMP 1234H', [0o104, 0x34, 0x12]), ('CALL 2345H', [0o106, 0x45, 0x23]), ('RET', [0o007]), ('HLT', [0])]
    for c, false in enumerate(('NC', 'NZ', 'P', 'PO')):
        true = ('C', 'Z', 'M', 'PE')[c]
        table += [(f'J{false} 0102H', [0o100 | c << 3, 2, 1]), (f'J{true} 0102H', [0o140 | c << 3, 2, 1]),
                  (f'C{false} 0304H', [0o102 | c << 3, 4, 3]), (f'C{true} 0304H', [0o142 | c << 3, 4, 3]),
                  (f'R{false}', [0o003 | c << 3]), (f'R{true}', [0o043 | c << 3])]
    table += [(f'RST {n}', [0o005 | n << 3]) for n in range(8)]
    table += [(f'IN {port}', [0o101 | port << 1]) for port in range(8)]
    table += [(f'OUT {port}', [0o101 | port << 1]) for port in range(8, 32)]
    return table


@unittest.skipUnless((ROOT / 'plm8/upstream/mac8.sav').is_file(), 'optional Intel MAC8 image not supplied; see plm8/README.md')
class MAC8(unittest.TestCase):
    def run_image(self, text, budget):
        with tempfile.TemporaryDirectory(prefix='mac8 test ') as directory:
            path = Path(directory, 'assembled.hex')
            path.write_text(text, encoding='ascii')
            result = subprocess.run([str(HOST), f'-n:{budget}', str(path)], capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.replace(b'\r\n', b'\n')

    def test_example(self):
        source = ROOT / 'plm8/examples/mac8hello.asm'
        text, listing = mac8.assemble_source(source.read_text())
        self.assertIn('NO PROGRAM ERRORS', listing)
        self.assertNotIn('\r', listing)
        self.assertEqual(self.run_image(text, 100_000), b'HELLO FROM MAC8!\n')
        source.with_suffix('.hex').write_text(text, encoding='ascii')

    def test_opcodes(self):
        table = opcode_table()
        self.assertEqual(len(table), 8 * 8 - 1 + 8 + 12 + 8 * 9 + 4 + 4 + 4 * 6 + 8 + 32)
        source = ''.join(f'        {instruction}\n' for instruction, _ in table)
        memory = image(mac8.assemble_source(source)[0])
        expected = b''.join(bytes(encoding) for _, encoding in table)
        self.assertEqual(bytes(memory[a] for a in sorted(memory)), expected)

    def test_a08_programs(self):
        # The same programs assembled by a08 from 1972 mnemonics and by MAC8
        # from translated 8080-style source must give identical images.
        for name in ('hello', 'count', 'echo', 'sieve', 'e', 'ttt', 'robson', 'b8008'):
            with self.subTest(name=name):
                source = translate_a08((ROOT / f'a08/{name}.asm').read_text())
                text, _ = mac8.assemble_source(source)
                self.assertEqual(image(text), image((ROOT / f'a08/{name}.hex').read_text()))

    def test_runners_agree(self):
        source = translate_a08((ROOT / 'a08/sieve.asm').read_text())
        if not pdp10.NATIVE.is_file():
            self.skipTest('native PDP-10 runner not built')
        native = mac8.assemble_source(source)
        os.environ['PLM8_PYTHON'] = '1'
        try:
            self.assertEqual(mac8.assemble_source(source), native)
        finally:
            del os.environ['PLM8_PYTHON']

    def test_listing_lines(self):
        # Every listing line ends in CRLF, including those after the first
        # 640-character disk buffer.
        source = ''.join(f'        {instruction}\n' for instruction, _ in opcode_table())
        listing = mac8.assemble_source(source)[1]
        self.assertGreater(len(listing), 5000)
        self.assertEqual(sum(1 for line in listing.splitlines() if re.match(r'   [0-9A-F]{4}   ', line)),
                         len(opcode_table()))

    def test_source_checks(self):
        for source, message in (('        mvi a,1\n', 'alphabet'), ("        DB 'x'\n", 'alphabet'),
                                ('        DB ' + ','.join(['1'] * 40) + '\n', '72-column'),
                                ('$T=1\n        HLT\n', 'control lines')):
            with self.subTest(source=source):
                with self.assertRaisesRegex(mac8.CompileError, message):
                    mac8.assemble_source(source)
        # Lowercase and long comments are allowed, and END is optional.
        text, _ = mac8.assemble_source('        ORG 64 ; lowercase comment' + ' ' * 80 + 'x\n        HLT\n')
        self.assertEqual(image(text), {64: 0})

    @unittest.skipUnless((ROOT / 'plm8/upstream/mac8e.sav').is_file(), 'optional MAC8E image not supplied')
    def test_expanded(self):
        # MAC8E, the 1975 expanded MAC8 2.3, needs KI10 arithmetic and the
        # Tymshare interrupt calls. It gives the same images, and its symbol
        # table holds 3,990 labels where MAC8's holds 490.
        for name in ('sieve', 'b8008'):
            with self.subTest(name=name):
                text, listing = mac8.assemble_source(translate_a08((ROOT / f'a08/{name}.asm').read_text()), True)
                self.assertIn('8008 MACRO ASSEMBLER, VER 2.3', listing)
                self.assertEqual(image(text), image((ROOT / f'a08/{name}.hex').read_text()))
        labels = ''.join(f'L{i:04d}:  DB {i % 256}\n' for i in range(491))
        with self.assertRaisesRegex(mac8.CompileError, 'PROGRAM ERROR'):
            mac8.assemble_source(labels)
        self.assertEqual(len(image(mac8.assemble_source(labels, True)[0])), 491)

    def test_errors(self):
        with tempfile.TemporaryDirectory(prefix='mac8 test ') as directory:
            output = Path(directory, 'old.hex')
            output.write_text('keep\n', encoding='ascii')
            source = Path(directory, 'bad.asm')
            source.write_text('        JMP NOWHERE\nX:      HLT\nX:      HLT\n        MVI A,300\n        END\n')
            result = subprocess.run([sys.executable, str(ROOT / 'plm8/mac8.py'), str(source), '-o', str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(output.read_text(), 'keep\n')
        self.assertIn('U 0000', result.stderr)
        self.assertEqual(result.stderr.count(' M 00'), 2)
        self.assertIn('V 0005', result.stderr)
        self.assertIn('4 PROGRAM ERRORS', result.stderr)


if __name__ == '__main__':
    unittest.main()
