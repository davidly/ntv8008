# ACK C for ntv8008

The Amsterdam Compiler Kit's ANSI C frontend can now produce programs for
ntv8008 through this repository's **new 8008 code generator and runtime**.
Upstream ACK has an 8080 backend, but no 8008 backend; this integration does
not use the 8080 backend or translate 8080 binaries.

The pipeline is:

```
C -> ACK cpp.ansi -> ACK em_cemcom.ansi -> ACK em_opt
  -> readable EM22 -> codegen.py -> A08 assembly -> Intel HEX -> ntv8008
```

The resulting application executes native 8008 instructions. Python, ACK,
and EM decoding are used only while compiling. No changes to the CPU emulator
or console callbacks are required. The existing PDP-10 PL/M compiler remains
independent and unchanged.

## Build the compiler

On Linux, macOS, or a Unix environment such as WSL, install Python 3, a C
compiler available as `gcc`, GNU make, Ninja, flex, and yacc/Bison. macOS needs
GNU make available as `make` for this upstream build. Then, from the repo root:

```sh
./m.sh
./ack/build.sh
python3 ack/compile.py ack/examples/hello.c
./ntv8008 ack/examples/hello.hex
```

This prints `HELLO, ACK C!`. `build.sh` downloads pinned ACK and Lua source
archives, verifies their SHA-256 hashes, builds Lua and the required ACK host
tools locally, and builds A08. It does not install anything system-wide.
The native build is tested on Linux. On Windows, use WSL for the compiler build;
the generated HEX files also run in the ordinary Windows `ntv8008.exe`.
A native MSYS2/MinGW build of this integration has not been validated.

ACK sources, dependencies, and build products stay in ignored `ack/build/`.
The script builds only the preprocessor, C frontend, EM optimizer, and EM
format converters, rather than ACK's other languages or machine backends.
Lua is needed by upstream's build-time code generation; it is not needed
when invoking the finished compiler or running an application.

To build without network access, provide the already downloaded archives:

```sh
ACK_ARCHIVE=/path/to/ack.tar.gz LUA_ARCHIVE=/path/to/lua-5.4.7.tar.gz \
    ./ack/build.sh
```

The archives must match the hashes in [NOTICE.txt](NOTICE.txt). Verified
archives are cached locally for subsequent builds. `ACK_TOOLS` can instead
point at an existing directory containing compatible `cpp.ansi`,
`em_cemcom.ansi`, `em_opt`, and `em_decode` host executables.

## Compile programs and examples

```sh
python3 ack/compile.py program.c -o program.hex
python3 ack/compile.py main.c helpers.c -o program.hex
python3 ack/compile.py program.c --assembly program.asm --em program.e
./ntv8008 -p program.hex
./ack/rebuild.sh
```

`--assembly` saves the generated A08 source, and `--em` saves the optimized EM
for inspection. The default output is the first source's name with `.hex`.
Compilation occurs in a temporary directory; a failed build leaves an existing
HEX output intact. No network access is needed after building the host tools.
`PYTHON` selects Python for the shell scripts. `rebuild.bat` is also supplied
for users who already have compatible **native Windows** ACK tools, selected
with `ACK_TOOLS`; it cannot execute the Linux tools produced by WSL.

| Example | Result | Workload |
| --- | --- | --- |
| `hello.c` | `HELLO, ACK C!` | String and console output |
| `arithmetic.c` | `22 checks` | 8/16-bit arithmetic, casts, shifts, arrays, structures, calls and recursion |
| `sieve.c` | `1899 primes.` | Ten passes over 8191 odd candidates |
| `e.c` | 192 digits without a decimal point, then `done.` | 200-element decimal spigot |
| `ttt.c` | `6493 moves`, `10 iterations` | Recursive alpha-beta search, last-move win dispatch |

The checked-in HEX examples can be run without building ACK. `perfrun.sh` /
`perfrun.bat` include the three C benchmarks with `-p`, alongside assembly,
BASIC, PL/M and Forth. Their C timings include only the compiled application,
not compilation.

## C support and limits

This is an initial **freestanding integer C target**, not a complete hosted
C implementation or a claim that every ACK EM instruction is supported.
ACK's frontend is ANSI C (C89), not a modern C11/C23 frontend.

Supported and exercised features include:

* 8-bit signed/unsigned characters, 16-bit signed/unsigned shorts and ints,
  and 16-bit pointers into the 14-bit address space.
* Integer arithmetic, full 16-by-16 multiplication and division, signed
  remainder, bitwise operations, shifts, comparisons and conversions.
* Global/static/local variables, initialized byte/word arrays and strings,
  pointers, array indexing and structure member access.
* Branches, loops, dense `switch` tables, direct and indirect function calls,
  multiple source files, and recursion with automatic local variables.
* Preprocessing, including macros and quoted includes relative to a source.

The included headers provide the relevant 8/16-bit types and the small console
interface. `putchar`, `getchar`, `puts`, and the nonstandard `putu(unsigned)`
are available. There is no hosted libc: `printf`, files, allocation, system
calls, and standard stream objects are not supplied. Console input is the
host's existing blocking port-2 input; input EOF ends emulation rather than
returning a C `EOF` value. LF output maps to the host's console newline.

Use `int main(void)`; argc/argv startup is not supplied. A return from main
halts normally. The host emulator's exit status does not represent main's
return value. Keep the names `putchar`, `getchar`, `puts`, and `putu` for the
supplied console routines rather than defining replacements.

Actual long/long-long or floating-point operations, wide object transfers,
structure/union value copies, sparse switch descriptors, varargs and other
unimplemented EM instructions fail compilation. Merely declaring a type or
using a compile-time `sizeof` does not imply its runtime operations are
supported. Unsupported generated instructions are reported instead of being
silently treated as no-ops. Additional EM operations can be added later.

The target assumes 16 KiB RAM, including its patched jump instructions. Code
starts at 0x0040. Code and data grow upward; the RAM call/evaluation stack grows
down from 0x3f00, with runtime variables in the last page. The linker wrapper
requires at least 512 bytes of stack room; actual room depends on image size.
Stack growth into the rounded-up image boundary prints `ACK stack overflow`
and halts. Integer division by zero prints `ACK division by zero` and halts.
The emulator still reports a normal HLT exit; these messages indicate a
runtime failure. Invalid pointers and other C undefined behavior are not
memory-safety checked.

C calls save their frame pointer and return address in RAM. The hardware
return stack is used only for short runtime helpers, so C recursion is limited
by RAM rather than seven nested function calls. Arithmetic helpers currently
favor clarity over speed: multiplication and division use repeated arithmetic,
and could be improved later without changing the C frontend.

## Validation and provenance

The normal `test.sh` and `test.bat` execute the distributed examples and check
the unsupported-EM error paths without needing an ACK installation. After
building ACK, run the compiler tests too:

```sh
python3 tests/ack.py --compile
```

These rebuild every example and compare its HEX, test deep recursion, dense
switches with negative cases, function pointers, multiple translation units,
console input, signed/unsigned integer boundary pairs, byte conversions,
stack values across branch joins/calls, duplication, indirect stores and
short-circuit/conditional expressions with side effects,
runtime traps, and preservation of output on failed compilation. Expected e
digits come from Python Decimal; sieve and TTT use independent reference
calculations. The generated programs are also tested in the Windows emulator.

See [NOTICE.txt](NOTICE.txt) and [ACK-COPYRIGHT](ACK-COPYRIGHT) for source pins,
licenses and the distinction between upstream tools and this new backend.

## Generated-code performance

PUSH/POP update the RAM stack directly without temporary spills or nested
ADDSP/LOADSP calls. ACK's stack stays word aligned, so a stack word cannot
cross a page boundary. C call frames, arguments, and return addresses retain
the existing RAM-stack convention and stack-overflow checks.

Within generated expressions, the backend caches the top EM stack word in AB.
Arithmetic and memory helpers consume that register operand and leave results
in AB; only additional operands use RAM. Before ordinary instructions, labels,
branches, or C calls, the backend conservatively spills any cached word.
Control-flow joins and calls therefore see the original physical stack layout.
DUP2 handles both cached and materialized top values. This is local register
caching, without a global register allocator or changes to the C frontend.

The benchmark C sources, workloads, and outputs are unchanged. Measurements
at the original 500 kHz clock use these complete workloads:

