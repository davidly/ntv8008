#!/usr/bin/env python3
"""Exercise the PDP-10 runner without requiring historical compiler images."""
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plm8'))
import random
import tempfile
from pdp10 import NATIVE, PDP10, MASK, RH, SIGN, pred


def instruction(op, ac=0, address=0, index=0, indirect=False):
    return op << 27 | ac << 23 | int(indirect) << 22 | index << 18 | address


class Runner(unittest.TestCase):
    def setUp(self):
        # Loading real images is covered by plm8.py. These tests also run in CI
        # where the optional historical compiler executables are unavailable.
        self.cpu = object.__new__(PDP10)
        self.cpu.m = [0] * (RH + 1)
        self.cpu.pc = 64
        self.cpu.channels = {}
        self.cpu.input = io.StringIO()
        self.cpu.output = io.StringIO()

    def execute(self, op, ac=1, address=200, index=0, indirect=False):
        self.cpu.execute(instruction(op, ac, address, index, indirect), 63)

    def test_move_and_immediate(self):
        self.cpu.m[200] = SIGN | 123
        self.execute(0o200)
        self.assertEqual(self.cpu.m[1], SIGN | 123)
        self.execute(0o201)
        self.assertEqual(self.cpu.m[1], 200)
        self.execute(0o202, address=201)
        self.assertEqual(self.cpu.m[201], 200)
        self.execute(0o200, ac=0)
        self.assertEqual(self.cpu.m[0], SIGN | 123)

    def test_other_move_forms(self):
        self.cpu.m[200] = MASK - 4  # -5
        self.execute(0o210)  # MOVN
        self.assertEqual(self.cpu.m[1], 5)
        self.execute(0o214)  # MOVM
        self.assertEqual(self.cpu.m[1], 5)
        self.cpu.m[200] = 123 << 18 | 456
        self.execute(0o204)  # MOVS
        self.assertEqual(self.cpu.m[1], 456 << 18 | 123)
        self.cpu.m[1] = 9
        self.execute(0o212)  # MOVNM
        self.assertEqual(self.cpu.m[200], MASK - 8)
        self.execute(0o213)  # MOVNS
        self.assertEqual(self.cpu.m[1], 9)
        self.assertEqual(self.cpu.m[200], 9)

    def test_indexed_address(self):
        self.cpu.m[3] = 17
        self.cpu.m[217] = 12345
        self.execute(0o200, index=3)
        self.assertEqual(self.cpu.m[1], 12345)
        self.execute(0o201, index=3)
        self.assertEqual(self.cpu.m[1], 217)

    def test_index_wrap(self):
        self.cpu.m[3] = MASK
        self.cpu.m[RH] = 54321
        self.execute(0o200, address=0, index=3)
        self.assertEqual(self.cpu.m[1], 54321)
        self.execute(0o201, address=0, index=3)
        self.assertEqual(self.cpu.m[1], RH)

    def test_indirect_indexed_chain(self):
        self.cpu.m[3] = 17
        self.cpu.m[217] = instruction(0, address=300, index=4, indirect=True)
        self.cpu.m[4] = MASK
        self.cpu.m[299] = 400
        self.cpu.m[400] = 123456
        self.execute(0o200, index=3, indirect=True)
        self.assertEqual(self.cpu.m[1], 123456)
        self.cpu.m[400] = 654321
        self.execute(0o200, index=3, indirect=True)
        self.assertEqual(self.cpu.m[1], 654321)

    def test_indirection_limit(self):
        ir = instruction(0o200, 1, 200, indirect=True)
        for address in range(200, 228):
            self.cpu.m[address] = instruction(0, address=address + 1, indirect=True)
        self.cpu.m[228] = 400
        self.cpu.m[400] = 123
        self.cpu.execute(ir, 63)
        self.assertEqual(self.cpu.m[1], 123)
        self.cpu.m[228] = instruction(0, address=229, indirect=True)
        self.cpu.m[229] = 400
        with self.assertRaisesRegex(RuntimeError, 'indirection limit'):
            self.cpu.execute(ir, 63)

    def test_accumulator_alias(self):
        self.cpu.m[1] = 200
        self.cpu.m[200] = 123
        self.execute(0o200, address=0, index=1)
        self.assertEqual(self.cpu.m[1], 123)
        self.execute(0o202, address=0, index=1)
        self.assertEqual(self.cpu.m[123], 123)

    def test_self_modifying_code(self):
        self.cpu.m[200] = instruction(0o201, 2, 42)
        self.cpu.m[64:69] = [instruction(0o200, 1, 200),
                            instruction(0o202, 1, 67),
                            instruction(0o254, address=67),
                            instruction(0o254, 4),  # Replaced before execution.
                            instruction(0o47, address=0o12)]
        self.assertEqual(self.cpu.run(5), '')
        self.assertEqual(self.cpu.m[2], 42)
        self.assertEqual(self.cpu.pc, 69)

    def test_local_uuo(self):
        self.cpu.m[0o41] = instruction(0o201, 2, 99)
        self.cpu.m[3] = 17
        self.execute(1, address=200, index=3)
        self.assertEqual(self.cpu.m[0o40], instruction(1, 1, 217))
        self.assertEqual(self.cpu.m[2], 99)
        self.assertEqual(self.cpu.pc, 64)

    def test_execute_instruction(self):
        self.cpu.m[200] = instruction(0o201, 2, 42)
        self.execute(0o256)
        self.assertEqual(self.cpu.m[2], 42)
        self.assertEqual(self.cpu.pc, 64)

    def test_conditions(self):
        for value in (-SIGN, -1, 0, 1, SIGN - 1):
            expected = (False, value < 0, value == 0, value <= 0,
                        True, value >= 0, value != 0, value > 0)
            for condition, result in enumerate(expected):
                with self.subTest(value=value, condition=condition):
                    self.assertEqual(pred(value, condition), result)
                    self.cpu.pc = 64
                    self.cpu.m[1] = value & MASK
                    self.execute(0o320 + condition)
                    self.assertEqual(self.cpu.pc, 200 if result else 64)

    def test_monitor_output(self):
        self.cpu.m[200] = ord('X')
        self.cpu.m[64:66] = [instruction(0o51, 1, 200),
                            instruction(0o47, address=0o12)]
        self.assertEqual(self.cpu.run(2), 'X')

    def test_instruction_budget(self):
        self.cpu.m[64] = instruction(0o254, address=64)
        with self.assertRaisesRegex(RuntimeError, 'instruction limit'):
            self.cpu.run(3)
        self.assertEqual(self.cpu.pc, 64)

    def test_halt_and_unknown_opcode(self):
        with self.assertRaisesRegex(RuntimeError, 'HALT'):
            self.execute(0o254, ac=4)
        with self.assertRaisesRegex(RuntimeError, 'unsupported PDP-10 opcode 777 at 000077'):
            self.execute(0o777)


