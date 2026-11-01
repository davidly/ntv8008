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

The assembly TTT benchmark uses nine explicit 16-byte frames in one page,
with B encoding the frame offset and depth parity. E carries the candidate
move through occupied-cell scans and supplies WINNER's last-move argument;
node counting and child-frame setup preserve it until that call. The parent
resume position is written only before descent. The return path still reads
the child's saved last move to undo its board placement.

One iteration takes 14,457,102 clocks (28.9 seconds at 500 kHz), versus
16,111,346 before these frame-access refinements (10.3% fewer). Ascending moves,
the three drawn openings and 6493 nodes are unchanged. The integration suite
checks repeated iterations and the winner against every reachable board/last
move, poisoning the old frame argument to verify the register interface.
