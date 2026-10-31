# Native 8008 Forth

## Optional local-source component — setup first

The Baker Forth kernel has no established redistribution grant in the reviewed
pinned sources. Its source and adapted assembly/HEX are not distributed or
automatically downloaded. Only integration code and project examples are here.
[NOTICE.txt](NOTICE.txt) records the upstream location and expected source hashes.

If you have the right to use the pinned sources, supply a directory containing
`forth.asm`, `forth-extra.inc` and `bufio.inc`:

```sh
python3 setup.py --forth-source /path/to/lawfully-obtained/sources
```

Run from the repository root. Setup verifies all three hashes, makes local
ignored copies, adapts and assembles the kernel. Supplying files does not grant
permission to redistribute them. The usage below assumes this setup is complete.


Scott Baker's [8008-Forth](https://github.com/sbelectronics/8008-forth), a rewrite
of JonesForth, now runs in ntv8008. All interpretation, compilation, dictionary
lookup and application execution happen in native 8008 code. No host Forth or
CPU emulator modifications are needed.

## Run

Build ntv8008 with `./m.sh` (Windows: `call m.bat`), then:

```sh
./ntv8008 a08/forth.hex
```

Type `1 2 + . CR` to print `3`, or define and invoke a word:

```forth
: SQUARE DUP * ;
12 SQUARE . CR
BYE
```

`BYE` halts the CPU. Input EOF also ends the host emulator. Source files work
with either stdin redirection or `-l:`; these examples include their invocation
and `BYE`, so no additional commands are required:

```sh
./ntv8008 -l:forth/examples/hello.f a08/forth.hex
./ntv8008 -p -l:forth/examples/e.f a08/forth.hex
./ntv8008 -p -l:forth/examples/sieve.f a08/forth.hex
./ntv8008 -p -l:forth/examples/ttt.f a08/forth.hex
./ntv8008 a08/forth.hex < forth/examples/hello.f
```

Windows uses `ntv8008.exe` with the same arguments. The interpreter echoes
input; application results appear after the final `APP BYE` input line.

| Example | Result | Workload |
| --- | --- | --- |
| `hello.f` | `HELLO, 8008 FORTH!` | Colon definition and console output |
| `e.f` | 192 digits without a decimal point, then `done` | DX-FORTH decimal spigot, 200 elements |
| `sieve.f` | `count of primes: 1899`, `10 iterations` | Ten passes over 8191 odd candidates |
| `ttt.f` | `10 iterations`, `moves evaluated: 6493` | Ten alpha-beta searches over corner/edge/center openings |

The examples adapt the user's DX-FORTH benchmark sources, without including
DX-FORTH itself. E emits digits directly instead of using the space-delimited
`?` printer, and drops its remaining loop counter. Sieve packs the flags into
1024 bytes so the full workload fits alongside Forth in 16 KiB, and resets its
count every iteration. TTT uses explicit `>=`/`<=` instead of complementing
comparison results: this implementation's true value is **1**, not -1.
The examples supply `FILL`, which is absent from the upstream dictionary.
Its address, count, and byte stay on the stacks instead of in global variables.
Sieve uses native packed-bit access while retaining BYTE's marking order and
starting multiple. E keeps its running accumulator on the stack and uses one
`/MOD` for digit output. TTT checks winning lines through the last move, reuses
the current board address, and keeps returned scores on the stack. Its ascending
move order, alpha-beta pruning, and 6493-node count are unchanged.

## Rebuild and test

Python 3 and the existing A08 C assembler are sufficient. No AS installation,
network access, Forth installation, or downloaded executable is required:

```sh
./forth/rebuild.sh
python3 tests/forth.py
```

On Windows, use a Visual Studio developer command prompt:

```bat
call forth\rebuild.bat
py -3 tests\forth.py
```

`PYTHON` selects a Python command for either rebuild script. The Windows
script otherwise uses `py -3` or `python`. The default `test.sh` / `test.bat`
suites include the Forth tests and all three full benchmarks. Tests rebuild
and compare the locally generated assembly/HEX, exercise stacks, bytes and variables,
recursive definitions, branches and loops, and independently verify e's digits,
sieve's prime count and TTT's node count. They require `BYE` to execute rather
than accepting premature input EOF as success.

`prepare.py` expands only the AS macro dialect used by the three pinned
upstream sources. It translates the newer 8008 mnemonics, numeric radix,
expressions and string literals into A08 syntax, then writes `a08/forth.asm`.
A08 assembles the generated file normally. Upstream files stay unchanged.
The generated assembly is created locally for inspection and direct assembly.

Adaptations and fixes:

* Entry at decimal 64, kernel at 0x2000, without board memory banking.
* Console input on port 2 and output on physical port 10 (octal 12), using
  the emulator's ready bit. Forth LF output becomes one host newline; the
  upstream CR/LF sequences do not create doubled blank lines.
* Correct the upstream `CG` dictionary name to `C@`, and expose its immediate
  `[RECURSE]` implementation under the conventional name `RECURSE`.
* Allocate `VARIABLE` storage after its dictionary body so the common idiom
  `VARIABLE ARRAY n ALLOT` provides contiguous data without erasing the
  variable's own dictionary header/code. This is essential for the benchmarks.

## Limits and licensing

This is a small JonesForth-style implementation, not a claim of ANS Forth
conformance. Cells are 16 bits. The kernel retains upstream's unsigned
16-by-8-bit multiplication/division routines: the second operand must be
0..255 for `*`, and 1..255 for `/`, `MOD`, `/MOD`. Larger operands are silently
truncated; the benchmarks stay within these limits. Signed division and
full-range signed comparison overflow are not corrected by this integration.

RAM layout: 0x0100 contains kernel variables and the downward-growing return
stack; 0x0200 the downward-growing data stack; 0x0300 the line buffer;
0x0400..0x1fff the user dictionary/data; 0x2000..0x3fff the kernel. Stacks and
user dictionary have no overflow checks. Keep input lines below 256 characters
and names at most 31 characters. Upstream `I`/`J` inspect fixed return-stack
offsets, so use them directly in the definition containing their `DO`, rather
than in a helper called from that loop. A `DO` loop must execute at least once;
avoid equal or inverted initial bounds. These examples do not require disks,
floating point, CP/M calls, or hardware serial devices.

See [NOTICE.txt](NOTICE.txt) for the pinned revision, source hashes and licensing
status. **No explicit license grant was found for Baker's rewrite.** Confirm
its redistribution terms before publishing the upstream sources, adapted
assembly, or HEX. This integration does not assign them a new license.

## Native packed flags

`native.inc` adds three words through the adapter, leaving all pinned upstream
files unchanged:

* `3RSHIFT ( u -- u/8 )` shifts all 16 unsigned bits logically.
* `BIT@ ( base index -- mask-or-zero )` reads one packed bit.
* `BITCLR ( base index -- )` clears one packed bit, preserving its neighbors.

The bit words use a shift rather than general division and combine address and
mask calculation with byte access. They preserve the data/return-stack pointers
and support byte-page crossings. No bounds checks are added. Sieve calls them
directly in its original marking loop, with the same 1024-byte packed flags,
8191 candidates, ten passes, and 1899-prime result.

Sieve drops from 8,561,996,610 to 3,023,351,976 clock cycles (17,124.0 to 6,046.7
seconds at 500 kHz), a 2.83x speedup. Tests cover every mask bit across a byte-page
boundary, neighboring bytes, a live return-stack value, and logical shifts at
0, 7, 8, 255, 256, 32768, and 65535.
