# Official A08 assembler dependency

A08 is not bundled in this repository. Its official source and documentation
are available from [Herb Johnson](https://www.retrotechnology.com/restore/a08.html).
The assembler supports the original 1972 Intel 8008 mnemonics used here.

From the repository root, build locally with:

```sh
./a08/m.sh
```

On Windows in a Visual Studio developer command prompt:

```bat
call a08\m.bat
```

Python 3 downloads the official ZIP, verifies SHA-256, extracts only the assembler
sources and notices into ignored `a08/build/src/`, and builds `a08/a08` or
`a08/a08.exe`. For offline setup, set `A08_ARCHIVE` to a previously obtained
matching ZIP. `CC` selects the host C compiler; defaults are `cc` and `cl`.

Pinned URL: https://www.retrotechnology.com/restore/a08.zip

SHA-256: `37e5061618a89debd98955d682a494c78c9d6e445d8af6a1173235b68fcf67c0`

Verified 2026-10-30. This official version already includes the RTS fix reported
by David Lee. The build makes one local portability change, `void main(argc,argv)`
to `int main(argc,argv)`, leaving copyright notices intact. The change is
recorded in `a08/build/LOCAL_CHANGES.txt`. The original verified ZIP is unchanged.
If upstream replaces its ZIP, setup deliberately rejects a different hash;
review and update the pin rather than silently applying old patches.

A08's Legal Note allows commercial and noncommercial use and free copying /
distribution, limits distribution charges to media, shipping and nominal handling,
requires written permission for other distribution, and requires preservation
of copyright notices in source, object code and documentation. The complete
controlling notice is in the fetched `a08/build/src/A08.DOC`, not the BSD project
license. Credits: William C. Colley III (1985/1987) and Herb Johnson's adaptations.

The assembly examples in this repository are separate from the download. We do
not extract the official ZIP's sample programs or assume A08's terms license
those distinct historical works. `echo.asm` is an original keyboard demo;
`hello`, `count`, `sieve`, `e` and `ttt` are project examples; `robson` is an MIT
interpreter derivative. Rebuild these with `./a08/rebuild.sh` or `rebuild.bat`.

The assembly TTT benchmark uses nine explicit 16-byte frames at offsets
10H through 90H, with B encoding the depth. Separate MIN and MAX copies know
the side to move statically. A frame stores its last tried board address,
which also tells a returning child which move to undo. A MIN frame's alpha and
a MAX frame's beta are read from the parent instead of copied. The root's
virtual parent starts at offset 00H; its first byte stays zero. Board addresses
F7H through FFH wrap into that zero sentinel, so `ORL` detects exhaustion
without loading and comparing the board address against a constant. The board,
frames and node counter share a page; D caches the count's low byte.

WINNER takes the last move's board address in E and the known piece in C,
patches only the low byte of a trampoline (all line checks start in one page),
and returns Z for a win. The winning score is loaded only when the check wins.
The source and tests preserve ascending moves, all three drawn openings, and
6493 search nodes per iteration.

Sieve uses an 8× unrolled `CPM`/`CFZ PRIME` scan and a short marking loop for
steps below 256. Eight copies of that marking loop fall through on the common
no-carry path; a low-byte carry updates H and resumes the correct next copy.
The byte flags already allow direct loads and clears, so the 4004's packed-bit
scan and RAM-bank optimizations do not transfer directly.

E unrolls division into quotient cases 0 through 9. On failure, each case stores
the remainder and falls into its own lookup-multiply tail, adding the known
quotient with an immediate instruction. Quotient zero omits the addition and
carry check. A generic fallback handles the initial division-by-one result of
27; the algorithm and both multiply lookup pages remain unchanged. Thus the
4004's small-quotient specialization and inlining ideas transfer, while its
nibble arithmetic and RAM-bank scheduling do not.

| Benchmark | Previous 8008 clocks | Current clocks | Reduction | Seconds at 500 kHz |
| --- | ---: | ---: | ---: | ---: |
| sieve (10 passes) | 25,430,180 | 25,124,060 | 1.2% | 50.25 |
| e | 9,523,146 | 8,139,284 | 14.5% | 16.28 |
| ttt (1 iteration) | 7,722,478 | 7,589,800 | 1.7% | 15.18 |

Before either optimization pass these took 39,067,880, 18,262,668, and
14,457,102 clocks, respectively. The current changes trade more repeated code
for fewer executed instructions; the fixed array/frame allocations are unchanged.
The integration suite checks exact output, alternative e sizes, repeated sieve
and TTT runs, every reachable board/last move, more than 5000 quotient/remainder
cases, and every sieve flag against independently generated primes. Intel MAC8
also checks that the project sources produce the same bytes as A08 when the
historical image is available.

The original b8008 integer BASIC image is included as `b8008.asm` and
`b8008.hex`. Its source macros, examples, memory layout, and regeneration
instructions are documented in [the b8008 guide](../b8008/README.md).
It is part of default setup and tests, with no additional historical download.
