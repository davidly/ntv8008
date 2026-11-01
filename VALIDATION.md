# Publication validation

Validated 2026-10-30 on Linux and native Windows. macOS execution was not tested.

* A08 was fetched from its official site and pinned by SHA-256. The official
  release contains the RTS fix; the build-copy patch only changes `main`'s
  return type. Core assembly and Robson regenerate successfully.
* SmallC and all four ACK frontends were built from source in a separate build
  tree, using verified source archives. No original-tree tool binary is needed.
* A fresh local Git clone, containing only the publication inventory, completed
  `setup.py --all` and `test.sh --compile`: 152 tests reported, with explicit
  skips for unavailable historical components. It completed all 18 default
  benchmark runs (assembly, ACK C/Pascal/Modula-2/BASIC, SmallC).
* Private staging validation supplied the existing Forth and PL/M inputs and
  fetched the pinned SCELBAL source through the optional setup path. All 155
  tests reported by `test.sh --compile --basic-benchmarks` passed, including
  full SCELBAL benchmarks. The historical inputs/outputs are not publication
  files and are not copied into the new repository.
* Native Windows `setup.bat --smallc` builds the emulator, A08 and SmallC.
  CPU and language/native-codegen suites passed; the POSIX terminal test was
  explicitly skipped. Windows ACK frontend rebuilding was not tested; use WSL
  or supply compatible native tools with `ACK_TOOLS`.
* Windows validation exposed a Git ownership/path normalization issue when
  auditing a WSL UNC directory. The audit now supplies the correctly normalized
  per-command safe-directory path; all three Windows publication tests pass.
  No global Git configuration was changed.
* Publication tests verify the file inventory, required notices, preserved
  upstream hashes and rejection of restricted/uncleared historical candidates.
  Checksum verification passes after a Git checkout. Original upstream files
  use binary-preserving Git attributes; project text has deterministic endings.

Build artifacts and downloaded dependencies are Git-ignored. These checks
validate the recorded publication boundary; each third-party license remains
applicable as documented in THIRD_PARTY_NOTICES.md.


## Occam integration validation — 2026-10-31

ACK's dormant Occam frontend was added to the build graph, repaired in a verified
build copy, and exercised through the shared native 8008 backend. A fresh source
export built all host tools with `setup.py --all`, passed `test.sh --compile`
(170 reported tests, including 18 Occam tests and expected optional-component
skips), and completed all 21 default benchmark runs. Sieve prints 1899 primes,
e matches the independent 192-digit Decimal reference, and TTT visits 6493
nodes per iteration with all three openings checked for a tie.

Native Windows `setup.bat` and `test.bat` passed with the new Occam images,
including `20 checks` from the arithmetic/array/parameter example. Host Occam
frontend compilation remains a Linux/WSL build; Windows can run the supplied
HEX or use compatible native ACK tools. The compiler regression tests cover
lexical links, parameter passing, signed constant folding, zero/boundary
replication, generic versus direct arrays, four/five-byte copies, input/exit,
traps, rejected concurrency/recursion, diagnostics, resource limits and repeated
patching from the original verified archive. Existing CPU/codegen tests pass.
No additional third-party source archive or historical runtime is bundled.

The ACK and SmallC PUSH/POP primitives now avoid storing the stack pointer's
high byte unless a borrow/carry changes it. The ordinary PUSH saves 8 clock
periods and POP saves 24; crossing a page costs 18 and 6 extra respectively.
PUSH still checks STACKMIN on both paths. New stack regression tests cover
register preservation, stored words, pointer restoration, even/odd addresses,
page crossings, and exhaustion with and without a low-byte borrow. All 18
compiled-language benchmark runs retained their outputs and used 0.6–3.6% fewer
cycles. The README performance table reflects the rebuilt images.

ANSI Snake is implemented in SmallC with guest-side polling/delay helpers.
The 32x16 game uses a circular body buffer and byte occupancy map. New tests
cover growth, forbidden reversal, self/wall collisions, departing-tail entry,
ring wrap, a full board, movement cost independent of body length, and helper
return values/timing. Host tests exercise nonblocking status with queued bytes,
EOF, files, remapped ports, and an open empty pipe. A POSIX pseudo-terminal test
runs at 500 kHz, receives a live quit key, and verifies terminal restoration.
A no-input run hits the wall after 3,213,044 clocks: 6.426 seconds estimated,
6.426 seconds measured with throttling. The initial board takes about three
seconds; ordinary movement is about five moves/second. Existing SmallC sieve,
e and TTT cycle counts are unchanged after rebuilding with the new runtime.

