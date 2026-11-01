# Write your first 8008 program

This guide takes you from a fresh checkout to a program of your own. Commands
start in the repository root unless a step says otherwise. The programs run
on the emulated 8008; the compilers run on your modern computer.

## Choose a starter

| Starter | Good starting point for | Compiler host |
| --- | --- | --- |
| [SmallC](../starters/smallc/program.c) | Small C programs, including on native Windows | Linux/macOS or Windows with MSVC |
| [b8008 BASIC](../starters/b8008/program.bas) | Editing and running integer BASIC immediately | No host compiler; BASIC executes on the 8008 |
| [Assembly](../starters/assembly/program.asm) | Direct control of registers, memory and ports | A08 on Linux/macOS or Windows |
| [ACK C](../starters/ack-c/program.c) | ANSI C, pointers and multiple source files | Linux or native Windows with MSVC |

All four starters look up a square in a four-element byte array. Input `3`
produces these last two result lines:

```text
SQUARE =
9
```

An input outside 0..3 prints `USE A DIGIT FROM 0 TO 3.`. The C and assembly
programs read one character. BASIC reads a whole integer followed by Enter.

## First program: SmallC

Install a C/C++ compiler and Python 3. Windows commands belong in a Visual Studio
developer command prompt. Then build the emulator, assembler, and SmallC:

Linux/macOS:

```sh
./setup.sh --smallc
mkdir -p work
cp -R starters/smallc work/first
cd work/first
./build.sh
./run.sh
```

Windows:

```bat
setup.bat --smallc
mkdir work
xcopy /E /I starters\smallc work\first
cd work\first
build.bat
run.bat
```

Create `work` only if it does not already exist. These copy commands are for a
new `first` project; choose another name rather than overwriting an existing one.

Type `3` at the prompt. The program echoes the character, prints its square,
and halts. Enter is not required for this one-character input. Ctrl-C ends a
running program and restores the terminal.

Your project contains:

| File | Purpose |
| --- | --- |
| `program.c` | Your source code |
| `build.sh`, `build.bat` | Compile to `build/program.hex`; retain assembly, listing and trace map under `build/` |
| `run.sh`, `run.bat` | Run the HEX image; accept additional emulator options |
| `input.txt` | A sample keyboard response for automated runs |

`work/` is ignored by Git and the publication audit, so personal projects do
not change the repository's reviewed source inventory. Keep starter copies
exactly two directories below the repository root: `work/first`, `work/game`,
etc. The wrappers locate the tools through `../..`. You can also keep source
elsewhere and invoke the compiler explicitly with its full path.

### Make a change

Open `program.c`. Change the title in `puts("8008 SQUARE TABLE")`, rebuild,
and run again. Compilation is a separate step; `run` executes the last successful
build. If a build fails, fix the error and rebuild before running.

The byte array is:

```c
unsigned char squares[4] = { 0, 1, 4, 9 };
```

Change the final value to `8`, rebuild, and enter `3`: the result becomes `8`.
Restore it to `9` when done. The program converts ASCII `'0'` through `'3'` to
indices 0 through 3 and validates the input before indexing the array.

Now enter `4`: the validation message appears instead of reading beyond the
array. C has no general array-bounds checking here; the program must do this.

SmallC uses `main()` and declarations at the start of a block. It has 16-bit
integers and pointers, and 8-bit characters. There is no `printf`; `puts`,
`putchar`, and `putu` cover the output used here. See the
[SmallC language guide](../smallc/README.md) before using modern C syntax.

### Run with recorded input

From your project directory:

```sh
./run.sh -l:input.txt
./run.sh -p -l:input.txt
```

Windows:

```bat
run.bat -l:input.txt
run.bat -p -l:input.txt
```

These runs do not wait for the keyboard. Edit `input.txt` to try another digit.
`-p` reports clock periods and the estimated runtime at 500 kHz, as well as host
time. It measures the target application, not compilation.

### Find an error

A missing semicolon or an unclosed parenthesis is a compile-time error. Read the
compiler diagnostic, correct `program.c`, and rerun the build script. An existing
C HEX image is preserved when compilation fails, so a subsequent run could still
execute the earlier program.

For a program that loops unexpectedly, use a cycle budget and instruction trace:

```sh
./run.sh -t -i -n:1000000 -l:input.txt
```

Windows:

```bat
run.bat -t -i -n:1000000 -l:input.txt
```

