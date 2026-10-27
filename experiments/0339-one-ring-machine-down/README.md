# 0339 — one ring for all compute: the shared build with BC5_DIRECT_COMPUTE_RING=-1, RT off, two 600-s S6N runs

**Question.** Since 2026-10-25 the box went down four times: 10-25 16:05 (RT off, no kernel line); 10-26 00:01:52
(the lean build, RT off, `ring comp_1.2.0 timeout` and never a reset line); 10-26 21:42 (exp 0334's arm D, RT on,
F360's stray store); 10-27 07:28:38 (lean, RT on, a gfxhub TCP fault, vmid 6). The maintainer's priority is the
errors that take the machine down, and his go to the plan (verbatim: "tak cały plan, ale docelowo chcemy RT ON"). Its
second step, this experiment: take the compute ring out of play entirely. A job that hangs on the compute ring is
the case whose reset fails and kills the machine (F332; the 00:01 case); on the GFX ring a hang is reset and the box
survives (exp 0320/0321's recovered hangs). `BC5_DIRECT_COMPUTE_RING=-1` puts every compute buffer on the GFX ring in
submission order (F384; exp 0334's arm D ran it with RT on, the smoothest play the maintainer had). Does the shared
normal build run the S6N route with RT off on one ring, with nothing ever on a compute ring, and at what cost in
flips against today's two rings with RING_DEPS=dcb (exp 0323 RT-off: 36.5/s; exp 0338 N1: 38.0/s; exp 0320/0321
measured one ring at ~36/s)?

**Setup.** `s6n0339.sh` = exp 0338's S6N chain (`s6n0338.sh`, on main) with: the binary the shared normal build
`~/bc5-work/kytyplus-build/src/kyty_emulator` 9382b1e9 (every fix up to exp 0337; the md5 checked), the launcher a copy
of the integrated `play-pkg.sh` b10eac6d (md5 checked) with ONE line changed — `export BC5_DIRECT_COMPUTE_RING=0
BC5_DIRECT_CROSS_RING_WAITS=all` → `COMPUTE_RING=-1` (RING_DEPS=dcb stays) — beside 0338's four private-path edits and
the input-configuration hook (the diff checked at 11 lines, the one-ring line checked by content, the emulator's
environ checked for `BC5_DIRECT_COMPUTE_RING=-1` and `BC5_DIRECT_RING_DEPS=dcb`); no import log. RT off through the
private input configuration (`input-rtoff.cfg`, the RT-off drop line checked by 180 s); the private working directory
(`exp0339/wd`, 0330's layout, its own `_SaveData`, log and learned file); the live saves (88374d489b09ac70 at the
start) snapshot and compared only, never written; exp 0330's memory sampler every 10 s. Added: amdgpu fdinfo of the
emulator at 120 s and at the end (`drm-engine-gfx` / `drm-engine-compute`, ns of GPU time per engine — the ring proof),
the journal's `compute ring:` lines (expected 0: no buffer is ever placed on a compute ring, so exp 0290's refusal has
nothing to refuse), flips per 10 s and the mean. `stream0339.sh` (exp 0338's) follows the kernel log and the journal
from the laptop while the chain's lock line is there. Two runs, R1 and R2, 600 s each, the second 20 s after the first.

**Run.** `./s6n0339.sh 88374d489b09ac70 R1 600; ./s6n0339.sh 88374d489b09ac70 R2 600` on the box (07:59:37 →), under
the lock line `bvh exp 0339 | s6n run`; the kernel and journal streams in `raw/`. Readings: pass on both = the
route runs 2 × 600 s on one ring with no kernel line, no crash, no TIMEOUT, fdinfo gfx only and 0 `compute ring:`
lines; the flips against 36.5–38/s say the cost. A kernel line, a hang or a crash on one ring is the finding of its
own (the GFX ring's reset either recovers or not). Next, on a pass: the maintainer's play on a test shortcut, then
the launchers on his yes. RT on stays the goal: the RT-on classes (F360's stray store, the TCP fault of devcd1
07:28) are for after.

**Result (2026-10-27, 07:59–08:20).** Both runs **pass**: R1 and R2 ran the full 600 s each on the shared normal build
9382b1e9 with every compute buffer on the GFX ring — 0 crash lines, 0 kernel lines (the kernel stream from the laptop
caught no amdgpu line either), 0 TIMEOUT lines, 0 devcoredumps, the live saves 88374d489b09ac70 unchanged, the
private learned file unchanged, the launcher's exit 0. The ring proof: the emulator's amdgpu fdinfo at 120 s and at
600 s lists **`drm-engine-gfx` only** (R1: 1.66 s of GPU time on the title's client at 122 s, 377.6 s at the end; R2
the same picture) — no `drm-engine-compute` entry exists, so no job ever ran on a compute ring; the journal has
**0 `compute ring:` lines** in both runs (exp 0290's refusal had nothing to refuse). RT off held (R1 5747, R2 5492 RT-off
drop lines; `KYTY_BC5_RT=0`, the emulator's environment checked for `BC5_DIRECT_COMPUTE_RING=-1` and `BC5_DIRECT_RING_DEPS=dcb`
by the chain). Memory as on two rings (exp 0330's sampler): MemAvailable after 3 minutes R1 min 725 / median 747 MiB,
R2 716 / 735 MiB; GTT at most 11,881 / 11,889 MiB; swap free at least 7,081 / 7,070 MiB; 11,226 / 11,242 MiB pinned.

| run | flips | span | flips/s | per 10 s median (min–max) |
|---|---|---|---|---|
| R1 | 23033 | 596.1 s | **38.6** | 415 (131–463) |
| R2 | 22005 | 595.7 s | **36.9** | 391 (117–453) |
| exp 0338 N1 (two rings, RING_DEPS=dcb) | | 600 s | 38.0 | 40.3/s median |
| exp 0323 rt-off (two rings, RING_DEPS=dcb) | | | 36.5 | |
| exp 0320/0321 (one ring, their binary) | | | ~36 | |

**Verdict.** One ring costs nothing measurable against today's two rings with the ordering: 38.6 and 36.9 flips/s
against 38.0 (exp 0338 N1) and 36.5 (exp 0323 RT-off) — the spread between the two runs here is as wide as the
difference to either reference. With `COMPUTE_RING=-1` nothing is ever submitted to a compute ring (fdinfo, the
journal), so the compute-ring reset that fails and takes the machine down (F332; the 10-26 00:01 case) cannot occur;
a GFX-ring hang stays a recoverable one. The route ran 2 × 600 s without a kernel line. Next, on the maintainer's
yes: his play on a test shortcut with the one-ring launcher line, then the three launchers (`COMPUTE_RING=0` → `-1`,
one line each) — the RT-on classes (F360's stray store, the 07:28 TCP fault) remain for after, with RT on the goal.