| Benchmark | Previous cycles | Fast stack only | Stack + register caching | Total reduction |
| --- | ---: | ---: | ---: | ---: |
| Sieve (10 passes) | 4,454,191,036 | 2,445,728,490 | 1,479,098,676 | 66.8% |
| E (192 digits) | 736,721,188 | 452,294,724 | 320,840,824 | 56.5% |
| TTT (10 iterations) | 9,486,983,924 | 5,312,020,292 | 3,202,735,608 | 66.2% |

`-p` reports each complete run. Divide TTT's cycles/runtime by ten when comparing
one iteration with the assembly or BASIC version.

ACK also includes [Modula-2 support](modula2/README.md), using the same native
8008 backend, with hello, arithmetic, sieve, E, and recursive TTT examples.

## Fixed array access in Pascal and Modula-2

For immutable constant array descriptors, the Wirth-language wrappers lower
AAR/LAR/SAR directly to `(index - lower_bound) * stride + base`, followed by
native byte/word memory operations for loads/stores. Byte strides need no
scaling; word strides use an addition. This avoids generic support calls and
lets the existing expression-stack register cache cover the access. Negative
bounds and multidimensional arrays use the same calculation, with 16-bit
address arithmetic. Range checks remain disabled as before.

Dynamic descriptors, mutable descriptor storage, offset descriptor addresses,
and unsupported scalar element sizes retain the existing generic path.
Aggregate address calculations support arbitrary positive constant strides.
Unneeded generic array procedures are omitted from the linked runtime.

The benchmark sources and workloads are unchanged:

| Language | Benchmark | Previous cycles | Fixed-array cycles | Speedup |
| --- | --- | ---: | ---: | ---: |
| Pascal | Sieve (10 passes) | 5,621,356,010 | 1,324,033,310 | 4.25x |
| Pascal | E (192 digits) | 1,127,387,762 | 578,875,298 | 1.95x |
| Pascal | TTT (10 iterations) | 15,404,160,992 | 4,588,101,232 | 3.36x |
| Modula-2 | Sieve (10 passes) | 5,809,112,304 | 1,511,789,604 | 3.84x |
| Modula-2 | E (192 digits) | 943,440,272 | 394,927,808 | 2.39x |
| Modula-2 | TTT (10 iterations) | 14,427,869,046 | 4,309,147,946 | 3.35x |

At 500 kHz, divide cycles by 500,000 for the complete runtime. Divide TTT's
result by ten for a single iteration. `tests/array_codegen.py` covers native
byte/word stores and loads across page boundaries, stack preservation, negative
and positive lower bounds, aggregate strides, and conservative fallbacks.
Compiler tests additionally compare specialized Pascal arrays against the
generic runtime and execute Modula-2 open-array VAR parameters with dynamic
descriptors.

## Shared native instruction optimizations

C, Pascal, and Modula-2 now share these additional backend optimizations:

* Comparisons followed by branches compare bytes and branch directly, without
  calling CMI/CMU or materializing a -1/0/1 result. Constant operands use
  immediate comparisons, and zero tests use shorter sequences. Signed ordering
  biases the high byte; equality compares the original bits.
* Constant additions/subtractions and bit operations use immediate native
  instructions. Increments/decrements update local/global words directly,
  carrying/borrowing into the high byte. Multiplication by 1/2/4/8 and doubled
  expression values avoid the general multiplication/addition helpers.
* Fixed-base array accesses combine the index, constant scaling/offset, and
  memory operation. Ordinary indirect loads/stores are inlined. Dynamic-base
  address additions followed by a memory access share one helper. Global
  loads/stores avoid constructing and pushing their addresses.

The fused instruction sequences participate in the existing AB expression
cache, avoiding intermediate RAM-stack traffic. Recognition stops at labels,
calls, and unsupported expressions; those retain the general lowering. Calls,
joins, and ordinary instructions still use the existing conservative stack
convention. No frontend, benchmark source, or workload was changed. This does
not introduce a global register allocator, pointer induction, or a new ABI.

Measurements below use full workloads (ten sieve passes, 192 E digits, and ten
TTT iterations). The intermediate stage records comparison/constant arithmetic
changes; the final stage also includes memory fusion and shorter zero/equality
comparisons. Previous cycles are after the fixed-array optimization above.

