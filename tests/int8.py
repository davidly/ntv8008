#!/usr/bin/env python3
"""Run 8008 programs in Intel's INTERP/8 simulator and compare them with ntv8008."""
import importlib.util
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plm8'))
spec = importlib.util.spec_from_file_location('plm8_int8', ROOT / 'plm8/int8.py')
int8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(int8)
import pdp10  # noqa: E402
HOST = ROOT / ('ntv8008.exe' if os.name == 'nt' else 'ntv8008')
UPSTREAM = ROOT / 'plm8/upstream'
REGISTERS = 'ABCDEHL'


def hex_text(memory):
    lines = []
    for start in range(0, 16384, 16):
        data = [memory[a] for a in range(start, start + 16) if a in memory]
        if data:
            first = min(a for a in range(start, start + 16) if a in memory)
            record = bytes([len(data), first >> 8, first & 255, 0, *data])
            lines.append(':' + (record + bytes([-sum(record) & 255])).hex().upper())
    return '\n'.join(lines + [':00000001FF']) + '\n'


def random_program(generator):
    """Straight-line ALU, register and memory code with conditional jumps,
    calls and returns, ending in HLT at a known address. Memory operands use
    page 20H; the subroutine at 300H ends with a conditional return."""
    code = []
    for r in range(7):
        code += [0o006 | r << 3, generator.randrange(256)]
    for _ in range(60):
        kind = generator.randrange(8)
        if kind == 0:
            d, s = generator.randrange(7), generator.randrange(7)
            code.append(0o300 | d << 3 | s)
        elif kind == 1:
            code.append(0o200 | generator.randrange(8) << 3 | generator.randrange(7))
        elif kind == 2:
            code += [0o004 | generator.randrange(8) << 3, generator.randrange(256)]
        elif kind == 3:
            code.append(generator.randrange(1, 7) << 3 | generator.randrange(2))  # INR/DCR
        elif kind == 4:
            code.append(0o002 | generator.randrange(4) << 3)
        elif kind == 5:  # memory: store, load or ALU through HL
            code += [0o056, 0x20, 0o066, generator.randrange(256)]
            choice = generator.randrange(3)
            if choice == 0:
                code.append(0o370 | generator.randrange(5))  # MOV M,A..E
            elif choice == 1:
                code.append(0o307 | generator.randrange(5) << 3)  # MOV A..E,M
            else:
                code.append(0o207 | generator.randrange(8) << 3)  # ALU M
        elif kind == 6:  # conditional jump over one instruction
            target = 0x40 + len(code) + 4
            code += [0o100 | generator.randrange(8) << 3, target & 255, target >> 8, 0o010]
        else:  # conditional call
            code += [0o102 | generator.randrange(8) << 3, 0x00, 0x03]
    code.append(0o377)  # HLT (FF)
    memory = {0x40 + i: b for i, b in enumerate(code)}
    subroutine = [0o220 | generator.randrange(7), 0o003 | generator.randrange(8) << 3, 0o030, 0o007]
    memory.update({0x300 + i: b for i, b in enumerate(subroutine)})
    memory.update({0x2000 + i: generator.randrange(256) for i in range(256)})
    return memory


def ntv8008_state(path):
    """Final registers, flags and clock periods from an ntv8008 instruction trace."""
    with tempfile.TemporaryDirectory(prefix='int8 trace ') as directory:
        subprocess.run([str(HOST), '-t', '-i', '-n:1000000', str(path)], cwd=directory,
                       capture_output=True, timeout=60, check=True)
        log = Path(directory, 'ntv8008.log').read_text()
    last = [line for line in log.splitlines() if line.startswith('pc ') and line.endswith('HLT')][-1]
    fields = dict(re.findall(r'(\w+) ([0-9a-f]+),', last))
    flags = re.search(r', ([cC][zZ][sS][pP]),', last).group(1)
    clocks = int(re.search(r'halt at \w+, (\d+) cycles', log).group(1))
    return [int(fields[r.lower()], 16) for r in REGISTERS], [int(f.isupper()) for f in flags], clocks


def int8_state(obj, load):
    transcript = int8.simulate(obj, f'$F\n{load}\nSET PC = 64.\nGO.\nDISPLAY CPU.\n$E\n', 10 ** 9)
    int8.check(transcript)
    lines = transcript.splitlines()
    header = next(i for i in range(len(lines) - 1, -1, -1) if lines[i].startswith('CYZSP'))
    values = re.findall(r'\d+', lines[header + 1])
    names = lines[header].split()
    state = dict(zip(names, values))
    states = int(re.search(r'^HLT CYCLE (\d+)$', transcript, re.M).group(1))
    return [int(state[r]) for r in REGISTERS], [int(c) for c in state['CYZSP']], 2 * (states - int8.HALT_STATES)