Native Windows MSVC builds pass without warnings. Windows runtime and SmallC
compile tests pass, including multi-byte pipe polling; the host bypasses CRT
stdio read-ahead with one-byte binary descriptor reads so PeekNamedPipe cannot
miss a retained character. Both blocking reads and poll/read sequences are
covered. POSIX-specific terminal tests are explicitly skipped on Windows.

TTT byte-state/code-generation work (2026-10-31): ACK C and SmallC retain
recursive search, ascending moves, the three opening positions, and ten runs
of 6493 nodes. Bounds, positions, depth and scores are unsigned bytes; counters
remain words. Byte lowering, leaf-local allocation to C, truth-only branch
threading (SmallC), dense switches (ACK), cross-block frame-address reuse and
liveness-based promotion/load elimination are tested independently of the
benchmark. The new native differential suite covers odd/even page crossings,
live flags and address-result registers, escaped and overlapping locals,
conditional initialization, register interference and software-call returns.
Optional compiler tests enumerate all 256 byte values and exercise aliases
and recursive byte state.

ACK C TTT: 1,624,852,796 -> 1,093,895,626 clocks (32.7% fewer).
SmallC TTT: 1,423,549,596 -> 1,045,360,912 clocks (26.6% fewer).
These are ten-iteration totals. The README table reflects all 18 regenerated
compiled-language benchmarks. Snake also benefits from the shared pass; its
no-input run now takes 3,131,122 clocks (6.262244 seconds at 500 kHz).

The finalized Linux `test.sh --compile` run reports 196 tests with the expected
optional historical-component skips. Native Windows `setup.bat --smallc`,
`test.bat`, `tests/smallc.py --compile` and `tests/native_codegen.py --compile`
pass; the latter skips the unavailable native ACK frontend. Windows regenerated
SmallC images match Linux byte-for-byte. MSVC emits no new warnings. Existing
CPU/console tests and the Snake rules, polling and terminal tests pass.

Further frame/register work (2026-10-31) keeps byte locals in free C/D registers
with RAM copies at call boundaries. Eligible regions hold frame addresses in
CD; HL-relative frame reuse also handles offsets up to 255 bytes in either
direction. Expression joins can retain AB instead of a PUSH/POP pair. SmallC
removes stacked addresses for closed local assignments and follows BYTE_CMP
branch edges in stack-depth analysis. The recursive benchmark sources and
search workload are unchanged.

ACK C TTT: 1,093,895,626 -> 922,437,514 clocks (15.7% fewer).
SmallC TTT: 1,045,360,912 -> 762,252,864 clocks (27.1% fewer).
ACK BASIC TTT: 3,369,136,732 -> 2,481,289,378 clocks (26.4% fewer).
All are ten-iteration totals. All 18 compiled benchmarks produce their expected
results; the README table records their measured times. Snake's no-input run
uses 3,130,426 clocks. The 13 native/codegen regressions cover wider offsets,
register-held address results, live scratch registers, call invalidation,
conditional local stores, byte-branch stack depths and stack-join values, as
well as all earlier cases. Compiler tests retain two byte locals across
recursive calls and verify escaped aliases.

The follow-up Linux run exercises 201 reported tests with expected missing
historical-component skips in the isolated validation tree. The optional
components in the working clone are preserved. Native Windows MSVC builds and
the runtime/codegen suites pass; final native SmallC rebuild tests and the
13 register/codegen tests exercise the same generated images on Windows.
The ACK frontend remains a Linux/WSL build, so that optional native-Windows
frontend test is skipped.

Manual C TTT winner inlining (2026-10-31): the switch now lives in `minmax()`
and returns a win's score directly. Nine function-pointer specializations were
also measured in ACK C, but all three formulations were slower than the old
switch function; those experiments are not included in the examples.

ACK C: 922,437,514 -> 761,427,614 clocks (17.5% fewer).
SmallC: 762,252,864 -> 656,075,244 clocks (13.9% fewer).
Totals cover ten iterations, each with 6493 nodes and three drawn opening
positions. Existing runtime and frontend-rebuild tests validate both examples.

