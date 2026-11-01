#!/usr/bin/env python3
"""Portable regressions for native ACK source generation and build metadata."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ack'))
spec = importlib.util.spec_from_file_location('ack_native_build', ROOT / 'ack/msvc.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class Generation(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='ACK native generation ')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.builder = native.Builder(self.root, self.root / 'objects', self.root / 'tools')

    def test_allocation_directives_inside_comments(self):
        (self.root / 'records.xh').write_text('''struct record { int value; };
/* ALLOCDEF "record" 20 */
/* STATICALLOCDEF "scratch" 2 */
''')
        output = self.builder.transform('make.allocd', ['records.xh'])
        self.assertIn('struct record { int value; };', output)
        self.assertIn('extern struct record *h_record;', output)
        self.assertIn('#define new_record()', output)
        self.assertIn('sizeof(struct record), 20)', output)
        self.assertIn('#define free_record(p)', output)
        self.assertIn('\nstruct scratch *h_scratch;', output)
        self.assertNotIn('extern struct scratch', output)
        self.assertNotIn('ALLOCDEF', output)

    def test_parameters_ignore_bang_comments_and_crlf(self):
        (self.root / 'Parameters').write_bytes(b'! comment\r\n#define WORD 2\r\n\r\n')
        output = self.builder.transform('make.parameters', ['Parameters'])
        self.assertEqual(output, '#ifndef PARAMETERS_H\n#define PARAMETERS_H\n#define WORD 2\n\n#endif\n')

    def test_token_names_preserve_frontend_fallback(self):
        (self.root / 'make.tokcase').write_text("""cat <<'--EOT--'
#include "Lpars.h"
char* symbol2str(int tok) { switch(tok) {
--EOT--
sed 'original source transformation'
cat <<'--EOT--'
default: return "bad token";
} }
--EOT--
""")
        (self.root / 'tokens.c').write_text('{TOKEN, "word"},\n{OTHER, "another"},\n')
        output = self.builder.transform('make.tokcase', ['tokens.c'])
        self.assertIn('case TOKEN :\n\t\treturn "word";', output)
        self.assertIn('case OTHER :\n\t\treturn "another";', output)
        self.assertTrue(output.endswith('default: return "bad token";\n} }\n'))

    def test_unrecognized_recipe_never_runs_a_shell(self):
        with patch.object(self.builder, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'unhandled generator'):
                self.builder.generate({'deps': [], 'outs': [], 'commands': ['unknown-shell-tool input']})
            run.assert_not_called()

    def test_recipe_has_complete_generated_dependency_graph(self):
        plan = self.builder.plan
        nodes = set(plan['units']) | set(plan['libraries']) | set(plan['programs'])
        nodes.update(p for rule in plan['rules'] for p in rule['outs'])
        dependencies = [p for group in plan['groups'] for p in group['deps']]
        dependencies += [p for rule in plan['rules'] for p in rule['deps']]
        dependencies += [v[0] for v in plan['units'].values()]
        dependencies += [p for inputs in plan['libraries'].values() for p in inputs]
        dependencies += [p for inputs in plan['programs'].values() for p in inputs]
        for node in dependencies:
            if node.startswith('.obj/'):
                self.assertIn(node, nodes, 'generated dependency has no recipe: ' + node)
        for name in native.RUNTIME_TOOLS:
            self.assertIn(plan['targets'][name], nodes)


if __name__ == '__main__':
    unittest.main()
