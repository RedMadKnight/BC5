# 0323 — integrating the ring ordering: the refusal into the shared archive, `BC5_DIRECT_RING_DEPS=dcb` and the compaction in the launchers

**Question.** Exps 0320–0322 found the mechanism of the second title's F332-class hang with RT on (the BVH build split
between compute ring 0 and the GFX ring with nothing ordering them — exp 0290's refusal puts the leaf builders and the
title's own dispatching dcbs on GFX while the count passes run on compute) and the fix that works: every GFX-ring job
starts after the compute rings' last jobs (`BC5_DIRECT_RING_DEPS=dcb`, exp 0129's kernel CS dependency; 0321: 2 × 600 s
clean, 0322's dcb-aware form the same at the same cost). The maintainer's word on 2026-10-25: "ok - zastosuj zmiany -
pozniej będziemy myslec nad wydajnoscia - najwazniejsze ze dziala". Every RT test today ran on exp 0290's private archive
825ae1d1; the shared builds link 549892e8, without the refusal. Does the integrated setup — the refusal in the shared
archive, both shared emulators relinked, the three launchers with the dcb ordering and the compaction on — run the S6N
route clean with RT on, what does RT-off play cost, and does the lean build start?

**Setup (parts 1–2, the top session runs them).** The backend change is on the branch (commit e08bf84: exp 0290's
`patch_0290.diff` applied to `backend/` — `kMecIndirectCheckVerified = false` keeps every `DISPATCH_INDIRECT` off the
compute ring, the policy test updated). `int0323.sh`: guards (lock empty, no emulator, `~/src/bc5` clean and carrying the
refusal, the archive 549892e8 and the binaries d02f4696 / 759cd455 as expected), backups into
`~/bc5-work/exp0323/integration/`, `cmake --build ~/bc5-work/backend-ubuntu` (the archive in place, as
`tools/scripts/bc5-build.sh` builds it), the backend tests built and run in `exp0323/backend-tests` (a failure stops
before the relink), `ninja kyty_emulator` in both shared build directories, the refusal's string checked in the new
normal binary, the new md5s in `integration/new-md5.txt` and `new-md5.env`; then `launchers0323.pl` on the three
launchers: `export BC5_DIRECT_RING_DEPS=dcb` after the `BC5_DIRECT_COMPUTE_RING=0` line, and the default skip list
without 909744000's compaction (`play-pkg.sh`: `${BC5_DIRECT_SKIP_PGM:-0}`; `-log` / `-quiet`:
`${…:-11d049aa00,11d04a6000}`); anchors required once, backups with md5s, a refusal if the ring line exists. Undo: the
`.before-0323` copies.

**Setup (part 3, this session on the GO).** `ver0323.sh <mode> [runs] [secs]` on the shared **normal** build through a
copy of the new `play-pkg.sh` (its md5 from `new-md5.env`), exp 0306's private wd and route saves, the live saves
compared only, the launcher's own defaults (no `BC5_DIRECT_SKIP_PGM` from the chain; the environ must show
`BC5_DIRECT_RING_DEPS=dcb`, `BC5_DIRECT_COMPUTE_RING=0`, `BC5_DIRECT_SKIP_PGM=0`): (a) `rt-on 2 600` — the S6N route,
the 180-s marker = the refusal's `stays on the GFX ring` journal line (the shared build has no 0302 descriptor check);
(b) `rt-off 1 600` — the private input configuration with `RayTracing.PPSA03671=off`, flips per 10-s window against F382's
40.9–42.0/s (the ordering applies with RT off too; if it costs more than ~3 % it gets gated on RT); (c) `lean 1 120` —
the lean build (`BC5_LEAN=1`: no journal), a short start, kernel log only. fdinfo at ~121 s and at the end in every mode.

