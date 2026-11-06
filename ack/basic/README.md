# ACK integer BASIC for the 8008

The pinned ACK BASIC frontend (`em_bem`) compiles to this project's native
8008 backend. Generated programs execute 8008 instructions; the host does not
interpret BASIC or EM. This is an **integer-only, freestanding subset**, with
console I/O and a bounded RAM GOSUB stack, rather than the hosted BASIC library.

From the repository root on Linux or WSL:

```sh
./ack/build.sh
./ack/basic/rebuild.sh
./ntv8008 -p ack/basic/examples/ttt.hex
python3 tests/ack_basic.py --compile
```

Compile a program:

```sh
python3 ack/basic.py program.bas -o program.hex \
    --assembly program.asm --em program.e
./ntv8008 program.hex
```

Native Windows host tools now build with `setup.bat --ack` (or `--all`) in a
Visual Studio 2022 developer command prompt, using Python/MSVC and bundled
parser generators. No WSL is required. After setup, the local `rebuild.bat`
script and `tests/ack_basic.py --compile` use the native tools. `ACK_TOOLS` can
select an alternative compatible tool directory. See the [MSVC guide](../MSVC.md).


## Supported subset

Begin integer programs with `10 DEFINT A-Z`, or use `%` variable suffixes.
Unsuffixed variables otherwise retain ACK's floating-point default, which this
target rejects. All numeric values and array elements are signed 16-bit words;
addresses and expression stacks are also 16 bits.

```basic
10 DEFINT A-Z
20 DIM A(9)
30 FOR I=0 TO 9:A(I)=I*I:NEXT I
40 PRINT A(7)
50 END
```