Pascal/Modula-2/Occam winner-inlining experiment (2026-10-31):
Pascal: 2,603,063,742 -> 2,394,463,122 clocks (8.0% fewer).
Modula-2: 1,879,420,868 -> 1,628,518,588 clocks (13.3% fewer).
Occam: 4,364,965,452 -> 4,086,062,652 clocks (6.4% fewer).
These are ten-iteration totals. All three retain the same last-move line checks,
search order, data types, three drawn openings and 6493 nodes per iteration.
Pascal and Modula-2 remain recursive; Occam retains its explicit frames.
The existing language runtime tests check independent minimax results, and
frontend tests check exact regeneration of the updated HEX files.

Native byte/frame refinements (2026-10-31): benchmark sources are unchanged
from the manual winner-inlining revisions. ACK C TTT uses 726,710,020 clocks
instead of 761,427,614 (4.6% fewer); SmallC uses 635,817,708 instead of
656,075,244 (3.1% fewer). These remain ten-iteration totals. All 18 compiled
benchmarks were regenerated and produced the expected results, with no cycle
regressions. The byte-copy prototype was dropped: ACK regressed and SmallC's
benefit was negligible compared with its added complexity.

New regressions check byte wrap, negative/large increments, full promoted
results and older stack operands; CPM carry/equality behavior and live D;
zero-offset address results and flags; ACK frame restoration, CD preservation
in ENTER and bounds failures; and SmallC returns at odd/even page boundaries.
The Linux compiler/runtime suite reports 207 tests (with historical-component
skips in the isolated validation tree), including all prior language, alias,
recursive-call and Snake tests.

PL/M winner inlining (2026-10-31): WINNER2's DO CASE and short-circuit checks
are inside the explicit-frame search, with one shared winning-score handler.
TTT falls from 475,999,642 to 465,342,822 clocks (2.2% fewer), retaining ten
iterations, three drawn openings and 6493 nodes per iteration. The existing
PL/M suite checks independent minimax results and exact image regeneration.
The generated PL/M HEX remains a local ignored output and is not published.

Assembly TTT frame-access refinements (2026-10-31): WINNER receives the last
move in E instead of reloading it; occupied-cell scans retain their cursor in
E and save the parent's resume position only before descent. A redundant
frame-address reload at the descent point is also removed. The nine 16-byte
frames, search order and node workload are unchanged.

TTT falls from 16,111,346 to 14,457,102 clocks (10.3% fewer), or 32.22 to 28.91
seconds at 500 kHz. The independent minimax reference checks three drawn
openings and 6493 nodes. Existing repeated-iteration/rebuild tests exercise
frame reuse; the exhaustive winner test now passes E and poisons the old RAM
argument, while continuing to check that B is preserved.


## b8008 integer BASIC (2026-10-31)

Added an original BSD-3-Clause 8008 assembly interpreter, its mechanical macro
expander and reproducible HEX, plus full sieve/e/TTT sessions. All BASIC parsing,
tokenization, execution, and checked byte/word array operations run on the CPU.
The full 8191-byte sieve array fits with the interpreter and tokenized program.

Fourteen regressions cover reproducible assembly and RAM fit, randomized signed
16-bit arithmetic and comparisons, arrays, randomized line insertion/replacement/
deletion, listings, structured loops including zero trips and signed overflow,
GOSUB/RETURN, INPUT across loops/subroutines, console input, memory access,
error recovery, and all three complete benchmarks. Independent references check
1899 odd primes over ten passes, 192 digits of e, and three drawn minimax roots
with 6493 positions. Linux and native Windows tools pass these regressions.

Measured session totals, including native loading/tokenization: sieve
10,486,655,256 cycles; e 2,116,305,366; TTT 7,788,531,192. At 500 kHz these are
20,973.3, 4,232.6, and 15,577.1 seconds, respectively. Compared with the locally
installed SCELBAL sessions (143,207,960,826 / 8,088,060,426 / 59,022,995,742
cycles), these are 13.7x / 3.8x / 7.6x faster. Sieve uses the same ten full passes,
e the same 192 digits, and TTT the same one-iteration 6493-node search.

Default setup also rebuilds the integer BASIC image successfully. The full Linux
`test.sh` run passes the CPU checks and 160 Python tests (eight expected optional
compiler-test skips without `--compile`). Native Windows assembler/emulator
execution passes all 14 integer BASIC tests, including the complete benchmarks.
The publication audit covers 254 reviewed files plus its manifest.


