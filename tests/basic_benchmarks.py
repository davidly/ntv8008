#!/usr/bin/env python3
"""Run the full SCELBAL BASIC benchmarks (takes about a minute on this host)."""
from decimal import Decimal, localcontext
import unittest

import integration
from integration import ROOT, run


@unittest.skipUnless((ROOT/'a08/scelbal.hex').is_file(), 'optional SCELBAL not installed; see scelbal/README.md')
class BasicBenchmarks(unittest.TestCase):
    def execute(self, app):
        result = run('-n:500000000000',
                     '-l:' + str(ROOT / 'scelbal/examples' / (app + '.bas')),
                     ROOT / 'a08/scelbal.hex', timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'RUN\n', result.stdout)
        output = result.stdout.split(b'RUN\n', 1)[1]
        self.assertTrue(output.endswith(b'\nREADY\n\n'), output[-200:])
        return output[:-len(b'\nREADY\n\n')].strip()

    def test_e(self):
        with localcontext() as context:
            context.prec = 220
            expected = str(Decimal(1).exp()).replace('.', '')[:192]
        self.assertEqual(self.execute('e'), (expected + '\nDONE').encode())

    def test_sieve(self):
        # Independent trial division, without the port's segmentation strategy.
        def prime(n):
            return all(n % divisor for divisor in range(2, int(n ** 0.5) + 1))
        count = sum(prime(n) for n in range(3, 2 * 8190 + 4, 2))
        self.assertEqual(count, 1899)
        self.assertEqual(self.execute('sieve'), f'{count} PRIMES\n10 ITERATIONS'.encode())

    def test_ttt(self):
        scores, nodes = integration.Integration.minimax_reference()
        self.assertEqual(scores, [5, 5, 5])
        self.assertEqual(nodes, 6493)
        self.assertEqual(self.execute('ttt'), f'1 ITERATIONS\nFINAL MOVE COUNT {nodes}'.encode())


if __name__ == '__main__':
    unittest.main(verbosity=2)
