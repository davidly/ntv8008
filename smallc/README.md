# SmallC-85 for the Intel 8008

This is a new native 8008 backend for [SmallC-85](https://github.com/ncb85/SmallC-85),
using its preserved C frontend at revision
`cfeb1bce46d6454a91ec0d819626a1c75358a030`. It runs alongside the ACK toolchain.
Target programs contain 8008 instructions, with C calls and their return
addresses on a software stack in the emulator's 16 KB RAM.

## Build and compile

Linux/macOS: Python 3 and a C compiler with GNU89 support (GCC or Clang):

```sh
./smallc/build.sh
python3 smallc/compile.py smallc/examples/hello.c
./ntv8008 smallc/examples/hello.hex
./smallc/rebuild.sh
python3 tests/smallc.py --compile
```

`CC` selects the host compiler. The build uses the checked-in frontend sources;
no network, ACK tools, or Intel compiler images are needed. macOS uses its
standard `cc` (Clang); Linux and Windows are validated directly.

Windows, in a Visual Studio developer command prompt with Python 3:

```bat
call smallc\rebuild.bat
ntv8008.exe -p smallc\examples\ttt.hex
py -3 tests\smallc.py --compile
```

The Windows build uses MSVC `cl` by default; `CC` can select GCC/Clang instead.
`PYTHON` selects the Python command in the batch scripts. Build products live
in ignored `smallc/build/`. Old frontend warning suppression is confined to
building this historical compiler, which contains implicit int and K&R code.

Compilation accepts one translation unit, plus the automatically supplied
`console.c`. `-o file.hex` selects the output. `--assembly file.asm` preserves
native A08 assembly; `--ir file.ir` preserves the backend's temporary operations.
The latter is a compile-time interface, not an interpreted target instruction
set. Compilation errors leave an existing HEX output untouched.

## C subset

Use traditional Small C declarations and K&R function definitions:

```c
#include <stdio.h>
sum(a, b)
int a, b;
{
    int result;
    result = a + b;
    return result;
}
main()
{
    putu(sum(12, 30));
    putchar('\n');
    return 0;
}
```

* `char` is signed 8-bit; `unsigned char` is unsigned 8-bit.
* `int`, `unsigned int`, and pointers are 16-bit, little endian. Spell out
  `unsigned int`; the original parser does not accept standalone `unsigned`.
* Functions implicitly return int. ANSI parameter lists also work, e.g.
  `sum(int a, int b)`, but explicit return-type declarations/prototypes and
  `(void)` parameter lists are outside this frontend's supported syntax.
* Arrays, pointers, integer arithmetic, comparisons, bit operations, recursion,
  if/else, loops, break/continue, and switch/case are supported.
* Put local declarations first, and assignments afterward. Automatic variable
  initializers, casts, floating point, long integers, variadic functions, and
  a full hosted C library are not provided. Other frontend restrictions and
  inherited quirks remain; this is not a conforming modern C implementation.
* Global initializers and zero-initialized globals are supported. The frontend
  also has struct support, but general struct functionality is not comprehensively
  validated by this port. Prefer byte/int arrays and scalar locals.
* `<stdio.h>` selects `putchar`, `getchar`, `puts`, `putu` (unsigned decimal),
  `kbhit`, and `waitkey`. `kbhit()` returns 128 when a character is available,
  otherwise zero. `waitkey(ticks)` polls for roughly `ticks` milliseconds at
  500 kHz (0..255 ticks), returning the last seven-bit character or -1. Zero
  ticks returns -1 without consuming input. Each empty tick is 524 clock periods
  (the final tick is 520), plus call overhead; input adds a small amount of work.
  These helpers use the default keyboard/status ports 2/1.
  These function names are reserved. Only that system header is provided.
  Quoted local includes are flattened
  relative to their containing file, before the Small C preprocessor runs;
  includes should be unconditional, without relying on conditional inclusion.
  EOF ends the emulator; it does not return a C EOF value. Console newlines are
  converted between C LF and the emulator's CR interface.
* One source file per compilation; no object-file linker or separate-unit ABI.
  Inline assembly is not a documented interface. Unknown backend operations
  and unresolved symbols fail compilation.

The software stack starts at `3f00h` and grows downward. Arguments are evaluated
and pushed left to right, as in the original Small C ABI. The last argument is
at SP+2 upon entry; locals and temporary values are tracked relative to SP.
Functions push a RAM return address and jump; return patches a RAM trampoline.
The hardware return stack is used only by bounded runtime helpers. Byte locals
and unaligned word accesses are handled, including page crossings.

The compiler rejects images larger than `3d00h`, leaving at least 512 bytes
below the stack/runtime variables. Stack allocation checks against the image
boundary. Division by zero and stack exhaustion print a message and halt;
these runtime halts currently return the emulator's normal exit status. There
is no general bounds checking or pointer validation. Arithmetic wraps to 16
bits; shift counts outside 0..15 are unsupported. Multiplication/division use
simple runtime algorithms and leave room for future performance improvements.

## Examples and validation

* `hello`: console output.
* `arithmetic`: 24 checks, signed/unsigned arithmetic, pointers, page-crossing
  accesses, odd-sized locals, switch, argument order, and recursion 40 levels deep.
* `sieve`: 8191 byte flags, ten iterations, 1899 primes.
* `e`: decimal spigot producing 192 digits, followed by `done.`.
* `ttt`: recursive alpha-beta minimax with last-move switch dispatch; ten
  iterations, 6493 nodes per iteration and three tied opening positions.

* `snake`: ANSI Snake at roughly five moves per second with `-s:500000`.
  See the root README for controls and `tests/snake.py --compile` for rule tests.

`tests/smallc.py` runs the benchmark/demo images and independently checks prime,
e-digit, and minimax results. `--compile` additionally rebuilds every example
and checks signed/unsigned boundary comparisons, console input, ANSI parameters,
switch fallthrough, full-width arithmetic, nested calls with unaligned locals,
runtime traps, and compiler error handling. Root test and
performance scripts include Small C without requiring its compiler to be built.

See [NOTICE.txt](NOTICE.txt) and [upstream/LICENSE](upstream/LICENSE) for source
provenance and the upstream public-domain dedication. The original frontend is
preserved; the build applies its small compatibility fixes to temporary copies.

## Generated-code performance

The 8008 backend keeps binary operations' right operand and result in AB. Only
its left operand uses the RAM expression stack. PUSH/POP update the stack pointer
directly, preserving C/D and handling unaligned words across page boundaries,
without temporary spills or nested stack-helper calls. Constant increments and
pointer offsets use immediate arithmetic. Page-crossing checks remain on unknown
addresses; accesses to fixed runtime variables need no such checks.

These general code-generation/runtime changes leave the C benchmark sources,
algorithms, output, and iteration counts unchanged. At the default 500 kHz clock:

| Benchmark | Previous cycles | Optimized cycles | Reduction |
| --- | ---: | ---: | ---: |
| Sieve (10 passes) | 5,784,960,824 | 1,562,413,828 | 73.0% |
| E (192 digits) | 1,074,044,140 | 429,611,964 | 60.0% |
| TTT (10 iterations) | 11,580,886,186 | 3,704,081,744 | 68.0% |

Run `./ntv8008 -p smallc/examples/NAME.hex` to measure the complete workload.
For a per-iteration TTT comparison, divide its cycles/runtime by ten.

### Comparison, constant, and memory fusion

The backend now recognizes comparisons used by branches, immediate arithmetic
and bit operations, small constant scaling, and local word updates. It avoids
the general comparison/arithmetic helpers for these cases. Boolean-valued
comparisons still produce canonical 0/1. For fused branches, a conservative
successor scan proves whether AB is overwritten before its next use; otherwise
the comparison result is retained on both paths. This preserves short-circuit
expression joins, return values, and side effects.

Constant-base indexing folds the base into immediate address arithmetic,
removing a temporary PUSH/POP. Stack-relative index offsets are adjusted for
the removed push. The match accepts only a local scalar load and unary
scaling/offsets, stopping at labels, calls, and other expressions. Local constant
stores and read/modify/write word updates avoid saving the destination on the
expression stack. Constant-address loads go directly through HL; dynamic-base
ADD followed by LOAD shares one native sequence.

All word loads, stores, and updates keep page-crossing checks, including odd
stack addresses. The C sources, frontend, ABI, workloads, and outputs are
unchanged. Compared with the previous fast-stack version above:

| Benchmark | Previous cycles | New cycles | Speedup |
| --- | ---: | ---: | ---: |
| Sieve (10 passes) | 1,562,413,828 | 938,308,312 | 1.67x |
| E (192 digits) | 429,611,964 | 387,165,694 | 1.11x |
| TTT (10 iterations) | 3,704,081,744 | 2,451,806,726 | 1.51x |

`tests/smallc_codegen.py` runs native differential tests with the new
optimizations enabled and disabled. It checks signed/unsigned comparisons,
constant operands, branch paths where the boolean is dead or live, arithmetic
boundaries, scaling, odd local words crossing pages, and fixed/dynamic indexed
accesses. Both root test scripts include these tests without requiring a Small
C compiler build. `python3 tests/smallc.py --compile` also checks short-circuit
expressions and calls with side effects. The internal
`generate(ir, optimize=False)` switch retains the prior lowering for differential
testing; it does not undo the earlier fast-stack runtime improvements.

### Constant stack-relative addressing

The backend now forms SP plus a constant displacement directly instead of
materializing a 16-bit operand and calling SPADDR. Local updates and constant
stores use the resulting HL address directly, and adjacent address/load pairs
avoid copying the address through AB. This also covers local index loads exposed
by the earlier indexed-address optimization. CD is preserved, signed offsets and
low-byte carries are supported, and word loads retain the odd-address page check.
The benchmark sources and frontend are unchanged.

| Benchmark | Previous cycles | New cycles | Reduction |
| --- | ---: | ---: | ---: |
| Sieve (10 passes) | 938,308,312 | 766,768,816 | 18.3% |
| E | 387,165,694 | 361,945,222 | 6.5% |
| TTT (10 iterations) | 2,451,806,726 | 2,073,765,118 | 15.4% |

Differential code-generation tests retain the previous address lowering as a
reference and cover odd stack frames, local word updates crossing a page,
indexed accesses, live values, and signed byte loads. Full compiler tests cover
nested calls and argument layouts.

### Reusing a remainder calculation's quotient

Within a basic block, matching local-word MOD and DIV operands can share one
native division. The first operation saves the quotient; the second loads it
without repeating its operand loads or division. Tracking the original PUSH
depth gives SP-relative locals stable identities. Calls, control flow, another
division, and overlapping writes invalidate the candidate. The pass declines
the unit if a local address escapes or its abstract stack cannot be followed.
Signed remainders and quotients retain the existing C semantics.

The unchanged E benchmark drops from 361,945,222 to 313,250,614 clock cycles
(723.9 to 626.5 seconds at 500 kHz, a 13.5% reduction). Sieve and TTT retain their
previous cycle counts. Differential tests cover signed/unsigned boundary pairs,
including -32768, negative divisors, overlapping byte/word writes, address
escapes discovered before or after a candidate, calls, and branch boundaries.

### Constant factors, local assignments, and dense switches

The backend now lowers small constant multiplication on either side to shifts
and adds. In particular, E's `10 * a[...]` previously used the generic runtime
multiply with the array value as its loop count. The new native sequence has
three doublings and one addition. Supported factors are 0, 1, 2, 3, 4, 5, 8, 10,
16, 32, 64, 128, 256, and -1, with the existing 16-bit wraparound. Right-hand
expressions still execute, including side effects when multiplying by zero.

A local assignment can compute its right-hand expression first and then store
directly through SP plus the destination offset. This removes the saved address
and its PUSH/POP. The pass tracks temporary PUSH depth, adjusts all intervening
SP-relative references, and allows direct calls with balanced argument cleanup.
Indirect calls, intervening assignments, and control-flow joins retain the
original sequence. Stores preserve the assignment value in AB and retain the
word-access page guard, including odd byte-local frames.

Consecutive stack adjustments in the same direction are combined; constant
adjustments update the RAM stack pointer directly while preserving AB and the
stack-overflow check. This avoids allocating each local through a separate
helper call.

Dense constant switches now use a range check and indexed jump table. The pass
requires at least three distinct cases, at most 128 table slots, and at least
half the slots occupied. Negative cases and holes are supported; holes and
out-of-range selectors go to the original default. Other switches retain the
existing linear scanner. The old descriptor is retained for conservative
fallback, so this trades some image size for speed.

All benchmark C sources, workloads, and outputs are unchanged:

| Benchmark | Previous cycles | New cycles | Seconds at 500 kHz | Reduction |
| --- | ---: | ---: | ---: | ---: |
| Sieve (10 passes) | 766,768,816 | 741,767,762 | 1,483.5 | 3.3% |
| E | 313,250,614 | 132,228,146 | 264.5 | 57.8% |
| TTT (10 iterations) | 2,073,765,118 | 1,485,836,332 | 2,971.7 | 28.3% |

For the usual single-iteration TTT comparison, divide its runtime by ten:
297.2 seconds, versus ACK C's current 340.1. E compares with ACK C's 359.4.
These are simulated original-8008 times, rather than host execution times.

Differential tests compare optimized and generic native code on arithmetic
boundaries, left/right constant factors, nested calls and aliased destinations,
zero-multiply side effects, odd stack frames, combined adjustments, dense and
sparse switches, negative selectors, holes/defaults, and jump tables forced to
byte offsets 254 and 255. The compiler tests still check all five rebuilt images,
recursive calls, stack traps, and the independent benchmark outputs.

### Immediate byte stores, variable local updates, and native fills

A constant byte assignment now writes the memory-immediate value directly and
preserves the assignment expression's original AB result. Variable local word
updates such as `k += prime` load both operands before writing the destination,
avoiding the saved address and expression-stack ADD sequence. Word accesses
retain their page-carry checks, including odd frames and partially overlapping
source/destination words.

Canonical zero-based unsigned byte-fill loops now use a native pointer and
byte/block counter. Recognition requires a constant count and a known static
allocation containing the complete range; both reserved DS buffers and numeric
DB/DW initializers are understood. The loop must have no other entry, calls,
extra effects, or dynamic address. Fallback retains the previous code for other
forms. The native operation preserves the final induction variable and the
loop-exit AB result, including for zero count, and leaves older stack values
intact.

Measured stages for the unchanged sieve (8191 flags, ten passes, 1899 primes):

| Stage | SmallC cycles | Seconds at 500 kHz |
| --- | ---: | ---: |
| Before these changes | 741,767,762 | 1,483.5 |
| Immediate byte stores | 594,743,162 | 1,189.5 |
| Native variable local updates | 386,257,062 | 772.5 |
| Native fill loop | 316,320,656 | 632.6 |

The combined reduction is 57.4%, a 2.34x speedup. The remaining gap to PL/M's
335.1-second sieve is approximately 1.89x. E takes 132,101,374 cycles (264.2
seconds), and TTT takes 1,444,651,692 cycles for ten iterations (288.9 seconds
per iteration). No benchmark source or workload changed.

Differential tests cover signed/unsigned byte loads and assignment values,
16-bit addition carry/wraparound, identical and partially overlapping operands,
odd frames crossing pages, zero and page-sized fills through 8191 bytes,
surrounding sentinels, every filled byte, and live stack/index/AB values.
Unrecognized or externally entered loops, unknown addresses, and out-of-range
fills are checked for conservative fallback.


Unsigned constant byte-store loops with a local variable stride now keep the
index in DE and stride in BC across iterations. HL computes the buffer address
separately, preserving 16-bit index wraparound. The final index is written back
on exit; SmallC also retains the original false comparison result. Only loops
with a known static buffer, a bound within that allocation, separate index and
stride words, and no extra loop entries or body effects are lowered.

Sieve now takes **189,099,736 cycles (378.2 seconds at 500 kHz)**, a further
40.2% cycle reduction from the native-fill result above. This is about
1.13x PL/M's 335.1 seconds. Benchmark sources are unchanged. Differential tests
cover zero-trip loops, page crossings, wrapping strides, untouched stride and
older stack values, final indices, and conservative fallback.

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

Truth-only short-circuit joins are threaded into direct branches. Constant
indexed global loads and byte comparisons avoid intermediate expression-stack
words. The frontend marks function entries in IR comments so ordinary branch
labels are never mistaken for independent functions.
