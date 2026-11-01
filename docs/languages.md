# Choose a language

The [comparison programs](../examples/compare/) all sum the integers 1 through 10
and print `55`. Read their source side by side:

| Language | Source | Model and useful limits |
| --- | --- | --- |
| Assembly | [sum.asm](../examples/compare/sum.asm) | Explicit registers and calls; unmarked A08 constants are octal |
| SmallC | [sum.c](../examples/compare/sum.c) | Traditional C declarations; byte arrays, pointers, RAM-stack recursion; small library |
| ACK C | Same C source | ANSI frontend; freestanding target library, not a hosted C environment |
| b8008 | [sum.bas](../examples/compare/sum.bas) | Interactive signed 16-bit integers; no compilation; checked arrays |
| Pascal | [sum.p](../examples/compare/sum.p) | Structured procedures, arrays and integer output; target runtime subset |
| Modula-2 | [sum.mod](../examples/compare/sum.mod) | Modules and structured types; supplied InOut subset |
| Occam | [sum.ocm](../examples/compare/sum.ocm) | Sequential integer processes and console channels; no concurrent scheduler |

SmallC and ACK C share this simple source, but are separate compilers with
separate calling conventions. Do not mix their generated routines. The ACK
languages share a backend but have different frontend/runtime costs. The
[programming reference](programming.md) links each language's precise limits.

## Build and compare

Run setup with `--smallc --ack` (or `--all`) first. From the repository root:

```sh
python3 examples/compare/run.py
python3 examples/compare/run.py --languages assembly b8008
```

On Windows use `py -3` instead of `python3`, after `setup.bat --all` in a Visual
Studio developer prompt. The driver builds each selected source, checks its
output, and prints image bytes, clock periods and estimated 500 kHz time.
Generated assembly and images stay in `examples/compare/build/`. Each ACK
language can also be compiled directly using `ack/pascal.py`, `ack/modula2.py`
or `ack/occam.py`; C uses `smallc/compile.py` or `ack/compile.py`.

Measured with the current backends on 2026-11-01:

| Language | Loaded image bytes | Clock periods | Seconds at 500 kHz |
| --- | ---: | ---: | ---: |
| Assembly | 41 | 1,504 | 0.003008 |
| b8008 | 6,467 | 508,456 | 1.016912 |
| SmallC | 1,877 | 340,378 | 0.680756 |
| ACK C | 1,548 | 345,194 | 0.690388 |
| ACK Pascal | 2,642 | 373,286 | 0.746572 |
| ACK Modula-2 | 2,427 | 370,298 | 0.740596 |
| ACK Occam | 2,686 | 368,472 | 0.736944 |

These are deliberately tiny examples, not compiler rankings. Startup and decimal
output dominate much of the compiled run. Assembly uses an 8-bit accumulator and
a dedicated two-digit formatter; the high-level versions use integer arithmetic
and general output helpers. BASIC's image size is the interpreter, with the
program subsequently entered into RAM; its cycles include input, tokenization,
execution and prompts. Loaded image bytes count HEX data records, excluding
unmaterialized storage and stack usage. They are not peak memory consumption.
For substantial computations compare the established sieve, e and TTT workloads.

Choose SmallC or b8008 for a first personal project. Choose ACK C for its richer
frontend, assembly when exact layout matters, or another language you know well.
The [adventure examples](../examples/README.md) show a complete interactive task
in both C and BASIC.
