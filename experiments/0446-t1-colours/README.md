# 0446 — the first title's wrong colours

**Question.** Since when, and from which cause, does the first title show wrong colours on the shared normal build (the
maintainer, 2026-11-25: the alien should be green,
the sand colour is wrong)?

**Setup.** BC-250, image 45.20261123.1, kernel 7.3.5-ogc2.1, Mesa 26.3.1-2 (unchanged by the 11-25 image update:
`rpm-ostree db diff` lists only the kernel, bpfrag and nvtop). Shared normal `5727b07f` (host-built, bake H) and the
kept container-built `fd8e44e1` (`~/bc5-work/kytyplus-build.container-1124`), same source (tree `8a9ed0cf`).
Runner: a private copy of exp 0439's ab439/start439g (itself exp 0442's ab442r), `~/bc5-work/exp0446/ab446.sh` and
`start446g.sh`: 180 s per arm, a desktop shot every 6 s (spectacle, private: `~/bc5-data/priv/t1-shots/<tag>/`),
from the grid on a fresh working directory with an empty `_SaveData` per run and the window mode from a private
`KYTY_BC5_MENU_DIR` copy (`exp0446/menu-win`, `menu-full`; the maintainer's own per-title `window` file untouched).
Evidence stays private (never in git): shots on the box, copies in the laptop's private folder.

**Result.**

*Since when (no run).* The last good record is 2026-10-13 09:19-09:22 (`~/bc5-work/shots-loop/t129.png`: the alien
green; `t171.png`: the sand bright orange; windowed, "Source build f266548"). No shot of the intro exists between
10-13 and 11-25.

*Runs (boot 97c8eb58, 2026-11-25; all PASS 180 s, 0 kernel lines).*

| Run | Binary | Output | Modules | Alien | Sand | The maintainer at the box |
|---|---|---|---|---|---|---|
| x439sS1 (exp 0439) | host 5727b07f | windowed 1280x720 | BC5's own (3) | grey | brown | wrong colours 22:23 |
| x439sZ1 (exp 0439) | host priv61 | 720p swapchain, full | BC5's own (3) | grey | — | — |
| x446C1 | container fd8e44e1 | full 1920x1080 | BC5's own (3) | green | — | — |
| x446R1 | host 5727b07f | full 1920x1080 | opted out (=0): pack or HLE (3) | green | — | — |
| x446mA1 | host 5727b07f | full 1920x1080 | AGC opted out; driver, PSML BC5's | grey | — | colours broken ~23:02 |
| x446mD1 | host 5727b07f | — | driver opted out only | crashed at 5 s ("Unpatched object", runtimeLinker.cpp:1219) | | |
| x446gW1 | host 5727b07f | windowed 1280x720 | BC5's own (3) | grey (t129-t146) | brown | colours still broken 23:05 |
| x446gV1 | container fd8e44e1 | windowed 1280x720 | BC5's own (3) | partly: lips and hand coloured, body grey (t164, t171) | — | colours broken ~23:08 |
| x446gF1 | host 5727b07f | full 1920x1080 | BC5's own (3) | green (t139) | — | "Dobre kolory" ~23:12 |
| x446gG1 | container fd8e44e1 | full 1920x1080 | BC5's own (3) | green (t124) | bright orange (t165) | "Piasek ok. Dobre kolory" ~23:13-14 |

A first reading (C1 green against S grey: "the host toolchain with BC5's modules") was withdrawn the same evening:
C1 and R1 ran full screen, S windowed. Supporting checks for the withdrawal: one dump program linked against the
host-built (`09567e4a`) and the container-built (`ba25f31c`) backend archive prints identical default-state tables,
ported name tables and all 40 descriptors' name tables (28,909 lines, md5 `5a3195bb`); the re-created modules' code
is the same in both archives apart from relocation names, padding and `find_game_copy`'s filesystem code; the
backend's unit tests pass in four builds (host, container, host `-ftrivial-auto-var-init=pattern`, host
UBSan+ASan; logs `~/bc5-work/exp0446/tb-logs/`).

