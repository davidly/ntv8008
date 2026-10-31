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
