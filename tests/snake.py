#!/usr/bin/env python3
"""ANSI Snake, nonblocking console ports, and optional SmallC rule tests."""
from pathlib import Path
import re
import os
import time
import subprocess
import sys
import tempfile
import unittest
from integration import ROOT, HOST, ASSEMBLER, run

COMPILE = '--compile' in sys.argv
if COMPILE:
    sys.argv.remove('--compile')


class Console(unittest.TestCase):
    def assemble(self, text, data=b'', options=()):
        with tempfile.TemporaryDirectory() as directory:
            asm=Path(directory)/'console.asm';image=asm.with_suffix('.hex')
            asm.write_text(' ORG 40H\n'+text+'\n END\n')
            result=subprocess.run([str(ASSEMBLER),str(asm),'-o'+str(image)],capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            return run('-n:100000',*options,image,data=data)

    def test_status_preserves_bytes_and_reports_eof_without_halting(self):
        result=self.assemble('''READY: INP 1
 NDA
 JTZ READY
 RLC
 ADI 48D
 OUT 12
 INP 1
 RLC
 ADI 48D
 OUT 12
 INP 2
 OUT 12
 INP 1
 RLC
 ADI 48D
 OUT 12
 INP 2
 OUT 12
 INP 1
 RLC
 ADI 48D
 OUT 12
 HLT''',b'AB')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,b'11A1B0')

    def test_blocking_read_followed_by_poll(self):
        result=self.assemble(' INP 2\n OUT 12\n INP 1\n RLC\n ADI 48D\n OUT 12\n INP 2\n OUT 12\n HLT',b'AB')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,b'A1B')

    def test_no_input_does_not_block(self):
        result=self.assemble(' INP 1\n RLC\n ADI 48D\n OUT 12\n HLT')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,b'0')

    def test_remapped_ports(self):
        for options,status in ((('--in:4',),3),(('--in:4','--status:0'),0)):
            result=self.assemble(f'READY: INP {status}\n NDA\n JTZ READY\n INP 4\n OUT 12\n HLT',b'K',options)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout,b'K')
        for option in ('--status:8','--status:2'):
            result=run(option,ROOT/'a08/hello.hex')
            self.assertNotEqual(result.returncode,0)

    def test_status_on_file_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'keys.txt';source.write_bytes(b'K')
            result=self.assemble(' INP 1\n INP 2\n OUT 12\n INP 1\n RLC\n ADI 48D\n OUT 12\n HLT',options=('-l:'+str(source),))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout,b'K0')

    def test_open_empty_pipe_does_not_block(self):
        # Unlike run(input=b''), keep the writer open: neither data nor EOF exists.
        with tempfile.TemporaryDirectory() as directory:
            asm=Path(directory)/'poll.asm';image=asm.with_suffix('.hex')
            asm.write_text(' ORG 40H\n INP 1\n RLC\n ADI 48D\n OUT 12\n HLT\n END\n')
            result=subprocess.run([str(ASSEMBLER),str(asm),'-o'+str(image)],capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            process=subprocess.Popen([str(HOST),str(image)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                self.assertEqual(process.wait(timeout=5),0)
                self.assertEqual(process.stdout.read(),b'0')
            finally:
                if process.poll() is None: process.kill()
                process.communicate()


class Snake(unittest.TestCase):
    def test_quit_and_ansi_output(self):
        result=run('-n:5000000',ROOT/'smallc/examples/snake.hex',data=b'q')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(result.stdout.startswith(b'\x1b[2J\x1b[1;1H8008 SNAKE'))
        self.assertIn(b'\x1b[22;1HBye!\n',result.stdout)
        # Only portable clear-screen/cursor-position sequences are emitted.
        self.assertNotIn(b'\x1b',re.sub(rb'\x1b\[(?:2J|\d+;\d+H)',b'',result.stdout))

    @unittest.skipIf(os.name=='nt','requires a POSIX pseudo-terminal')
    def test_throttled_keyboard_and_terminal_restoration(self):
        import pty
        import termios
        import select
        master,slave=pty.openpty()
        saved=termios.tcgetattr(slave)
        process=None
        try:
            started=time.monotonic()
            process=subprocess.Popen([str(HOST),'-s:500000','-p',str(ROOT/'smallc/examples/snake.hex')],
                                     stdin=slave,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            # The title is printed after the host has configured raw keyboard input.
            self.assertTrue(select.select([process.stdout],[],[],10)[0])
            self.assertEqual(process.stdout.read(4),b'\x1b[2J')
            self.assertFalse(termios.tcgetattr(slave)[3] & termios.ICANON)
            os.write(master,b'q')
            output,error=process.communicate(timeout=15)
            elapsed=time.monotonic()-started
            self.assertEqual(process.returncode,0,error)
            self.assertIn(b'Bye!\n',output)
            clocks=int(re.search(rb'(\d+) cycles',error)[1])
            self.assertGreaterEqual(elapsed,clocks/500000*0.9)
            self.assertEqual(termios.tcgetattr(slave),saved)
        finally:
            if process is not None and process.poll() is None:
                process.kill();process.communicate()
            os.close(master);os.close(slave)

    def test_moves_without_input_and_hits_wall(self):
        result=run('-p','-n:5000000',ROOT/'smallc/examples/snake.hex')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(b'Game over!\n',result.stdout)
        self.assertIn(b'\x1b[12;33HO',result.stdout)  # reaches rightmost cell
        self.assertNotIn(b'\x1b[12;34HO',result.stdout)  # does not overwrite wall
        self.assertIn(b'500000 Hz',result.stderr)


@unittest.skipUnless(COMPILE,'pass --compile to test SmallC rules and helpers')
class Rules(unittest.TestCase):
    def compile_run(self, text, data=b''):
        sys.path.insert(0,str(ROOT/'smallc'))
        from compile import compile_source
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'rules.c';source.write_text(text)
            image,_,_=compile_source(source)
            target=source.with_suffix('.hex');target.write_text(image)
            result=run('-p','-n:5000000',target,data=data)
            self.assertEqual(result.returncode,0,result.stderr)
            return result

    def rules(self, body):
        source='#include "'+str(ROOT/'smallc/examples/snake_game.c')+'"\n'
        result=self.compile_run(source+'main() { int i; newgame(); '+body+' putchar(75); return 0; }\n')
        self.assertEqual(result.stdout,b'K')
        return result

    def test_turns_growth_and_collision(self):
        self.rules('''
 if(length!=4 || head!=3 || tail!=0 || body[head]!=271) return 0;
 turn('a'); if(direction!=0) return 0;
 food=272;
 if(advance()!=2 || length!=5 || tail!=0 || body[head]!=272) return 0;
 if(occupied[food] || erased!=65535) return 0;
 turn('w'); if(direction!=3 || advance()!=1) return 0;
 if(length!=5 || tail!=1 || occupied[268]) return 0;
 turn('a'); if(advance()!=1) return 0;
 turn('s'); if(advance()!=0) return 0;
 ''')

    def test_moving_into_departing_tail_and_ring_wrap(self):
        self.rules('''
 for(i=0;i<512;++i) occupied[i]=0;
 tail=510; head=1;
 body[510]=33; body[511]=34; body[0]=66; body[1]=65;
 occupied[33]=1; occupied[34]=1; occupied[66]=1; occupied[65]=1;
 direction=3; food=300;
 if(advance()!=1 || tail!=511 || head!=2 || body[head]!=33 || occupied[33]!=1) return 0;
 turn('a'); if(advance()!=1 || tail!=0 || head!=3 || occupied[34]) return 0;
 ''')

    def test_all_walls(self):
        for position,direction in ((31,0),(480,1),(32,2),(1,3)):
            with self.subTest(direction=direction):
                self.rules(f'body[head]={position}; direction={direction}; if(advance()!=0) return 0;')

    def test_full_board(self):
        self.rules('''
 for(i=0;i<512;++i) occupied[i]=1;
 occupied[272]=0; food=272; length=511;
 if(advance()!=3 || length!=512 || occupied[272]!=1) return 0;
 ''')

    def test_waitkey_and_kbhit(self):
        for data,expected in ((b'',b'0,65535,65535'),(b'A',b'128,65535,65'),
                              (b'AB',b'128,65535,66'),(b'ABC',b'128,65535,67')):
            result=self.compile_run('''#include <stdio.h>
main() { putu(kbhit()); putchar(','); putu(waitkey(0));
 putchar(','); putu(waitkey(1)); return 0; }
''',data)
            self.assertEqual(result.stdout,expected)
        result=self.compile_run('main() { waitkey(100); return 0; }')
        cycles=int(re.search(rb'(\d+) cycles',result.stderr)[1])
        self.assertGreater(cycles,52000)
        self.assertLess(cycles,57000)

    def test_movement_cost_does_not_grow_with_length(self):
        short=self.rules('advance();')
        long=self.rules('length=500; advance();')
        cycles=lambda r:int(re.search(rb'(\d+) cycles',r.stderr)[1])
        self.assertLess(abs(cycles(long)-cycles(short)),3000)


if __name__=='__main__': unittest.main()