**Readings.** (a) clean 2 × 600 s → the integration holds for RT-on play (F385's fix in the shared builds); (b) flips
within ~3 % of F382 → the ordering stays unconditional, else the launchers gate `BC5_DIRECT_RING_DEPS` on
`KYTY_BC5_RT`; (c) the lean build starts and runs 120 s → done. A hang in (a) → the private-archive runs and the shared
archive differ in something else (the objects, d02f4696, or the launcher defaults) — the journal says which.

**Result — parts 1–2 (the top session, 2026-10-25 19:46:58–19:48:21; `raw/int.out`).** `int0323.sh` ran cleanly: the
shared archive 549892e8 → 825ae1d1 — byte-identical to exp 0290's private archive, since main's `backend/` had no other
source change since 1853b14; the backend tests 55/55 in `exp0323/backend-tests`; the shared normal build d02f4696 →
5dd77a82 and the lean 759cd455 → 47e4a31a, the refusal's string in both; `play-pkg.sh` → 7d14f7e5, `play-pkg-log.sh` →
e1b361a1, `play-pkg-quiet.sh` → 2b23073d (the `.before-0323` copies in `~/bc5-work/exp0323/integration/`).

**Result — part 3, rt-on (this session; `ver0323.sh rt-on 2 600 1 bb14b6dd35b644ff`, 19:49:39–20:10:06; the shared
normal build 5dd77a82 through a copy of `play-pkg.sh` 7d14f7e5 with the four 0306 edits only; both environs
`KYTY_BC5_RT=1 BC5_DIRECT_SKIP_PGM=0 BC5_DIRECT_RING_DEPS=dcb BC5_DIRECT_COMPUTE_RING=0` — the launcher's own defaults;
`raw/S1-*`, `raw/S2-*`, `raw/journal-stream-rt-on.txt.gz`, `raw/kernel-stream-rt-on.txt.gz`).** PASS, 2 of 2: S1 and S2
each 600 s with 0 crash, 0 kernel amdgpu and 0 TIMEOUT lines, 0 devcoredumps, live saves bb14b6dd35b644ff unchanged. The
integrated setup behaves as the private runs did: the refusal counter at 179,201 / 177,153 buffers kept on the GFX ring,
fdinfo at 121 s with both engines (compute 31.1 / 32.3 s, gfx 52.2 / 56.1 s), flips 20,876 / 20,561 in 600 s, mean 35.6 /
35.0/s, windows 50–90 s 294/304/299/248 and 295/327/344/273 (0321 dcb-wide: 315/326/296/251; 0302 two rings without the
compaction: 484/470/485/397, 40.6/s). With exps 0320–0322 that is 9 × 600 s clean today with an ordering against 11 of 11
hangs at 112–118 s without one.

**Result — part 3, rt-off (`ver0323.sh rt-off 1 600 3 bb14b6dd35b644ff`, 20:10:59–20:21:15; `RayTracing.PPSA03671=off`
in the private configuration and `KYTY_BC5_RT=0`; the rest as rt-on; `raw/S3-*`, `raw/journal-stream-rt-off.txt.gz`,
`raw/kernel-stream-rt-off.txt.gz`).** PASS at 600 s, no kernel line, live saves unchanged. Flips 21,332 in 600 s, mean
36.5/s, windows 50–90 s 299/302/302/257 — against F382's RT-off reference of 40.9–42.0/s that is **about 11–13 % lower**,
above the ~3 % the supervisor set for leaving the ordering unconditional. Two things changed for RT-off play at once in
this integration, and the run cannot split them: the refusal itself is new in the shared build and still moves 185,345
buffers to the GFX ring in 600 s with RT off (the `DISPATCH_INDIRECT` buffers of the title's other compute work; fdinfo
at 121 s: compute 34.6 s, gfx 50.8 s — the compute ring stays busy), and `RING_DEPS=dcb` then makes every GFX job wait
for it. Attribution needs one more run: RT off on the same integrated build with `BC5_DIRECT_RING_DEPS` unset (1 × 600 s)
— if the flips return to F382's, the cost is the ordering and the launchers gate it on `KYTY_BC5_RT`; if not, it is the
refusal's, and the gate buys nothing (then the refusal's own scope — the RT build family only — is the lever).

**Result — part 3, lean (`ver0323.sh lean 1 120 4 bb14b6dd35b644ff`, 20:22:13–20:24:23; the shared lean build 47e4a31a,
`BC5_LEAN=1`, no journal; `raw/S4-*`, `raw/kernel-stream-lean.txt.gz`).** PASS: the lean build starts and runs 120 s on
the route's load with the ordering on (environ `BC5_LEAN=1 KYTY_BC5_RT=1 BC5_DIRECT_RING_DEPS=dcb
BC5_DIRECT_COMPUTE_RING=0`), no kernel line, both engines in fdinfo at 117 s (compute 21.6 s, gfx 43.1 s), live saves
unchanged; the chain released the lock at 20:24:23 (left empty).

**Verdict.** The integration holds: the refusal in the shared archive (= exp 0290's), both shared emulators relinked, the
three launchers with `BC5_DIRECT_RING_DEPS=dcb` and the compaction on with RT — the S6N route with RT on ran 2 × 600 s
clean on the shared normal build (9 × 600 s today with an ordering, 11/11 hangs without), RT off 600 s clean, the lean
build starts. The open point is the RT-off cost: 36.5 flips/s against F382's 40.9–42.0, ~11–13 % — above the gate
threshold, but the run cannot attribute it between the refusal (new in the shared build, still moving ~185 k buffers to
GFX with RT off) and the ordering; one more 600-s run with RT off and `BC5_DIRECT_RING_DEPS` unset on this build settles
it and decides whether the launchers gate the ordering on `KYTY_BC5_RT` (a new ask). The journals of the four runs
(`~/bc5-data/captures/play-20261025-1949`, `-1959`, `-2010`, ~190–200 MB each; the lean run has none) are private data,
not trimmed.
