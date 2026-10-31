# SCELBAL BASIC for ntv8008

## Optional noncommercial component — setup first

The interpreter and its generated assembly/HEX are not distributed here.
Read [NOTICE.txt](NOTICE.txt), then explicitly acknowledge its educational,
historical, noncommercial terms if they fit your intended use:

```sh
python3 setup.py --scelbal --accept-scelbal-terms
```

Run this from the repository root (Windows: `py -3` instead of `python3`).
Setup fetches the pinned official source, retains its complete required notice,
and builds locally. `SCELBAL_SOURCE` can name an already obtained matching source
file for offline setup. Sources and derivatives are Git-ignored. This does not
grant commercial rights. The BASIC example programs are separate project code.


The 2012 fast version of Mark G. Arnold and Nat Wadsworth's SCELBAL runs as native
8008 machine code in ntv8008. Its floating-point interpreter, program editor,
arrays, and control flow are executed by the emulated CPU.

From the repository root on Linux or macOS:

```sh
./m.sh
./ntv8008 a08/scelbal.hex
```

From a Visual Studio developer command prompt on Windows:

```bat
m.bat
ntv8008.exe a08\scelbal.hex
```

The interpreter starts at the host's default entry, `0x40`, initializes itself,
and displays `READY`. Try:

```text
PRINT 2+2
10 PRINT "HELLO, SCELBAL!"
20 FOR I=1 TO 5
30 PRINT I,I*I
40 NEXT I
50 END
RUN
```

`LIST` displays stored lines; entering an existing line number replaces its line;
entering a line number alone deletes that line. `SCR` clears the program and
variables. `RUN` starts the stored program. Ctrl-C or Ctrl-Q exits the emulator.
Backspace and Delete perform SCELBAL's rubout operation (displayed as a backslash).
Input is converted to uppercase, including text inside quotes. Keep lines within
79 characters and leave spaces between keywords, as required by this fast version.

For reproducible input, pass a text session containing numbered lines followed
by `RUN`. EOF exits the emulator. These two examples are included:

```sh
./ntv8008 -l:scelbal/examples/hello.bas a08/scelbal.hex
./ntv8008 -l:scelbal/examples/features.bas a08/scelbal.hex
```

Windows accepts the same options with backslash paths:

```bat
ntv8008.exe -l:scelbal\examples\hello.bas a08\scelbal.hex
```

`hello.bas` prints a greeting and sums 1 through 10. `features.bas` checks array
access and loops, branches to verify a sum of squares, calls a subroutine, reads
21 through `INPUT`, and prints 42, -2, 0.125, and the square root of 81. It includes
the reply to `INPUT` after `RUN`, so it can run without a keyboard.

## Building and provenance

The ready-to-run image is `a08/scelbal.hex`; the self-contained adapted source is
`a08/scelbal.asm`. It builds with our existing assembler:

```sh
./a08/rebuild.sh scelbal.asm
```

```bat
a08\rebuild.bat scelbal.asm
```

