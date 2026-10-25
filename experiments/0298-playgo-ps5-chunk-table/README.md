# 0298 — PlayGo: the host reads the PS5 chunk table, and the second title stops borrowing ASTRO BOT's PlayGo module

**Question.** At one point of the story (the maintainer's slot 4, 2026-10-25 ~09:25) the second title said that more
game data had to be installed, and it would not go on. Why, and does the host answering PlayGo itself fix it?

**Setup.**
- **What the title had been talking to.** `play-pkg.sh` set `SHADPS4_SYSMODULES_PACK_DIR` to
  `~/bc5-data/sysmodules-pack-hle-ampr`. That is a copy of ASTRO BOT's `fakelib/` without `libSceAmpr` (Q14), and
  it still held `libScePlayGo.sprx`. That module's `.sprx` takes precedence over the host's own library (F17, Q14),
  and what it answered for this title had never been traced.
- **What the host would have answered.** KytyPlus (f266548) reads the chunk count from
  `sce_sys/playgo-chunk.dat` in `PlayGo::Open` (`src/loader/systemContent.cpp`). It accepts only the PS4 magic
  `plgo` (0x6f676c70) and takes the count from offset 10. Its fallbacks are `../playgo-chunkdefs.xml` and
  `../Data/chunkmanifest`. Without a count, `libPlayGo.cpp` assumes one chunk, and `PlayGoGetLocus` returns
  `PLAYGO_ERROR_BAD_CHUNK_ID` for every chunk id from 1 up.
- **The title's table** (read-only, through a second bc5-mount of the package at 09:28). `sce_sys/playgo-chunk.dat`
  is 4,992 bytes and starts with `plgx` (0x78676c70), so the host rejected it. Offset 10 holds the u16 value 100,
  and the file has exactly 100 labels, "Chunk #0" to "Chunk #99" (`strings`, 0xdc0–0x1194). The package has
  neither fallback file. `playgo-scenario.json` has one scenario ("Single") and 12 languages.
  TODO(verify): that offset 10 is the chunk count in every PS5 table, not just this title's.
- **The private build** (`build0298.sh`; `edit0298.py`; diffs in `raw/`). Two units were compiled from private
  copies and relinked against the shared normal build's objects (893f8ab4), giving binary af40804e:
  - `systemContent.cpp` also accepts `plgx` and writes one stderr line with what it read;
  - `libPlayGo.cpp` writes the title's PlayGo calls to stderr, the first 32 of each kind, including every
    `GetLocus` answer among them.
- **The test** (`run0298.sh`, `play-pkg-0298.sh`, started over ssh as a user unit on the maintainer's yes).
  `play-pkg-0298.sh` is `play-pkg.sh` with three changes: that binary, its own log, and the pack
  `~/bc5-data/sysmodules-pack-hle-ampr-noplaygo` (the same three other modules, no `libScePlayGo.sprx`). The
  maintainer played from slot 4 with RT off. His saves were copied first (`~/bc5-work/exp0298/saves-before-test-0934`,
  f4e9ef9eab0442c2) and the kernel log was streamed (`raw/kernel-stream.txt`).

**Result.**
- **The trace** (`raw/play-0298-playgo.txt`): `... playgo-chunk.dat: magic 78676c70, 100 chunks`. Then, at start,
  `PlayGoInitialize`, `PlayGoOpen`, `PlayGoGetInstallChunkId`, `PlayGoGetChunkId` and `PlayGoGetLocus` for every
  chunk, all answered "local fast", and later one `PlayGoPrefetch`. The log has 0 `BAD_CHUNK_ID` lines and no
  unresolved import.
- **The play** (09:34–10:01, 27 min): the maintainer reports "Tak, gra przeszła dalej". He made a manual save in
  slot 4 at 10:00:46, an autosave followed at 10:01:03, and he quit at 10:01:36 (exit 0). The kernel stream has
  no amdgpu line (only IPv6 notices). Saves at the end: 8289704a9338a118.
- **Integration** (`int0298.sh`, `raw/int.out`, 10:03–10:04, the maintainer's yes: "Wprowadź poprawkę PlayGo do
  obu wspólnych buildów"):
  - the tree's two files received exactly the tested copies: `systemContent.cpp` a3a786ff → 7121c22c,
    `libPlayGo.cpp` 193cc47a → 8b149c75;
  - normal build 893f8ab4 → e62a97c6, lean build fa8d15f5 → 753889c9, rc 0, both carrying the strings;
  - `play-pkg.sh`, `play-pkg-log.sh` and `play-pkg-quiet.sh` use the pack without PlayGo:
    e6879ede → fde58cda, adde839c → 1efdd8dc, 6f0e07ab → 8e233fae;
  - backups of sources, binaries and launchers are in `~/bc5-work/exp0298/integration/`;
  - the regenerated patch 0001 differs from main's only by the two new files;
  - ASTRO BOT's launcher and its `fakelib/` are unchanged.

**Verdict.** Fixed and integrated. The second title asks PlayGo for all of its 100 chunks at start. Before, those
calls went to ASTRO BOT's module, and the host could not have answered either, since it could not read the PS5
table. Which of the two produced the stop was not traced, because the failing run had no PlayGo log. Now the host
reads `plgx` and answers every chunk as installed, and the title goes past the stop. For the second title this does
Q14's step (1) for PlayGo; `libScePsml.sprx` and the AGC pair are still loaded from the pack.
