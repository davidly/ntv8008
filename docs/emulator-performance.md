# Host parity-flag performance

The emulated parity flag is true when the result byte has an even number of set
bits, including zero. `set_szp()` now uses a 256-byte constant boolean table for
that flag. Sign and zero calculations are unchanged. The implementation is
shared across compilers and needs no optional host instructions or assembly.

## Measurements

Benchmarked on 2026-11-01, Core i9-14900KF, x64, pinned logical CPU 0, with
GCC 11.4 on Linux/WSL and MSVC 19.44.35229 on Windows. Builds used the same
optimization settings as `m.sh` / `m.bat`: `-O3 -flto` and `/O2 /GL /LTCG`.
The harness executes the actual ACK C sieve, e and TTT images and b8008's e
program. Console output is accumulated into a hash rather than sent to the
terminal. Each invocation repeats the application for at least 0.2 seconds;
results below are medians of six samples after one warmup round. Variant and
workload order are shuffled. CPU state, RAM and input reset before each run.

Milliseconds of host time per complete application:

| Compiler / parity implementation | Sieve | e | TTT | b8008 e |
| --- | ---: | ---: | ---: | ---: |
| GCC: original XOR folding | 30.115 | 31.275 | 134.031 | 113.191 |
| GCC: folded nibble / 0x9669 lookup | 30.983 | 30.835 | 135.462 | 111.633 |
| GCC: builtin parity | 28.533 | 30.413 | 132.900 | 110.364 |
| GCC: byte table (selected) | 27.555 | 29.188 | 126.759 | 111.221 |
| MSVC: original XOR folding | 27.924 | 28.953 | 124.216 | 102.455 |
| MSVC: folded nibble / 0x9669 lookup | 27.418 | 28.860 | 122.667 | 100.792 |
| MSVC: byte table (selected) | 26.357 | 28.362 | 120.259 | 98.286 |

The shared table saves approximately 2-9% against the old GCC implementation
and 2-6% against MSVC's. GCC's builtin wins narrowly on b8008 e in this run,
but the table is faster on the other three workloads. That small difference
does not justify a compiler-specific path. These are host measurements on one
machine; instruction count alone does not determine emulator throughput, and
results on other architectures may differ. No speedup is claimed for unmeasured
hosts. The table remains ordinary portable C++ on all supported hosts.

All candidates passed the existing exhaustive CPU tests, including parity for
all operand pairs in arithmetic and all byte values for increments/decrements.
Benchmark runs also verify identical target cycle counts and console hashes
between variants. Target cycle counts and the estimated original 500 kHz runtime
do not improve: this change makes the modern host execute those cycles faster.

## Reproduce

Run setup with `--ack` first so the benchmark images are available. From the
repository root on Linux:

```sh
python3 tools/bench_parity.py --compiler gcc --pin 0 --output /tmp/parity-gcc.json
```

In a Windows x64 Visual Studio developer prompt:

```bat
py -3 tools\bench_parity.py --compiler msvc --pin 0 --output "%TEMP%\parity-msvc.json"
```

Omit `--pin` if affinity control is unavailable, or select an allowed logical
CPU. Avoid other CPU-intensive work during measurement. The tool builds each
candidate in a temporary directory, runs the CPU tests, then measures the four
workloads. It does not edit the checkout. `--samples` changes the number of
measured samples; `--output` retains raw measurements and correctness checks.
The GCC builtin is excluded from MSVC candidates. POPCNT intrinsics are not
used because the default emulator build does not require that CPU feature.

## Opcode dispatch and helper inlining

A second round of host benchmarks keeps the parity table above and improves
instruction decoding. `execute()` now dispatches to `execute_decoded()` with a
constant opcode at each switch case. The compiler can eliminate instruction-group
tests, fix register indices, select individual ALU operations and discard unused
flag tests. There is one instruction implementation, with the same comments and
cycle counts; the switch does not duplicate the decoder's source logic.

The small PC, fetch, register, flag and ALU helpers are forced inline. This matters
particularly for MSVC: its normal decisions left many helper calls in the expanded
switch, making that prototype slower. Forcing helpers inline without specialized
dispatch was also slower. The selected combination improves both compilers.
The same portable C++ implementation is used on both; no computed-goto extension,
instruction cache, host assembly or CPU-specific feature is required.

Measured on the same x64 machine and compiler versions as above, with an
additional disabled tracer object to mirror the normal console wrapper. Each
pair uses six measured samples after warmup, shuffled order, one pinned CPU and
at least 0.2 seconds per invocation. The baseline includes the parity-table
optimization, so these savings are additional to that earlier change.

Milliseconds per application, before / after:

| Workload | GCC before | GCC after | Host time saved | MSVC before | MSVC after | Host time saved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ACK C sieve | 28.861 | 23.547 | 18.4% | 28.810 | 26.761 | 7.1% |
| ACK C e | 29.934 | 24.177 | 19.2% | 30.581 | 29.107 | 4.8% |
| ACK C TTT | 131.516 | 108.008 | 17.9% | 128.296 | 120.594 | 6.0% |
| b8008 e | 110.799 | 84.883 | 23.4% | 106.138 | 99.789 | 6.0% |
| asm sieve | 6.434 | 5.755 | 10.6% | 7.261 | 6.820 | 6.1% |
| asm e | 3.016 | 2.676 | 11.3% | 3.477 | 3.287 | 5.5% |
| asm ttt | 2.608 | 2.267 | 13.1% | 2.832 | 2.532 | 10.6% |
| smallc sieve | 27.939 | 24.172 | 13.5% | 30.000 | 27.981 | 6.7% |
| smallc e | 21.537 | 17.107 | 20.6% | 22.341 | 19.962 | 10.6% |
| smallc ttt | 104.939 | 91.801 | 12.5% | 108.478 | 104.532 | 3.6% |

