# Publication validation

Validated 2026-10-30 on Linux and native Windows. macOS execution was not tested.

* A08 was fetched from its official site and pinned by SHA-256. The official
  release contains the RTS fix; the build-copy patch only changes `main`'s
  return type. Core assembly and Robson regenerate successfully.
* SmallC and all four ACK frontends were built from source in a separate build
  tree, using verified source archives. No original-tree tool binary is needed.
* A fresh local Git clone, containing only the publication inventory, completed
  `setup.py --all` and `test.sh --compile`: 152 tests reported, with explicit
  skips for unavailable historical components. It completed all 18 default
  benchmark runs (assembly, ACK C/Pascal/Modula-2/BASIC, SmallC).
* Private staging validation supplied the existing Forth and PL/M inputs and
  fetched the pinned SCELBAL source through the optional setup path. All 155
  tests reported by `test.sh --compile --basic-benchmarks` passed, including
  full SCELBAL benchmarks. The historical inputs/outputs are not publication
  files and are not copied into the new repository.
* Native Windows `setup.bat --smallc` builds the emulator, A08 and SmallC.
  CPU and language/native-codegen suites passed; the POSIX terminal test was
  explicitly skipped. Windows ACK frontend rebuilding was not tested; use WSL
  or supply compatible native tools with `ACK_TOOLS`.
* Windows validation exposed a Git ownership/path normalization issue when
  auditing a WSL UNC directory. The audit now supplies the correctly normalized
  per-command safe-directory path; all three Windows publication tests pass.
  No global Git configuration was changed.
* Publication tests verify the file inventory, required notices, preserved
  upstream hashes and rejection of restricted/uncleared historical candidates.
  Checksum verification passes after a Git checkout. Original upstream files
  use binary-preserving Git attributes; project text has deterministic endings.

Build artifacts and downloaded dependencies are Git-ignored. These checks
validate the recorded publication boundary; each third-party license remains
applicable as documented in THIRD_PARTY_NOTICES.md.
