# ntv8008

A portable Intel 8008 emulator, native compiler backends and runnable examples.
The emulator implements the full instruction set, 16 KiB of RAM, console I/O,
instruction tracing and cycle accounting. Programs execute 8008 machine code;
compiler frontends and interpreters do not run inside the host as shortcuts.

Project code is **BSD-3-Clause**. Included third-party components retain their
own permissive terms. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and
[PROVENANCE.md](PROVENANCE.md) for the exact publication boundary. Historical
components with restricted or unresolved permissions are optional local inputs,
not part of the published source or binary images.

## Contents

| Path | Contents |
| --- | --- |
| `i8008.cxx`, `i8008.hxx` | Complete 8008 CPU implementation and embedding interface; instruction decoding, flags, interrupt injection, RAM access and clock-period accounting. |
| `ntv8008.cxx`, `trace.hxx` | Command-line host, Intel HEX loader, keyboard/console callbacks, speed limiting and optional debug/instruction tracing. |
| `a08/` | Original assembly demos and sieve/e/TTT benchmarks, Robson's adapted MIT interpreter, runnable HEX images, and scripts for the official A08 dependency. |
| `ack/` | ACK EM-to-8008 code generator, RAM-stack runtime, optimizer passes, host bootstrap, C/Pascal/Modula-2/BASIC/Occam integrations and examples. |
| `smallc/` | Preserved SmallC-85 frontend, new 8008 code generator/runtime, host build scripts, C benchmarks and ANSI Snake. |
| `robson/` | Original MIT Tiny BASIC source/license, console adaptation and small BASIC examples. |
| `scelbal/`, `forth/`, `plm8/` | Optional historical-language integration tools and project-authored examples; restricted or uncleared interpreter/compiler images are not bundled. |
| `tests/` | Native CPU tests, integration/console checks, compiler regression and differential tests, benchmark references and publication checks. |
| `tools/` | Verified dependency fetching/building, benchmark runner and publication-inventory audit. |
| `LICENSE`, `THIRD_PARTY_NOTICES.md`, `PROVENANCE.md` | Project BSD license, retained third-party licensing references and source provenance. |

## Build and run

Full setup on Linux/macOS requires a C++11 compiler, C compiler and Python 3.8 or newer.
Windows builds use Python 3 and a Visual Studio developer command prompt.
Building the emulator alone needs only the C++ compiler; running it needs no
Python, assembler or compiler frontend. Checked-in HEX examples work immediately:

```sh
git clone https://github.com/davidly/ntv8008.git
cd ntv8008
./m.sh
./ntv8008 -p a08/hello.hex
./ntv8008 -p ack/examples/sieve.hex
```

Windows equivalents:

```bat
m.bat
ntv8008.exe -p a08\hello.hex
ntv8008.exe -p ack\examples\sieve.hex
```

To fetch/build A08, rebuild the project assembly examples and Robson Tiny BASIC:

```sh
./setup.sh
./ntv8008 a08/echo.hex
./ntv8008 -l:robson/examples/hello.bas a08/robson.hex
```

On Windows use `setup.bat`. `PYTHON` can select another Python 3 command.
Setup writes only inside this directory and makes no system-wide installation.
Downloaded archives are checksum-verified; network access is needed only for
uncached dependencies. A08 is fetched from its official site, not bundled.

## Compilers and interpreters

