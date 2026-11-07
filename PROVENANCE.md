# Source provenance and publication boundary

Publication review: 2026-10-30. The publication tree was selected explicitly
from the existing i8008 development tree; it is not a recursive copy of that
tree. `publication-manifest.json` records the reviewed repository files, their
hashes, license categories and origins. It is an initial publication snapshot;
review and regenerate it when intentionally changing source files.

The original Intel 8008 emulator and portable host were developed for this
project, using [ntvao](https://github.com/davidly/ntvao) as a coding-style and
console reference. The ACK EM-to-8008 renderer, software-stack runtime, language
support, optimizer passes and wrappers were developed here rather than copied
from ACK's 8080 backend or historical language runtimes. The SmallC-85 frontend
is preserved separately from the new 8008 backend. Robson's original interpreter
is preserved with its MIT license; its dialect/console adaptation is documented.

Sieve uses the classic BYTE odd-number sieve algorithm. E uses a factorial-series
decimal spigot. TTT uses ascending-move alpha-beta minimax, starting at positions
0, 1 and 4. Ports were based on David Lee's benchmark implementations in:

* [cpm_compilers](https://github.com/davidly/cpm_compilers): `asm/SIEVE.ASM`,
  `asm/E.ASM`, `asm/TTT.ASM`, BASIC examples under `microsoft basic-80 v52`,
  and Forth examples under `DX-FORTH for CPM 4.56`.
* [dos_compilers](https://github.com/davidly/dos_compilers): David Lee's E/TTT
  example implementations under `Intel PLM-83 v3.1`.

Those repositories explicitly apply CC0-1.0 to the author's benchmark/build
code, while excluding the historical tools and warning that tool-supplied sieve
examples can have different terms. This publication includes the author's
project ports, not copies of those historical tools, runtime libraries, manuals,
or tool-supplied examples. The CC0 dedication is retained in
`licenses/CC0-1.0.txt`; the project's new code is BSD-3-Clause.

Explicit exclusions:

* A08 source, executable, bundled historical fixtures and manual: downloaded
  locally under its own terms, not republished here.
* STAR, Monitor-8, and the upstream opcode/dollar sample files and derivatives.
* SCELBAL interpreter source and derived assembly/HEX; optional acknowledged
  noncommercial download/build only.
* Baker Forth kernel source and derivatives; local-input integration only.
* Intel PL/M compiler and MAC8 assembler images, tape archives and generated
  images; local-input integration only.
* Original-tree executables, object files, logs, listings, archives, caches,
  screenshots and private configuration.

Hashes/URLs for each upstream tool are recorded in its NOTICE file and setup
code. Public availability is not treated as permission. Local-input integration
does not grant rights to the supplied historical software. The separate BA
compiler development tree is outside this publication; no BA source or binary
is copied here.

Occam 1 was added on 2026-10-31 using the same pinned ACK source and notice.
The dormant frontend is repaired only in its verified build copy. Its console
prelude/runtime and examples are project code; TTT uses explicit frames with
the same ascending alpha-beta search as the other project implementations.
No upstream Occam library/scheduler or new third-party dependency is included.

ANSI Snake, its separate SmallC rules implementation, keyboard/timing helpers
and regression tests were authored for this project. No external game source,
artwork, terminal translation library or additional dependency is included.
These contributions and the generated Snake image use BSD-3-Clause.

The b8008 integer BASIC under `b8008/`, and its generated `a08/b8008.asm`
and HEX image, are original project code under BSD-3-Clause. Palo Alto Tiny
BASIC was considered as a design reference for a compact integer dialect; no
Palo Alto, Apple, Microsoft, or other historical BASIC implementation code is
incorporated. Its examples reuse this project's existing benchmark algorithms.

Native Windows ACK bootstrap uses selected verbatim source from Berkeley Yacc
20260126 and Reflex 20260131, pinned in `ack/generators/*/NOTICE.txt`. Their
upstream notices remain in place; the Python/MSVC build driver, POSIX compatibility
shims, and replacements for ACK's small shell transformations are project code.
`ack/msvc/recipe.json` records the pinned ACK build graph as data, not generated
parser/table C. Lua and ACK sources remain verified, ignored downloads. All
frontend parsers and optimizer/scanner tables are regenerated on Windows.
This product includes software developed by the University of California,
Berkeley and its contributors.

## Wumpus for both C compilers

`examples/wumpus/program.c` derives from the local `davidly/dcc` checkout's
`tests/wumpus.c`, commit `1d4dff6e140b795899d5f4b7045636daf1c6ac72` (MIT,
Copyright 2026 David Lee). Struct state and multidimensional integer arrays were
flattened to global byte arrays; hosted console calls and argument parsing were
replaced; instructions and computer search were condensed for the 16 KiB target.
The full MIT license is retained alongside the example. The expected sessions
were executed independently with a native GNU89 build of the adapted source.
