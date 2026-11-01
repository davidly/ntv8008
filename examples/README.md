# Practical programs

`adventure-c` (SmallC) and `adventure-basic` (b8008) implement the same small
escape game: go south to the cellar, take a key, go north twice, then open the
exit. Arrays describe room connections; scalar variables hold room and inventory.
Input dispatch is a deliberately small command parser. C accepts digit keys
immediately; BASIC accepts an integer followed by Enter. Commands are printed
at startup. You can also quit with 0. Movement against a boundary stays put.

From the repository root, run setup with `--smallc` for C or default setup for
BASIC. Then `cd examples/adventure-c`, run `./build.sh` and `./run.sh`, or
`build.bat` and `run.bat`. BASIC needs only its run script. C builds retain the
assembly, listing and automatic symbol map under `build/`.

For a recorded winning game, C accepts `./run.sh -l:input.txt`. BASIC's run script
already combines its source with `input.txt`. Edit that file to try other routes.
Both accept `-p` or `-t -i`; use `-n:20000000` for a bounded run. Copy either folder
to `work/mygame` to experiment without changing reviewed sources.

Try adding a fourth room, a second object, or a move counter. Update every room
array together and keep the room index within its bounds. Source and wrappers
are project contributions under BSD-3-Clause.

See also [equivalent programs in seven languages](../docs/languages.md) and
[measured C optimization examples](../docs/optimization.md).
