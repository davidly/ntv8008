# ACK Pascal for the Intel 8008

The ACK Pascal frontend compiles to EM, then uses the existing optimized 8008
backend, RAM call stack, and arithmetic helpers. Programs execute native 8008
code. No Pascal interpreter, Intel compiler image, or hosted libpc is involved.

## Build and use

From the repository root on Linux, with the ACK build prerequisites listed in
[the C guide](../README.md):

```sh
./ack/build.sh
python3 ack/pascal.py ack/pascal/examples/hello.p
./ack/pascal/rebuild.sh
./ntv8008 -p ack/pascal/examples/ttt.hex
python3 tests/pascal.py --compile
```

`ack/build.sh` now includes `em_pc` from the same pinned ACK sources as the C
compiler. Existing installations need that build step once to add Pascal.
Subsequent compilation is offline. The source archive and license are unchanged;
see [the ACK notice](../NOTICE.txt) and [ACK-COPYRIGHT](../ACK-COPYRIGHT).

Native Windows host tools now build with `setup.bat --ack` (or `--all`) in a
Visual Studio 2022 developer command prompt, using Python/MSVC and bundled
parser generators. No WSL is required. After setup, the local `rebuild.bat`
script and `tests/pascal.py --compile` use the native tools. `ACK_TOOLS` can
select an alternative compatible tool directory. See the [MSVC guide](../MSVC.md).


`python3 ack/pascal.py source.p -o output.hex` compiles a single program.
`--assembly file.asm` and `--em file.e` save generated assembly and linked EM.
Compiler errors leave an existing HEX output untouched. Stable intermediate
source names make results reproducible across file paths and LF/CRLF inputs.
Pascal source is ASCII; external include files are not supplied by the wrapper.

## Language and runtime

For example:

```pascal
program hello(output);
var n: integer;
begin
  n := 42;
  writeln('Answer: ', n:1)
end.
```

The current integer subset supports:

* Signed 16-bit `integer`, Boolean and character values, subranges, and 16-bit
  pointers. Most standalone scalar objects occupy a word; packed scalar arrays
  use byte elements when appropriate.
* Integer arithmetic, DIV/MOD, comparisons, ABS, SQR, ODD, ORD and CHR.
* Fixed arrays with arbitrary constant lower bounds and byte/word elements;
  multidimensional element addressing can use the backend's array descriptors.
* IF/ELSE, FOR/WHILE/REPEAT loops, and dense CASE tables.
* Procedures/functions, VAR parameters (including fixed arrays), recursion, and
  nested procedures accessing enclosing locals and parameters through static links.
* `write`/`writeln` for integers, characters, Booleans, and constant strings,
  with field widths. Integers default to a six-character field; use `n:1` for
  compact decimal output. Boolean spelling is `true`/`false`, as in ACK's runtime.
* `read` for integers/characters and `readln` for consuming the rest of a line.
  EOF ends the emulator rather than producing a Pascal EOF condition. End numeric
  input with whitespace so its final digit can be consumed before EOF.

The wrapper selects 2-byte words, integers and pointers, and builds with ACK's
`-R` option: **range/bounds checks are disabled**. Signed arithmetic uses the
backend's 16-bit behavior; do not depend on overflow diagnostics. DIV truncates
toward zero. MOD requires a positive divisor and returns a nonnegative result.

`bootstrap.py` corrects an upstream Pascal constant-folder discrepancy: it used
C's negative remainder for negative constant operands, while Pascal's runtime
returns a nonnegative result. Thus `(-17) MOD 5` and the same expression using
variables both produce 3. A nonpositive constant MOD divisor is rejected. The
patch is applied only to the downloaded build sources; the pinned archive and
its checksum remain unchanged. No upstream Pascal runtime source is bundled.

The compact console runtime is newly written C, compiled with our ACK C target.
Its standard input/output handles are opaque tokens; the wrapper reserves one
word for each instead of allocating hosted FILE buffers. Only reachable support
procedures are linked. Array descriptors contain lower bound, range, and stride;
byte/word loads and stores use them. The 8008 backend follows static links in
RAM rather than consuming the hardware return stack for language recursion.
C and Pascal share the same conservative top-of-stack register caching.

