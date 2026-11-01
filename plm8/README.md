# Intel PL/M-8 3.3

## Optional local-image component — setup first

Historical compiler executables, tape archives and generated PL/M HEX are not
distributed or automatically downloaded. The runner, recovery utility and own
PL/M example sources are included under the project license. Redistribution
permission for the historical Intel/Fortran images and their runtime-bearing
output has not been established; source availability is not a license grant.

If you have the right to use the pinned images, run from the repository root:

```sh
python3 setup.py --plm-images /path/to/lawfully-obtained/images
```

Alternatively use `--plm-tape /path/to/169278.tape.bz2` to recover images from a
lawfully obtained matching archive. Pins and provenance are in
[upstream/NOTICE.txt](upstream/NOTICE.txt). Setup validates inputs and rebuilds
all five examples locally. Compiler images and generated HEX stay ignored.
The following usage assumes setup is complete; it does not assert historical
software use or redistribution rights.


The original Intel 8008 PL/M cross-compiler now compiles programs for ntv8008.
The recovered passes identify themselves as **PLM1 VERS 3.3** and **PLM2 VERS 3.3**.
These are the 8008 compilers, not the similarly named PLM81/PLM82 8080 compilers.

The compiler's Fortran source was not found. The locally supplied original PDP-10
executables run under `pdp10.py`, a Python 3 runner for the integer instructions
and Fortran I/O they use. No Fortran compiler, assembler, historical operating
system, third-party Python packages, or network access is needed to compile.
Generated programs run as ordinary machine code in the unmodified 8008 emulator.

## Compile and run

From the repository root on Linux/macOS:

```sh
./m.sh
python3 plm8/compile.py plm8/examples/hello.plm
./ntv8008 plm8/examples/hello.hex
```

On Windows, from a Visual Studio developer command prompt:

```bat
call m.bat
py -3 plm8\compile.py plm8\examples\hello.plm
ntv8008.exe plm8\examples\hello.hex
```

Both print `HELLO, PL/M-8!`. Use `-o program.hex` to select an output path and
`--listing program.lst` to save the original compiler's two-pass listing.
`plm8/rebuild.sh` and `plm8/rebuild.bat` rebuild all five included examples.
The Windows script prefers `py -3`, falls back to `python`, and honors `PYTHON`.
The shell script also honors `PYTHON`.

```sh
python3 plm8/compile.py plm8/examples/arithmetic.plm
./ntv8008 plm8/examples/arithmetic.hex
python3 plm8/compile.py plm8/examples/sieve.plm
./ntv8008 -p plm8/examples/sieve.hex
```

Arithmetic prints `OK` after checking byte wraparound, 16-bit arithmetic,
multiply/divide/remainder, shifts, indexed arrays, based pointers, and procedure
calls. Sieve runs ten iterations over 8191 odd candidates and prints `1899`.
It uses 167,529,328 clock periods, approximately 335.06 seconds at 500 kHz.
Compilation runs separately and is considerably slower than executing the
compiled program.

The `e` and `ttt` examples port the algorithms from the DOS Intel PL/M-83
examples. Compile them with `compile.py` or either rebuild script:

```sh
./ntv8008 -p plm8/examples/e.hex
./ntv8008 -p plm8/examples/ttt.hex
```