@unittest.skipUnless(NATIVE.is_file(), 'native runner not built; run m.sh or m.bat')
class Native(unittest.TestCase):
    """The native runner must match the Python reference instruction for instruction."""
    OPS = ([0o200 + i for i in range(16)] + list(range(0o220, 0o224)) + list(range(0o230, 0o234)) +
           list(range(0o270, 0o300)) + list(range(0o300, 0o400)) + list(range(0o400, 0o700)) +
           [0o240, 0o241, 0o242, 0o246, 0o250, 0o251, 0o252, 0o253, 0o254, 0o255,
            0o260, 0o261, 0o262, 0o263, 0o264, 0o265, 0o266, 0o267, 0o133, 0o134, 0o135, 0o136, 0o137,
            0o001, 0o777])

    def setUp(self):
        # Overwritten UUO vectors can reach file I/O; keep any files private.
        self.directory = tempfile.TemporaryDirectory(prefix='pdp10 native ')
        self.addCleanup(self.directory.cleanup)

    def machine(self, generator):
        cpu = object.__new__(PDP10)
        cpu.m = [0] * (RH + 1)
        cpu.channels = {}
        cpu.input = io.StringIO()
        cpu.output = io.StringIO()
        cpu.directory = Path(self.directory.name)
        cpu.pc = 0o1000
        cpu.m[0o41] = instruction(0o255)  # local UUOs return through JFCL
        for ac in range(1, 16):
            cpu.m[ac] = generator.choice((0, 1, MASK, SIGN, SIGN - 1, 0o1000, 0o2000 << 18 | 0o2000,
                                          generator.getrandbits(36)))
        for address in range(0o2000, 0o2100):
            cpu.m[address] = generator.getrandbits(36)
        for address in range(0o3000, 0o3010):
            # Byte instructions use only these well-formed pointers: position
            # <= 36 and size <= 27 keep every word below 2**64. (Real code never
            # uses wider bytes; Python's unbounded integers would then differ.)
            position, size = generator.randrange(37), generator.randrange(1, 28)
            cpu.m[address] = position << 30 | size << 24 | generator.randrange(0o2000, 0o2100)
        for address in range(0o1000, 0o1100):
            op = generator.choice(self.OPS)
            if 0o133 <= op <= 0o137:
                cpu.m[address] = instruction(op, generator.randrange(16), generator.randrange(0o3000, 0o3010))
                continue
            cpu.m[address] = instruction(op, generator.randrange(16), generator.choice(
                (generator.randrange(0o2000, 0o2100), generator.randrange(0o1000, 0o1100),
                 generator.randrange(64), generator.randrange(0o4000, RH + 1))),
                generator.choice((0, 0, 0, generator.randrange(16))), generator.random() < 0.05)
        cpu.m[0o1100] = instruction(0o47, address=0o12)  # EXIT
        return cpu

    def test_random_programs_match_reference(self):
        for seed in range(150):
            with self.subTest(seed=seed):
                reference, native = self.machine(random.Random(seed)), self.machine(random.Random(seed))
                try:
                    reference.run(400)
                    expected = 'finished'
                except (RuntimeError, ZeroDivisionError, IndexError, KeyError):
                    expected = 'error'
                try:
                    native.run_native(400, state=True)
                    outcome = 'finished'
                except RuntimeError:
                    outcome = 'error'
                self.assertEqual(outcome, expected)
                self.assertEqual(native.pc, reference.pc)
                differences = [a for a in range(RH + 1) if native.m[a] != reference.m[a]]
                self.assertEqual(differences, [], [(oct(a), reference.m[a], native.m[a]) for a in differences[:5]])

    def test_monitor_output_and_errors(self):
        for program, output, failure in (
                ([instruction(0o51, 1, 0o2000), instruction(0o47, address=0o12)], 'X', None),
                ([instruction(0o254, 4)], '', 'HALT'),
                ([instruction(0o777)], '', 'unsupported PDP-10 opcode 777 at 001000'),
                ([instruction(0o254, address=0o1000)], '', 'instruction limit')):
            with self.subTest(program=program):
                cpu = self.machine(random.Random(0))
                cpu.m[0o2000] = ord('X')
                cpu.m[0o1000:0o1000 + len(program)] = program
                if failure:
                    with self.assertRaisesRegex(RuntimeError, failure):
                        cpu.run_native(5)
                else:
                    self.assertEqual(cpu.run_native(5), output)

    def test_output_buffer_ring_and_core(self):
        # The Fortran runtime reads the size in a buffer's ring link word and
        # may then return buffer memory with CORE, which always succeeds here.
        for native in (False, True):
            with self.subTest(native=native):
                cpu = self.machine(random.Random(0))
                cpu.m[:] = [0]*len(cpu.m)
                cpu.pc = 64
                cpu.m[0o2002] = 0o3000 << 18
                cpu.m[64:70] = [instruction(0o50, 1, 0o2000), instruction(0o255), instruction(0o67, 1),
                                instruction(0o47, 2, 0o11), instruction(0o254, 4), instruction(0o47, address=0o12)]
                if native:
                    cpu.run_native(10, state=True)
                else:
                    cpu.run(10)
                base = 0o101000
                self.assertEqual(cpu.m[0o3000:0o3003], [base - 2, 7 << 24 | base - 1, 640])
                self.assertEqual(cpu.m[base - 2], 0o201 << 18 | base - 2)
                self.assertEqual(cpu.m[2], 0o400)

    def test_monitor_control_blocks_at_memory_boundary(self):
        def sixbit(text):
            value = 0
            for ch in text.ljust(6):
                value = value << 6 | (ord(ch)-32)
            return value

        cases = []
        for address in (RH-2, RH-1, RH):
            cases.append(('open', 0o50, address, address > RH-2))
        for op in (0o76, 0o77):
            for extended in (False, True):
                last_valid = RH-3 if extended else RH-1
                for address in (last_valid, last_valid+1, RH):
                    cases.append(('extended' if extended else 'original', op,
                                  address, address > last_valid))
        for op in (0o56, 0o57, 0o66, 0o67):
            for address in (RH-2, RH-1, RH):
                cases.append(('header', op, address, address > RH-2))
        for kind,op,address,invalid in cases:
            for native in (False, True):
                with self.subTest(kind=kind,op=oct(op),address=address,native=native):
                    cpu = self.machine(random.Random(0))
                    cpu.m[:] = [0]*len(cpu.m)
                    cpu.pc = 64
                    cpu.input = io.StringIO('X\n')
                    if kind == 'open':
                        program = [instruction(op, 1, address), instruction(0o255)]
                    else:
                        program = [instruction(0o50, 1, 0o2000), instruction(0o255),
                                   instruction(op, 1, address if kind!='header' else 0),
                                   instruction(0o255)]
                        if kind == 'header':
                            cpu.m[0o2002] = address << 18 | address
                        else:
                            f = address+2 if kind=='extended' else address
                            if f <= RH:
                                cpu.m[f] = sixbit('TEST')
                            if f+1 <= RH:
                                cpu.m[f+1] = sixbit('DAT')
                    program.append(instruction(0o47, address=0o12))
                    cpu.m[64:64+len(program)] = program
                    run = cpu.run_native if native else cpu.run
                    if invalid:
                        with self.assertRaisesRegex(RuntimeError if native else IndexError,
                                                    'list (?:assignment )?index out of range'):
                            run(10)
                    else:
                        self.assertEqual(run(10), '')

    def test_monitor_input_cannot_overrun_guest_memory(self):
        for native in (False, True):
            with self.subTest(native=native):
                cpu = self.machine(random.Random(0))
                cpu.m[:] = [0]*len(cpu.m)
                cpu.pc = 64
                base = 0o140000 + 0o1000  # channel 1 input buffer
                cpu.input = io.StringIO('X'*((len(cpu.m)-base)*5)+'\n')
                cpu.m[0o2002] = 0o3000
                program = [instruction(0o50, 1, 0o2000), instruction(0o255),
                           instruction(0o56, 1), instruction(0o47, address=0o12)]
                cpu.m[64:64+len(program)] = program
                with self.assertRaisesRegex(RuntimeError if native else IndexError,
                                            'list (?:assignment )?index out of range'):
                    (cpu.run_native if native else cpu.run)(10)


if __name__ == '__main__':
    unittest.main()
