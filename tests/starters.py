#!/usr/bin/env python3
"""Build and run first-program starters using their actual user-facing scripts."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILE = '--compile' in sys.argv
if COMPILE:
    sys.argv.remove('--compile')
SUFFIX = '.exe' if os.name == 'nt' else ''
ACK_TOOLS = Path(os.environ.get('ACK_TOOLS', str(ROOT / 'ack/build/bin')))


class Starters(unittest.TestCase):
    def script(self, project, name, *options, data=b''):
        script = name + ('.bat' if os.name == 'nt' else '.sh')
        command = (['cmd.exe', '/d', '/c', 'call', str(project / script)] if os.name == 'nt'
                   else [str(project / script)])
        env = dict(os.environ)
        env['PYTHON'] = ('"' + sys.executable + '"' if os.name == 'nt'
                         else sys.executable)
        # cmd cannot start in a UNC directory; each batch file uses pushd.
        cwd = tempfile.gettempdir() if os.name == 'nt' else project
        result = subprocess.run(command + list(options), cwd=cwd, env=env,
                                input=data, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.replace(b'\r\n', b'\n')

    def check_compiled(self, project):
        self.script(project, 'build')
        self.assertTrue((project / 'build/program.hex').is_file())
        self.assertTrue((project / 'build/program.map').read_text().strip())
        self.assertTrue((project / 'build/program.lst').is_file())
        for key, square in ((b'0', 0), (b'1', 1), (b'2', 4), (b'3', 9)):
            with self.subTest(project=project.name, key=key):
                output = self.script(project, 'run', '-n:1000000', data=key)
                self.assertEqual(output, b'8008 SQUARE TABLE\nChoose 0..3:\n' +
                                 key + b'\nSQUARE =\n' + str(square).encode() + b'\n')
        for key in (b'4', b'/', b'x'):
            with self.subTest(project=project.name, invalid=key):
                output = self.script(project, 'run', '-n:1000000', data=key)
                self.assertIn(b'USE A DIGIT FROM 0 TO 3.\n', output)
                self.assertNotIn(b'SQUARE =', output)
        output = self.script(project, 'run', '-n:1000000', '-l:input.txt')
        self.assertIn(b'SQUARE =\n9\n', output)

    def test_assembly(self):
        self.check_compiled(ROOT / 'starters/assembly')

    def test_basic_session(self):
        output = self.script(ROOT / 'starters/b8008', 'run', '-n:20000000')
        # Stored source is echoed too. Check execution after the RUN command.
        execution = output.split(b'>RUN\n')[-1]
        self.assertIn(b'8008 SQUARE TABLE\nChoose 0..3:\n?3\nSQUARE =\n9\n', execution)
        self.assertNotIn(b'?SYNTAX', execution)
        self.assertNotIn(b'?BOUNDS', execution)
        self.assertNotIn(b'USE A DIGIT', execution)

    def test_copied_project_with_spaces(self):
        work = ROOT / 'work'
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='first program ', dir=work) as directory:
            project = Path(directory)
            shutil.copytree(ROOT / 'starters/assembly', project, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('build'))
            self.check_compiled(project)

    def test_copied_basic_project_with_spaces(self):
        work = ROOT / 'work'
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='first BASIC ', dir=work) as directory:
            project = Path(directory)
            shutil.copytree(ROOT / 'starters/b8008', project, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('build'))
            for value in (2, 4, -1):
                with self.subTest(value=value):
                    (project / 'input.txt').write_text(str(value) + '\n')
                    output = self.script(project, 'run', '-n:20000000')
                    execution = output.split(b'>RUN\n')[-1]
                    if value == 2:
                        self.assertIn(b'SQUARE =\n4\n', execution)
                    else:
                        self.assertIn(b'USE A DIGIT FROM 0 TO 3.', execution)
                        self.assertNotIn(b'SQUARE =', execution)

    @unittest.skipUnless(COMPILE and (ROOT / ('smallc/build/scc8008' + SUFFIX)).is_file(),
                         'use --compile after setup --smallc to build the C starter')
    def test_smallc(self):
        self.check_compiled(ROOT / 'starters/smallc')

    @unittest.skipUnless(COMPILE and all((ACK_TOOLS / (name + SUFFIX)).is_file()
                         for name in ('cpp.ansi', 'em_cemcom.ansi', 'em_opt', 'em_decode')),
                         'use --compile with compatible ACK host tools to build the C starter')
    def test_ack_c(self):
        self.check_compiled(ROOT / 'starters/ack-c')


if __name__ == '__main__':
    unittest.main()
