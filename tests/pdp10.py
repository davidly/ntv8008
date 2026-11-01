#!/usr/bin/env python3
"""Exercise the PDP-10 runner without requiring historical compiler images."""
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plm8'))
from pdp10 import PDP10, MASK, RH, SIGN, pred


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


if __name__ == '__main__':
    unittest.main()