| Tool | Included here | Rebuild |
| --- | --- | --- |
| A08 assembly | Project examples and runnable HEX; assembler fetched separately | `./a08/rebuild.sh` |
| [ACK C](ack/README.md) | New 8008 backend/runtime, examples, HEX; frontend downloaded | `python3 setup.py --ack` |
| [ACK Pascal](ack/pascal/README.md) | Same backend, original Pascal support, examples and HEX | `python3 setup.py --ack` |
| [ACK Modula-2](ack/modula2/README.md) | Same backend, original InOut support, examples and HEX | `python3 setup.py --ack` |
| [ACK Occam 1](ack/occam/README.md) | Sequential subset, original console runtime, five examples and HEX | `python3 setup.py --ack` |
| [ACK integer BASIC](ack/basic/README.md) | Same backend, original BASIC runtime, examples and HEX | `python3 setup.py --ack` |
| [SmallC-85 C](smallc/README.md) | Permitted frontend source, new backend/runtime, examples and HEX | `python3 setup.py --smallc` |
| [Robson Tiny BASIC](robson/README.md) | MIT interpreter, adaptation, examples and HEX | `python3 setup.py` |
| b8008 integer BASIC | Original BSD interpreter, byte/word arrays, full benchmarks | [b8008 guide](b8008/README.md) |
| SCELBAL floating-point BASIC | Integration and examples; optional noncommercial download | [SCELBAL setup](scelbal/README.md) |
| Baker 8008-Forth | Integration, native additions and examples; kernel not included | [Local-source setup](forth/README.md) |
| Intel PL/M-8 | Runner, recovery tool and example sources; compiler/output images not included | [Local-image setup](plm8/README.md) |

`./setup.sh --all` builds the default tools plus SmallC and all five ACK frontends
and rebuilds their examples. ACK host builds currently require Linux/WSL with
`make`, `ninja`, `gcc`, `flex` and `yacc` (for example, bison's yacc compatibility
command), plus the usual C/C++ build tools. Lua is downloaded/built locally.
Native Windows setup builds SmallC and the other default tools; ACK images still
run there. Rebuild ACK under WSL, or supply compatible native tools via
`ACK_TOOLS`. See the component READMEs for language subsets and ABI details.
The ACK upstream toolchain has platform assumptions; macOS host rebuilding is
not validated. The emulator and supplied images require no ACK host tools.

All full compiler integrations include sieve, e and tic-tac-toe benchmarks.
Robson's byte-only Tiny BASIC lacks the arrays/precision needed for these full
benchmarks; its own small examples exercise its supported dialect instead.

## Console, options and tracing

Input port 2 supplies a seven-bit character with bit 7 set when ready. Output
physical port 10 (octal 12) writes to the console. Status port 1 returns 0x80
when a character is ready, or zero otherwise, without consuming it or waiting.
Polling EOF returns zero; a blocking input read still exits on EOF.
`--in:port` also moves the default status port to the preceding port (modulo 8);
`--status:port` overrides that choice. Input and status ports must differ.
Keyboard handling uses portable C/C++ plus the appropriate Windows/POSIX console
primitives. Ctrl-C interrupts execution and restores the terminal. Windows
console output enables ANSI processing and restores its original mode on exit.

```sh
./ntv8008 -p a08/sieve.hex
./ntv8008 -t -i -n:100000 a08/hello.hex
./ntv8008 -l:robson/examples/hello.bas a08/robson.hex
./ntv8008 a08/robson.hex < robson/examples/hello.bas
```

`-p` prints emulated clock periods and an approximate runtime at the original
500 kHz clock; host I/O waits are excluded. `-t` creates `ntv8008.log`, and `-i`
adds per-instruction tracing. `-n:count` sets a cycle budget. The default entry
is 0x40; run the emulator without a filename to see all options. All 16 KiB are
RAM; the emulated hardware stack has seven saved return-address slots, while
compiler integrations use software stacks in RAM for deeper calls.

Sieve makes ten passes over 8191 odd candidates and prints 1899 primes. E prints
192 digits. Most compiled TTT examples run ten iterations; assembly, b8008,
and SCELBAL run one. Divide total TTT cycles by the iteration
count for comparisons.

## Snake at 500 kHz

Snake is written in SmallC, with assembly helpers for nonblocking keyboard
polling and a cycle-based delay. The runnable image is included:

```sh
./m.sh
./ntv8008 -s:500000 smallc/examples/snake.hex
```

