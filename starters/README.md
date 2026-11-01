# Starter projects

Start with the [first-program guide](../docs/first-program.md). It covers setup,
copying a project, changing its source, recorded input, tracing, and common errors.

| Directory | Source | Setup from the repository root |
| --- | --- | --- |
| `smallc` | Traditional C | `./setup.sh --smallc` or `setup.bat --smallc` |
| `b8008` | Integer BASIC session | `./setup.sh` or `setup.bat` |
| `assembly` | A08 assembly | `./setup.sh` or `setup.bat` |
| `ack-c` | ANSI C | `./setup.sh --ack` or native Windows `setup.bat --ack` |

Each program uses a four-element byte array to look up the square of an input
from 0 through 3, checks the index, and prints the result. Input `3` prints
`SQUARE =` followed by `9`. Invalid input prints a validation message.

Copy a directory to `work/<project>` to begin your own program. Its wrappers
expect to be two directories below the repository root. Build and run from that
project directory with `./build.sh` / `./run.sh`, or `build.bat` / `run.bat`.
BASIC needs only the run script; it combines the source and `input.txt` into a
session and feeds that to b8008. The other starters accept interactive input, or
`./run.sh -l:input.txt` / `run.bat -l:input.txt`. Build first; run does not compile.

`build/` holds generated files and is ignored. These starters do not download or
build their prerequisites: run setup once before using them. Shell scripts use
`PYTHON` or `python3`; batch scripts use `PYTHON`, the Python launcher, or `python`.
ACK's native Windows setup builds all required generators and host tools with
MSVC; WSL is optional. See [the Windows build guide](../ack/MSVC.md).

The starter source and wrappers are BSD-3-Clause project code; see [LICENSE](../LICENSE).
