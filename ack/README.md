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

On Linux, macOS, or a Unix environment such as WSL, install Python 3.9 or
newer, a C compiler available as `gcc`, GNU Make 4.x, Ninja, flex, and both
`yacc` and `bison`. ACK invokes Bison directly for its optimizer; Berkeley yacc
alone is insufficient. On Ubuntu/Debian:

```sh
sudo apt install build-essential ninja-build flex bison
```

On macOS, use `brew install make ninja flex bison` and put the installed tools
on PATH; the bootstrap automatically finds Homebrew's `gmake`. Setup checks
these prerequisites before rebuilding tools or downloading ACK. Then, from the
repo root:

```sh
./m.sh
./ack/build.sh
python3 ack/compile.py ack/examples/hello.c
./ntv8008 ack/examples/hello.hex
```

This prints `HELLO, ACK C!`. `build.sh` downloads pinned ACK and Lua source
archives, verifies their SHA-256 hashes, builds Lua and the required ACK host
tools locally, and builds A08. It does not install anything system-wide.
The host tools build on Linux and native Windows. In a Visual Studio 2022
developer command prompt, use `setup.bat --ack` or `setup.bat --all`. The
[Python/MSVC bootstrap](MSVC.md) builds its bundled generators and generates all
parser/table inputs locally; no Linux/WSL preparation is required.
This product includes software developed by the University of California,
Berkeley and its contributors.

ACK sources, dependencies, and build products stay in ignored `ack/build/`.
The scripts build the preprocessor, five language frontends, EM optimizers and
format converters, rather than upstream machine backends or target libraries.
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
for native Windows builds after setup; `ACK_TOOLS` can select another compatible
Windows toolchain. A Windows process cannot execute Linux tools produced by WSL.

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


The [Occam 1 integration](occam/README.md) uses the original ACK frontend with
recorded build/portability fixes and an original sequential console runtime.
`setup.py --ack`/`--all` now build `em_occam` and its five examples. Sieve, e and
TTT run natively; TTT uses explicit software frames rather than recursion.
`tests/occam.py --compile` exercises frontend, lexical links, arrays, I/O,
errors and benchmark results; `perfrun.sh --languages occam` reports timings.

### Byte state, leaf registers and frame reuse

Unsigned byte comparisons use native 8-bit comparisons when both operands are
known bytes. Other signed/word comparisons keep the full 16-bit semantics.
The shared `tools/native8008.py` pass can keep one unescaped byte local in C
inside an eligible leaf function. It checks control-flow initialization,
register/flag liveness, interfering instructions, and overlapping word access;
address exposure or unknown calls retain memory storage. Recursive calls keep
the existing RAM-stack ABI.

Frame-pointer/stack-pointer address calculations can reuse HL when every
incoming path agrees on its value. Page crossings are handled explicitly;
software-call return labels start with unknown pointer state. Dead register
loads and unnecessary word promotions are removed only when their register
and flag results are unused. `tests/native_codegen.py` differentially tests
page boundaries, live flags/results, register interference, word aliases and
software-call joins; `--compile` also checks all byte values, escaped locals
and recursive byte state with the C frontends.

Byte local loads/stores and branch comparisons are fused before EM stack
lowering. Small constant dense-switch descriptors use a direct jump-table
sequence, including negative minima and page-crossing tables.

### Register caches and stack joins

The shared `tools/register8008.py` pass caches unescaped byte locals in free C/D
registers, intersecting known values at control-flow joins. Stores retain their
RAM copy, register writes invalidate the cache, and software-call continuations
start empty. This permits reuse within recursive functions without changing
argument layout or requiring a new calling convention. CD can also hold a frame
address in regions where both registers are dead; callers, stores and conflicts
conservatively end that region. Wider HL-relative adjustments handle carry and
borrow at page boundaries.

Expression values stay in AB across joins when every incoming path would
otherwise PUSH immediately before a shared POP. Scratch-register and flag
liveness, computed entries, and alternative consumers retain the original code.

