"""Reachability safeguards for the shared assembly runtime pruning."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from runtime_prune import prune_runtime


class RuntimePruning(unittest.TestCase):
    def test_calls_and_fallthrough(self):
        runtime = '''        ORG 40H
        CAL used
        HLT
DEAD:   RET
USED:   RTZ
TAIL:   CAL LEAF
        RET
LEAF:   RET
'''
        result = prune_runtime(runtime, '')
        self.assertNotIn('DEAD:', result)
        for label in ('USED:', 'TAIL:', 'LEAF:'):
            self.assertIn(label, result)

    def test_address_taken_table_and_interior_data(self):
        runtime = '''        ORG 40H
        HLT
DEAD:   RET
HANDLER: RET
TABLE:  DW HANDLER
INTERIOR: DW 0
OTHER: RET
'''
        result = prune_runtime(runtime, '        LHI HIGH TABLE\n')
        for label in ('TABLE:', 'INTERIOR:', 'HANDLER:'):
            self.assertIn(label, result)
        for label in ('DEAD:', 'OTHER:'):
            self.assertNotIn(label, result)

    def test_self_modifying_jump_and_equates(self):
        runtime = '''RSP EQU 3F00H
        ORG 40H
        HLT
UNUSED: RET
SCRATCH EQU RSP+2
JUMPAB: LHI HIGH INDIRECT
        LLI LOW INDIRECT+1
        LMA
INDIRECT: JMP 0
'''
        result = prune_runtime(runtime, '        JMP JUMPAB\n')
        self.assertIn('SCRATCH EQU RSP+2', result)
        self.assertIn('INDIRECT: JMP 0', result)
        self.assertNotIn('UNUSED:', result)

    def test_literal_and_comment_names_are_not_references(self):
        runtime = '''        ORG 40H
        HLT
UNUSED: RET
MESSAGE: DB "UNUSED; text",0
'''
        result = prune_runtime(runtime, '        LHI HIGH MESSAGE ; UNUSED\n')
        self.assertIn('MESSAGE:', result)
        self.assertNotIn('UNUSED:', result)

    def test_equate_alias_keeps_target(self):
        runtime = '''        ORG 40H
        HLT
UNUSED: RET
ALIAS EQU TARGET
TARGET: RET
'''
        result = prune_runtime(runtime, '        CAL ALIAS\n')
        self.assertIn('TARGET:', result)
        self.assertIn('ALIAS EQU TARGET', result)
        self.assertNotIn('UNUSED:', result)


if __name__ == '__main__':
    unittest.main()