The budget bounds the run; `ntv8008.log` contains the trace. Starter builds now also create `build/program.lst` and `build/program.map`.
The latter is found automatically during `-t -i` tracing, showing resolved labels.
For other generated assembly, obtain an addressed listing by reassembling with A08:

```sh
../../a08/a08 build/program.asm -lbuild/program.lst -obuild/program.hex
```

Windows:

```bat
..\..\a08\a08.exe build\program.asm -lbuild\program.lst -obuild\program.hex
```

A08 listings display addresses as octal page/offset pairs; an address is
`page * 256 + offset` after converting both parts from octal. Compare that
address with the hexadecimal PC in the trace. The listing also retains labels
and source instructions. Source-level stepping and symbolic breakpoints are
not provided. Trace output can be large, so begin with a small budget.
Runtime checks in the C stack helpers
print a message and halt on stack exhaustion; the emulator's exit status alone
does not establish that a program produced the right result.

## Try b8008 BASIC

Return to the repository root. The default `setup.sh` / `setup.bat` builds the
emulator, assembler and b8008 image; no historical BASIC download is needed.
Copy `starters/b8008` to `work/first-basic` using `cp -R` or `xcopy /E /I` as above.
From the copied project, run:

```sh
./run.sh
```

Windows:

```bat
run.bat
```

There is no compile step. `program.bas` contains numbered lines followed by
`RUN`. The run script appends `input.txt` and feeds the combined session into
b8008. The default response is `3`; change it to `2` to print `4`. The source and
input echo, BASIC prompts, and the final prompt are expected. EOF ends emulation.
A `?SYNTAX`, `?BOUNDS`, or other interpreter error is not a successful run even
if the host process exits normally.

To experiment interactively, from the repository root run:

```sh
./ntv8008 a08/b8008.hex
```

Windows:

```bat
ntv8008.exe a08\b8008.hex
```

Enter the numbered lines from `program.bas`, then `RUN`, then your response to
`INPUT`. Use `LIST` to inspect the program. Retype a numbered line to replace it,
or enter just its number to delete it. Save source in your editor: the interpreter
has no host-file SAVE command. `-l:file` supplies all console input from that file;
it does not switch back to the keyboard when the file ends.

`DIM BYTE S(3)` allocates four elements, 0 through 3. BASIC checks their bounds;
ordinary `DIM S(3)` uses two bytes per element instead. Arithmetic uses signed
16-bit integers. See the [b8008 guide](../b8008/README.md) for the dialect.

## Try assembly

After the default setup, copy `starters/assembly` to `work/first-asm`. From the
copied project, use `./build.sh` and `./run.sh`, or `build.bat` and `run.bat`.
Type `3`, or pass `-l:input.txt`. Edit `program.asm` and rebuild to make changes.

This starter includes input validation, array lookup, output and a string-printing
subroutine. Its comments explain the register use and page-crossing adjustments.
It starts at hexadecimal `0040H`, the emulator's default entry address, and ends
with `HLT`. The assembler writes the image to `build/program.hex`.

A08's unmarked numbers are **octal**: `OUT 12` selects decimal output port 10,
and the fourth array entry `011` is decimal 9. `0040H` explicitly selects hex.
The input instruction returns bit 7 as a readiness flag, so `NDI 177` removes
that flag before treating the value as ASCII. See [the assembly examples](../a08/README.md)
for more A08 conventions.

## Try ACK C

On Linux, install the prerequisites listed in the [ACK guide](../ack/README.md)
and run `./setup.sh --ack`. On native Windows, use `setup.bat --ack` in a Visual
Studio 2022 developer command prompt; no WSL is needed. Copy `starters/ack-c` to
`work/first-ack`, then use `./build.sh` / `./run.sh`, or `build.bat` / `run.bat`.

This example uses ANSI `int main(void)`; SmallC uses traditional `main()` syntax.
Both build scripts retain assembly in `build/program.asm`. The resulting HEX
runs on either host. `ACK_TOOLS` can select an alternative compatible host
toolchain; the default setup supplies native tools automatically. See the
[native Windows build guide](../ack/MSVC.md) for the generator sources and build
process.

## Share your program

The starter source and wrappers use BSD-3-Clause; retain the project's license
notice when redistributing copied project code. Preserve any additional notices for
code you bring in. Personal `work/` folders are deliberately excluded from Git.
To contribute an example, move the source and build instructions to a reviewed
location, add a small automated output test, and update the publication inventory
after reviewing the files. Do not force-add downloaded compiler binaries or
historical interpreter images. See [the licensing references](../THIRD_PARTY_NOTICES.md).
