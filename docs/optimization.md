# Measure before optimizing

The [example sources](../examples/optimization/) isolate three changes. Each pair
prints the same answer and runs ten passes over 128 elements or iterations.
They use traditional C accepted by both SmallC and ACK C.

After setup with `--smallc --ack`, from the repository root run:

```sh
python3 examples/optimization/run.py
python3 examples/optimization/run.py --compilers smallc
```

Windows uses `py -3`. The driver compiles every selected variant, verifies its
answer, then reports target clock periods and loaded HEX bytes. Generated
assembly is retained under `examples/optimization/build/`. No runtime timing
assertions are baked into the regression tests; correctness is checked.

## Store small values in bytes

[words.c](../examples/optimization/words.c) uses `int values[128]`;
[bytes.c](../examples/optimization/bytes.c) uses `unsigned char values[128]`.
Everything else is identical. Stored values range from 0 through 127, so both
representations are exact. The sum remains a 16-bit integer and prints `8128`.
The byte version saves 128 bytes of array storage and can simplify loads and
address calculation. Inspect the generated assembly near the array accesses.
Results differ by backend; the smaller type is not an automatic speed guarantee.

## Avoid a tiny hot call

[calls.c](../examples/optimization/calls.c) calls `twice(i)` in its inner loop;
[inline.c](../examples/optimization/inline.c) writes `i+i` directly. Both print
`16256`. Find the generated function label and its jumps/RAM-stack operations
in the first assembly file, then compare the direct arithmetic in the second.
These compilers cannot be assumed to inline every small procedure automatically.
Inlining a larger or frequently repeated body can increase code size; measure it.

## Carry a value instead of recomputing it

[remainder.c](../examples/optimization/remainder.c) sums `i % 10`;
[counter.c](../examples/optimization/counter.c) maintains a digit counter, resets
it after 9, and sums that instead. Both print `568`. The sequential iteration
makes this replacement valid: an increment and comparison replace repeated
remainder calculations. It would not be valid if `i` could jump arbitrarily or
start at another value without initializing the counter accordingly. Compare
arithmetic helper calls with the counter update in the generated assembly.

## Measured results

Clock periods, 2026-11-01; these include startup and final output:

| Change | SmallC before | SmallC after | ACK C before | ACK C after |
| --- | ---: | ---: | ---: | ---: |
| Word array to byte array | 3,932,454 | 3,799,846 | 4,973,378 | 2,806,850 |
| Tiny call to direct addition | 6,418,738 | 4,549,938 | 6,366,464 | 3,540,224 |
| Remainder to rolling counter | 7,232,228 | 2,171,588 | 6,252,128 | 2,170,688 |

Loaded image bytes for the same changes:

| Change | SmallC before / after | ACK C before / after |
| --- | ---: | ---: |
| Byte array | 2,451 / 2,300 | 2,063 / 1,870 |
| Direct addition | 2,091 / 2,031 | 1,707 / 1,650 |
| Rolling counter | 2,035 / 2,064 | 1,649 / 1,674 |

The rolling counter buys speed with a modest size increase. Loaded bytes do not
include all uninitialized data or the RAM stack. These are independent examples,
not successive changes to one benchmark; their improvements cannot be added.

For your own program, first preserve an output test and a cycle count. Change
one thing, rerun both, inspect the relevant generated instructions, and keep the
change only if its benefit justifies the complexity. Prefer target cycles over
host elapsed time for tiny programs. The [debugging guide](debugging.md) explains
how listings and automatic symbol maps help identify the code being executed.
