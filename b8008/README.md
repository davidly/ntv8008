# b8008 integer BASIC

A compact integer BASIC interpreter written for this project's 16 KiB 8008
machine. Tokenization, editing, expression evaluation, arrays, and program
execution all run on the emulated CPU. No host-side BASIC compiler or runtime
is involved. The source, generated assembly, and ready-to-run HEX image are
original BSD-3-Clause project code; no historical interpreter source is included.

Run from the repository root:

```sh
./ntv8008 a08/b8008.hex
./ntv8008 -p -l:b8008/examples/sieve.bas a08/b8008.hex
./ntv8008 -p a08/b8008.hex < b8008/examples/e.bas
./perfrun.sh --languages b8008
```

On Windows:

```bat
ntv8008.exe -p -l:b8008\examples\ttt.bas a08\b8008.hex
perfrun.bat --languages b8008
```

The prompt is `>`. Input is echoed; EOF exits through the console host. A session
file contains numbered program lines followed by `RUN`, and any responses to
`INPUT`. Linux, macOS, and Windows use the same interpreter image and console
ports (input 2, output 10 decimal). Backspace/Delete edits the current input line.

```basic
10 DIM BYTE B(100)
20 FOR I=0 TO 100
30 B(I)=I
40 NEXT I
50 PRINT B(100)
60 END
RUN
```

## Language

* Twenty-six scalar variables `A`–`Z`, initialized to zero by `RUN`/`NEW`.
  Keywords and names are case insensitive. Strings preserve case.
* Signed 16-bit arithmetic, wrapping modulo 65536. Decimal constants also wrap.
  Division truncates toward zero; `MOD` has the dividend's sign. Division by zero
  reports an error. `-32768/-1` wraps to `-32768`.
* Parentheses, unary `+`/`-`, `ABS(expression)`, `PEEK(address)`, `*`, `/`, `MOD`,
  `+`, `-`, bitwise `AND`/`OR`, and comparisons `= <> < <= > >=`. Precedence is
  unary, multiplicative, additive/bitwise, then comparison; each binary group
  associates left to right. Comparisons return 0 or 1.
* `[LET] A=expression`; `DIM A(n)` allocates zeroed **word** elements `0..n`;
  `DIM BYTE B(n)` allocates zeroed **byte** elements `0..n`. Multiple declarations
  can be separated by commas, with `BYTE` applying to the following declaration.
  Scalar and array names are independent. Array indices and allocation sizes
  are checked; byte assignments keep the low eight bits. Arrays are allocated
  once per run and cannot be redimensioned.
* `PRINT` accepts numbers, quoted strings, and `CHR(expression)`. Semicolons join
  items; commas insert one space. A trailing separator suppresses the newline.
  `PRINT` alone emits a newline. There are no string variables.
* `IF expression THEN line-number` or `IF expression THEN statement`.
  A false condition skips the rest of that physical line, including statements
  after colons. `GOTO expression`, `GOSUB expression`, `RETURN`, `END`, and `REM`.
* `FOR I=start TO limit [STEP increment]` / `NEXT [I]`, with signed bounds,
  zero-trip loops, and up to 24 nested loops. Increment zero is rejected.
  Overflow ends a loop rather than wrapping into another iteration. `NEXT`
  leaves the counter one increment beyond the limit, including 16-bit wrap.
  Nested loops must have matching `NEXT` statements. Up to 16 `GOSUB` levels.
* `INPUT variable-or-array-element` reads one signed decimal value per line.
  `POKE address,value` writes a byte; `PEEK`/`POKE` accept addresses 0..16383.
  They access actual machine RAM: changing interpreter code or workspace can
  corrupt execution. Array access is the appropriate interface for normal data.
* `NEW`, `LIST`, and `RUN`. Lines 1..32767 may be inserted in any order, replaced,
  or deleted by entering their number alone. Editing clears variables/arrays.
  Statements can be separated by colons. Source lines are limited to 239 input
  characters and 250 token bytes including the terminator. The expression stack
  is checked; deeply nested expressions report `?STACK`.

Errors report `?SYNTAX`, `?BOUNDS`, `?STACK`, `?LINE`, `?MEMORY`, or
`?DIVIDE BY ZERO` and return to the prompt. REM comment text is discarded
during tokenization. There is no floating point, file I/O,
DATA/READ, ELSE, STOP/CONT, or compatibility promise for another BASIC dialect.
Use structured FOR/NEXT loops inside stored programs; entering another direct
command uses the same scratch page as the saved loop/subroutine frames.

## Implementation and memory

