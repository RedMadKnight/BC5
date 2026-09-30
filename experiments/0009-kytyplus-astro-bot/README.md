# 0009 — How far does KytyPlus (HLE, no firmware) get with ASTRO BOT on the BC-250?

**Question.** Experiment 0007 showed that Prosper captures describe Prosper, not the console, and the
LLE route (RPCSX + the maintainer's firmware dump) is blocked on that dump. The maintainer asked whether
an HLE host that needs no firmware could replace it. KytyPlus is the only GPL-2.0 candidate
(Kyty is MIT; Prosper has no licence). Does it run ASTRO BOT from a `bc5-mount` mount, and how far?

**Setup.** BC-250 dev box, 2026-09-30 08:40–09:05, `ubuntu` distrobox (experiment 0006), D8 memory
split (15,194 MiB host RAM visible to Linux), KDE Plasma Wayland session on DP-1.
- KytyPlus `github.com/Coder787-source/KytyPlus` commit `f266548` (2026-09-28), GPL-2.0-only. Built
  from source with clang/lld/Ninja, `KYTY_BUILD_LAUNCHER=OFF` (no Qt), emulator target only:
  [`raw/build-kytyplus.sh`](raw/build-kytyplus.sh); dependencies 11 s, configure 102 s, build 466 s,
  `kyty_emulator` 157 MB, `ver = 0.2.2`.
- Game: the maintainer's own `PPSA21567` container (sha256 `435a2527…9af6d`), mounted read-only by
  `bc5-mount`. Mount root: `eboot.bin`, `sce_module/` (`libc.prx`, `libSceNpCppWebApi.prx`),
  `fakelib/` (5 `.sprx`), `sce_sys/`, `data/`, `param.sfx`.
- Runner: [`raw/run-astro-kytyplus.sh`](raw/run-astro-kytyplus.sh) — guest `printf` to file, command
  buffer dump on, shader log on, `spectacle` screenshots at 30/90/150 s, `timeout`.
- Run 2 needed a 6-line patch to KytyPlus (env override of the guest memory size,
  [`raw/kytyplus-guest-memory.patch`](raw/kytyplus-guest-memory.patch), GPL-2.0 like its target),
  [`raw/rebuild-run-kytyplus.sh`](raw/rebuild-run-kytyplus.sh).
- Reference for "how far": Prosper's log from experiment 0007 on the same box and mount.
- Captures under `~/bc5-data/captures/kytyplus-*` (never committed); only counts are reported here.
- No BC5 GPU submission; KytyPlus renders through RADV/Vulkan.

**Result.**

| Run | Guest memory | Outcome |
| --- | --- | --- |
| 1 | KytyPlus default: host RAM − 3.5 GiB, minus 1 GiB flexible (≈ 10.4 GiB direct) | Game runs 30 s, 87,746 lines of its own log (threads, mutexes, savedata), then **its own assert**: `Can't allocate direct memory`, texture pool request 4,608 MB on top of 7,604 MB already held, reservation target 11,366 MB. Emulator exits 65 on the resulting null write. Six stubbed `libkernel` imports had been called before that; resolved with shadPS4's public NID table (GPL-2.0, `src/core/aerolib/aerolib.inl`): `sceKernelMlock`, `rmdir`, `getrusage`, `sceKernelUtimes`, `sceKernelTruncate`, `sceKernelChmod` — all benign. |
| 2 | `KYTY_GUEST_MEMORY_MB=13824` (13.5 GiB, memfd-backed and lazily committed) | No assert. Window opens (title reports `ASTRO BOT, PPSA21564, 01.018.000`, RADV GFX1013, 62 fps, 81 presented frames at 150 s), **black**. 163,500 log lines; after savedata probing and `fiber init: ProductNextSequence` every game thread sits in `PthreadCondWait` from ~10 s until the 240 s timeout. **0 command buffers dumped, 0 shaders**: the game never reached GPU initialisation. Only one unresolved import was called (`sceConvertKeycodeGetImeKeyboardType`). |

Progress markers the game prints itself: Prosper reaches `Resident Load end` within seconds, then
`Armadillo Load end`, `Level has started: ps_logo`, and the title screen. KytyPlus never prints the
first one in either run.

Side finding, from the mount listing: the game ships **its own copies of five Sony runtime libraries**
in `fakelib/` — `libSceAgc.sprx` (95 KB executable segment), `libSceAgcDriver.sprx`, `libSceAmpr.sprx`,
`libScePlayGo.sprx`, `libScePsml.sprx` — as decrypted SELF containers with plaintext code (byte entropy
6.3–6.6 over the text; [`raw/selfinfo.py`](raw/selfinfo.py)). Prosper deliberately never links from
`fakelib/` (its `module_path_policy.cpp`), KytyPlus ignores the directory too, but KytyPlus documents an
LLE loader (`SHADPS4_SYSMODULES_PACK_DIR`, `runtimeLinker.cpp:2062-2076`) whose modules "take
precedence over Kyty's built-in HLE". Not tried here (separate question).

**Verdict.** KytyPlus `f266548` **does not get ASTRO BOT to its first load milestone** on the BC-250:
with the stock memory cap the game aborts on direct-memory exhaustion; with a 13.5 GiB pool it deadlocks
in its kernel-primitive layer before touching the GPU. Prosper, on the same mount, reaches the title
screen. An HLE track built on KytyPlus therefore starts with an unknown amount of `libkernel`/fiber
work before any GPU question can even be asked, and KytyPlus's compatibility list has no title that
gets past "ingame (broken)". This experiment does not decide the route; it prices it. The `fakelib`
finding opens a third option worth its own experiment: an HLE host that LLE-loads the game's own
`libSceAgc.sprx`, so that the DCB encoder is Sony's while the kernel stays HLE.
