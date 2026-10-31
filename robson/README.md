# Paul Robson's 8008 Tiny BASIC

Robson's compact BASIC runs as native 8008 code in the existing console host.
The upstream source and MIT license are preserved under `upstream/`; see
[NOTICE.txt](NOTICE.txt) for the pinned revision and checksums. The interpreter
and BASIC programs execute entirely on the emulated CPU.

From the repository root, after building the emulator:

```sh
./ntv8008 a08/robson.hex
./ntv8008 -l:robson/examples/hello.bas a08/robson.hex
./ntv8008 -l:robson/examples/features.bas a08/robson.hex
```

On Windows:

```bat
ntv8008.exe -l:robson\examples\hello.bas a08\robson.hex
```

The prompt is `]`. Commands are lowercase and variables are uppercase:

```text
print 2+3
let A=42
print A
10 print "Hello!"
20 stop
xecute
```

`hello.bas` prints a greeting and sums 1 through 10, displaying `055`.
`features.bas` exercises a software-stack subroutine and `fetch`, with its
numeric input included after `xecute`; it prints `007` and `042`.
EOF exits the emulator. Ctrl-C/Ctrl-Q exits at input; Ctrl-C also interrupts
running code through the host's signal handler. Use LF endings in input files.

## Language and limits

This is the original compact dialect, with its deliberately minimal syntax
checking and storage limits:

* Twenty-six unsigned byte variables, A-Z; arithmetic wraps modulo 256.
* Expressions evaluate left to right: `2+3*4` gives 20. Operators are `+`, `-`,
  `*`, `/`, `.` (bitwise AND), and `,` (bitwise XOR). No arrays, floating point,
  parentheses, or FOR/NEXT loops. Division by zero returns zero.
* Program line numbers 1-127. Each line occupies a fixed 64-byte slot. Keep
  stored text following the number to at most 63 bytes including spaces,
  leaving room for its terminating zero. Input and program slots have no
  overflow protection; short lines are recommended.
* `let A=expression`, `print "text";A`, `out 65`, `fetch A`, and `key A`.
  Numbers print with a leading space and three digits; `out` emits a character.
  `fetch` prompts with `?` and reads a numeric expression; `key` reads one
  character without echoing it.
* `if A<10 goto 30` supports `<`, `=`, and `>` and has no THEN keyword. A false
  condition skips the remainder of the line. Colons separate statements.
* `call 60` / `return` use the interpreter's RAM stack. `goto` accepts an
  expression; `goto 0` and `stop` return to the prompt.
* `view` lists up to twelve stored lines; `view 60` starts at line 60. Entering
  a numbered line replaces it; a line number alone deletes it. `new` clears
  the stored program, and `xecute` runs it. `new` does not clear variables.
* Keywords are dispatched by their first letter. Unknown commands, invalid
  assignment variables, and some syntax errors report `?C`, `?V`, or `?S`.
  There is no REM command.

The byte-only variables and lack of arrays prevent straightforward ports of
the repository's full sieve, e, and tic-tac-toe benchmarks. This integration
does not extend the language to accommodate them.

## Adaptation and rebuild

Input uses port 2 and output physical port 10 (octal 12). The driver strips
the host's ready bit and maps Delete to Backspace. It preserves case. The
upstream run-loop keyboard poll is omitted because this host's input blocks:
polling it would consume subsequent session input or stop execution at EOF.
The original Backspace-to-interrupt feature is therefore unavailable; use
Ctrl-C. Explicit `fetch` and `key` remain supported.

The fixed restart vectors remain at 0, 8, 0x10, 0x18, and 0x38. The default
entry at 0x40 clears program storage, the evaluator and remaining interpreter
start at 0x100, and line-input code starts at 0x800. The original RAM layout
is retained: variables at 0x1000, input at 0x1100, update scratch at 0x1200,
software-stack pointer at 0x1313, stack pages at 0x1400/0x1500, and stored
program lines at 0x2000..0x3fff. The upstream development autoloader is omitted.
No emulator changes are required.

The ready-to-run HEX and generated A08 source are included. Rebuild using:

```sh
python3 robson/prepare.py
./a08/rebuild.sh robson.asm
python3 tests/robson.py
```

On Windows:

```bat
py -3 robson\prepare.py
call a08\rebuild.bat robson.asm
py -3 tests\robson.py
```

`prepare.py --check` verifies offline regeneration and the pinned upstream
checksum. Default assembler rebuilds and `test.sh` / `test.bat` include Tiny
BASIC. Its tests cover reproducibility, arithmetic and wraparound, expression
order, conditions, stored programs, calls, input, editing/listing, and rubout.