The magenta UFO thrusters appear in the correct runs too: they are the game's colour. V1's alien, with some
materials coloured and others grey in one frame, reads as textures not yet arrived rather than a wrong colour value.
`kscreen-doctor -o`: sRGB, no ICC profile, no HDR or wide gamut, RGB range automatic, scale 1.

*Repeats on one binary (host 5727b07f, BC5's own modules, fresh save, a per-second I/O sample per run in
`~/bc5-work/exp0446/raw/<tag>-io.txt`, shots every 3 s from t112).* x446r W/F/X/Y (2026-11-26 00:00-00:14) are
void for colour: with nobody at the box all four stayed on the title screen ("press any button") from t49, so every
intro of the evening had passed the title by the maintainer's own presses. x446p W/F/X/Y (00:15-00:28, ✕ pressed by
`KYTY_BC5_INPUT_CMD` at 58 s and 63 s, nothing else): all four correct, the alien green and the sand bright orange,
windowed (W1, X1) and full screen (F1, Y1) alike.

| Set | /var/home free | io pressure full avg10, max | bc5-mount read by 60 s | Colours |
|---|---|---|---|---|
| the evening's wrong runs (S, Z, A1, W1g, V1g) | 14-21 GB (98 % full) | not sampled (16-19 % read by hand during F1g) | — | wrong in all |
| x446r (title only) | 54-78 GB | 27-46 % | 232-1,276 MiB | — |
| x446p | 78 GB | 9.9-17.7 % | 1,183-1,287 MiB | right in all |

*The load pair (2026-11-26 00:30-00:40, host 5727b07f, windowed, fresh save, the same presses; `load446.sh` via the
arm word `X446_LOAD`, from t40).*

| Run | Load from t40 | io pressure full, mean after t40 (max) | Alien | Sand |
|---|---|---|---|---|
| x446lA1 | none | 4.4 % (14.9) | green t118-t139 | bright orange t170 |
| x446lB1 | reader: `cat` of the third title's installed files | 14.3 % (21.1) | grey t127-t148, every scene later | orange at t177, after the reader ended |
| x446lC1 | reader and an fsync'd 1-GiB-chunk writer | 37.3 % (56.4) | not reached: still in the loading tunnel at t150 | — |

**Verdict.** The wrong colours are the first title's own texture streaming arriving late under disk load: with the same
binary, mode, save and input, a background reader alone turns the alien grey (B1) where the run without it is green
(A1). The grey and brown are the game drawing without the textures it has not yet received, not a wrong colour
value; on the evening of 2026-11-25 the load came from a 98 %-full btrfs with a 65-GB archive move and a 43-GB log
compression running. Toolchain and window mode are ruled out. The read path (bc5-mount's per-read latency under
pressure, read-ahead off since F396 for the second title's surplus reads, the 8-GiB block cache) goes to exp 0415's
session as its loading-time task. Earlier reading kept for the record:

Toolchain and window mode are ruled out. Every wrong run fell in the evening's disk state (98 %
full btrfs, a 65-GB archive move and a 43-GB log compression running); every run after the disk was freed was right.
With V1's half-coloured alien this reads as textures arriving late under I/O pressure. Not yet shown causally: next, a
controlled pair on one boot with and without a background reader.

## The second title on exp 0439's private build (2026-11-26 03:00-06:20)

Five arms on the second title from its NAS package (`ser446.sh`, priv61 `f21bfa76` and two halves of it built by
`hb446.sh`: A `fbaa9dfe`, the shared units + priv61's backend archive; A1 `e110936c`, the shared archive with priv61's
`direct.cpp.o` only) hung at 50-51 s in the black load before the title screen, each a hang without a page fault:
x446n2I, x446n4N, x446zZ, x446hbAZ, x446hbA1Z. **All five are void for their purpose.** Each set
`BC5_DIRECT_DMA_SYNC=0` and `BC5_DIRECT_FLAT_APERTURE=0`, which the shared tree sets to 1 as the second title's own
rows (`switch_defaults.hpp` `{BC5_T2, ...}`, F107 and F249); the word list came from the first title's series, where both are
no-ops, and the clean control (x446s1, the shared normal) set neither. They tested the second title without its own two
fixes, which hangs; five boots. Since 06:15 `ser446.sh` leaves both alone and refuses an arm that sets a word the
title's own row sets.