| Language | Benchmark | Previous cycles | Comparison/arithmetic stage | Final cycles | Speedup |
| --- | --- | ---: | ---: | ---: | ---: |
| C | sieve | 1,479,098,676 | 1,231,491,784 | 1,020,228,486 | 1.45x |
| C | e | 320,840,824 | 282,880,222 | 255,812,310 | 1.25x |
| C | ttt | 3,202,735,608 | 2,273,177,596 | 1,898,822,526 | 1.69x |
| Pascal | sieve | 1,324,033,310 | 1,006,113,474 | 613,107,268 | 2.16x |
| Pascal | e | 578,875,298 | 538,176,972 | 503,868,728 | 1.15x |
| Pascal | ttt | 4,588,101,232 | 3,667,642,354 | 3,330,650,138 | 1.38x |
| Modula-2 | sieve | 1,511,789,604 | 1,226,465,056 | 742,788,754 | 2.04x |
| Modula-2 | e | 394,927,808 | 369,533,602 | 309,004,022 | 1.28x |
| Modula-2 | ttt | 4,309,147,946 | 2,874,456,016 | 2,401,827,006 | 1.79x |

Divide cycles by 500,000 to obtain seconds at the original 500 kHz clock, and
divide TTT by ten to compare one iteration. Native differential tests in
`tests/ack_codegen.py` check optimized and previous lowering against independent
expected outputs. They cover signed/unsigned comparison boundaries, constants,
carry/borrow and wraparound, local/global updates, scaling, stack preservation,
and fixed/dynamic indexed memory accesses across page boundaries. Both root
test scripts run these tests. The internal `generate(..., optimize=False)`
switch retains the previous lowering for these tests; it does not disable the
older fixed-descriptor specialization in the language wrappers.

ACK's [integer BASIC frontend](basic/README.md) also uses this backend and the
fixed-array specialization. Its compact runtime supports console I/O and
BASIC's RAM-based GOSUB return stack. No hosted libbasic runtime is linked.

