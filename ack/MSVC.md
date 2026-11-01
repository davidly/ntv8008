# Native Windows ACK build

ACK's five frontends and their required helpers now build directly on Windows
with **Python and Visual Studio 2022/MSVC**. A fresh checkout needs no Linux/WSL
preparation, MSYS2, CMake, GNU compiler, Make, Ninja, or installed lex/yacc tools.

From a Visual Studio 2022 x64 developer command prompt:

```bat
setup.bat --ack
ntv8008.exe ack\examples\hello.hex
py -3 tests\ack.py --compile
```

`setup.bat --all` also builds SmallC and the other default tools. `test.bat
--compile` then runs the complete available regression suite, including real
compiler rebuilds. Internet access is needed for uncached pinned ACK and Lua
source archives; both downloads are SHA-256 verified. The assembler is fetched
by the normal setup path.

## What gets built

The native driver, `ack/msvc.py`, builds its own generators:

* **Berkeley Yacc 20260126**: public-domain yacc-compatible parser generator;
  selected original source and license are included under `generators/byacc/`.
* **Reflex 20260131**: Thomas E. Dickey's maintained Flex 2.5.4 derivative;
  selected original source and complete terms are included under
  `generators/reflex/`. It avoids an external GNU M4 dependency. This is the
  C scanner generator, distinct from the similarly named C++ RE/flex project.
* **Lua 5.4.7**: MIT-licensed source fetched and built locally with MSVC, used to
  run ACK's existing EM table generators.
* **ACK LLgen and tabgen**: built directly from ACK's own source. The upstream
  LLgen source includes its bootstrap parser; no previously built LLgen is needed.

This product includes software developed by the University of California,
Berkeley and its contributors. See the complete [Reflex terms](generators/reflex/upstream/COPYING)
and [third-party notices](../THIRD_PARTY_NOTICES.md) when redistributing binaries.

The driver generates the frontend parsers, scanner C, EM headers/tables and
optimizer patterns on Windows. It replaces the small upstream sed/awk shell
transformations with Python and invokes each C generator through `subprocess`,
without a shell pipeline. Optimizer pattern generation passes the preprocessor's
output directly to the native table generator.

Nine host tools are written to `ack/build/bin/`:

```text
cpp.ansi.exe       em_cemcom.ansi.exe
em_pc.exe          em_m2.exe
em_bem.exe         em_occam.exe
em_opt.exe         em_opt2.exe          em_decode.exe
```

The existing Python language drivers select these executables automatically.
`ACK_TOOLS` can select another compatible native tool directory. The generated
HEX programs still run on every supported emulator host.

## Build directories and diagnostics

All extracted ACK/Lua sources, generated files, native tools and objects remain
inside ignored `ack/build/`. Included generator source under `ack/generators/`
is unchanged from its recorded upstream archives. Configuration headers and
compatibility shims are maintained separately.

To build only the host tools, without rebuilding the emulator or examples:

```bat
py -3 ack\msvc.py
```

For an isolated experiment:

```bat
py -3 ack\msvc.py --build-dir "ack\build\native experiment" --bin-dir "ack\build\alternate tools"
set "ACK_TOOLS=%CD%\ack\build\alternate tools"
py -3 ack\compile.py ack\examples\hello.c
```

`ACK_ARCHIVE` and `LUA_ARCHIVE` can select existing archives for offline setup,
using the same pinned checksums as the Linux bootstrap. Previously verified
archives in `ack/build/` are reused automatically. Generated parser/table C,
objects and host executables from a Linux build are never bootstrap inputs.

Every invocation regenerates/recompiles the selected targets. Logs under
`ack/build/msvc/objects/logs/` retain compiler output and a JSON-lines command
record. A failure identifies the relevant log. Source and output paths containing
spaces, including a WSL UNC share accessed by native Windows tools, were tested.

## MSVC adaptations

No new changes to compiler algorithms or grammar files were needed. The native
build reuses the Pascal, BASIC and Occam patches from the ordinary ACK bootstrap.

| Issue | Handling |
| --- | --- |
| GNU compile/archive/link commands | Python invokes `cl`, `lib`, and `link` directly |
| GCC unreachable/noreturn annotations | `__assume(0)` and `__declspec(noreturn)` |
| Old ACK compatibility branches | `/std:c11 /Zc:__STDC__` enables the ANSI-C paths |
| POSIX CRT names and `<unistd.h>` | Small shims in `ack/msvc/` select the Microsoft equivalents |
| Temporary-file seed and creation | `timespec_get`, `_mktemp_s`, and exclusive binary `_open` |
| LLgen's Unix filename handling | Pass normalized forward-slash input paths |
| Deep upstream object filenames | Short hashed object names in a flat build directory |

Upstream warnings are retained in logs. This includes old-style declarations,
narrowing conversions, BASIC debug-output formatting and a guarded shift in a
floating-point helper. The build does not broadly suppress or rewrite those
sources. The 8008 integrations remain integer language subsets.

## Validation

A native Windows build starting with fresh verified ACK/Lua archives and the
included generator source regenerated all inputs and built all nine host tools.
It took approximately 46 seconds on the development machine, including native
generator compilation and all ACK generation/compilation, excluding download
and extraction time. MSVC 19.44.35229 x64 was used. No GNU build executable was
invoked.

All five language compile/runtime suites passed. They rebuilt and compared all
**25 example HEX images byte for byte** with the existing published images,
including sieve, E and TTT. The native C differential test also passed. Parser C
and table formatting can differ from Bison/Flex output; target program output
and HEX comparisons are the relevant checks.

Both main test scripts include `tests/ack_msvc.py`, which checks allocation
comments, Windows line endings, token-name generation, complete generated-input
dependencies and rejection of unsupported recipe commands. Windows CI builds
all host tools natively with `setup.bat --all`, then runs `test.bat --compile`.
Linux retains its existing ACK bootstrap and full compiler tests.

## Maintaining the pinned build recipe

`ack/msvc/recipe.json` contains build metadata derived from the pinned ACK graph:
372 C compilation units, grouped include paths/defines, libraries, and 83 source
creation rules. It contains no generated parser/table C or compiled objects.
The native driver supports only the recognized operations used by this graph;
unrecognized commands fail rather than being passed to a shell.

After changing the pinned ACK revision, maintainers can refresh metadata from a
completed Linux ACK build:

```sh
python3 ack/msvc_recipe.py --source ack/build/src/ack --output ack/msvc/recipe.json
```

Review generator-operation changes and rerun clean Windows setup and the compiler
suites. This export step is for maintaining the recipe; Windows users never
need to run it. Source pins, selected files and terms are recorded in
`generators/*/NOTICE.txt`, [ACK-COPYRIGHT](ACK-COPYRIGHT), and [NOTICE.txt](NOTICE.txt).