Read on the way, and standing: fw439 changes only the umr watchdog's thread, which starts only with
`BC5_DIRECT_UMR_ON_TIMEOUT`; `bc5-chainwd`, the thread the kernel named, is the shared chain-hold watchdog (section B.2),
the submitter of every held chain; mkmg439 is a census behind `BC5_0439_MG_CENSUS=1`; va439 (`BC5_0439_VA_DEFER`) and
nm439 (`BC5_0439_NO_MERGE`) are opt-in. priv61's archive differs from the shared `09567e4a` only in direct, policy,
full_state and state_stack (37 members compared).

## Stage-1 bake candidate (2026-11-26 08:15-11:00)

Built by `prep446s1.sh` and `b446s1.sh` (exp 0439's kit steps, copied, in its order) from the shared sources (tree diff
`8a9ed0cf`, backend `9956715f`): normal `31711245`, lean `af1c90b5`, archive `b4b2119c`; private, nothing deployed.
In it: the rows universal by measurement for every title (IB_CHAIN, IB_CHAIN_FLAT, AGC_EOP_IDENT, DMA_SYNC_MEC,
DMA_SYNC_LABEL, PREFIX_CHAINS, CHAIN_WRITERS, AT9_DMC, DCC_PRESENT=2), DMA_SYNC and FLAT_APERTURE as every-title rows with
the second title's own rows removed, FLIP_LABEL_PIECES on, fakelib precedence with the pair rule; the descriptor-import
work and EAGER_GPU_WRITE out (its code compiled, off); PASS_CONTEXT_CONTROL compiled in, off, inside the cs439 bundle
(the lean build carries that bundle's diagnostic words: to be replaced by exp 0439's PASS-only step in stage 2).