## b8008 integer BASIC literal branches (2026-10-31)

A native RUN prepass now resolves standalone literal GOTO/GOSUB/THEN targets.
A three-byte numeric token becomes a three-byte address token in place, with
no additional per-program RAM. Computed target expressions retain runtime
lookup and caching. Missing targets remain numeric until a branch executes,
so untaken branches do not introduce startup errors. Before the editor or LIST
runs, the interpreter restores original line numbers from target record headers.
Re-running, inserting/replacing/deleting lines, and error recovery rebind safely.
False-IF and zero-trip FOR scanners skip address operands as binary words.

All 17 integer BASIC tests pass on Linux and with the native Windows emulator
and assembler. New regressions disable runtime line lookup and run literal
GOTO, GOSUB, THEN, and the complete 6493-position TTT search successfully. They
also verify computed-expression fallback, untaken/taken missing targets,
listings during and after execution, repeated RUN, moved/deleted/replaced
lines, and restoration after errors. Existing independent arithmetic, arrays,
full benchmark results, image reproducibility, and sieve RAM-fit checks pass.

Session cycle totals (including input/tokenization, binding and unbinding):

| Benchmark | Before | After | Fewer cycles |
| --- | ---: | ---: | ---: |
| Sieve, ten passes | 10,486,655,256 | 9,990,355,052 | 4.7% |
| E, 192 digits | 2,116,305,366 | 2,113,854,452 | 0.1% |
| TTT, one iteration | 7,788,531,192 | 6,800,631,862 | 12.7% |

The interpreter code occupies 5810 bytes starting at 0040h, with a startup jump
at zero; its end is 16f2h. The full sieve program plus its 8191-byte flag array
still fit below workspace at 3b00h. Publication remains 254 reviewed files plus
the manifest; no new upstream source or dependency is introduced.


## b8008 integer BASIC stack, operand, and NEXT performance (2026-10-31)

Implemented three native runtime changes without changing the BASIC benchmarks:

* CALL expands into a checked direct push of its known return address, avoiding
  RPUSH's DE save/restore and a second helper call. VPUSH advances its existing
  stack index. VPOP returns a register value without an unused RAM copy; LPOP
  supplies RAM operands only for comparison and long multiply/divide. SRET
  patches the return jump directly from the stack while preserving A/BC/DE.
* TERM handles constants, scalars, and array operands directly; FACTOR avoids
  re-reading a consumed variable through LVALUE. Unary/parenthesized expressions
  retain recursive parsing, and all precedence and array checks remain.
* NEXT specializes STEP +1 with an in-place increment and signed bound check.
  Other steps retain the checked general path, including signed overflow exit.

All 19 tests pass with both the Linux and native Windows assemblers/emulators.
Additional regressions cover nested array/unary expressions, a 30-parenthesis
expression near the 126-word software-stack limit, long flat expressions, and
unit/general loops across -32768/32767 and low-byte carries. Earlier arithmetic,
branch-binding/no-runtime-lookup, errors, editing, full benchmark, reproducibility,
and memory-fit regressions also pass. No stack capacity or bounds check was
removed. The interpreter ends at 187dh (6205 bytes from 0040h, plus the jump at
zero); the full sieve and 8191-byte flag array remain below workspace at 3b00h.

| Benchmark | Before cycles | After cycles | Fewer cycles |
| --- | ---: | ---: | ---: |
| Sieve, ten passes | 9,990,355,052 | 5,750,828,782 | 42.4% |
| E, 192 digits | 2,113,854,452 | 1,424,933,270 | 32.6% |
| TTT, one iteration | 6,800,631,862 | 3,669,857,000 | 46.0% |

Stack changes alone measured 7,182,944,848 / 1,644,662,322 / 4,622,413,880 cycles.
Adding operand fast paths measured 6,014,406,504 / 1,422,104,054 / 3,670,063,126.
Unit-step dispatch then saved another 4.4% on sieve, adding 0.2% on e's general
negative-step loops; all three benchmarks improve substantially overall. Totals
include native session loading, tokenization, binding/unbinding, and execution.


## b8008 naming (2026-10-31)

