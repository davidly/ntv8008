# Programming the ntv8008 machine

Start with [your first program](first-program.md), then use this reference when
choosing a language or connecting your code to the emulated machine.

## Machine contract

All addresses 0000h through 3fffh are writable RAM. HEX records load bytes at
specified addresses; multiple images can be loaded. Execution starts at 0040h
unless `-a:address` selects another address. There is no operating system,
filesystem, loader relocation, or memory protection on the target.

`HLT` ends an application successfully. Ctrl-C/Ctrl-Q or input EOF ends a console
session. A cycle budget (`-n:1000000`) makes runaway programs fail. Interpreter
errors and runtime errors may print a message and halt: check output as well as
exit status in automated tests.

Default ports (numbers here are decimal):

| Port | Operation | Result |
| --- | --- | --- |
| 1 | INP status | 80h if input is ready; zero otherwise |
| 2 | INP character | Seven-bit character with bit 7 set when ready |
| 10 | OUT character | Write the low seven bits to the console |

Input linefeed becomes carriage return; output carriage return becomes linefeed.
Mask a received character with 7fh before comparing ASCII. See the assembly
starter for a polling example. `--in`, `--status` and `--out` override ports;
compiled console libraries assume their default assignments. Use `-l:file` for
recorded input; EOF ends emulation rather than returning to the keyboard.

## Calls, data and space

The hardware has eight address registers, one holding the active PC: only seven
saved return addresses are available. Assembly routines must bound their call
nesting or explicitly implement a RAM stack. Compiler runtimes implement deeper
calls and recursion with software stacks. Do not mix calling conventions merely
because two sources assemble with A08. Consult [ACK](../ack/README.md) and
[SmallC](../smallc/README.md) before adding assembly helpers.

C integers and pointers are 16 bits; characters occupy one byte. Byte arrays can
save both space and address-calculation time. Validate indices yourself in C.
Both C compiler drivers reject images extending beyond 3d00h, reserving a minimum
stack margin; recursion and large local arrays can still exhaust that margin.
There is no supported general malloc/free interface. Prefer fixed-size buffers.

## Choose a language

| Language | Useful properties | Read before writing code |
| --- | --- | --- |
| A08 assembly | Explicit registers, layout and cycle costs | [Assembly guide](../a08/README.md); unmarked constants are octal |
| SmallC | Traditional C syntax, byte arrays, pointers, recursion | [Subset and runtime](../smallc/README.md); no full standard library |
| ACK C | ANSI frontend with freestanding 8008 runtime | [Supported types and libraries](../ack/README.md) |
| b8008 | Interactive signed 16-bit integer BASIC, byte arrays | [Dialect and limits](../b8008/README.md) |
| Pascal / Modula-2 / Occam | Structured alternatives using ACK | Respective guides under `ack/`; host frontend support exceeds target runtime support |
| PL/M / Forth / SCELBAL | Historical toolchains and interpreters | Respective guides; some require separately acquired sources |

For C console work start with `putchar`, `getchar`, `puts` and the supplied integer
output helpers. Their implementations and the starter programs are the API
examples; do not assume hosted C functions such as `printf` exist. Language
READMEs describe additional keyboard helpers and arithmetic restrictions.

## Measure and debug

`-p` reports target clock periods and estimated time at the original 500 kHz
clock, alongside host time. `-s:500000` throttles execution to that rate. Neither
models external memory wait states. Compare equivalent workloads and iteration
counts, and keep terminal I/O out of computational timing comparisons.

Keep generated assembly (`--assembly`) when compiling C. It exposes runtime calls
and the exact operations to compare when optimizing. See the
[debugging walkthrough](debugging.md) for listings and symbolic traces.