The initial target does not supply real/long arithmetic, sets, dynamic allocation,
files other than the standard console, conformant/open arrays, nonlocal GOTO,
procedure-valued parameters, packed records, or aggregate copies/value parameters.
Unsupported EM operations and unresolved runtime calls are diagnosed. Declaring
an unused unsupported type does not imply its operations work. This is not a
claim of complete ISO Pascal conformance; ACK's language/frontend restrictions
also apply, including constant-only array bounds rather than general constant
expressions such as `digits-1` in an array type.

Code/data must end by `3d00h`, leaving at least 512 bytes below the stack at
`3f00h`. Runtime stack growth is checked against the image boundary. Division
by zero, invalid MOD divisors, invalid output widths, and unsupported scalar
array sizes print an error and halt. As with ACK C, these halts currently have
the emulator's normal exit status; the printed message indicates failure.
There is no general pointer or memory-safety checking.

## Examples and validation

* `hello`: greeting.
* `arithmetic`: 13 checks, including negative DIV/MOD, constant-folding consistency,
  negative/nonzero array bounds, packed byte and word arrays, VAR parameters,
  recursion and an inner function using its parent's local and parameter.
* `sieve`: 8191 packed byte flags, ten iterations, 1899 primes.
* `e`: 200 working digits, 192 digits printed, followed by `done.`.
* `ttt`: recursive alpha-beta search with last-move CASE dispatch, three tied
  roots, ten iterations, and 6493 nodes per iteration.

Root tests execute all distributed images without needing the compiler.
`tests/pascal.py --compile` additionally rebuilds every example and validates
multiple levels of static links, VAR arrays, signed division and modulo boundary
pairs, formatting/input, runtime traps, reproducibility, unsupported constructs,
and preservation of existing output on compilation errors. Expected benchmark
results use Python Decimal and independent prime/minimax calculations.

Both performance scripts include Pascal. They measure startup plus the compiled
application, without compilation. As with the C versions, divide TTT's reported
runtime by ten for a single-iteration comparison. Sieve performs ten passes;
e prints the same 192 digits as the other languages.

Fixed array accesses with constant descriptors now use direct address
arithmetic and native loads/stores. Dynamic descriptors retain the generic
runtime path. See the [backend performance notes](../README.md#fixed-array-access-in-pascal-and-modula-2)
for benchmark measurements and details.

Native DIV/MOD lowering now bypasses the C wrapper frames while preserving the
semantics and diagnostics above. A MOD/DIV pair on unchanged scalar operands can
also share a quotient. The unchanged E example takes 291,316,520 cycles (582.6
seconds at 500 kHz), down from 488,423,496 (976.8 seconds). TTT takes
2,784,448,444 cycles for ten iterations, or 556.9 seconds per iteration.
See the [shared backend notes](../README.md#native-pascal-arithmetic-and-quotient-reuse)
for alias restrictions and differential validation.

The subsequent shared memory-fusion stage reduces sieve to 468,837,268 cycles
(937.7 seconds at 500 kHz), E to 291,192,120 (582.4 seconds), and ten-iteration
TTT to 2,744,043,324 (548.8 seconds per iteration). Benchmark sources are
unchanged; details and validation are in the
[backend memory notes](../README.md#constant-byte-stores-local-updates-and-native-fills).


Signed global-variable marking loops now retain the index in DE and the stride
in BC. The backend recognizes both top-tested and bottom-tested loops and
stores the final index back on exit. Nonnegative indices must be within a
separate known static byte buffer. If an initial or wrapped index is negative,
the backend writes it back and resumes the original loop: unchecked negative
array accesses could otherwise overwrite the retained index or stride.

The unchanged sieve now takes **330,720,108 cycles (661.4 seconds at 500 kHz)**,
down from 937.7 seconds, a 29.5% cycle reduction. Differential EM tests
cover both layouts, zero-trip loops, page crossings, signed wrapping, negative
indices that alias the stride, final variable/stack values, and fallback for
unknown buffers, extra entries, aliased operands, or added body effects.

### Inlined TTT win dispatch

The last-move winner dispatch now lives inside the search, avoiding its separate
procedure call. Pascal records the win in its existing Boolean local before assigning the score.
The search order, data types, three drawn openings, 6493 nodes per iteration,
and ten iterations are unchanged. TTT uses 2,394,463,122 clocks instead of
2,603,063,742 (8.0% fewer). This is source inlining, not automatic compiler inlining.