Supported/tested features include assignments, integer arithmetic and bitwise
boolean operations, comparisons (true is -1), integer division `\`, `MOD`,
`IF ... THEN ... ELSE`, `GOTO`, `GOSUB`/`RETURN`, `ON ... GOTO/GOSUB`, integer
`FOR`/`NEXT` including negative steps, `WHILE`/`WEND`, constant-bound integer
arrays including multiple dimensions and `OPTION BASE`, `PRINT`, and numeric
`INPUT`. Programs use conventional numbered BASIC lines. Avoid colons in REM
comments: the historical lexer treats a colon as a statement separator there.

Division truncates toward zero and MOD has the dividend's sign. `/` requests
floating-point division and is unsupported; use `\`. Arithmetic wraps at 16
bits. Avoid FOR increments that wrap the loop variable at its endpoint. A zero
step retains the frontend's behavior and can loop indefinitely.

String literals, string-variable assignments, string comparisons, `LEN`, `ASC`,
and ASCII `CHR$` (0 through 127) are supported. Literal and character strings
have stable storage; there is no general string heap. Concatenation, substrings,
string input, DEF FN, floating point/transcendentals, DATA/READ/RESTORE, file I/O,
PEEK/POKE/VARPTR, and other hosted functions are outside the supported subset.
Unsupported EM operations or missing runtime procedures fail compilation;
POKE is explicitly rejected because the original frontend otherwise emits no
operation for it. DATA/READ file channels are rejected, not emulated as input.

`PRINT` keeps BASIC's leading/trailing spaces around numbers, and semicolons
suppress the newline. Comma zones are reduced to one space. Numeric INPUT uses
the emulator's keyboard/stdin callbacks; redirection works, with a delimiter
such as newline needed after the last number. INPUT prints its normal prompt;
host EOF terminates execution. Only console channel -1 is supported.

GOSUB allows 64 nested returns, independent of the CPU's seven hardware return
addresses. Ordinary backend/support calls also use the shared RAM call stack.
At least 512 bytes of RAM are reserved for that stack. There is no array bounds
checking. Invalid indices and pointers must be avoided. GOSUB errors print
`ACK BASIC error`; division by zero and stack exhaustion use native runtime
diagnostics. These errors halt the emulated CPU, which does not itself produce
a failing host exit code.

## Examples and performance

* `hello.bas`: greeting and integer output.
* `arithmetic.bas`: 12 checks, arrays, signed division/remainder, loops, and a
  GOSUB nested 20 levels deep.
* `sieve.bas`: ten passes over the same 8191 odd candidates, yielding 1899 primes.
  Integer flags require two bytes, so this version uses 1024-cell segments to
  fit in RAM. Its segmentation differs from the byte-flag assembly/C versions.
* `e.bas`: the 200-cell integer spigot, yielding 192 digits and `done.`.
* `ttt.bas`: the project's SCELBAL last-move minimax port with integer frames,
  ten iterations, three tied opening positions, and 6493 nodes per iteration.

Root `test.sh`/`test.bat` validate all five images. The optional `--compile`
suite validates their rebuilds plus arithmetic boundaries, loop directions and
bounds, default types, multidimensional arrays, computed jumps, strings/input,
GOSUB errors, stable paths/newlines, and rejection without overwriting outputs.
Both performance scripts run these three benchmarks with `-p` as `ackbasic`;
the existing `basic` label continues to mean SCELBAL.

## Compiler patches and provenance

`patch.py` applies small checked, idempotent patches to the verified pinned
ACK archive during bootstrap. Original archives remain unchanged:

* Add `-8` for this target to omit hosted signal/setjmp and DATA-file startup.
* With `-8`, implement integer FOR bounds with signed comparisons selected by
  the step's sign, avoiding floating-point conversions and sign multiplication.
  Start, limit, and step expressions are evaluated once, as before.
* Make DEFINT letter ranges work with the lexer's lowercase identifiers, and
  honor default types when allocating arrays.
* Fix a filename-descriptor length incorrectly emitted from a host pointer.
* With `-8`, reject the original no-op POKE implementation.

The shared fixed-array lowering and native backend optimizations apply to these
programs. The new runtime is original project code plus shared project array
support; ACK's historical hosted BASIC runtime is not linked. See
[NOTICE](../NOTICE.txt) and the root licensing review for provenance.

Measured full-workload clock counts at the default 500 kHz clock:

| Benchmark | Clock cycles | Approximate seconds |
| --- | ---: | ---: |
| sieve | 317,265,600 | 634.5 |
| e | 102,059,050 | 204.1 |
| ttt | 1,406,038,082 | 2,812.1 |

TTT's row includes all ten iterations; divide by ten for a per-iteration
comparison. Sieve's segmented representation means its timing should be
compared with that difference in mind.

### Assignment and constant-division performance

BASIC's original lowering saved each assignment destination in `dummy3`, then
loaded it again before the store. The wrapper now replaces scalar assignments
with direct stores when their right-hand expressions are independent and pure.
Constant array assignments put the constant below the address expression,
exposing the store to the shared backend. Calls, branches, labels, and other
stores stop recognition; other assignments retain the original convention.
`optimize.py` checks expression stack effects before applying these rewrites.

Sieve also exposed a larger cost: the native division runtime uses repeated
subtraction, so dividing an index near 16000 by two took thousands of iterations.
The shared backend now lowers division/remainder by positive constant powers
of two from 1 through 256 to native shifts/masks. Signed division biases negative
inputs before arithmetic shifting to preserve truncation toward zero; signed
remainder retains the dividend's sign, including at -32768. Other divisors,
zero-divisor diagnostics, and the generic runtime remain unchanged.

No benchmark BASIC source, algorithm, segment size, or iteration count changed:

| Benchmark | Before cycles | After cycles | Speedup |
| --- | ---: | ---: | ---: |
| sieve | 7,527,000,134 | 1,331,113,038 | 5.65x |
| e | 400,555,760 | 370,797,104 | 1.08x |
| ttt | 4,454,388,424 | 3,594,530,188 | 1.24x |

`tests/ack_codegen.py` compares optimized and generic native division/remainder
against independent expected values across signed/unsigned boundaries and all
supported powers. The BASIC compiler tests also execute scalar/array/string
assignments with assignment lowering enabled and disabled.

The current timings above include shared local-access and quotient-reuse
optimizations. E can reuse a MOD calculation's quotient for a following DIV
when its internal scalar operands remain unchanged. The BASIC sources remain
unchanged. See the [shared backend notes](../README.md#native-pascal-arithmetic-and-quotient-reuse).
The older stage tables retain their historical measurements.

### FOR-loop and comparison performance

With `-8`, the frontend keeps each FOR step in a temporary and tests its sign
before every bound check. Those tests, and comparisons that passed one operand
through a spill slot, cost sieve more than its segmentation. `optimize.py` now:

* folds a step stored once from a literal into its uses. The sign tests become
  nothing or a jump, the unreachable bound check is removed, and the variable
  is stepped in place.
* tests a variable step's sign once on entry, then runs an ascending or a
  descending copy of the loop. A body is copied only if no label inside it is
  referenced from outside, such as a GOSUB return point.
* compares two global words with one native operation (`wcmp`) that loads them
  straight into AB and CD.
* evaluates `x = x + expression` with x loaded last, so the backend adds x
  from memory instead of stacking the expression under it.

No benchmark source, segment size, or iteration count changed, and the other
ACK frontends' images are unchanged:

| Benchmark | Before cycles | After cycles | Fewer cycles |
| --- | ---: | ---: | ---: |
| sieve | 487,824,822 | 317,265,600 | 35.0% |
| e | 102,148,100 | 102,059,050 | 0.1% |
| ttt | 1,418,358,456 | 1,406,038,082 | 0.9% |

About a tenth of the remaining sieve time is the generic runtime dividing
each segment's start by P, which counts quotients below 256 by subtraction.
`tests/ack_basic.py` compares loops in both directions, nested bodies, GOSUB
bodies, and zero-trip loops against the output with these passes disabled.
