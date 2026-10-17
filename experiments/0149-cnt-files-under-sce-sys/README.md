# 0149 — The package's `\x7fCNT` container read: the title's own `param.json` and icons under `sce_sys`

**Question.** Experiment 0148 gave the host a `param.json` made from the content ID. The
package's own `param.json`, icons and PlayGo tables live in the `\x7fCNT` container. Is that
container readable, and can the mount show its files where a console has them
(`/app0/sce_sys`)?

**Setup.**
- BC-250 dev box, 2026-10-17 08:50–09:05, maintainer away (Claude over SSH).
- The container at header `+0x58` (`0x17a28d0000` in the package seen) read with `xxd`/`dd`: the
  PS4 package header's layout, big-endian; 33 entries at `+0x3560`; names in entry `0x200`;
  `param.json` is entry `0x2000` at `+0x3ed0`, 3,286 bytes, plaintext; `icon0.png` (`0x1200`)
  starts with the PNG magic; `playgo-chunk.dat` (`0x1001`) with `plgx`. Every entry of this
  debug image is plaintext (`docs/formats/ps5pkg.md`, section 6a).
- `tools/bc5-mount` (commit bbf97e2): `pkg::cnt` parses the table (bounds-checked, a malformed
  container is reported and skipped, nothing decrypted); `PkgImage` lists the named entries under
  `sce_sys/<name>` when the directory exists in the inner image and the file does not, read
  straight from the package file; the content-ID `param.json` stays as the fallback. Fixture
  writer: `write_pkg_with(spec, out, Some((content_id, files)))` builds a container with
  `cnt::build`. Tests: table round trip and bounds, the overlay (reads at offsets, subdirectory
  entries, the image's own file winning, no directory → skipped), the fallback; `cargo test`
  (59 + 15 + 10), `clippy --all-targets -D warnings`, `fmt --check` pass.
- Box: `~/bc5-work/bc5-main` at bbf97e2, release build 7 s, package remounted.
- Run 578: the play shortcut's settings with the guest log, one ✕ at 80 s, screenshot of the
  slot list, killed there.

**Result.**
- `inspect`: `cnt files: 21 shown under sce_sys` (param.json, icon0/pic0/pic1/pic2 .png and
  .dds, save_data.png, snd0.at9, playgo-chunk/hash-table/ficm/scenario, uds/ and trophy2/
  npbind.dat and .ucp, origin-/target-param.json). The mounted `sce_sys/param.json` has the
  SHA-256 of the raw entry (`164ac4df…`); `titleId` `PPSA03671`, `contentId`
  `UP9000-PPSA03671_00-MARVELSWOLVERINE`, `kernel.flexibleMemorySize` 289,406,976.
- Run 578 (08:55): the host's journal opens with `TITLE_ID, string = PPSA03671`,
  `CONTENT_ID, string = UP9000-…` and `flexible memory size = 0x11400000 (276 MiB)` (before: no
  `param.json`, so KytyPlus's default); the title reaches the slot list, the saves open from
  `_SaveData/PPSA03671`, the three slots show with their dates; killed there (exit 0).

**Verdict.**
- **Passed.** The container is plaintext in this image and the PS4 header's layout; the mount
  shows its 21 files under `sce_sys/`, and the host reads the title's own `param.json`
  (including the flexible memory size) instead of the synthesised one. `/app0/sce_sys/save_data.png`
  now exists for `SaveDataSaveIconByPath`, which the host still ignores (`SaveDataLoadIcon`
  returns no data): the slot list has no icons.
- Not covered: retail images (the body entries are skipped on the signed-byte guess, `TODO(verify)`
  in the format note), and whether a title reads anything else from `sce_sys` (PlayGo tables)
  through the mount.
