"""Safety checks for static Occam workspace selection."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ack'))
from occam_storage import static_workspaces


class Storage(unittest.TestCase):
    def test_stack_mode_is_unchanged(self):
        program=' pro $main,2\n loc 7\n stl -2\n ret 0\n end 2\n'
        self.assertEqual(static_workspaces(program,'stack'),program)

    def test_outer_workspace_moves_but_parameter_addresses_do_not(self):
        program=''' pro $child,4
 lxl 1
 adp -2
 loi 2
 stl -4
 lol 2
 ret 0
 end 4
 pro $main,2
 lxl 0
 cal $child
 asp 2
 ret 0
 end 2
'''
        result=static_workspaces(program)
        self.assertIn(' pro $child,0',result)
        self.assertIn(' pro $main,0',result)
        self.assertIn(' lol 2',result)
        self.assertNotIn(' adp -2',result)
        self.assertEqual(result.count(' bss '),2)

    def test_recursive_workspace_stays_private(self):
        program=''' pro $child,4
 lxl 1
 cal $child
 asp 2
 lol -4
 ret 0
 end 4
 pro $main,2
 lxl 0
 cal $child
 asp 2
 ret 0
 end 2
'''
        result=static_workspaces(program)
        self.assertIn(' pro $child,4',result)
        self.assertIn(' lol -4',result)
        self.assertIn(' pro $main,0',result)

    def test_escaped_or_indirect_frames_stay_on_stack(self):
        escaped=' pro $main,2\n lxl 0\n ret 2\n end 2\n'
        indirect=' pro $main,2\n cai \n ret 0\n end 2\n'
        self.assertEqual(static_workspaces(escaped),escaped)
        self.assertEqual(static_workspaces(indirect),indirect)


if __name__=='__main__':unittest.main()