@unittest.skipUnless((UPSTREAM / 'int8.sav').is_file(), 'optional Intel INT8 image not supplied; see plm8/README.md')
class INT8(unittest.TestCase):
    def ntv8008(self, path):
        result = subprocess.run([str(HOST), '-p', str(path)], capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        clocks = int(re.search(rb'(\d+) cycles, ', result.stderr).group(1))  # -p reports on stderr
        return result.stdout.decode('ascii').replace('\r\n', '\n'), clocks

    def assertSameRun(self, path, program=None):
        obj, load, memory = int8.load_program(program or path)
        output, clocks = int8.run_program(obj, load, memory)
        self.assertEqual((output, clocks), self.ntv8008(path))

    def test_a08_programs(self):
        # Output and cycle counts match ntv8008 for each program run to HLT.
        for name in ('hello', 'count', 'sieve', 'e', 'ttt'):
            with self.subTest(name=name):
                self.assertSameRun(ROOT / f'a08/{name}.hex')

    @unittest.skipUnless((UPSTREAM / 'mac8.sav').is_file(), 'MAC8 image not supplied')
    def test_mac8_source(self):
        source = ROOT / 'plm8/examples/mac8hello.asm'
        sys.path.insert(0, str(ROOT / 'plm8'))
        import mac8
        with tempfile.TemporaryDirectory(prefix='int8 test ') as directory:
            path = Path(directory, 'mac8hello.hex')
            path.write_text(mac8.assemble_source(source.read_text())[0], encoding='ascii')
            self.assertSameRun(path, source)

    @unittest.skipUnless(all((UPSTREAM / n).is_file() for n in ('plm1.sav', 'plm2.sav')), 'PL/M images not supplied')
    def test_plm_programs(self):
        import compile
        for name in ('hello', 'arithmetic'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix='int8 test ') as directory:
                path = Path(directory, name + '.hex')
                path.write_text(compile.compile_source((ROOT / f'plm8/examples/{name}.plm').read_text())[0],
                                encoding='ascii')
                self.assertSameRun(path)

    def test_random_programs_match_ntv8008(self):
        # Registers, flags and cycle counts after random ALU, memory, jump,
        # call and return sequences agree with Intel's simulator.
        with tempfile.TemporaryDirectory(prefix='int8 test ') as directory:
            for seed in range(40):
                with self.subTest(seed=seed):
                    memory = random_program(random.Random(seed))
                    path = Path(directory, f'random{seed}.hex')
                    path.write_text(hex_text(memory), encoding='ascii')
                    self.assertEqual(int8_state(int8.mac8_object(memory), 'LOAD 7.'), ntv8008_state(path))

    @unittest.skipUnless((UPSTREAM / 'mac8.sav').is_file(), 'MAC8 image not supplied')
    def test_command_session(self):
        # MAC8 symbols load with the program, as in the tape's INT8.EXA session.
        with tempfile.TemporaryDirectory(prefix='int8 test ') as directory:
            commands = Path(directory, 'session.txt')
            commands.write_text('DISPLAY SYM.\nBASE HEX.\nGO.\nDISPLAY CPU.\n', encoding='ascii')
            result = subprocess.run([sys.executable, str(ROOT / 'plm8/int8.py'), '--commands', str(commands),
                                     str(ROOT / 'plm8/examples/mac8hello.asm')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r'000110Q 00072 0048H +PRINT')
        self.assertIn('HEX BASE OK', result.stdout)
        self.assertRegex(result.stdout, r'HLT CYCLE \d+')

    def test_errors(self):
        loop = {64: 0o104, 65: 64, 66: 0}  # JMP 64
        with self.assertRaisesRegex(int8.CompileError, 'no HLT within 1000 clock periods'):
            int8.run_program(int8.mac8_object(loop), 'LOAD 7.', loop, limit=1000)
        with self.assertRaisesRegex(int8.CompileError, 'invalid Intel HEX record'):
            int8.read_hex(':0100400000BE\n:00000001FF\n')
        result = subprocess.run([sys.executable, str(ROOT / 'plm8/int8.py'), '-p', str(ROOT / 'a08/count.hex')],
                                capture_output=True, text=True)
        self.assertEqual(result.stdout, '0123456789\n1088 cycles (INTERP/8 560 states)\n')

    def test_runners_agree(self):
        if not pdp10.NATIVE.is_file():
            self.skipTest('native PDP-10 runner not built')
        obj, load, memory = int8.load_program(ROOT / 'a08/hello.hex')
        native = int8.run_program(obj, load, memory)
        os.environ['PLM8_PYTHON'] = '1'
        try:
            self.assertEqual(int8.run_program(obj, load, memory), native)
        finally:
            del os.environ['PLM8_PYTHON']


if __name__ == '__main__':
    unittest.main()