Positive constant power-of-two divisors (1 through 256) now use native shifts
and masks. Signed division preserves truncation toward zero, and signed
remainder keeps the dividend's sign. This avoids quotient-sized subtraction
loops, particularly in [ACK BASIC sieve](basic/README.md#assignment-and-constant-division-performance).
Zero and other divisors continue through the existing runtime. Differential
native tests cover every supported divisor across signed/unsigned boundaries.

### Constant frame-relative loads and stores

Local word loads/stores now form FP plus their constant displacement directly,
preserving AB during stores and keeping loads inside the expression register
cache. This removes the general LOCAL helper and expression spills around these
accesses. Positive argument displacements still include the four-byte frame
header; negative local displacements propagate carry into the high address byte.
The C sieve uses stack locals where the Pascal and Modula-2 examples mostly use
globals, which accounted for part of its higher cost. No benchmark source changed.

| C benchmark | Previous cycles | New cycles | Reduction |
| --- | ---: | ---: | ---: |
| Sieve (10 passes) | 1,020,228,486 | 765,296,138 | 25.0% |
| E | 255,812,310 | 227,446,940 | 11.1% |
| TTT (10 iterations) | 1,898,822,526 | 1,697,806,888 | 10.6% |

The same lowering applies to the other ACK frontends. Differential tests compare
it with the previous lowering, including live expression values, argument loads,
and negative local offsets spanning multiple pages. Existing call/frame and
language tests also cover nested calls and indirect access.

### Native Pascal arithmetic and quotient reuse

The Pascal wrapper lowers the known libpc DIV/MOD call sequence to native
operations before linking support functions. DIV truncates toward zero; Pascal
MOD still rejects nonpositive divisors and returns a nonnegative remainder.
The generic C wrappers remain available as a differential reference.

The backend also recognizes a scalar MOD followed by DIV of the same unchanged
operands in straight-line code. The first division saves its quotient in private
runtime scratch; the second loads it directly, removing both operand loads and
the duplicate division. Recognition stops at calls, branches, labels, another
division, and potentially aliasing writes. Frame locals must not have their
addresses exposed to intervening indirect stores. Internal globals are eligible
only when a whole-unit scan proves their addresses never escape, including via
data initializers or exports. Signed C remainders retain the dividend's sign;
Pascal's adjusted remainder shares the same truncating quotient.

No C, Pascal, Modula-2, or BASIC benchmark source changed:

| E implementation | Previous cycles | New cycles | Seconds at 500 kHz |
| --- | ---: | ---: | ---: |
| ACK C | 227,446,940 | 179,705,804 | 359.4 |
| ACK Pascal | 488,423,496 | 291,316,520 | 582.6 |
| ACK Modula-2 | 308,859,834 | 266,044,970 | 532.1 |
| ACK BASIC | 370,015,774 | 324,261,038 | 648.5 |

Tests compare the old and new native code on signed/unsigned boundaries,
including -32768, negative divisors, live remainder values, overlapping local
writes, address escapes, calls, and private versus exported global operands.
Pascal compiler tests compare native arithmetic against the original wrappers
and retain the invalid-divisor and zero-division diagnostics.

This runtime change also exposed and fixed an older dense-switch descriptor
page-crossing bug: advancing between descriptor words must carry into H.
Forced-boundary tests place descriptors at byte offsets 250, 252, and 254 and
exercise every case and the default. The added carry checks slightly increase
switch-heavy TTT timings (ACK C: 340.1 seconds per iteration).

### Constant byte stores, local updates, and native fills

The backend now emits a memory-immediate byte store for a literal assigned to
a direct address or simple indexed address. This removes the saved value and
its stack round trip. Native local word additions read both operands before
writing the destination and avoid the general ADD/stack sequence. The C
frontend's `1 + local` increment form is also normalized to the existing native
local increment operation.

A canonical zero-based unsigned loop that assigns a constant byte to a static
buffer becomes a native fill. Recognition requires a constant count, a known
BSS allocation large enough for the entire range, a simple base plus constant
offset, and no other entry into the loop. Calls, extra effects, signed bounds,
and unknown/dynamic addresses retain the original loop. The fill keeps its
pointer and byte/block counters in registers, carries across pointer pages,
and stores the original induction variable's final value, including zero-length
fills. Older expression-stack values remain intact.

Measured stages for the unchanged C sieve (8191 flags, ten passes, 1899 primes):

| Stage | ACK C cycles | Seconds at 500 kHz |
| --- | ---: | ---: |
| Before these changes | 765,296,138 | 1,530.6 |
| Constant byte stores | 672,002,358 | 1,344.0 |
| Native local updates | 396,134,778 | 792.3 |
| Native fill loop | 283,287,038 | 566.6 |

The combined reduction is 63.0%, a 2.70x speedup. PL/M's current sieve is 335.1
seconds, so the remaining gap is approximately 1.69x. E takes 179,544,220 cycles
(359.1 seconds), and TTT takes 1,660,131,528 cycles for ten iterations (332.0
seconds per iteration). Shared lowering also reduces Pascal sieve to 468,837,268
cycles (937.7 seconds), with no benchmark source changes.

Differential native tests cover byte truncation, live older stack values,
word carry/wraparound and aliased operands, zero and page-sized fills through
8191 bytes, every filled byte and surrounding sentinels, and the final loop
index. Negative tests retain loops with extra entries/effects, signed bounds,
unknown addresses, and ranges exceeding the known allocation.


Unsigned constant byte-store loops with a local variable stride now keep the
index in DE and stride in BC across iterations. HL computes the buffer address
separately, preserving 16-bit index wraparound. The final index is written back
on exit; SmallC also retains the original false comparison result. Only loops
with a known static buffer, a bound within that allocation, separate index and
stride words, and no extra loop entries or body effects are lowered.

Sieve now takes **178,978,918 cycles (358.0 seconds at 500 kHz)**, a further
36.8% cycle reduction from the native-fill result above. This is about
1.07x PL/M's 335.1 seconds. Benchmark sources are unchanged. Differential tests
cover zero-trip loops, page crossings, wrapping strides, untouched stride and
older stack values, final indices, and conservative fallback.


The register-retaining marking-loop optimization also recognizes Pascal and
Modula-2 signed global-variable loops, including either test placement. It
keeps the original loop as a fallback for negative indices, because unchecked
negative stores can alias the loop variables. The final index is written back
on either normal exit or fallback. Pascal sieve now takes 330,720,108 cycles
(661.4 seconds at 500 kHz); Modula-2 takes 406,072,124 (812.1 seconds), without
changing either benchmark source.
