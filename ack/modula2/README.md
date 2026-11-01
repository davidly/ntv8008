# Modula-2 for the 8008

The pinned open-source ACK Modula-2 frontend compiles to the same native 8008
backend as ACK C and Pascal. Calls and expression stacks live in RAM, allowing
recursive programs to exceed the CPU's seven saved return addresses. No EM
interpreter or hosted Modula-2 library is linked.

From the repository root on Linux (or WSL):

```sh
./ack/build.sh
./ack/modula2/rebuild.sh
./ntv8008 -p ack/modula2/examples/ttt.hex
python3 tests/modula2.py --compile
```

Compile your own program:

```sh
python3 ack/modula2.py program.mod -o program.hex \
    --assembly program.asm --em program.e
./ntv8008 program.hex
```

The checked-in HEX files run on Linux, macOS, and Windows. The Windows
`rebuild.bat` wrapper can use native ACK tools via `ACK_TOOLS`; building the
frontend from source is validated on Linux. On Windows, WSL is the supported
way to build the compiler. Run checked-in programs with `ntv8008.exe` and
validate them with `py -3 tests\modula2.py`.

## Examples

* `hello.mod`: console greeting.
* `arithmetic.mod`: eight checks of arithmetic, recursion, arrays with negative
  bounds, `VAR` arguments, and nested procedures accessing enclosing frames.
* `sieve.mod`: ten passes over 8191 byte-sized Boolean flags; 1899 primes.
* `e.mod`: decimal spigot producing 192 digits, followed by `done.`.
* `ttt.mod`: recursive alpha-beta minimax, ten iterations of three opening
  positions; 6493 nodes per iteration. Uses a CASE jump table for the last move.

Root `test.sh` / `test.bat` execute all five images. `perfrun.sh` / `perfrun.bat`
include the three Modula-2 benchmarks with `-p`. The reported clock counts are
for the full workload, including all ten sieve/TTT iterations.

## Console and target subset

The supplied, original `InOut.def` exposes these procedures:

```modula2
PROCEDURE Write(c: CHAR);
PROCEDURE WriteString(s: ARRAY OF CHAR);
PROCEDURE WriteInt(n: INTEGER; width: CARDINAL);
PROCEDURE WriteCard(n, width: CARDINAL);
PROCEDURE WriteLn;
PROCEDURE Read(VAR c: CHAR);
```

Import them with `FROM InOut IMPORT ...`. Strings stop at their first zero byte
or the end of the array. Integer fields use a minimum width. `Read` uses the
emulator's ordinary keyboard/stdin input, including redirection; host EOF ends
execution. This is a compact subset of the usual InOut module, with no files.

INTEGER and CARDINAL are 16 bits; CHAR and BOOLEAN occupy one byte. The tested
subset includes loops, CASE, recursive/nested procedures, scalar returns,
VAR parameters, fixed arrays (including multiple dimensions), and open CHAR
arrays passed to InOut. Signed DIV rounds down and MOD has the divisor's sign,
matching this ACK frontend's runtime semantics. Arithmetic outside the target's
16-bit range wraps; avoid the unrepresentable `MIN(INTEGER) DIV -1` case.

The wrapper compiles one program module with the supplied InOut definition.
Separate user implementation/definition modules, general open-array value
copies, procedure-valued parameters, coroutines, sets, floating point, long
arithmetic, heap allocation, aggregate copies/returns, and other hosted
libraries are outside the supported subset. Unsupported EM operations or
unresolved support procedures fail compilation. Range checks are disabled
(`-R`); array indices and pointers must be valid. At least 512 bytes of RAM are
reserved for the stack, but recursive programs can need more. Stack exhaustion
and division by zero use the shared native runtime diagnostics and halt the
CPU; these emulated halts do not produce a failing host exit code.

The compiler source retains ACK's license. The small console shim is original
project code; array and lexical-frame support is shared with the project's
Pascal integration, without linking ACK's historical libm2 or libpc runtimes.

Fixed array accesses with constant descriptors now use direct address
arithmetic and native loads/stores. Dynamic descriptors retain the generic
runtime path. See the [backend performance notes](../README.md#fixed-array-access-in-pascal-and-modula-2)
for benchmark measurements and details.

The shared quotient-reuse optimization applies to unchanged CARDINAL MOD/DIV
pairs in E, reducing its clock count from 308,859,834 to 266,044,970 (618.0 to
532.1 seconds at 500 kHz), without changing the source. See the
[backend notes](../README.md#native-pascal-arithmetic-and-quotient-reuse).


Signed global-variable marking loops now retain the index in DE and the stride
in BC. The backend recognizes both top-tested and bottom-tested loops and
stores the final index back on exit. Nonnegative indices must be within a
separate known static byte buffer. If an initial or wrapped index is negative,
the backend writes it back and resumes the original loop: unchecked negative
array accesses could otherwise overwrite the retained index or stride.

The unchanged sieve now takes **406,072,124 cycles (812.1 seconds at 500 kHz)**,
down from 1,269.2 seconds, a 36.0% cycle reduction. Differential EM tests
cover both layouts, zero-trip loops, page crossings, signed wrapping, negative
indices that alias the stride, final variable/stack values, and fallback for
unknown buffers, extra entries, aliased operands, or added body effects.

### Inlined TTT win dispatch

The last-move winner dispatch now lives inside the search, avoiding its separate
procedure call. Winning cases return their score immediately; the obsolete result test is removed.
The search order, data types, three drawn openings, 6493 nodes per iteration,
and ten iterations are unchanged. TTT uses 1,628,518,588 clocks instead of
1,879,420,868 (13.3% fewer). This is source inlining, not automatic compiler inlining.
