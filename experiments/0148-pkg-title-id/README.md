# 0148 — The second title's saves under its title ID: `sce_sys/param.json` synthesised by `bc5-mount`

**Question.** The host puts the second title's saves under `_SaveData/UNKNOWN` because it finds
no `TITLE_ID` (F189). Where is the package's `param.json`, and can the mount give the host one?

**Setup.**
- BC-250 dev box, 2026-10-17 08:30–, maintainer away (Claude over SSH).
- Cause: KytyPlus reads `<app0>/sce_sys/param.json` (`emulator.cpp`, `Psf::OpenJson`:
  `titleId` → `TITLE_ID`, `contentId` → `CONTENT_ID`). The package's inner image has
  `sce_sys/{keystone, pfs-version.dat, lem_notification.dat, about/, trophy2/, uds/}` and no
  `param.json`: the title's own lives in the `\x7fCNT` container (`docs/formats/ps5pkg.md`,
  section 6), which `bc5-mount` reads only for the 36-byte content ID
  (`UP9000-PPSA03671_00-MARVELSWOLVERINE`, `bc5-mount inspect`).
- Change (`tools/bc5-mount`, commit dd299f7): when the inner image has no `sce_sys/param.json`,
  has a `sce_sys` directory and the content ID is readable, `PkgImage` adds one synthesised entry
  (`contentId`, `titleId` = bytes 7–16 of the content ID, and a note) to the tree: one more index,
  listed in `sce_sys`, found case-insensitively, read from memory. `inspect` prints the title ID.
  The fixture writer gained an optional minimal `\x7fCNT` (`write_pkg_with`) for the end-to-end
  test; `cargo test`, `cargo clippy --all-targets -- -D warnings` and `cargo fmt --check` pass
  (57 + 14 + 10 tests).
- On the box: `~/bc5-work/bc5-main` pulled to dd299f7, `cargo build --release -p bc5-mount` in
  the `ubuntu` distrobox (`CARGO_TARGET_DIR=~/bc5-work/bc5-tools-ubuntu`); the previous binary
  kept as `release/bc5-mount.before-0148`. Saves moved from `_SaveData/UNKNOWN` to
  `_SaveData/PPSA03671` (copy of the old state in `_SaveData.bak-0145`).
- Run 577: the play shortcut's settings with the guest log, one ✕ at 80 s, screenshot of the
  slot list, then the emulator killed.

**Result.**
- The build on the box took 6 s; `bc5-mount inspect` prints `title id: PPSA03671
  (sce_sys/param.json synthesised from the content id)`. The remounted package shows
  `sce_sys/param.json` (221 bytes, read-only) with the two IDs and the note.
- Run 577 (08:42): the host's first journal line is `TITLE_ID, string = PPSA03671` (before:
  `TITLE_ID missing`); the slot list's search and mounts open
  `_SaveData/PPSA03671/i38-slot1-settings-autosave/settings.save` and the other slots from the
  moved directory; the slot list shows the three saves with their dates. Killed at the slot list.
- The `_SaveData-pkg-play` directory the shortcut names in `KYTY_BC5_SAVEDATA_DIR` stays empty
  (F190: that variable covers `sce_sdmemory/memory.dat` only).

**Verdict.**
- **Passed.** A mounted package now carries a `sce_sys/param.json` with its title ID, and the
  host keys the second title's saves on `PPSA03671`. Any host that reads `param.json` from
  `/app0` gets the same two fields; the rest of the real `param.json` (`localizedParameters`,
  `kernel.flexibleMemorySize`, …) stays unread until the `\x7fCNT` container is parsed.
- Follow-up: per-title settings may now use `RenderScale.PPSA03671` (none set; the title runs
  unscaled, F-series 0115).