SCELBAL is excluded from default rebuilds. After optional setup, the explicit
commands above use the locally built A08. No network is needed with cached
verified dependencies. The locally downloaded source is preserved at `upstream/sc1fast.asm`,
downloaded from [Mike Willegal's SCELBAL archive](https://www.willegal.net/scelbi/scelbal.html),
[2012 fast source](https://www.willegal.net/scelbi/software/sc1fast.asm).
Its SHA-256 at download is:

```text
f687a816cfd115cb2632c610341f75a6f64c713d7c526319357f1b8ab93853dc
```

`prepare.py` regenerates the adapted source entirely offline:

```sh
python3 scelbal/prepare.py
python3 scelbal/prepare.py --check
```

On Windows use `py -3` or your Python 3 command. The generated source is created locally,
so Python is only needed for regeneration and the test suite. Change the console
adaptation in `prepare.py`, then regenerate rather than editing generated code.

The adaptation retains the upstream interpreter's layout after page zero. It
converts AS8's HIGH/LOW spelling, decimal reservation counts, and mark-parity text
constants for A08, and renames labels that conflict with A08 expression operators.
Page-zero character input/output replaces the original 110-baud bit-serial driver.
The entry point jumps to the existing SCR initialization before presenting READY.
The driver uses input port 2 and output port octal 12. It preserves the registers
required by the interpreter, echoes input, and suppresses the old terminal-control
character and CR portion of CR/LF pairs. No emulator instruction or host I/O changes
were needed. A08's RTS encoding was corrected from RFS (`0x13`) to RTS (`0x33`).

## Limits and validation

This is the base fast SCELBAL interpreter; optional historical supplements are
not included. `SAVE` and `LOAD` retain the upstream unimplemented behavior and
return to READY. Keep BASIC programs as host text files and feed them with `-l`.
The `UDF` machine-code hook is uninstalled and halts if called. Memory limits,
variable limits, numerical precision, syntax, and error codes are those of the
archived interpreter; this is not Microsoft BASIC or a modern BASIC dialect.

`test.sh` and `test.bat` assemble SCELBAL and check source regeneration, HEX
reproducibility, cold start, direct arithmetic, FOR/NEXT, arrays, IF/THEN,
GOSUB/RETURN, INPUT, negative and fractional numbers, square roots, line editing,
and rubout. The A08 RTS encoding has a separate regression check. Linux and
Windows (Visual Studio 2022) runs have passed.

## Original terms

SCELBAL is copyright 1975 Scelbi Computer Consulting, Inc., all rights reserved.
The archived source grants permission for **educational, historical,
non-commercial purposes**, with no warranty. Its complete original notice is
retained in both the archived and adapted assembly sources and in `NOTICE.txt`.
These terms apply to SCELBAL; do not assume it has the same terms as other code in
this repository.

## BASIC benchmark ports

The BASIC versions of the three benchmarks are in `examples/sieve.bas`,
`examples/e.bas`, and `examples/ttt.bas`. They start from the Microsoft BASIC-80
programs in David Lee’s `cpm_compilers/microsoft basic-80 v52` benchmark sources (see PROVENANCE.md), adapted to SCELBAL.
Each file includes `RUN`, so either stdin redirection or `-l` executes it:

```sh
./ntv8008 -p a08/scelbal.hex < scelbal/examples/sieve.bas
./ntv8008 -p a08/scelbal.hex < scelbal/examples/e.bas
./ntv8008 -p a08/scelbal.hex < scelbal/examples/ttt.bas
```

On Windows:

```bat
ntv8008.exe -p a08\scelbal.hex < scelbal\examples\ttt.bas
```

These are interpreted BASIC computations, without machine-code helpers or changes
to SCELBAL. Their full workloads are retained:

| Program | Expected output after the echoed `RUN` |
| --- | --- |
| `sieve.bas` | `1899 PRIMES` followed by `10 ITERATIONS` |
| `e.bas` | The first 192 digits of e without a decimal point, followed by `DONE` |
| `ttt.bas` | `1 ITERATIONS` followed by `FINAL MOVE COUNT 6493` |

SCELBAL's arrays are one-based and share a 256-byte array-values page: at most 64
four-byte floating-point elements in total. The ports therefore use these layouts:

* Sieve processes the original 8191 odd-number candidates in segments of 63 flags,
  and repeats all segments ten times. Odd divisors up to the square root of each
  segment's largest candidate strike out their odd multiples, starting at the
  divisor's square. Composite divisors cause harmless repeated clearing. Segment
  bounds and divisor squares are cached; marking uses local array indices and
  FOR/NEXT rather than a GOTO for every multiple. The existing segmented sieve
  and its full ten-pass workload are retained, without a precomputed prime list.
* E uses 50 base-10000 chunks for fixed-point arithmetic, with an integer chunk
  and 196 fractional digits. It evaluates the factorial series backwards using
  `X=(X+1)/N` for N=200 down to 1, then adds one and prints 192 digits. This
  replaces BASIC-80's large remainder array and unsupported MOD/integer division.
  Guard digits protect the printed prefix; quotient estimates are corrected by
  comparisons before taking a remainder. Each quotient product is computed once
  and updated with its correction, avoiding repeated multiplication.
* TTT combines its board and four saved-state arrays into `A(45)`: elements 1–9
  are the board, 10–18 saved move positions, 19–27 saved values, 28–36 saved alpha,
  and 37–45 saved beta. As in the original, GOTOs and saved state simulate
  recursion; GOSUB is used only for shallow helpers. Ascending move order,
  alpha-beta pruning, and first positions 0, 1, and 4 are preserved. Every starting
  position is checked for a tie; a failed check prints `FAIL`.
  Turn parity toggles on descent and unwind. Win checks examine only lines
  through the last move, and the search routine precedes the winner helper to
  reduce SCELBAL's linear branch-target searches. These changes preserve the
  search order and the 6493-node count.

Integer counters are printed digit by digit with `CHR`, avoiding the original
SCELBAL number formatter's small decimal artifacts (for example, it displays the
integer 6493 as `6493.002`). `%` type suffixes, ELSE, colon-separated statements,
and bitwise AND have been replaced with SCELBAL expressions and branches. The
interpreter's FOR counter stays at the final value, so the iteration reports use
that value instead of BASIC-80's final value minus one.

The full BASIC benchmarks are slower than the assembly versions. Run their
separate regression suite when desired; it takes about a minute on the development
Linux host and is not part of the short `test.sh` / `test.bat` suite:

```sh
./test_basic.sh
```

```bat
test_basic.bat
```

These scripts build the emulator and SCELBAL, then run `tests/basic_benchmarks.py`.
The checks independently count the primes, compare all 192 e digits with Python
Decimal, and verify TTT's result against the Python minimax reference. The full suite has passed on Linux and Windows (Visual Studio 2022). Each run
has both a cycle limit and a host timeout. The usual Python 3 requirement and
Windows `PYTHON` override apply.