Recursive C TTT now uses 922,437,514 clocks for ten runs, versus 1,093,895,626
before this revision (15.7% fewer). Integer BASIC TTT also benefits from
register-held values and stack-join elimination: 3,369,136,732 to
2,481,289,378 clocks (26.4% fewer). Benchmark sources are unchanged.

### Inlined TTT winner dispatch

The TTT example now contains its last-move winner switch directly in `minmax()`.
Winning cases return their minimax score immediately, avoiding the winner's
software call/frame and intermediate result. This is explicit source inlining,
not automatic compiler inlining; recursion, move order and node counts are
unchanged. ACK C falls from 922,437,514 to 761,427,614 clocks for ten runs (17.5% fewer).

### Byte increments, memory comparisons and frame primitives

Unsigned byte increments can update their RAM slot without loading and storing
the frame address twice. The shared register cache recognizes the new update
operation, so it retains the updated byte and unaffected locals. The native
pass uses CPM for eligible static-memory comparisons when D is dead, preserving
operand order and all comparison flags. FP/SP+0 uses a shorter pointer load
when A and arithmetic flags are dead; its E result is retained.

ACK folds the consumed EM byte increment, including an optional same-size
conversion, while preserving older expression-stack operands. ENTER directly
saves the parent frame, retaining CD and the bounds check. LEAVE reads the
adjacent saved FP/return words and releases both together, with an explicit
page-crossing guard. Software calls may clobber CD; return values stay in RV.
TTT drops from 761,427,614 to 726,710,020 clocks for ten iterations (4.6% fewer).

### Assembly runtime pruning

The final 8008 backend retains only reachable assembly runtime blocks. It seeds
reachability from startup and symbolic references in the emitted application
code/data, follows runtime dependencies and fall-through, and retains addresses
loaded into registers or stored in tables. Equates remain available; consecutive
data blocks are retained together for interior table labels. Application code
and data are not removed by this pass. Arithmetic traps, stack checks, and the
self-modifying indirect-call trampoline remain when reachable.

This applies to ACK C, Pascal, Modula-2, BASIC, and Occam, after their existing
EM optimizations and higher-level runtime selection. Small C shares the same
pass; see `../smallc/README.md`.
`tests/runtime_prune.py` checks reachability edge cases; the language and native
code-generation suites exercise the resulting binaries.

### Selective sequence sharing

After native optimization, long frame-address-plus-load sequences may use one
shared byte/word helper. Candidates must be outside backward-branch spans and
outside functions on a known direct or mutual recursion cycle. Each helper
requires at least eight eligible sites: replacing 17-byte sequences with
seven-byte calls then saves at least 65 bytes after its 15-byte body. This is a
static selection policy, not profile-guided proof that a site is infrequent.
Simple loads, stores, byte operations, and short arithmetic remain inline.
The helper preserves the original final registers and arithmetic flags; it
adds one hardware CALL/RET level, with no nested calls or RAM-stack allocation.
No helper is emitted when the threshold is not met. Frame outlining is disabled
when the backend's native optimization is disabled.

ACK also shares identical return-value stores through LEAVEVALUE immediately
before LEAVE, when at least two occurrences make it smaller. The shared entry
falls through into LEAVE, adding no executed instructions or CALL/RET pair.
This runs after register allocation so the new entry does not inhibit it.

Tests cover selection thresholds, loops, mutual recursion, byte/word loads,
positive/negative offsets, and address-page carries. The benchmark size report
records the rejected blanket-sharing experiment and the selected policy.

## Pointer strides and conditional word updates

Two SmallC optimizations also apply to the ACK backend. Recognized local-index
byte-store loops use an advancing pointer when a conservative runtime guard
proves that the absolute address cannot wrap; large or potentially wrapping
strides retain the original index loop. Final induction variables and older
EM stack operands are preserved. Local/global word increments and decrements
update the high byte only when the low-byte operation carries or borrows.
ACK already has native lowering for repeated-value doubling and indexed access.