| Check | Result |
|---|---|
| the first title, candidate normal, image, full screen, fresh save, 180 s (x446c1K1) | PASS, 0 kernel lines; GTT 8,947 MiB at 150 s against 8,814 for the same night's control; the desert scene right |
| the second title, lean pair from the NAS, 600 s each, order S C C S (x446l5-l8), boot 10:15:45 | all four 600 s, 0 kernel lines; mean fps over 100-590 s: shared 25.17 and 24.83, candidate 24.80 and 24.77 (-0.9 %, inside the shared build's own 1.4 % spread); lowest available 1,016 / 1,080 MiB shared, 1,113 / 1,024 candidate |

Not yet: the third title's single start on the candidate (it faults without the EAGER replacement; it costs a boot).

### The trimmed candidate and the 1 % (2026-11-26 afternoon)

The cleaned and trimmed candidate (s3: PASS_CONTEXT_CONTROL alone, the unadopted flip-label arm removed): normal `5a407b8d`,
lean `577e1e06`, archive `073359aa` (members equal to the cleaned `d926ecb8`); with exp 0447's bc5-mount `31d9bbfa` in the
kit. The first title on its lean (x446c5K1): PASS, GTT 8,852 MiB at 150 s, the desert scene right. The second title, one
boot (14:51:51), lean, from the NAS, 600 s each, 100-590 s:

| Arm | Build / words | fps | frames over 33.4 ms | lowest available |
|---|---|---|---|---|
| x446oS | shared lean | 25.13 | 4,562 | 944 MiB |
| x446oC | candidate | 24.62 | 4,666 | 1,090 MiB |
| x446oP | candidate, FLIP_LABEL_PIECES=0 | 24.77 | 4,705 | 1,067 MiB |
| x446oI | candidate, IB_CHAIN=0, IB_CHAIN_FLAT=0 | 24.77 | 4,755 | 1,034 MiB |
| x446oQ | as P | 24.80 | 4,786 | 1,094 MiB |

The candidate is slower than the shared lean in all four pairs of the day (-1.5, -0.2, -1.2, -2.0 %); neither switch
carries it alone (each gives back about 0.6-0.7 %, inside one-run noise). Memory does not differ. Open: a host profile of
one candidate run against one shared run.

### Deployed (2026-11-26 17:11)

Stage 1 is the shared build since 17:11:35 (the maintainer's yes and the top session's word), by `bake446.sh swap`:
normal `36e5233f`, lean `17cfa2a2`, archive `b5ae2c16`, bc5-mount `31d9bbfa`; tree diff `85d0da76`. The kept set (`*.bakeH`:
`5727b07f`, `94a6513c`, `09567e4a`, `3ef38b1d`; sources in the bake's `orig`) is the undo. Check runs from the shared paths,
0 GPU kernel lines: the first title lean 180 s PASS (the desert right, GTT 8,882 MiB at 150 s); the second title lean 600 s
(24.68 fps over 100-590 s, lowest available 1,042 MiB) and normal 180 s. Before the swap, the old shared normal was ended
by the OOM killer on the second title at 112 s (x446pSND) with nothing else running: shmem 11,985 MB pinned, ~1.4 GB of file
cache counted as available (F921's class). Per-thread CPU of the candidate equals the shared build's (4.30 against 4.34
cores): the ~1 % on the second title is on the GPU side.

### The 1 % explained (2026-11-26 17:36 boot, F936)

The second title from the NAS, lean, 600 s each, 100-590 s, one boot, one lock line for the chain (`chain446d.sh`):

| Arm | Build / words | fps | frames over 33.4 ms | GPU load |
|---|---|---|---|---|
| x446qO | bake H's lean (kept `.bakeH`) | 25.31 | 4,409 | 53.5 % |
| x446qD | the deployed stage-1 lean | 24.98 | 4,496 | 53.7 % |
| x446qZ | stage 1 with `BC5_DIRECT_DCC_PRESENT=0` | 25.11 | 4,499 | 53.9 % |
| x446qM | stage 1 with `BC5_DIRECT_DMA_SYNC_MEC=0 BC5_DIRECT_DMA_SYNC_LABEL=0` | 25.10 | 4,470 | 54.1 % |

Each of the two gives back about 0.5 %; together they cover most of the -1.3 %. The host's per-thread CPU is the same
(chain446c), so both are GPU-side: a decompress of the display surface at every flip, and waits in the command streams.

### The shared tree's index (2026-11-26 17:45)

The deployed tree's diff read 85d0da76 because the four headers patch 0003 creates (`src/bc5/{dc,cw,fp,dm}0439.hpp`)
were untracked; `tools/scripts/kytyplus-tree.sh` counts new files intent-to-add. They were intent-added in
`~/src/KytyPlus` (`git add -N`, the index only, no file changed): the tree diff is 5440a94c, as the series gives on a
fresh checkout and as `TREE-DIFF` records. Undo: `git -C ~/src/KytyPlus rm --cached src/bc5/{dc,cw,fp,dm}0439.hpp`.

### Stage 2 (open)

- The decompress at every flip only for a surface actually presented compressed: it exists for the host shell's Vulkan
  copy and blit that brings the frame to the screen.
- The DMA-sync waits narrowed to the cases they guard (a copy another queue reads behind a label or an indirect dispatch).
- Experiment 0439's run-time import rule in place of `BC5_DIRECT_EAGER_GPU_WRITE` and the second title's heap-name lists;
  then the third title on the shared build.
- The job-slot fix (experiment 0442, g442) ported onto this tree (`prep446s1.sh S1_G442=1`), checked on the second title.
- Experiment 0443's backend patch for more than 8 rings, rebased on this tree.
- `BC5_DIRECT_AMM_PRT` for every title (the console drops writes to unbacked sparse pages), the first and third titles
  shown unchanged; `GPU_CHECK_PRODUCT` and `SHADOW_LABELS` for every title as guards, recorded as open defects (F403,
  F360) with their catch counts.
- The launcher's stale `unset BC5_DIRECT_FLIP_DEFER` dropped (the proposed file is beside the kit on the box).
