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
| `ack/` | ACK EM-to-8008 code generator, RAM-stack runtime, optimizer passes, host bootstrap, C/Pascal/Modula-2/BASIC integrations and examples. |
| `smallc/` | Preserved SmallC-85 frontend, new 8008 code generator/runtime, host build scripts and C examples. |
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
| [ACK integer BASIC](ack/basic/README.md) | Same backend, original BASIC runtime, examples and HEX | `python3 setup.py --ack` |
| [SmallC-85 C](smallc/README.md) | Permitted frontend source, new backend/runtime, examples and HEX | `python3 setup.py --smallc` |
| [Robson Tiny BASIC](robson/README.md) | MIT interpreter, adaptation, examples and HEX | `python3 setup.py` |
| SCELBAL floating-point BASIC | Integration and examples; optional noncommercial download | [SCELBAL setup](scelbal/README.md) |
| Baker 8008-Forth | Integration, native additions and examples; kernel not included | [Local-source setup](forth/README.md) |
| Intel PL/M-8 | Runner, recovery tool and example sources; compiler/output images not included | [Local-image setup](plm8/README.md) |

`./setup.sh --all` builds the default tools plus SmallC and all four ACK frontends
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
physical port 10 (octal 12) writes to the console. EOF ends input-driven apps.
Keyboard handling uses portable C/C++ plus the appropriate Windows/POSIX console
primitives. Ctrl-C interrupts execution and restores the terminal.

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
192 digits. Most compiled TTT examples run ten iterations; assembly and SCELBAL
TTT run one. Divide total TTT cycles by the iteration count for comparisons.

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

The performance script reports unavailable optional languages and runs every
installed benchmark with `-p`. To select a subset:

```sh
./perfrun.sh --languages assembly ack pascal modula2 smallc
```

Measured from the included images on 2026-10-30. Values below are estimated
**seconds on a 500 kHz 8008**, not seconds elapsed on a modern host:

| Implementation | Sieve | E | TTT per iteration |
| --- | ---: | ---: | ---: |
| A08 assembly | 78.1 | 36.5 | 32.2 |
| ACK C | 358.0 | 359.1 | 332.0 |
| SmallC-85 C | 378.2 | 264.2 | 288.9 |
| ACK Pascal | 661.4 | 582.4 | 548.8 |
| ACK Modula-2 | 812.1 | 531.8 | 420.0 |
| ACK integer BASIC | 2,662.2 | 648.5 | 719.4 |

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