The original native integer BASIC is named b8008. Source/examples now reside
under `b8008/`, generated images are `a08/b8008.asm` and `a08/b8008.hex`, and the
regression suite is `tests/b8008.py`. Setup, assembler rebuilds, both default
test scripts, and `perfrun --languages b8008` use the new name. The console
banner and licensing/provenance references have been updated. No old-name
source/image files or performance-language alias are retained.

All 19 interpreter tests pass on Linux and native Windows, and the renamed
performance command runs all three complete benchmarks. Session cycle counts
are 5,750,828,866 / 1,424,933,366 / 3,669,866,632 for sieve/e/TTT. The banner is
one byte longer, leaving code end at 187eh; RAM-fit and reproducibility checks
still pass. The publication inventory retains 254 reviewed files plus manifest.


## b8008 indices, arithmetic, division reuse, and simple stores (2026-10-31)

Implemented the four proposed runtime improvements:

* Array indices accept a fast atom or atom +/- constant. The existing full
  bounds check remains; complex or nested expressions restore the original
  token pointer and retain general expression evaluation.
* Multiplication terminates when the remaining multiplier is zero. Division
  returns early for a smaller dividend and skips leading zero dividend bits
  before the restoring loop, retaining 16-bit wrapping and signed remainders.
* A private eight-byte last-division cache keys both raw signed operand values
  and saves quotient/remainder independently of arithmetic scratch. Zero
  divisors are rejected before lookup. Unsigned decimal formatting bypasses
  the cache, avoiding signed/unsigned collisions for 8000h.
* Simple assignment RHSs share the index fast parser, covering increments,
  decrements, constants, and scalar stores. This runs natively at statement
  execution; no added tokens, precompiled BASIC, or benchmark changes are used.

To retain RAM fit, prepare.py eliminates redundant immediate H/L reloads in
straight-line assembly only. It tracks register writes and byte wrap and drops
facts at labels/control transfers; removed instructions do not alter flags.
This recovered roughly 250 bytes before adding the runtime paths. Final code
ends at 18c3h (6275 bytes from 0040h plus the three-byte startup jump at zero),
only 69 bytes above the prior image. The full sieve's 8191-byte array still fits
with its tokenized program below workspace at 3b00h.

All 23 b8008 tests pass on Linux and with native Windows assembler/emulator.
Four added tests cover offset/assignment fast paths and precedence fallback,
wrapped/negative/out-of-range indices, small arithmetic and signed boundaries,
and actual execution equivalence of address-load elimination (including calls,
register clobbers, low-byte wrap, and flags). A native DIVMAIN counter proves
one signed division supplies both / and MOD across multiplication and unsigned
printing, changed operands/signs, INPUT/NEW, and division-by-zero recovery.
Earlier image reproducibility, stack limits, literal-branch/no-lookup, editing,
full prime/e/minimax benchmarks, and RAM-fit checks all pass.

| Benchmark | Before cycles | After cycles | Fewer cycles |
| --- | ---: | ---: | ---: |
| Sieve, ten passes | 5,750,828,866 | 4,199,466,844 | 27.0% |
| E, 192 digits | 1,424,933,366 | 939,516,764 | 34.1% |
| TTT, one iteration | 3,669,866,632 | 2,789,402,456 | 24.0% |

Intermediate cycle totals (sieve / e / TTT): address cleanup alone
5,649,945,454 / 1,361,251,810 / 3,619,410,560; index paths
4,714,487,622 / 1,203,653,668 / 3,071,722,680; shorter arithmetic
4,714,777,628 / 998,848,360 / 3,071,700,558; division reuse
4,714,473,848 / 897,096,190 / 3,071,611,836. Shared simple-store matching then
helps sieve/TTT further while adding about 4.7% to e's compound-assignment paths;
all three workloads improve substantially overall. Totals include native input,
tokenization, binding/unbinding, and execution, excluding host I/O waits.

## b8008 dispatch, comparisons, and descending loops (2026-11-01)

Implicit assignments are recognized before keyword dispatch. Comparisons try
an atomic RHS (optionally plus/minus a constant) through the existing leaf
parser before saving operator/recursive parser frames. Compound expressions
restore the token pointer and use the original precedence parser. STEP -1
updates the scalar in place, checks signed underflow, and shares the general
signed-bound comparison; other descending steps retain the general path.
The common byte/word store preserves width flags while loading its pointer;
redundant operator stores/reloads were removed to retain the RAM-size guard.