With unchanged sources and workloads, ACK C sieve drops from 160,667,418 to
**148,787,838 cycles** (7.39% fewer), or **297.575676 seconds at 500 kHz**,
with the same 1899 primes. The pointer loop alone takes 152,190,478 cycles.
Pascal sieve improves by 0.20%, e by 0.24%, and TTT by 0.48%; Modula-2 sieve
improves by 0.17% and TTT by 0.72%. Occam and BASIC timings are unchanged.
Boundary tests compare optimized and generic EM for empty/already-finished
loops, page crossings, large and wrapping strides, word carry/borrow/wraparound,
and older live operands. All five frontends retain their original outputs.

## Stack pointer register copy

The shared runtime's `POP` reads the stack pointer's low byte once and copies it
to E instead of reading RAM twice, saving three cycles per call. This is the same
change as SmallC's `POP`; ACK's separate frame-return helper does not contain
that repeated read. `PUSH`, register preservation and stack checks are unchanged.

Rebuilt benchmarks produce identical output with the following cycle counts:

| Frontend | Sieve | E | TTT (ten iterations) |
| --- | ---: | ---: | ---: |
| C | 148,559,868 | 171,318,508 | 725,540,982 |
| Pascal | 316,895,014 | 286,559,656 | 2,354,540,420 |
| Modula-2 | 368,164,228 | 262,693,250 | 1,588,752,590 |
| Occam | 290,779,670 | 328,710,078 | 1,831,444,390 |
| BASIC | 1,278,485,094 | 307,852,262 | 2,436,950,244 |

This saves 0.15% to 0.65% across these workloads. Stack tests cover pointer page
crossings, preserved AB/CD registers, stored words and overflow on both paths;
all five frontend suites also pass with compilation enabled.

## Constant multiplication, fixed main frames and deferred counters

- **Constant multiplication.** `x * constant` uses inline shifts and adds when
  that takes at most eight steps. Factors 0 and -1 become a clear or `NEG`. Other
  factors still call the repeated-addition `MUL`.
- **Division.** The runtime divide loop counts the quotient in HL, matching SmallC.
- **Fixed main frame.** Startup reaches `F_MAIN` with a constant frame pointer.
  When no unit calls `main` or takes its address, `main`'s locals use constant
  addresses.
- **Other lowering changes:**
  - `x + local` adds directly from the frame.
  - A byte stored through a simple index waits in D instead of on the RAM stack.
  - `++global` becomes an in-place increment.
  - A zero-extended byte tested for zero skips loading a zero high byte. Signed
    `gt`/`le` tests read that byte, so they keep it.
  - Pointer marking loops test at the bottom.
- **Deferred byte updates.** The shared deferred-update pass now also copies a
  step reached by a conditional jump. TTT's `++pos` therefore stays in a register on
  the occupied-cell path.

Rebuilt benchmarks produce identical output:

| Frontend | Sieve | E | TTT (ten iterations) |
| --- | ---: | ---: | ---: |
| C | 83,422,156 (-43.8%) | 81,860,644 (-52.2%) | 571,062,078 (-21.3%) |
| Pascal | 315,372,124 (-0.5%) | 271,948,964 (-5.1%) | 2,291,398,212 (-2.7%) |
| Modula-2 | 217,585,250 (-40.9%) | 247,899,190 (-5.6%) | 1,566,758,444 (-1.4%) |
| Occam | 289,288,974 (-0.5%) | 299,499,678 (-8.9%) | 1,831,265,794 (0.0%) |
| BASIC | 1,103,876,654 (-13.7%) | 291,442,914 (-5.3%) | 2,436,737,834 (0.0%) |

New tests cover:

- multiplication by constants against generic EM
- constant and FP-relative frames
- a `main` whose address is taken, which keeps FP-relative addressing
- byte stores, local adds and global increments
- signed byte zero tests
- deferred counters across calls and recursion
