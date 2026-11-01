# Licensing and third-party notices

The root [LICENSE](LICENSE) is BSD-3-Clause and covers David Lee's project
contributions: the emulator, console host, compiler backends and original
runtimes, integration/build/download scripts, tests, documentation, and original
examples. It does not replace any third-party license, copyright notice, or
restriction. Third-party license texts themselves retain their original terms.

| Component / files | Terms and provenance | Publication treatment |
| --- | --- | --- |
| ACK frontend/optimizer and local source patches | BSD-style three-clause grant, Copyright 1987, 1990, 1993, 2005 Vrije Universiteit. Full notice: [ack/ACK-COPYRIGHT](ack/ACK-COPYRIGHT); pins: [ack/NOTICE.txt](ack/NOTICE.txt). | Host sources/tools are downloaded and built in ignored `ack/build/`. Retain upstream file notices and the full ACK grant when redistributing ACK or patched ACK sources/binaries. New 8008 runtime/code generator is project code. Occam frontend repairs are recorded in `ack/occam/patch.py`; no upstream Occam runtime is linked. |
| Lua 5.4.7, ACK build dependency | MIT, Copyright 1994–2024 Lua.org, PUC-Rio. License is in the fetched source's `src/lua.h` and `README`. | Downloaded to ignored `ack/build/`; not linked into generated 8008 applications. Preserve its license if redistributing Lua. |
| Berkeley Yacc, `ack/generators/byacc/upstream/` | Public-domain statement retained in [LICENSE](ack/generators/byacc/upstream/LICENSE); [source pin](ack/generators/byacc/NOTICE.txt). | Selected unmodified sources and bootstrap skeleton included; built locally with MSVC for native ACK generation. |
| Reflex, `ack/generators/reflex/upstream/` | Thomas E. Dickey's MIT-style grant and original Flex BSD-style acknowledgement/advertising terms; full [COPYING](ack/generators/reflex/upstream/COPYING), [source pin](ack/generators/reflex/NOTICE.txt). | Selected unmodified C/grammar/skeleton sources included; generated scanners are unrestricted under COPYING. Binary-distribution acknowledgement: **This product includes software developed by the University of California, Berkeley and its contributors.** Preserve the complete notice and acknowledgement when redistributing the generator. |
| SmallC-85 frontend, `smallc/upstream/*` | Upstream public-domain dedication / Unlicense and disclaimer, retained verbatim in [smallc/upstream/LICENSE](smallc/upstream/LICENSE). Original source notices and README retained. [Provenance](smallc/NOTICE.txt). | Selected unmodified frontend source included. No upstream 8080 backend, CP/M library, or historical executable included. New 8008 backend/runtime is BSD-3-Clause. |
| Robson Tiny BASIC, `robson/upstream/basic.asm`, adapted `a08/robson.asm` and `a08/robson.hex` | MIT, Copyright 2016 paulscottrobson. Full grant: [robson/upstream/LICENSE](robson/upstream/LICENSE); [provenance and adaptations](robson/NOTICE.txt). | Source and adapted images included, with MIT attribution and license. Project additions retain the root BSD license without removing upstream rights. |
| Benchmark ports from David Lee's CP/M and DOS repositories | David Lee's own benchmark source was released under CC0-1.0, separately from the historical tools. [Full CC0 text](licenses/CC0-1.0.txt); details in [PROVENANCE.md](PROVENANCE.md). | The project ports/additions use BSD-3-Clause; upstream CC0 material retains its dedication. This does not relicense historical compilers or third-party examples in those repositories. |
| ntvao style/reference code | The reference repository uses CC0-1.0. [Full CC0 text](licenses/CC0-1.0.txt). | Attribution recorded in PROVENANCE.md. New emulator/host contributions use BSD-3-Clause. |
| A08 assembler | William C. Colley III and Herb Johnson; custom use/redistribution terms in the official package's `A08.DOC`, Legal Note. [Details](a08/README.md). | Not bundled. Setup fetches verified official sources into ignored `a08/build/`, retaining notices, and applies a documented `main` return-type portability fix. No upstream sample programs are extracted for use. |
| SCELBAL | Copyright 1975 Scelbi Computer Consulting, Inc.; Mark G. Arnold permits educational, historical, noncommercial use. Complete required comment: [scelbal/NOTICE.txt](scelbal/NOTICE.txt). | Interpreter source, generated assembly and HEX are NOT included. Explicit optional download/build requires acknowledging its terms. The terms still apply to local/downloaded derivatives and are not made BSD by this repository. |
| Scott Baker's 8008-Forth | No explicit redistribution grant established for the pinned rewrite. [Provenance and hashes](forth/NOTICE.txt). | Kernel source and derived assembly/HEX are NOT included or automatically downloaded. Only project integration code, native additions and independently authored examples are included. Users must supply pinned sources they may lawfully use. |
| Intel PL/M-8 3.3 | Redistribution permission for the recovered Intel/PDP-10 runtime images and compiler-supplied output runtime remains unresolved. [Provenance](plm8/upstream/NOTICE.txt). | Compiler images and generated HEX are NOT included or automatically downloaded. Project runner/recovery code, example source and local-input build instructions are included. No permission to use or redistribute the historical images is asserted. |

The generated ACK/SmallC applications use this project's original 8008 runtime;
upstream ACK libpc, libm2, BASIC/Occam runtimes and the SmallC CP/M runtime are not
linked. Robson's image is a derivative of its MIT interpreter and retains that
license. An assembler's license does not by itself govern an independently
authored program assembled with it.

When packaging binaries or a release, include this file, the root LICENSE and
all applicable third-party grants. A source archive generated from the reviewed
publication manifest excludes fetched dependencies and restricted/uncleared
historical components. Do not upload an arbitrary ZIP of a populated working
directory: local build directories may contain such components.

The b8008 integer BASIC interpreter (`b8008/`, `a08/b8008.asm`, and
`a08/b8008.hex`) is an original BSD-3-Clause project contribution, with no
third-party interpreter source or runtime linked or translated.

## Hunt the Wumpus example

`examples/wumpus/` adapts `davidly/dcc`'s `tests/wumpus.c` at commit
`1d4dff6e140b795899d5f4b7045636daf1c6ac72`. Copyright (c) 2026 David Lee,
MIT licensed; the complete notice is retained in `examples/wumpus/LICENSE`.
Adaptation, build wrappers and recorded sessions in that directory use MIT.
