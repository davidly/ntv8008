# ACK Occam 1 for the Intel 8008

This integration builds ACK's original Occam frontend and lowers its EM output
through the existing native 8008 backend. The resulting HEX executes on the
emulated CPU, including the language runtime and benchmark algorithms. Python
is used only to compile programs and prepare their images.

## Build and run

On Linux/WSL, from the repository root:

```sh
./setup.sh --ack
./ntv8008 ack/occam/examples/hello.hex
./ntv8008 -p ack/occam/examples/sieve.hex
python3 ack/occam.py ack/occam/examples/e.ocm
./ntv8008 -p ack/occam/examples/e.hex
./ack/occam/rebuild.sh
python3 tests/occam.py --compile
./perfrun.sh --languages occam
```

Building ACK needs the same host tools as the other ACK frontends, including
flex and LLgen (LLgen is built from ACK). The pinned archive and checksum are
unchanged. `ack/bootstrap.py` now builds and installs `em_occam` alongside the
existing host tools. `--all` also includes Occam.

On Windows, supplied HEX examples run immediately after building the emulator:

```bat
ntv8008.exe ack\occam\examples\hello.hex
ntv8008.exe -p ack\occam\examples\ttt.hex
py -3 tests\occam.py
perfrun.bat --languages occam
```

Native Windows host tools now build with `setup.bat --ack` (or `--all`) in a
Visual Studio 2022 developer command prompt, using Python/MSVC and bundled
parser generators. No WSL is required. After setup, the local `rebuild.bat`
script and `tests/occam.py --compile` use the native tools. `ACK_TOOLS` can
select an alternative compatible tool directory. See the [MSVC guide](../MSVC.md).


The compile wrapper accepts `-o image.hex`, `--assembly program.asm` and
`--em program.e`. Failed compilation preserves an existing output image.

## Language subset and ABI

This is the sequential subset of ACK's Occam 1 dialect: `SEQ`, replicated
`SEQ`, `WHILE`, guarded `IF`, `PROC`, lexical nesting, value/reference
parameters, scalar/word/byte arrays, constant tables, slices, array copying,
and the built-in `input`, `output` and `error` console channels. `PAR`, `ALT`,
process-local channels, timing/`NOW` and host file operations are unsupported;
the compiler rejects their runtime requirements rather than serializing them.
Recursion is rejected. TTT uses explicit frames to implement its search.

* Values, words and pointers are 16-bit; arithmetic wraps modulo 65536 and
  comparisons are signed. Division truncates toward zero; remainder has the
  dividend's sign. Booleans use zero/negative-one for false/true. Byte array
  accesses load unsigned values and truncate stores to the low byte.
* Occam requires parentheses when mixing different operators. For example,
  use `(a * 10) + (x / n)`. Keywords may be all lower- or all uppercase;
  identifiers cannot reuse reserved words such as `value`.
* An ordinary array contains words. Use `a[byte 200]` and `a[byte i]` for byte
  arrays. Dynamic array bounds are unchecked, matching the shared backend's
  current array ABI. Constant out-of-range subscripts are rejected. Array
  copies/slices should use disjoint source and destination regions.
* A string is a byte array with a length byte at element zero. `*n` is newline;
  `**` is a literal asterisk. Raw array output sends every element, including
  the length byte if a string is sent directly.
* The original `console.ocm` prelude is prepended automatically. `puts(text)`
  writes a length-prefixed string without its prefix. `putu(number)` prints
  nonnegative values through 32767 in decimal. Scalar channel output writes a
  character: `output ! 'A'`. `input ? variable` reads a character. The `error`
  channel shares the host console; writing the input channel is diagnosed.
* `exit(status)` halts; code following it does not execute. An IF with no
  enabled guard reports `Occam runtime trap` and halts. Like other target
  runtimes, errors halt the CPU and are identified by their console diagnostic,
  rather than a separate application exit-status ABI.
* Procedure calls use the shared RAM stack, with the lexical/static link first
  and other arguments following it. The CPU's seven saved hardware return slots
  are used only by shallow helpers. Main-frame storage plus code/data is checked
  against the 16 KiB budget; runtime stack checks also remain active.

## Examples and performance

| Example | Expected output / workload |
| --- | --- |
| `hello.ocm` | `HELLO, ACK OCCAM!` |
| `arithmetic.ocm` | `20 checks`; arithmetic, arrays, parameters and loop tests |
| `sieve.ocm` | `1899 primes.`; ten passes over 8191 odd candidates |
| `e.ocm` | First 192 digits of e, then `done.`; 200 working byte cells |
| `ttt.ocm` | `6493 moves`, `10 iterations`; ascending alpha-beta search at openings 0, 1 and 4, with last-move winner checks |

The programs implement their arithmetic, search, loops and printing in Occam;
no benchmark work is delegated to C. The small C runtime implements console
channels, traps and block copies. TTT uses an explicit stack because Occam
prohibits recursive procedures. Each opening is checked for a tie.

Measured at the default 500 kHz clock, excluding host I/O waits:

| Benchmark | Clock periods | Estimated seconds |
| --- | ---: | ---: |
| Sieve, ten passes | 724,808,788 | 1,449.6 |
| E | 374,133,814 | 748.3 |
| TTT, ten iterations | 4,687,643,702 | 9,375.3 |

TTT is **937.5 seconds per iteration**. These are cycle-derived estimates for
physical hardware; the emulator executes the supplied images much faster.
Array descriptors with known element widths are lowered directly to byte/word
accesses, while regression tests compare this path with generic array support.

## Frontend repairs and regression coverage

The historical frontend was absent from the current ACK build graph. Its build
copy receives a generated build rule and compatibility repairs recorded in
`patch.py`: missing C declarations/types, modern library prototypes, correct
variadic diagnostics on 64-bit hosts, the TRUE keyword entry, syntax errors
producing a failing status, and rejection of recursion/constant bad subscripts.
Target-width constant folding and modulo-zero diagnostics are repaired, as is
replication across the signed 16-bit boundary and odd-length byte block copies. A false-only IF now traps instead
of falling through. Patches start from the verified archive on each application;
no modified upstream archive or copied historical runtime is distributed.

Tests check all five regenerated images, independent sieve/e/minimax results,
constants versus variables, nested lexical links, reference and array arguments,
byte truncation, disjoint slices/block copying, zero and boundary replication,
console I/O, exit/trap behavior, unsupported concurrency, invalid syntax,
resource limits, and output preservation after errors. Default root tests run
the supplied applications; `--compile` adds the host frontend regressions.

ACK's existing BSD notice is retained in `../ACK-COPYRIGHT`. The frontend patch,
wrapper, console prelude, runtime, examples and tests are project contributions
under the root BSD-3-Clause license. No additional upstream archive or runtime
library is required; see `../NOTICE.txt` and the root third-party notices.

### Inlined TTT win dispatch

The last-move winner dispatch now lives inside the search, avoiding its separate
procedure call. The IF dispatch is inside the explicit-frame search and writes its score directly.
The search order, data types, three drawn openings, 6493 nodes per iteration,
and ten iterations are unchanged. TTT uses 4,086,062,652 clocks instead of
4,364,965,452 (6.4% fewer). This is source inlining, not automatic compiler inlining.
