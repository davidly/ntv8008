# Debug an 8008 program

This walkthrough uses the assembly starter so each traced instruction has a
visible source counterpart. Begin at the repository root after default setup.
Use a scratch copy under `work/trace` as described in [the first-program guide](first-program.md).

## Introduce a controlled bug

In your copied `program.asm`, change the last entry of `SQUARES` from `011`
(octal 9) to `010` (octal 8). Build, then run with `-l:input.txt`. Input 3 now
prints 8. The process exits normally: this is an incorrect result, not a crash.

Generate a listing and a symbol map from the same assembly build. These commands
run at the repository root; use `python` or `py -3` instead of `python3` on Windows,
and `a08\a08.exe` / `ntv8008.exe` as appropriate:

```sh
a08/a08 work/trace/program.asm -lwork/trace/build/program.lst -owork/trace/build/program.hex
python3 tools/symbols.py work/trace/build/program.lst -o work/trace/build/program.map
./ntv8008 -t -i -n:100000 -l:work/trace/input.txt work/trace/build/program.hex
```

Both listing and map must match the HEX image. Recreate them after every edit.
`ntv8008.log` is written in the current directory and replaced on each traced run.

## Read the trace

Find `FOUND:` in the log. Its `LAM` loads the selected table byte into A; the
*following* instruction's state shows A = 08. State is recorded before each
instruction executes. Follow execution through the string-printing call and back
to `LAB`, then `ADI 060`, which converts the value to an ASCII digit. This shows
the wrong value was already present at the table load. Inspect `SQUARES` in the
listing, restore `011`, regenerate the image/listing/map, and confirm output 9.

The listing displays an octal page and octal offset. Convert to a byte address
with `int(page, 8) * 256 + int(offset, 8)`; PCs in the log and addresses in the map
are hexadecimal. Trace rows include registers, flags, hardware stack selection,
decoded instruction and accumulated clock periods.

## Symbol maps

`tools/symbols.py` extracts A08's resolved symbol table, including compiler and
runtime labels. It combines aliases at one address with `|`. You may edit a map
to retain only function entry labels for a quieter trace. A hand-written map is
also accepted:

```text
# hexadecimal address, then a single name
0040 start
007d PRINT
```

Each nonempty, non-comment row must contain exactly an address and a name.
Addresses must be in 0000..3fff; duplicate addresses are rejected. Missing or
malformed explicitly requested maps fail the run with a diagnostic.

With `-t -i`, the emulator automatically looks for `program.map` beside
`program.hex` (replacing the final extension, preserving its directory). It checks
one adjacent map per loaded HEX file. Missing maps are fine; a present malformed
map or duplicate address across maps fails with a diagnostic. Normal execution
does not read these automatic debug files. `-m:file` explicitly selects one map
instead of all automatic maps, and an explicitly requested missing map fails.
Starter build scripts generate the listing and adjacent map automatically; for
other A08 sources `python3 tools/build_map.py source.asm output.hex` produces all
three together. Rebuild after edits so labels match the image.

A heading appears whenever the nearest preceding mapped
symbol changes. A heading includes `+ offset` when execution first reaches the
middle of its region. Calls, returns and jumps may all produce headings; these
are address annotations, not a reconstructed call stack. Local labels and data
labels are included unless removed from the map. No source-line stepping or
symbolic breakpoints are provided. Without a map, instruction tracing retains
its ordinary numeric format; normal execution does no symbol lookup.

For C, retain generated assembly with the compiler's `--assembly` option, then
assemble it with `-l` and generate a map exactly as above. Other languages that
emit A08 assembly can use the same workflow. Function names may be mangled by
the backend; the map preserves the assembler's actual names.

For hangs, begin with a small cycle budget and inspect repeated PCs. For damaged
return addresses, compare the last correct call/return and review software-stack
usage. For keyboard waits, supply the expected characters with `-l:file` and
check that input masking and port assignments match the machine contract.