This is approximately 11-23% less GCC host time and 4-11% less MSVC host time
across these ten workloads. Absolute times vary between measurement rounds;
compare each paired baseline and optimized result. Guest RAM usage, application
HEX images and target cycle counts are unchanged. The tradeoff is a larger host
executable: the GCC benchmark's text segment grew from 12,914 to 36,521 bytes.
There is no opcode cache to invalidate: self-modifying guest code still fetches
its new instruction directly from RAM on the next execution.

Other experiments were not retained: combining two operand fetches, replacing
flag packing with conditional selection, checking immediate loads before the
low-opcode switch, and combining all result flags in one table. None produced
consistent gains across the workloads and compilers. Hardware sampling counters
were unavailable in WSL; opcode-frequency instrumentation and optimized assembly
inspection guided the experiments instead. The parity table was rechecked with
the specialized GCC decoder and remained the best overall choice.

Reproduce with the CPU-only harness (no terminal-output timing):

```sh
python3 tools/bench_cpu.py --compiler gcc --pin 0 --extra --output /tmp/cpu-gcc.json
```

Windows, in an x64 Visual Studio developer prompt:

```bat
py -3 tools\bench_cpu.py --compiler msvc --pin 0 --extra --output "%TEMP%\cpu-msvc.json"
```

Run setup with `--ack --smallc` first. Omit `--extra` for just ACK C and b8008 e;
omit `--pin` or choose another allowed CPU where appropriate. The tool reconstructs
a runtime-opcode baseline in a temporary directory, restores ordinary helper
inlining choices there, and compares it with the current specialized decoder.
That equivalent baseline may compile differently from the historical pre-change
binary. Both variants pass the exhaustive CPU tests before measurement, and the
harness verifies matching guest cycle counts and console hashes for every run.
The tool does not change the checkout. As with parity, measurements are specific
to the tested x64 hosts; other machines and compilers can be measured with the
tools rather than assuming the same percentage gain.


## Decoder stop markers (2026-11-06)

The decoder now returns a stop marker with its T-state count for HLT and
undefined opcodes. The execution wrapper tests that marker before reading the
tracer pointer or public halt/error fields. Normal instructions avoid those
loads. The original instruction address, public flags, stop behavior and trace
messages are retained; the marker is private and excluded from guest clocks.

Against commit 89a1b5e, seven measured samples after warmup, shuffled order,
one pinned CPU and the CPU-only harness gave these median milliseconds per run:

| Workload | GCC before | GCC after | Host time saved | MSVC before | MSVC after | Host time saved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ack-sieve | 11.237 | 10.808 | 3.82% | 12.535 | 12.390 | 1.16% |
| ack-e | 10.118 | 9.589 | 5.23% | 10.615 | 10.366 | 2.34% |
| ack-ttt | 52.175 | 50.023 | 4.12% | 54.008 | 53.804 | 0.38% |
| asm-sieve | 4.072 | 3.965 | 2.63% | 4.074 | 4.077 | -0.08% |
| asm-e | 1.490 | 1.371 | 8.01% | 1.706 | 1.693 | 0.78% |
| asm-ttt | 1.316 | 1.262 | 4.15% | 1.362 | 1.317 | 3.29% |
| smallc-sieve | 11.409 | 11.075 | 2.93% | 12.691 | 12.721 | -0.23% |
| smallc-e | 11.721 | 11.121 | 5.13% | 12.802 | 12.481 | 2.50% |
| smallc-ttt | 48.380 | 46.780 | 3.31% | 54.989 | 54.313 | 1.23% |
| basic-e | 77.261 | 73.202 | 5.25% | 84.362 | 82.772 | 1.89% |

The geometric-mean host-time reduction is 4.47% with GCC and 1.33% with MSVC.
The two MSVC sieve differences below 0.3% are too small to treat as meaningful.
Every measured run had identical guest cycle counts and console hashes. These
host-speed changes do not alter target-runtime spreadsheet values or guest RAM.
The GCC benchmark text segment grows by 184 bytes, from 39,306 to 39,490.

Moving halt/error instruction-address capture out of the normal path was also
tried, but regressed MSVC workloads. Combining branch operand fetches was not
retained. The selected version retains the original trace address capture.
Tests exercise normal and injected halts/undefined opcodes, including PC wrap.

Reproduce the paired stop-check comparison with:

```sh
python3 tools/bench_cpu.py --compiler gcc --stop-check --samples 7 --pin 0 --extra --output /tmp/stop-check-gcc.json
```

For MSVC, run the same command with Windows Python and `--compiler msvc` from
an x64 Visual Studio developer prompt. The baseline reconstructs the previous
stop-field check while retaining the current opcode dispatch. Both variants run
the CPU tests first; the benchmark checks guest clocks and output hashes.
