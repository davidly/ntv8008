# Test your own program

Save console input in a text file and a known-good answer in another. Build
before testing; a failed compiler invocation can leave the last successful HEX.
Use both a target cycle budget and a host timeout. An exit code of zero alone
cannot prove success: BASIC and compiler runtimes can print an error and halt.

The reusable [check_output.py](../tools/check_output.py) runs an emulator command,
checks its exit status, normalizes CRLF, and compares output. Run from the repo
root after default setup. Create `work/hello.txt` containing `HELLO, 8008!` and a
trailing newline, then:

```sh
python3 tools/check_output.py --expect work/hello.txt -- ./ntv8008 -n:100000 a08/hello.hex
```

Windows uses `py -3` and `ntv8008.exe`. Pass `-l:path/to/input.txt` within the
emulator command for recorded responses. `--timeout 10` changes the default
30-second host limit. Omit `-p` for a plain test, or inspect its separate stderr
report when measuring performance. Exact comparison is the default.

## A game with several outcomes

Build `examples/adventure-c` using its build script. Its recorded input takes the
key and escapes:

```sh
python3 tools/check_output.py --contains --expect examples/adventure-c/win.txt -- ./ntv8008 -n:20000000 -l:examples/adventure-c/input.txt examples/adventure-c/build/program.hex
```

A fragment check tolerates prompts and room descriptions. It is weaker than exact
comparison: also test quitting without winning, opening without a key, invalid
commands, and a boundary move. [tests/practical.py](../tests/practical.py) shows
these checks for both C and BASIC. Run `python3 tests/practical.py --compile`
after full setup to rebuild all practical examples and verify comparison and
optimization programs too. Both main test scripts include these tests; use
`test.sh --compile` or `test.bat --compile` for compiler-dependent cases.

## BASIC source echo and errors

A BASIC session contains numbered source, `RUN`, and responses to `INPUT`.
Use LF line endings for these session files, as in the supplied examples. Its
console echoes that source, so searching the entire transcript for a success
message can match a PRINT statement that never ran. Check output only after the
last `>RUN` marker. Create a combined session first (the BASIC example's run
script does this under its `build/` directory), then:

```sh
python3 tools/check_output.py --after ">RUN" --contains --expect examples/adventure-basic/win.txt --reject "?SYNTAX" --reject "?BOUNDS" --reject "?DIV" -- ./ntv8008 -n:20000000 -l:examples/adventure-basic/build/session.bas a08/b8008.hex
```

Choose rejection strings for the errors your interpreter/runtime can emit;
`--reject` is repeatable and has no implicit list. Exact expected execution
output is stronger when it is practical. EOF terminates input sessions, so a
missing answer can end the process before the expected result; the output check
catches that. Keep separate input fixtures for each branch you want to test.
