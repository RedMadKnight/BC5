# 0306 — is the BVH compaction 0x909974400 safe on the S6N route?

**Question.** The water session's exp 0305 (2026-10-25, build 226bcb82, launcher 628b2714, RT on, the lab) showed the
compaction 0x909974400 is the fix for the lab's reflections: nothing skipped → correct reflections, white 0.6 %,
45.9 / 45.6 flips/s (L10, L10b); only 909974400 skipped → white 6.4 %, 48.5 flips/s (L11). So the compaction costs
~3 flips/s there, not half (F304's ~0.7 ms was a different measure), with no fault in three runs; it seems to run at
load or now and then, not every frame. The second title's launchers skip it by default (`BC5_DIRECT_SKIP_PGM`, F304).
Does it run cleanly on the S6N route — where the F332 / F360 hangs live — and what does it cost there?

**Setup.** Exp 0302's chain as it is (`s6n0302.sh`: RT on through a private input configuration and a derived launcher,
a private working directory with its own `_SaveData`, the live saves compared only, the probe and the descriptor check
armed, the stop rules: the first machine-down, a crash, or a live-save change), on **exp 0302's binary 39440597**
(the tree 5bccbb80 + the descriptor check + exp 0290's archive), with **the compaction not skipped**: the derived
launcher gets every `BC5_DIRECT_SKIP_PGM=` assignment turned into `=0` and one `export BC5_DIRECT_SKIP_PGM=0` after the
`bc5-run.env` export loop (the launcher exports its own list after that loop, so an outer value alone would not get
through — as with the input configuration); the emulator's environment must carry `BC5_DIRECT_SKIP_PGM=0` or the run
stops at once. `s6n0306.sh` is `s6n0302.sh` with those edits, its own directory `exp0306/` (wd, cfg, launcher, saves
snapshot), the launcher derived by four anchored edits of `play-pkg.sh` 628b2714 itself (exp 0299's diff no longer
applies: 21 lines, one hunk fails on the lab-fix launcher) — the input-config re-export after the `bc5-run.env` loop,
its own log, the `cd` into the private wd, `KYTY_BC5_SAVEDATA_DIR` into it (7 changed lines, checked) — and three more
extracts per run: the journal's `skip pgm` lines (expected none), its lines naming
`909974400` (proof the compaction's dispatches went through) and its last `flip` lines (the rate, against 0302's
S1/S2 journals). 2 × 600 s; a hang now would also give the descriptor check its event. `stream0306.sh` on the laptop.
The maintainer approved RT-on testing today; the supervisor's GO 13:17 (the box free since 13:17:15), under their
2-hour autonomous mandate.

**Result (2026-10-25, binary 39440597, launcher 628b2714 derived, RT on, compaction ON; `raw/kernel-stream.txt`,
`raw/journal-stream.txt` from the laptop; the box's `exp0306/raw/S*`).** Three false starts first, all stopped by the
script's own checks with nothing run (`raw/s6n0306-attempt1..4.out` on the box): the md5 pin, a quoting slip, and exp
0299's launcher diff no longer applying to 628b2714 — hence the four anchored edits.

| run | start | hang | kernel | verdict |
|---|---|---|---|---|
| S1 | 13:31:32 | 116 s | 13:33:28 `ring comp_1.2.0 timeout … reset succeeded`, then `ring gfx_0.0.0 timeout … reset succeeded`, "device wedged, but no recovery needed"; no page fault | **HANG, recovered** |
| S2 | 13:34:03 | 118 s | 13:35:57 the same two resets, the same words | **HANG, recovered** |

Both hangs are the **F332 class**, the same buffer each time: the timed-out acb (S1 #124870, 4,361 dwords; S2 #119484,
4,333) holds the first family's chain — 0x909939400 count A ×35, **0x909936c00 leaf builder ×63 indirect**, 0x909939700
×35, 0x909939900 refit ×35 indirect, 0x909971300 ×15, 0x90992af00 ×11 — 211 dispatches, 117 indirect, every one marked
`ran`, and **the leaf builder's indirect arguments are floats**: groups 1065528192 × 996016128 × 1063549696, 1063358464
× 1015382016 × 3206794752, … ("the largest grid 1.8e19 groups"), arguments at 0x1271aba0e0, 0x12124b1020, … — the
argument pointer lands in BVH node data, so the CP launched absurd grids (the GPU check leaves these to the CP, exp
0052). The dcb timed out behind it (44 dispatches, 0 indirect). `timeout: fault 0x0`: no page fault, unlike F360. The
compaction ran in both: no `skip pgm` line, the journal's cs-prefix lines name the queue's program 0x0909974400 (8 and
18 such buffers by t 105 s in S1). The descriptor check got its first events, of the other family: 34 tables of
0x11d03a2000 per run, **every slot unchanged** between filter time and the timeout (2.1 s apart), 0x11d03a3400 without a
table as expected — a clean negative control (for a buffer hung for another reason, the tables were intact), no F360
event. Live saves untouched; the IB dumps (`ib-timeout-00124870-acb-4361.bin`, `ib-timeout-00119484-acb-4333.bin`) and
two devcoredump copies (13:33:28, 13:35:57) are on the box.

**Verdict.** The compaction is **not safe on the S6N route today**: with it on, the route hung at ~2 min in both runs,
in the F332 way, both times recovered by the kernel's ring resets; with it skipped, the same binary, launcher, route
and day gave 2 × 600 s clean (exp 0302, 12:27–12:47). Four runs are not statistics, and exp 0290's six F332 hangs at
02:00 came with the compaction skipped — but today's A/B has one switch and nothing else, so the lab's reflections fix
(exp 0305) costs the route's stability for now. The mechanism to chase: with the compaction on, the leaf builder's
DISPATCH_INDIRECT arguments read floats — its argument pointer, or the counter buffer the count pass writes, is wrong
(the compaction rewrites the tree the chain works on); the two acb dumps hold the argument addresses. Flips/s with
the compaction on vs off: to be read from the four journals on the box (pending the supervisor's slot).