Code-layout testing exposed NEW clearing the second empty-header byte on the
wrong page when PROGRAM ended in ffh. It now addresses PROGRAM+1 explicitly.
A regression assembles a deliberately padded image with that layout and checks
editing, RUN, NEW, and LIST. Extra comparisons cover scalar signed boundaries,
all six operators, constant offsets, complex-RHS fallback, chaining and nested
IF. Descending-loop cases cover byte boundaries, signed underflow, zero trips,
and non-unit steps. All 25 tests pass on Linux and native Windows. Rebuilding
matches the checked-in image; the original full-sieve RAM guard still passes.

| Benchmark | Before cycles | After cycles | Fewer cycles |
| --- | ---: | ---: | ---: |
| Sieve, ten passes | 4,199,466,844 | 3,924,396,176 | 6.6% |
| E, 192 digits | 939,516,764 | 915,743,020 | 2.5% |
| TTT, one iteration | 2,789,402,456 | 2,448,409,404 | 12.2% |

Each proposed path was also disabled independently and measured against the
combined image: assignment dispatch and comparison matching help all three;
the decrement specialization primarily helps E. Workloads and examples are
unchanged. Counts include input/tokenization and execution, excluding I/O waits.

## b8008 code-size savings (2026-11-01)

Saved 120 bytes without changing program tokens or reducing the benchmark:

* Seventeen pairs of byte-reader calls now share a native GETWORD leaf. It
  advances BC twice, handles either page crossing, returns DE and the high byte
  in A, and retains the original reader's final increment flags.
* Decimal formatting loads the digit before constructing its destination;
  DIM loads descriptor values before constructing descriptor addresses.
  Both avoid scratch-address saves and reconstruction.
* Removed the division loop's duplicate subtraction for a 17-bit remainder.
  Signed divisor magnitudes are at most 32768, and the prior partial remainder
  is smaller than the divisor, so extending it cannot overflow 16 bits. The
  only unsigned caller is decimal formatting with divisor 10.

Code ends at 1887h instead of 18ffh: 6215 resident bytes from 0040h, plus the
startup jump at zero. The unchanged full sieve's 8191-byte array and program
leave 402 bytes below workspace (previously 282); the conservative regression
size guard now has 121 bytes to spare. All 26 tests pass on Linux and native
Windows. The new native word-reader regression checks values, BC advancement,
A, and flags with either byte crossing a page. The existing forced-header
boundary regression now emits padding in short DATA lines for the assembler.

| Benchmark | Before cycles | After cycles |
| --- | ---: | ---: |
| Sieve, ten passes | 3,924,396,176 | 3,902,725,516 |
| E, 192 digits | 915,743,020 | 910,363,660 |
| TTT, one iteration | 2,448,409,404 | 2,433,730,726 |

All three improve by roughly 0.6%; totals include input/tokenization and
execution, excluding host I/O waits. Benchmark sources are unchanged.

## b8008 atomic arithmetic operands (2026-11-01)

SUMOP and TERMOP recognize a scalar or numeric constant on their right without
saving/restoring the operator or entering the recursive TERM/FACTOR parser.
The left value still uses the checked value stack; the change removes the
operator frame and software parser return frames. SUM rejects the fast result
when followed by *, /, or MOD, preserving multiplicative precedence. Scalars
followed by '(' restore the token pointer and enter the general array parser;
unary, parenthesized, and other complex operands also retain the general path.
Helpers run natively on the 8008, adding no program tokens or host evaluation.

The helpers consume 108 of the 120 bytes just recovered. Code ends at 18f3h;
full sieve free space is 294 bytes, and the conservative size guard still has
13 bytes to spare. All 28 tests pass on Linux and native Windows. Added tests
cover signed scalar RHSs for every arithmetic/bitwise operator, precedence,
left associativity, array/nested/unary fallback, division by zero, and malformed
operand recovery. A native FACTOR marker proves atomic multiply/divide bypass
recursive parsing while an array RHS still takes that path.

| Benchmark | Before cycles | After cycles | Fewer cycles |
| --- | ---: | ---: | ---: |
| Sieve, ten passes | 3,902,725,516 | 3,840,704,110 | 1.6% |
| E, 192 digits | 910,363,660 | 885,172,030 | 2.8% |
| TTT, one iteration | 2,433,730,726 | 2,412,522,654 | 0.9% |

Workloads are unchanged. Counts include native loading/tokenization and
execution, excluding host I/O waits.
