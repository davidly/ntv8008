#!/usr/bin/env python3
"""Assembler, console, CPU benchmarks, Intel HEX validation, and optional SCELBAL."""
import collections
from decimal import Decimal, localcontext
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / ('ntv8008.exe' if os.name == 'nt' else 'ntv8008')
ASSEMBLER = ROOT / 'a08' / ('a08.exe' if os.name == 'nt' else 'a08')


def run(*args, data=b'', cwd=None, timeout=10):
    result = subprocess.run([str(HOST), *map(str, args)], input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, cwd=cwd)
    if os.name == 'nt':
        result.stdout = result.stdout.replace(b'\r\n', b'\n')
    return result


def terminal_state(fd):
    import termios
    state = termios.tcgetattr(fd)
    # Darwin sets this kernel-maintained bit when canonical mode is restored,
    # even if tcsetattr receives an otherwise identical saved state.
    if sys.platform == 'darwin':
        state[3] &= ~termios.PENDIN
    return state


def record(address, kind, data=()):
    raw = bytes([len(data), address >> 8, address & 255, kind, *data])
    return ':' + (raw + bytes([-sum(raw) & 255])).hex().upper() + '\n'


class Integration(unittest.TestCase):
    def test_apps(self):
        for app, expected in [('hello', b'HELLO, 8008!\n'), ('count', b'0123456789\n')]:
            result = run('-n:100000', '-p', ROOT / 'a08' / (app + '.hex'))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, expected)
            self.assertIn(b'cycles', result.stderr)

    def test_sieve(self):
        # Independent ordinary sieve, including 2; the benchmark counts odd primes.
        limit = 2 * 8190 + 3
        primes = bytearray([1]) * (limit + 1)
        primes[0:2] = b'\0\0'
        for p in range(2, int(limit ** 0.5) + 1):
            if primes[p]:
                for multiple in range(p * p, limit + 1, p):
                    primes[multiple] = 0
        expected = sum(primes[3:])
        self.assertEqual(expected, 1899)
        result = run('-n:100000000', ROOT / 'a08/sieve.hex')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f'{expected} primes.\n'.encode())

    def test_e(self):
        with localcontext() as context:
            context.prec = 220
            expected = str(Decimal(1).exp()).replace('.', '')[:192]
        result = run('-n:100000000', ROOT / 'a08/e.hex')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, (expected + '\ndone.\n').encode())

    @staticmethod
    def minimax_reference():
        lines = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6),
                 (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
        board = [0] * 9
        nodes = 0

        def search(depth, alpha, beta):
            nonlocal nodes
            nodes += 1
            if depth >= 4:
                for a, b, c in lines:
                    if board[a] and board[a] == board[b] == board[c]:
                        return 6 if board[a] == 1 else 4
                if depth == 8:
                    return 5
            maximize = depth % 2 == 1
            value = 2 if maximize else 9
            for move in range(9):
                if board[move]:
                    continue
                board[move] = 1 if maximize else 2
                score = search(depth + 1, alpha, beta)
                board[move] = 0
                if score == (6 if maximize else 4):
                    return score
                if maximize and score > value:
                    value = score
                    if value >= beta:
                        return value
                    alpha = max(alpha, value)
                elif not maximize and score < value:
                    value = score
                    if value <= alpha:
                        return value
                    beta = min(beta, value)
            return value

        scores = []
        for first in (0, 1, 4):
            board[first] = 1
            scores.append(search(0, 2, 9))
            board[first] = 0
        return scores, nodes

    def test_ttt(self):
        scores, nodes = self.minimax_reference()
        self.assertEqual(scores, [5, 5, 5])
        self.assertEqual(nodes, 6493)
        result = run('-n:100000000', ROOT / 'a08/ttt.hex')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f'moves: {nodes}\niterations: 1\n'.encode())

    def test_ttt_last_move_winner(self):
        # Exercise the native dispatch/checker against every reachable
        # (board, last move), including terminal wins. No alpha-beta pruning.
        lines = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6),
                 (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
        cases, seen = [], set()
        board = [0] * 9

        def visit(piece):
            for move in range(9):
                if board[move]:
                    continue
                board[move] = piece
                key = (tuple(board), move)
                if key not in seen:
                    seen.add(key)
                    winner = next((board[a] for a, b, c in lines
                                   if board[a] and board[a] == board[b] == board[c]), 0)
                    cases.append([*board, move, winner])
                    if not winner:
                        visit(3 - piece)
                board[move] = 0

        visit(1)
        self.assertGreater(len(cases), 10000)
        original = (ROOT / 'a08/ttt.asm').read_text().rsplit('        END', 1)[0]
        # TREAD preserves B/C; WINNER takes the last move's board address in E,
        # returns Z (A = piece) for a win, and preserves B.
        # Fixtures start above the jump table and fit in the remaining RAM.
        harness = """
        ORG 0040H
        LHI HIGH VARS
        LLI 8D
        LMI LOW TDATA
        INL
        LMI HIGH TDATA
        LBI 40H
TCASE:  LCI 0
TLOAD:  CAL TREAD
        LDA
        LAC
        ADI LOW BOARD
        LHI HIGH BOARD
        LLA
        LMD
        INC
        LAC
        CPI 9D
        JFZ TLOAD
        CAL TREAD
        CPI 255D
        JTZ TDONE
        ADI LOW BOARD
        LEA
        LHI HIGH BOARD
        LLE
        LCM                    ; known last piece, now passed to WINNER in C
        CAL WINNER
        JTZ TWON
        XRA                    ; NZ: no winner
TWON:   LCA
        LHI HIGH VARS
        LLI 10D
        LMC
        CAL TREAD
        LHI HIGH VARS
        LLI 10D
        CPM
        JFZ TFAIL
        LAB
        CPI 40H
        JFZ TFAIL
        JMP TCASE
TDONE:  LAI 'K'
        OUT 12
        HLT
TFAIL:  LAI 'F'
        OUT 12
        HLT
TREAD:  LHI HIGH VARS
        LLI 8D
        LEM
        INL
        LHM
        LLE
        LDM
        INL
        JFZ TPOINTER
        INH
TPOINTER:
        LAH
        LEL
        LHI HIGH VARS
        LLI 8D
        LME
        INL
        LMA
        LAD
        RET
        ORG 2000H
TDATA:
"""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, 'winner.asm')
            image = source.with_suffix('.hex')
            for start in range(0, len(cases), 500):
                batch = cases[start:start + 500]
                data = ''.join('        DB ' + ','.join(f'{n}D' for n in case) + '\n'
                               for case in batch)
                data += '        DB 0,0,0,0,0,0,0,0,0,255D\n        END\n'
                source.write_text(original + harness + data)
                assembled = subprocess.run([str(ASSEMBLER), str(source), '-o' + str(image)],
                                           capture_output=True, timeout=10)
                self.assertEqual(assembled.returncode, 0, assembled.stdout + assembled.stderr)
                result = run('-n:10000000', image)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, b'K', f'cases {start}..{start + len(batch)}')

    def test_benchmark_assembly(self):
        # Reassemble each port, compare the distributed HEX, and exercise constants
        # to cover more than the default workload and loop bounds.
        with tempfile.TemporaryDirectory() as temp:
            for app in ('sieve', 'e', 'ttt'):
                original = ROOT / 'a08' / (app + '.asm')
                output = Path(temp) / (app + '.hex')
                result = subprocess.run([str(ASSEMBLER), str(original), '-o' + str(output)],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(output.read_text(), (ROOT / 'a08' / (app + '.hex')).read_text())
            variants = [
                ('sieve', 'LOOPS   EQU 10D', 'LOOPS   EQU 1', b'1899 primes.\n'),
                ('ttt', 'LOOPS   EQU 1', 'LOOPS   EQU 2', b'moves: 6493\niterations: 2\n'),
            ]
            for size in (10, 100, 255):
                with localcontext() as context:
                    context.prec = size + 20
                    digits = str(Decimal(1).exp()).replace('.', '')[:size - 8]
                variants.append(('e', 'DIGITS  EQU 200D', f'DIGITS  EQU {size}D',
                                 (digits + '\ndone.\n').encode()))
            for app, old, new, expected in variants:
                source = Path(temp) / (app + '.asm')
                output = source.with_suffix('.hex')
                text = (ROOT / 'a08' / (app + '.asm')).read_text()
                self.assertIn(old, text)
                source.write_text(text.replace(old, new, 1))
                result = subprocess.run([str(ASSEMBLER), str(source), '-o' + str(output)],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                result = run('-n:200000000', output)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def test_e_small_quotient_division(self):
        # Isolate division by making a[n-1] zero, then inspect the quotient
        # and stored remainder before the spigot advances to the next divisor.
        source = (ROOT/'a08/e.asm').read_text().rsplit('        END',1)[0]
        begin, end = source.index('INNER:'), source.index('DIGIT:')
        inner = source[begin:end].replace('        DCB\n        JFZ INNER','        JMP ECHECK')
        source = source[:begin]+inner+source[end:]
        cases = {(n,q*n+r) for n in range(2,256) for q in range(10) for r in (0,n-1)}
        cases.update((1,x) for x in (0,1,9,10,27,255))
        cases = sorted(cases)
        harness = """
        ORG 0040H
        JMP ETEST
        ORG 1800H
ETEST:  LHI HIGH HIGHVAL
        LLI 8D
        LMI LOW EDATA
        INL
        LMI HIGH EDATA
ECASE:  CAL EREAD
        NDA
        JTZ EGOOD
        LBA
        LHI HIGH ARRAY
        LLB
        DCL
        LMI 0
        CAL EREAD
        LCA
        CAL EREAD
        LEA
        LDC
        LHI HIGH ARRAY
        LAE
        JMP INNER
ECHECK: LCA
        LAD
        NDA
        JFZ EBAD
        CAL EREAD
        CPC
        JFZ EBAD
        CAL EREAD
        LEA
        LHI HIGH ARRAY
        LLB
        LAM
        CPE
        JFZ EBAD
        JMP ECASE
EGOOD:  LAI 'K'
        OUT 12
        HLT
EBAD:   LAI 'F'
        OUT 12
        HLT
EREAD:  LHI HIGH HIGHVAL
        LLI 8D
        LEM
        INL
        LHM
        LLE
        LDM
        INL
        JFZ EPOINT
        INH
EPOINT: LAH
        LEL
        LHI HIGH HIGHVAL
        LLI 8D
        LME
        INL
        LMA
        LAD
        RET
        ORG 2000H
EDATA:
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory,'divide.asm')
            image = path.with_suffix('.hex')
            for start in range(0,len(cases),500):
                data = ''
                for n,x in cases[start:start+500]:
                    q,r = divmod(x,n)
                    data += '        DB '+','.join(f'{v}D' for v in (n,x>>8,x&255,q,r))+'\n'
                path.write_text(source+harness+data+'        DB 0\n        END\n')
                result = subprocess.run([str(ASSEMBLER),str(path),'-o'+str(image)],
                                        capture_output=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                result = run('-n:10000000',image)
                self.assertEqual((result.returncode,result.stdout),(0,b'K'),f'cases starting at {start}')

    def test_sieve_flag_contents(self):
        # Check all 8192 bytes against independently generated packed prime
        # bits, including the padding byte, not just the aggregate count.
        flags = bytearray([1])*16384
        flags[:2] = b'\0\0'
        for n in range(2,128):
            if flags[n]:
                for multiple in range(n*n,len(flags),n): flags[multiple] = 0
        expected = list(flags[3::2])+[0]
        self.assertEqual((len(expected),sum(expected)),(8192,1899))
        packed = [sum(expected[8*i+b]<<b for b in range(8)) for i in range(1024)]
        source = (ROOT/'a08/sieve.asm').read_text().rsplit('        END',1)[0]
        source = source.replace('LOOPS   EQU 10D','LOOPS   EQU 1')
        source = source.replace('        JFZ ITERAGAIN\n','        JFZ ITERAGAIN\n        JMP FCHECK\n',1)
        harness = """
        ORG 0800H
FCHECK: LBI HIGH FDATA
        LCI LOW FDATA
        LDI HIGH FLAGS
        LEI LOW FLAGS
FPACK:  LHB
        LLC
        LAM
        INC
        JFZ FREADY
        INB
FREADY:
"""
        for bit in range(8):
            harness += f"""        RRC
        LHD
        LLE
        LLM
        DCL
        JTC FONE{bit}
        INL
        JFZ FBAD
        JMP FNEXT{bit}
FONE{bit}:  JFZ FBAD
FNEXT{bit}: INE
"""
        harness += """        JFZ FHIGH
        IND
FHIGH:  LAB
        CPI HIGH FEND
        JFZ FPACK
        LAI 'K'
        OUT 12
        HLT
FBAD:   LAI 'F'
        OUT 12
        HLT
        ORG 0900H
FDATA:
"""
        for start in range(0,len(packed),16):
            harness += '        DB '+','.join(f'{v}D' for v in packed[start:start+16])+'\n'
        harness += 'FEND:\n        END\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory,'flags.asm')
            image = path.with_suffix('.hex')
            path.write_text(source+harness)
            result = subprocess.run([str(ASSEMBLER),str(path),'-o'+str(image)],
                                    capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result = run('-n:10000000',image)
            self.assertEqual((result.returncode,result.stdout),(0,b'K'))

    def test_assembler_return_sign(self):
        # A08 formerly encoded RTS as RFS (0x13), breaking SCELBAL's FP math.
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'returns.asm'
            output = source.with_suffix('.hex')
            source.write_text('        ORG 0040H\n        RTS\n        RFS\n'
                              '        RS\n        HLT\n        END\n')
            result = subprocess.run([str(ASSEMBLER), str(source), '-o' + str(output)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = bytes.fromhex(output.read_text().splitlines()[0][9:17])
            self.assertEqual(data, bytes([0x33, 0x13, 0x33, 0xff]))

    @unittest.skipUnless((ROOT/'a08/scelbal.hex').is_file(),
                         'optional SCELBAL not installed; see scelbal/README.md')
    def test_scelbal_build(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scelbal/prepare.py'), '--check'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'scelbal.hex'
            result = subprocess.run([str(ASSEMBLER), str(ROOT / 'a08/scelbal.asm'),
                                     '-o' + str(output)], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(output.read_text(), (ROOT / 'a08/scelbal.hex').read_text())

    @unittest.skipUnless((ROOT/'a08/scelbal.hex').is_file(),
                         'optional SCELBAL not installed; see scelbal/README.md')
    def test_scelbal_hello(self):
        result = run('-n:100000000', '-l:' + str(ROOT / 'scelbal/examples/hello.bas'),
                     ROOT / 'a08/scelbal.hex')
        self.assertEqual(result.returncode, 0, result.stderr)
        output = result.stdout.split(b'RUN\n', 1)[1]
        self.assertRegex(output, rb'(?m)^HELLO, SCELBAL!$')
        self.assertRegex(output, rb'(?m)^SUM= +55\.0$')
        self.assertTrue(output.endswith(b'READY\n\n'))

    @unittest.skipUnless((ROOT/'a08/scelbal.hex').is_file(),
                         'optional SCELBAL not installed; see scelbal/README.md')
    def test_scelbal_features(self):
        result = run('-n:100000000', '-l:' + str(ROOT / 'scelbal/examples/features.bas'),
                     ROOT / 'a08/scelbal.hex')
        self.assertEqual(result.returncode, 0, result.stderr)
        output = result.stdout.split(b'RUN\n', 1)[1]
        self.assertNotIn(b'FAIL', output)
        self.assertRegex(output, rb'(?m)^ARRAY SUM= +55\.0$')
        self.assertRegex(output, rb'(?m)^SUBROUTINE$')
        self.assertRegex(output, rb'(?m)^INPUT DOUBLE= +42\.0$')
        self.assertRegex(output, rb'(?m)^NEGATIVE= *-2\.0$')
        self.assertRegex(output, rb'(?m)^FRACTION= +0\.1250*$')
        self.assertRegex(output, rb'(?m)^SQRT= +9\.0$')
        self.assertTrue(output.endswith(b'READY\n\n'))

    @unittest.skipUnless((ROOT/'a08/scelbal.hex').is_file(),
                         'optional SCELBAL not installed; see scelbal/README.md')
    def test_scelbal_console_and_editing(self):
        # No SCR is needed on cold start; lowercase and rubout are handled in
        # the 8008 driver. Replacing and deleting program lines exercises storage.
        commands = (b'print 1/0\nprint 2+3\b4\nprint 6+3\x7f2\n'
                    b'10 print "old"\n20 end\n10 print "new"\n'
                    b'15 print "deleted"\n15\nlist\nrun\n')
        result = run('-n:100000000', ROOT / 'a08/scelbal.hex', data=commands)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'\nDZ\n', result.stdout)  # divide-by-zero returns to READY
        self.assertIn(b' 6.0\n', result.stdout)
        self.assertIn(b' 8.0\n', result.stdout)
        listing, output = result.stdout.split(b'LIST\n', 1)[1].split(b'RUN\n', 1)
        self.assertIn(b'10 PRINT "NEW"', listing)
        self.assertNotIn(b'OLD', listing)
        self.assertNotIn(b'DELETED', listing)
        self.assertRegex(output, rb'(?m)^NEW$')

    def test_loader_and_options(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'test.hex'
            valid = record(0, 0, [6, 65, 0x55, 255]) + record(4, 1)
            path.write_text(valid)
            result = run('-a:0', '-p', path)
            self.assertEqual((result.returncode, result.stdout), (0, b'A'))
            self.assertIn(b'36 cycles', result.stderr)
            self.assertIn(b'0.000072 seconds at 500000 Hz (500 kHz; excluding I/O waits)', result.stderr)
            # Hardware estimate stays at the original clock even with another throttle.
            throttled = run('-a:0', '-p', '-s:1000000', path)
            self.assertEqual(throttled.returncode, 0, throttled.stderr)
            self.assertEqual(throttled.stdout, b'A')
            self.assertIn(b'0.000072 seconds at 500000 Hz', throttled.stderr)
            for text in [valid[:-3] + '00\n', ':ZZ00000000\n', record(16384, 0, [0]),
                         record(16383, 0, [0, 0]) + record(0, 1),
                         record(0, 0, [0]), record(0, 1), valid + record(0, 0, [0]),
                         record(0, 3, [0, 0, 0, 0]) + record(0, 1),
                         record(0, 4, [0, 1]) + valid,
                         record(0, 2, [4, 0]) + valid]:
                path.write_text(text)
                self.assertEqual(run('-a:0', path).returncode, 1, text)
            path.write_text(record(0, 4, [0, 0]) + valid)
            self.assertEqual(run('-a:0', path).returncode, 0)
            path.write_text(record(0, 0, [0x44, 0, 0]) + record(0, 1))
            self.assertEqual(run('-a:0', '-n:100', path).returncode, 2)
            path.write_text(record(0, 0, [0x22]) + record(0, 1))
            self.assertEqual(run('-a:0', path).returncode, 1)
            for arg in ['-a:16384', '-a:-1', '-n:0', '-s:abc', '--in:8', '--out:7', '-z']:
                self.assertEqual(run(arg, path).returncode, 1)
            path.write_text(record(0, 0, [0x45, 0x55, 255]) + record(0, 1))
            input_path = Path(temp) / 'input'
            input_path.write_bytes(b'Z')
            self.assertEqual(run('-a:0', '-l:' + str(input_path), path).stdout, b'Z')

    def test_tracing(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'test.hex'
            path.write_text(record(0, 0, [6, 65, 0x55, 255]) + record(0, 1))
            log = Path(temp) / 'ntv8008.log'
            plain = run('-a:0', '-p', path, cwd=temp)
            self.assertFalse(log.exists())
            instructions_only = run('-a:0', '-i', path, cwd=temp)
            self.assertEqual(instructions_only.stdout, plain.stdout)
            self.assertFalse(log.exists())
            events = run('-a:0', '-t', '-p', path, cwd=temp)
            text = log.read_text()
            self.assertIn('loaded HEX file', text)
            self.assertIn('output port 10, value 41', text)
            self.assertIn('execution ended: halt', text)
            self.assertNotIn('op2', text)
            traced = run('-a:0', '-t', '-i', '-p', path, cwd=temp)
            text = log.read_text()
            lines = [line for line in text.splitlines() if line.startswith('pc ')]
            self.assertEqual(len(lines), 3)
            self.assertIn('pc 0000, op 06, op2 41', lines[0])
            self.assertIn('cycles 0, LAI 41', lines[0])
            self.assertIn('cycles 16, OUT 10', lines[1])
            self.assertIn('cycles 28, HLT', lines[2])
            self.assertEqual(text.count('Intel 8008 console,'), 1)  # overwrite, not append
            for result in [events, traced]:
                self.assertEqual(result.returncode, plain.returncode)
                self.assertEqual(result.stdout, plain.stdout)
                self.assertIn(b'36 cycles', result.stderr)
            (Path(temp) / 'input').write_bytes(b'Z')
            path.write_text(record(0, 0, [0x45, 0x55, 255]) + record(0, 1))
            result = run('-a:0', '-t', '-l:' + str(Path(temp) / 'input'), path, cwd=temp)
            self.assertEqual(result.stdout, b'Z')
            self.assertIn('input port 2, character 5a, returning da', log.read_text())
            log.unlink()
            log.mkdir()
            self.assertEqual(run('-t', path, cwd=temp).returncode, 1)

    @unittest.skipUnless(os.name == 'posix', 'POSIX terminal test')
    def test_terminal_restore(self):
        import pty
        import select
        import signal
        import termios
        master, slave = pty.openpty()
        saved = terminal_state(slave)
        process = subprocess.Popen([str(HOST), str(ROOT / 'a08/echo.hex')],
                                   stdin=slave, stdout=slave, stderr=subprocess.PIPE)
        try:
            output = b''
            while b'ECHO> ' not in output:
                self.assertTrue(select.select([master], [], [], 5)[0], 'prompt timeout')
                output += os.read(master, 4096)
            self.assertFalse(termios.tcgetattr(slave)[3] & termios.ICANON)
            process.send_signal(signal.SIGINT)
            self.assertEqual(process.wait(timeout=5), 130)
            self.assertEqual(terminal_state(slave), saved)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stderr.close()
            os.close(master)
            os.close(slave)


if __name__ == '__main__':
    unittest.main()