On Windows, run `m.bat`, then
`ntv8008.exe -s:500000 smallc\examples\snake.hex`.
Use an ANSI-compatible terminal at least 34 columns by 23 rows. WASD steers
(upper or lower case), Q quits, and Ctrl-C interrupts. Reversing directly into
the snake is disallowed. Eat `*` to grow; walls and the snake's body end the game.

At the original 500 kHz clock, the board takes about three seconds to draw;
ordinary movement runs at about five moves per second. Only the new head,
departing tail, food and score changes are drawn. The game uses a circular body
buffer and occupancy map, so moving a longer snake does not require scanning
its body. The delay uses emulated instructions rather than a host clock; other
clock rates scale the game speed. CPU timing does not simulate serial baud rate.

Rebuild with `python3 smallc/compile.py smallc/examples/snake.c` after
`setup.py --smallc`, or use `smallc/rebuild.sh` / `smallc\rebuild.bat`.
`tests/snake.py` checks the supplied image, ANSI output, and console polling;
`--compile` also checks game rules and keyboard/timing helpers. Root test scripts
include these checks. Snake is interactive and is excluded from `perfrun`.

## Build and test scripts

| Script | Purpose |
| --- | --- |
| `m.sh` / `m.bat` | Build just the optimized console emulator. |
| `setup.sh` / `setup.bat` | Build the emulator, fetch/build A08 and regenerate the assembly demos and Robson interpreter. `--all` also builds available host compiler toolchains. |
| `a08/rebuild.sh` / `a08/rebuild.bat` | Reassemble the project assembly examples; accepts individual source filenames. |
| Each compiler's `rebuild.sh` / `rebuild.bat` | Recompile that language's examples after its host tools are available. |
| `test.sh` / `test.bat` | Build and run native CPU tests, then all available integration and compiler runtime tests. `--compile` also exercises compiler frontends and checks regenerated images. |
| `test_basic.sh` / `test_basic.bat` | Run the slow full SCELBAL benchmark tests when the optional interpreter has been installed. |
| `perfrun.sh` / `perfrun.bat` | Build the host and run installed sieve/e/TTT images with cycle and timing reports. |

```sh
./setup.sh
./test.sh
./setup.sh --all
./test.sh --compile
./perfrun.sh
```

Windows: `test.bat`, `test.bat --compile` (with compatible ACK host tools), and
`perfrun.bat`. Tests include CPU instructions, cycle counts, HEX validation,
keyboard/terminal behavior, source regeneration, native compiler differential
tests and reference benchmark results. Missing optional historical components
are explicitly skipped. Windows skips the POSIX terminal-restoration test.
Full optional SCELBAL benchmarks: `./test.sh --basic-benchmarks`.

Validation covers all instruction encodings, arithmetic and branch behavior,
clock counts, HEX loader errors, redirected/file/interactive input, terminal
restoration, and native generated code against unoptimized/reference behavior.
Benchmark outputs are checked against independent prime, decimal and minimax
references. See [VALIDATION.md](VALIDATION.md) for the tested platforms and scope.

## Performance

The emulator runs as fast as the host allows by default. `-s:500000` limits it
to the original 500 kHz clock rate; `-p` reports both host elapsed time and an
estimated real-8008 runtime. The latter is `clock periods / 500000`, independent
of host speed, with no memory wait states or host I/O delays included.

The original [b8008 integer BASIC](b8008/README.md) runs all three benchmarks
with checked byte/word arrays and 16-bit integer arithmetic. Its full sieve flag
array fits in RAM, avoiding SCELBAL's small segmented arrays. The interpreter
and its HEX image are included under BSD-3-Clause; setup needs no historical
BASIC download. Select it with `--languages b8008` in either performance script.

The performance script reports unavailable optional languages and runs every
installed benchmark with `-p`. To select a subset:

```sh
./perfrun.sh --languages assembly ack pascal modula2 smallc
```

Measured from the included images on 2026-10-31. Values below are estimated
**seconds on a 500 kHz 8008**, not seconds elapsed on a modern host:

| Implementation | Sieve | E | TTT per iteration |
| --- | ---: | ---: | ---: |
| A08 assembly | 78.1 | 36.5 | 28.9 |
| ACK C | 321.3 | 343.6 | 145.3 |
| SmallC-85 C | 349.0 | 251.8 | 127.2 |
| ACK Pascal | 639.2 | 575.7 | 475.2 |
| ACK Modula-2 | 740.8 | 526.3 | 319.9 |
| ACK Occam 1 | 1,354.1 | 730.2 | 817.2 |
| ACK integer BASIC | 2,568.7 | 617.0 | 489.2 |
| b8008 integer BASIC interpreter | 11,501.7 | 2,849.9 | 7,339.7 |

ACK and SmallC share conservative native optimizations for byte locals,
register/flag liveness, and frame addresses. Byte values can stay in otherwise
free C/D registers across branches; RAM remains authoritative around calls.
Frame addresses can stay in CD where liveness permits, or reuse HL with explicit
page-crossing adjustments. ACK keeps expression results in AB across eligible
joins instead of pushing and immediately popping them. SmallC also avoids
stacking local assignment addresses, including conditional expressions, and
tracks byte-comparison branch edges when calculating frame offsets.

C TTT still uses recursive minimax, ascending moves, the three opening positions,
and 6493 nodes per iteration. This revision reduces ACK C from 218.8 to 184.5
seconds per iteration (15.7% fewer clocks) and SmallC from 209.1 to 152.5 (27.1%).
The general RAM-stack calling convention is retained; reserving scratch registers
throughout every function would require additional save/restore traffic.

The C benchmarks now inline the last-move winner switch inside `minmax()`,
returning the score directly when a winning line is found. This source change
further lowers TTT to 152.3 seconds for ACK C and 131.2 for SmallC. The recursive
search, ascending moves, and 6493-node workload are unchanged.

Pascal, Modula-2, and Occam also inline their last-move winner dispatch.
This reduces TTT cycles by 8.0%, 13.3%, and 6.4%, respectively; their search
structure and data types are unchanged. Occam retains explicit frames.

The next compiler/runtime pass leaves those sources unchanged and reduces
ACK C TTT from 152.3 to 145.3 seconds per iteration (4.6% fewer cycles), and
SmallC from 131.2 to 127.2 (3.1%). It fuses unsigned byte increments, uses
direct-memory byte comparisons and shorter zero-offset pointer loads, and
specializes ACK frame entry/exit and SmallC returns.

Assembly TTT retains its nine 16-byte RAM frames, passes the last move to the
winner checker in E, and scans occupied cells in that register. It saves the
resume position only before descending. This reduces one iteration from
16,111,346 to 14,457,102 clocks (10.3% fewer), with the same 6493-node search.

Sieve includes all ten passes; E produces 192 digits. TTT is normalized to one
iteration (6493 search nodes): compiled images run ten iterations, while the
assembly image runs one. The raw `-p` reports contain total cycles/time, so divide
compiled TTT's total runtime by ten to reproduce this table. Robson's Tiny BASIC
cannot run these full workloads. Optional SCELBAL/Forth/PL/M results require their
separate local setup and are not included in this default-image comparison.

The compiler backends use software stacks in RAM, direct constant/array access,
constant arithmetic lowering, quotient reuse and register retention for recognized
loops. The compact 8008 targets provide language/runtime subsets sized for
16 KiB. Individual language READMEs document supported subsets, memory layout and optimization
history. Performance can change as code generation improves; rerun the script
when comparing revisions.

## Licensing and publication inventory

`publication-manifest.json` is the initial reviewed source inventory with hashes
and licensing categories. `python3 tools/publication.py` checks its hashes and
ensures Git's publication candidates exactly match that inventory. Intentionally
modified sources require review before `python3 tools/publication.py --update`.
Downloaded dependencies, historical local inputs, logs, listings, object files
and emulator/assembler binaries are ignored. Do not force-add them or publish a
raw working-directory ZIP. Preserve third-party notices in releases as well as
source checkouts. No GitHub repository is created or pushed by setup.
