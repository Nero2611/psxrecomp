# PSXRecomp (Frontschweine fork)

This is a fork of [RetroPortingToolKit/psxrecomp](https://github.com/RetroPortingToolKit/psxrecomp),
a general-purpose static recompiler for the PlayStation 1: it translates a PS1
game's MIPS code to C and links it against a hardware-accurate runtime, so the
game runs as a native PC program instead of under an emulator.

The fork exists to serve
[FrontschweineRecomp](https://github.com/Nero2611/FrontschweineRecomp), a
recompilation of *Hogs of War* (German release *Frontschweine*, SLES-02767),
which pins this repository as a submodule. For the framework itself, its
architecture and how to bring up a game, see the upstream project and the
[`docs/`](docs/) folder.

## Branch

`frontschweine` is upstream commit
[`44a45d3c`](https://github.com/RetroPortingToolKit/psxrecomp/commit/44a45d3c3d25eae026887b3dc27e90b9591e2f7b)
plus the changes below. None of them is specific to one game, and every
enhancement stays off unless a game or the player enables it.

## Changes

### CPU overclock (opt-in mod)

Built-in package `psx.enhancement.cpu-overclock`. Scales the emulated CPU clock
(for example to 200 %) while devices, timers and VBlank keep their stock
timing, which removes slowdowns the original hardware had in busy scenes.

The overclock engages at game handoff; the BIOS boots at stock speed. BIOS
boot code times CD-ROM handshakes with busy-wait loop counts (OpenBIOS polls
30000 times for the Init acknowledge), which a faster CPU exhausted before
the stock-timed drive answered, so boot never finished above about 325 %.

### CD audio smoothing (opt-in mod)

Built-in package `psx.enhancement.cd-audio-smoothing`. When the CD/XA audio
FIFO runs dry, playback fades out and resumes after a short prebuffer with a
fade-in, instead of clicking.

### Mod plugin services

Trusted game plugins (`runtime/include/mod_plugins.h`) get:

- **Function takeover.** A hook at a generated function entry can complete
  the guest call itself with `psx_mod_function_return()`, which returns to
  `$ra` and skips the generated body, or replace a guest poll loop with
  `psx_mod_function_wait()`: device time advances to the next event the
  guest could observe, its interrupts are delivered, and the function is
  entered again to re-check. Interpreted entries still only observe.
- **Disc and memory.** `psx_mod_find_disc_file()` locates a file on the
  mounted disc, `psx_mod_write_guest_bytes()` stores a block with the
  RAM-side effects of a to-RAM CD DMA (written code is invalidated),
  `psx_mod_exe_dir()` names the program directory and
  `psx_mod_guest_cycles()` exposes the device timeline.
- **Picture area.** `psx_mod_set_display_layout_pal()` keeps the PAL or NTSC
  active region whatever the video timing, so a PAL game switched to 60 Hz
  keeps all of its lines instead of an NTSC television's 240.

`ISOReader::FindFile` also walks nested directories now, so disc paths such
as `BRIEF\GERMAN\LEVEL1.BIN` resolve.

### Ahead-of-time overlays

- The `opcode_nibble_lz_files` method decodes runtime-loaded code that a game
  keeps in files compressed with a byte LZ whose operations are chosen by the
  high bits of each control byte. It reads the file from the player's disc,
  requires the stream to consume the file exactly and the decoded image to
  match the profile's SHA-256, and fails extraction instead of guessing.
- Setup packages may omit the profile's static overlay shard: it is
  generated from the player's own disc and must never ship.

### Toolchain download

The pinned Tiny C Compiler archive now lists mirrors besides
`download.savannah.gnu.org`; each gets two attempts, and a SHA-256 mismatch
moves on to the next one, so the archive is still verified against the pin.

### Overlay cache

- `[[overlays]]` entries in `game.toml` are part of the overlay cache
  namespace, so adding an entry rebuilds the shards compiled without it.
- In-range forward declarations get the same `dllexport` as their
  definitions; declared entries that split a function no longer fail to
  compile under clang.
- The overlay candidate capacity is raised from 32768 to 65536.
- Rescans after an autocompile run no longer stall the emulation thread.
  With several thousand cached DLLs every run caused a ~0.45 s freeze; path
  lookups now compare a hash first, parsed manifests are kept, `.resident`
  sidecars are found with one directory walk, and runs that built nothing
  skip the rescan.

### Widescreen: `hud43` mode

For titles that draw their HUD in the frontmost ordering-table ranks, the HUD
can be kept at its exact 4:3 position and proportions while the 3D world is
shown wide. Configured per game in `game.toml`:

```toml
[widescreen]
hud43_rank_band = 25            # frontmost ranks that hold the fixed HUD
hud43_keep = [                  # world-anchored overlays in those ranks
  { op = "0x64", height = 11 },
]
```

Polygons whose corners all come straight from the GTE already carry the
projection squash and are not squashed twice.

## License

Unchanged from upstream: [PolyForm Noncommercial License 1.0.0](LICENSE),
Copyright © 2026 Matthew Stanley. Commercial licensing inquiries go to him at
<https://1379.tech>.

Third-party components vendored into the runtime keep their own terms; see
[`THIRD_PARTY_ATTRIBUTION.md`](THIRD_PARTY_ATTRIBUTION.md) and
[`runtime/licenses/`](runtime/licenses). The bundled OpenBIOS image is
MIT-licensed, see [`bios/OpenBIOS.LICENSE`](bios/OpenBIOS.LICENSE).

Retail PS1 BIOS images and game disc images remain copyrighted by their
respective owners and are not distributed. Game data is always supplied by
the player from their own copy.