E prints 192 digits of e without a decimal point, followed by `DONE`.
It uses 322,904,266 clock periods. TTT runs ten iterations of ascending-move
alpha-beta search from corner, edge, and center openings, verifies that each
score is a tie, and prints `6493 MOVES` (the final iteration's node count).
It uses 465,342,822 clock periods. Explicit arrays hold the search frames:
PL/M-8 procedure locals are static, and recursive calls would overflow the
8008 return stack. Both examples need no keyboard input.

The benchmark algorithms and workloads are retained. Sieve uses based pointers
for flag traversal and marking, preserving BYTE's candidate order and starting
multiple. E shares the quotient between division and remainder calculations,
stores remainders and counters as bytes, and explicitly widens values before
multiplication. TTT short-circuits its last-move win checks and keeps the active
alpha, beta, and value in byte scalars, saving them to arrays before descent and
restoring them on return. Sieve and TTT also reuse the print routine's quotient.

Measured optimization comparisons, including program initialization and output:

| Benchmark | Original cycles | Optimized cycles | Reduction |
| --- | ---: | ---: | ---: |
| Sieve | 175,896,306 | 167,529,328 | 4.8% |
| E | 396,084,892 | 322,904,266 | 18.5% |
| TTT | 510,968,730 | 465,342,822 | 8.9% |

Using a pointer only for sieve marking took 171,412,308 cycles; pointer traversal
for filling and scanning improved that further. Based pointers for all four TTT
frame arrays took 508,889,362 cycles, so the scalar-cache version was retained.

## Source conventions

* Start programs with `64:` to match ntv8008's default entry at decimal 64.
  Other numeric origins are supported; select the corresponding `-a:address`
  when running the HEX file. The compiler's own default origin is zero.
* The original compiler accepts uppercase source and a limited character
  alphabet. The wrapper rejects unsupported characters outside comments,
  including inside string literals, because the old lexer silently replaces
  them with spaces. Use numeric ASCII initializers for other characters:
  `33` for `!`, `13` for the console newline. Comments may use lowercase.
* Source lines have at most 72 columns. Tabs expand to eight-column stops.
* `OUTPUT(2)=VALUE;` writes to ntv8008's console. PL/M numbers output ports from
  zero: PL/M port 2 is physical 8008 port 10, octal 12. `INPUT(2)` reads the
  keyboard port, with bit 7 indicating a ready character.
* `BYTE` is 8 bits; `ADDRESS` is 16 bits. Addresses used for memory must fit
  the 8008's 14-bit address space. The complete program and variables share
  16 KiB. Procedure nesting must respect the processor's small return stack.
* `HALT;` ends the app. The wrapper appends the compiler's `EOF` token when
  the source does not already end with it.
* Syntax and code-generation errors fail compilation. An existing output file
  is left intact on failure. Intel HEX lengths, checksums, memory bounds, and
  the end record are checked before writing the output.

The original object file has paper-tape decoration and a zero-length type-zero
terminator. The wrapper removes the decoration and replaces that terminator
with modern Intel HEX EOF `:00000001FF`. It preserves generated data bytes and
addresses. It does not translate 8080 code or implement a new PL/M compiler.

## Recovery and provenance

The images came from the `(UPL)` directory of Tymshare tape **169278**, archived
at [VTDA](https://vtda.org/bits/software/DEC/PDP-10/tymshare/169278.tape.bz2).
The original tape catalog separately lists PLM1/PLM2 and PLM81/PLM82.
See [upstream/NOTICE.txt](upstream/NOTICE.txt) for checksums and attribution.

To reproduce the extraction without building any archive utilities:

```sh
curl -fL https://vtda.org/bits/software/DEC/PDP-10/tymshare/169278.tape.bz2 \
    -o /tmp/169278.tape.bz2
python3 plm8/recover.py /tmp/169278.tape.bz2 --output /tmp/recovered-plm8
```

This downloads roughly 379 MiB. Recovery verifies the compressed tape's SHA-256,
extracts only the two compiler files, and verifies their SHA-256 before writing.
Each extracted 36-bit word is stored in an eight-byte little-endian container;
the original word values, entry instructions, and trailing tape words remain.
An off-by-one in the older `tito` extractor drops the final word of a file's
first tape record. `recover.py` includes that word; both images were verified
by independent extraction with the corrected utility.

The host runner installs the saved Fortran local-UUO vector and provides local
TTY/DSK I/O. It returns immediately from the old Tymshare RTYACT accounting
wrapper, which depends on a discontinued service. The wrapper is recognized by
its instruction sequence, and both complete compiler images are hash-checked.
Only that accounting entry is changed in the runner's memory; the files on
disk and the compiler's parser and code generator remain unchanged.
The runner deliberately supports these two executables, not general PDP-10
software, floating-point programs, or arbitrary TYMCOM-X services.

Useful references:

* [Intel's September 1973 PL/M programming guide](https://www.bitsavers.org/components/intel/MCS8/MCS-8_A_Guide_to_PLM_Programming_Sep73.pdf):
  language and 8008 runtime conventions; control switches differ in version 3.3.
* [Tymshare tape listings](https://vtda.org/bits/software/DEC/PDP-10/tymshare/169278.txt).
* [Lars Brinkhoff's archive tools](https://github.com/larsbrinkhoff/pdp10-its-disassembler):
  used to inspect the tape and disassemble the original executables.
* [DEC's PDP-10 System Reference Manual](https://bitsavers.org/pdf/dec/pdp10/KA10/DEC-10-HGAA-D_PDP-10_System_Reference_Manual_196805.pdf)
  and [TOPS-10 monitor call definitions](https://pdp-10.trailing-edge.com/decuslib20-04/01/decus/20-0131/uuosym.mac.html).

## Tests

`./test.sh` and `test.bat` include the PL/M tests. To run just this suite after
building ntv8008:

```sh
python3 tests/plm8.py
```

Tests compile and execute the examples, compare e against Python Decimal and
TTT against an independent minimax search, exercise multi-buffer intermediate
files and `DO CASE`, reject invalid source/object records, and check CLI paths
with spaces and preservation of existing HEX output after a compile error.

### Inlined TTT win dispatch

The last-move DO CASE and its short-circuit comparisons now live in the
explicit-frame search. Winning checks jump to a shared score handler and then
the existing return path, avoiding WINNER2's static parameter transfer and
hardware call/return. Root setup skips the shared handler before entering the
search. Search frames, byte state, ascending moves, three drawn openings and
ten iterations of 6493 nodes are unchanged.

Inlining reduces TTT from 475,999,642 to 465,342,822 clocks (2.2% fewer), or
95.2 to 93.1 simulated seconds per iteration at 500 kHz. A duplicated-handler
layout measured 464,937,262 clocks, but its additional code was not retained
for a further 0.09% saving. The shared-handler source is smaller and keeps
winning-score handling in one place.