`basic.src` is 8008 assembly with six mechanical build-time macros:
`LD`/`ST` load/store A, `LDW`/`STW` load/store DE, and `CALL`/`RETURN` use the
checked RAM stack. All memory macros clobber HL; CALL/RETURN preserve BC/DE.
CALL clobbers A on entry; RETURN preserves the result in A. CALL pushes its
known return address directly into RAM without saving live DE through a helper.
Register-only value pops avoid copying operands to RAM; comparisons and long
arithmetic request a separate pop into LEFT. RETURN patches its jump directly
from the stack rather than copying through temporary return-address variables.
`prepare.py` only expands these assembly macros. It
does not parse or execute BASIC. Leaf helpers use bounded hardware CAL/RET;
recursive expression parsing uses RAM, avoiding the CPU's shallow return stack.
The RAM return trampoline modifies its own JMP operand, so the code requires
writable RAM, as provided by this machine.

Program records contain a 16-bit line number, a byte record length, and tokens.
Numbers become binary 16-bit literals, keywords become single-byte tokens, and
spaces outside strings disappear. On RUN, a native prepass resolves bare literal
GOTO/GOSUB/THEN targets to token addresses. The three-byte number token becomes a
three-byte address token in place, so this does not enlarge the stored program.
Only a literal followed by a colon or line end is bound; computed expressions
such as `GOTO 100+I` keep their original meaning and use the 64-entry branch
cache. Missing literal targets remain unresolved and report an error only if the
branch executes. INPUT clears the cache but leaves resolved branches intact.

Before returning to the prompt or listing a program, a native unbinding pass
recovers each original line number from its target record. Editing and repeated
RUNs therefore preserve source numbers and resolve moved targets afresh. FOR/NEXT
and RETURN already save continuation addresses and do not search for lines.

Constants, scalar values, and indexed-array operands have fast parsing paths;
unary operators and compound/parenthesized expressions retain the recursive
parser and its precedence rules. Positive unit-step NEXT updates and compares
the saved counter directly, with the same signed-bound/overflow behavior; other
steps retain the general loop path. All stack capacity and error checks remain.

Code starts at `0040h` (with a jump at zero). Tokenized programs immediately
follow the interpreter; arrays grow upward after the program's end marker.
Workspace occupies `3b00h..3fffh`: input/branch cache, variables/state, array
metadata, FOR/GOSUB frames, and the expression/return stack. Allocation and
program growth are checked against `3b00h`. The full sieve program and its
8191-byte array fit together; a full word array of that size cannot fit.

## Examples, measurements, and validation

* `sieve.bas`: ten passes over 8191 odd-number candidates, one byte per flag;
  prints `1899 PRIMES` and `10 ITERATIONS`. No segmentation or precomputed primes.
* `e.bas`: the integer decimal spigot, with 200 byte elements; prints 192 digits
  of e followed by `DONE`.
* `ttt.bas`: ascending-move alpha-beta minimax, byte board/saved frames, root
  moves 0, 1, and 4; checks three draws and prints 6493 positions, one iteration.

Measured at 500 kHz on 2026-10-31:

| Benchmark | b8008 cycles | b8008 seconds | SCELBAL seconds | Speedup |
| --- | ---: | ---: | ---: | ---: |
| Sieve, ten passes | 5,750,828,866 | 11,501.7 | 286,415.9 | 24.9x |
| E, 192 digits | 1,424,933,366 | 2,849.9 | 16,176.1 | 5.7x |
| TTT, one iteration | 3,669,866,632 | 7,339.7 | 118,046.0 | 16.1x |

Literal branch resolution first reduced total cycles by 4.7% for sieve, 0.1%
for e, and 12.7% for TTT. Streamlined software calls/returns, operand parsing,
and positive unit-step loops then reduced cycles by another 42.4%, 32.6%, and
46.0%, respectively. The full sieve array still fits with the interpreter;
no benchmark workload was reduced.

Timings include session loading/tokenization and execution, excluding host I/O
waits. Use `-p` or `perfrun` for cycle counts and estimated 500 kHz runtime.

Rebuild and test on Linux/macOS:

```sh
python3 b8008/prepare.py
./a08/rebuild.sh b8008.asm
python3 tests/b8008.py
```

On Windows:

```bat
py -3 b8008\prepare.py
call a08\rebuild.bat b8008.asm
py -3 tests\b8008.py
```

The normal setup builds this interpreter, and `test.sh`/`test.bat` include its
regressions and all three full benchmarks. Tests compare randomized integer
arithmetic and signed comparisons against Python, verify arrays/editing/loops/
subroutines/INPUT and error recovery, reproduce the HEX image, and check benchmark
results against independent prime, decimal, and minimax calculations. Branch
regressions run a variant that traps runtime line searches: all three literal
branch forms and the full TTT workload must still succeed. They also cover
computed-target fallback, untaken missing targets, zero-trip loop scanning,
listing, rerunning, and edits/deletions that move or remove resolved targets.
