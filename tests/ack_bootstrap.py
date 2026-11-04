#!/usr/bin/env python3
"""ACK Unix build prerequisites must be checked before building anything."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ack_unix_build', ROOT/'ack/bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class Prerequisites(unittest.TestCase):
    def test_berkeley_yacc_does_not_replace_bison(self):
        with patch.object(bootstrap, 'find_make', return_value='gmake'), \
             patch.object(bootstrap.shutil, 'which', side_effect=lambda t: None if t=='bison' else '/usr/bin/'+t):
            with self.assertRaisesRegex(SystemExit, 'Missing ACK build tool\\(s\\): bison') as error:
                bootstrap.check_tools()
        self.assertIn('sudo apt install', str(error.exception))

    def test_all_missing_tools_are_reported(self):
        with patch.object(bootstrap, 'find_make', return_value='gmake'), \
             patch.object(bootstrap.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(SystemExit, 'ninja, gcc, flex, yacc, bison'):
                bootstrap.check_tools()

    def test_complete_toolchain_returns_selected_make(self):
        with patch.object(bootstrap, 'find_make', return_value='gmake'), \
             patch.object(bootstrap.shutil, 'which', side_effect=lambda t: '/usr/bin/'+t) as which:
            self.assertEqual(bootstrap.check_tools(), 'gmake')
        self.assertEqual([call.args[0] for call in which.call_args_list],
                         ['ninja','gcc','flex','yacc','bison'])

    def test_failure_precedes_downloads_and_builds(self):
        with patch.object(bootstrap, 'check_tools', side_effect=SystemExit('missing bison')), \
             patch.object(bootstrap, 'unpack') as unpack, \
             patch.object(bootstrap.subprocess, 'run') as run, \
             patch.object(bootstrap, 'BUILD') as build:
            with self.assertRaises(SystemExit):
                bootstrap.main()
        unpack.assert_not_called()
        run.assert_not_called()
        build.mkdir.assert_not_called()


if __name__=='__main__':
    unittest.main()
