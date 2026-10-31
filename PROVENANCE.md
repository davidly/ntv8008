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
* Intel PL/M compiler images, tape archives and generated images; local-input
  integration only.
* Original-tree executables, object files, logs, listings, archives, caches,
  screenshots and private configuration.

Hashes/URLs for each upstream tool are recorded in its NOTICE file and setup
code. Public availability is not treated as permission. Local-input integration
does not grant rights to the supplied historical software. The separate BA
compiler development tree is outside this publication; no BA source or binary
is copied here.
