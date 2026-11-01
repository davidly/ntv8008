# Hunt the Wumpus for SmallC and ACK C

One shared traditional-C source adapts David Lee's
[dcc example](https://github.com/davidly/dcc/blob/1d4dff6e140b795899d5f4b7045636daf1c6ac72/tests/wumpus.c)
to the freestanding 16 KiB 8008 machine. It includes human and computer play,
the twenty-room dodecahedron cave, two pits, two bat rooms, five crooked arrows,
nearby-hazard warnings and replay. This directory retains the original MIT
[license](LICENSE); the surrounding repository uses BSD-3-Clause.

## Build and play

From the repository root after `setup.sh --smallc --ack` (or Windows
`setup.bat --smallc --ack`):

```sh
python3 examples/wumpus/build.py smallc
python3 examples/wumpus/build.py ack
python3 examples/wumpus/run.py smallc
python3 examples/wumpus/run.py ack
```

Windows uses `py -3` instead of `python3`. Building C needs the toolchain already
installed by setup. Output images, assembly, listings and automatic trace maps
are under `examples/wumpus/build/`, with names `smallc.hex` and `ack.hex`.
The run wrapper executes the last build and forwards additional emulator flags.

Choose `H` for human or `C` for computer play, followed by Enter. Enter a seed
from 1 to 32767; 317 gives a reproducible starting cave, and 0 also selects 317.
All answers are line-oriented. Enter `S` to shoot or `M` to move, then answer
the room-number prompts. Room numbers are 1 through 20. Arrows can visit one
through five rooms; a nonexistent tunnel redirects that step randomly. A path
that doubles back to its room from two specified steps ago is rejected. Hitting
yourself, falling in a pit, meeting the Wumpus or exhausting your arrows loses.
Bats can carry you to another hazard. Type `Q` at the action prompt to quit.
After a game, `Y` restores the initial positions and five arrows, `N` generates
a new cave, and `Q` quits. Replay does not reset the random generator.

Computer mode knows all hazard positions, as in the source's `-c` mode. A
breadth-first search finds a shortest shot to the Wumpus. The cave diameter is
five, so this demonstration wins with one arrow and then halts. Input mode and
seed prompts replace target command-line arguments, which these runtimes lack.

## Recorded play and testing

```sh
python3 examples/wumpus/run.py smallc -p -l:examples/wumpus/sessions/computer.txt
python3 examples/wumpus/run.py ack -p -l:examples/wumpus/sessions/win.txt
python3 examples/wumpus/run.py ack -t -i -l:examples/wumpus/sessions/computer.txt
python3 tests/wumpus.py --compile
```

Paths above assume the repository root. LF session files include all responses,
including replay/quit where needed. The deterministic human winning shot for seed
317 is `17,16,15,14` from room 18. The final test command builds both compilers
and checks exact transcripts for winning, pits, bats, self-shooting, missed shots,
replay, invalid/overflowing input, editing, line limits and crooked-arrow checks.
Additional computer seeds exercise different layouts. `test.sh --compile` and
`test.bat --compile` include these tests; plain runs skip this build-dependent suite.

The expected transcripts were independently executed with the same adapted source
on a native host C compiler, with an explicit 16-bit random-generator mask. No
host compiler or original dcc checkout is needed to build or test the 8008 example.

## Porting choices

The cave is a flat byte array, indexed by `room*3+tunnel`. Global byte arrays
replace the original game-state struct and pointer parameters. K&R definitions,
declarations before statements, and globals before all functions accommodate the
SmallC frontend. The software stack handles calls; no recursive cave search is
needed. Numeric paths still use integer arrays to keep the pointer interface
simple. `putchar`, `puts`, `getchar` and `putu` replace hosted stdio and ctype.
Line input echoes characters, handles backspace and rejects numbers above 32767;
it drains overlong lines and discards them instead of accepting a truncated command.
EOF exits through the emulator, rather than returning a target C EOF value.

Instructions are condensed to keep SmallC's image within its stack reservation.
The pseudo-random generator is deterministic, not cryptographic, and its seed
must be supplied explicitly. The 500 kHz estimate includes setup and console
processing; do not expect modern-machine responsiveness when using `-s:500000`.
