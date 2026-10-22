# 0192 — Playing with the traversal fix: an instruction-fetch hang at 0x80'0000005000, long stalls, blocky reflections

**Question.** Experiment 0191 ran the second title's reflection traversals and the BVH compaction through two idle
300-s night runs without a stall once their stack pushes address the host's apertures (`BC5_DIRECT_FLAT_APERTURE=1`,
F249, F250). What happens in real play with no program skipped, and what are the hangs the maintainer saw?

**Setup.**
- BC-250 dev box, 2026-10-22 07:44–09:42; the maintainer played; host build of 2026-10-21 23:46:14 (patch 0001 with
  patch_0190), kernel 7.2.9-ogc3.1.
- Desktop shortcuts (`~/Pulpit`): "BC5 emulator (refleksy)" = `play-any.sh` with
  `BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_SKIP_PGM=1` (a dummy: nothing skipped); "BC5 emulator (refleksy + dziennik)"
  adds `BC5_DIRECT_DISPATCH_JOURNAL=1`. The TF ring is on (`play-pkg.sh` default), the timeout probe too.
- Sessions: 0744 (no trigger), 0808 (`catch-play.sh` armed: one `umr -O halt_waves -wa` dump when the journal stands
  still 0.7 s, synced at once), 0933 (`catch-fault.sh` armed: a dump only when such a stall comes with a new GPU page
  fault in the kernel log). The triggers ran only for these dedicated sessions (F229) and were stopped after them.
- Raw: `raw/session-0744.txt`, `raw/session-0808.txt`, `raw/catch-1-and-kernel.txt`, `raw/0808-timeout-buffer.txt`,
  `raw/session-0933.txt`. The wave dumps and journals stay on the box (`~/bc5-work/exp0192/`,
  `~/bc5-data/captures/play-20261022-*`); the session 0744 pad recording is `~/bc5-work/exp0190/route-record-0744.txt`.

**Result.**
- **Session 0744 (machine down).** The fix reached all six variants from t ≈ 40 s. At t ≈ 287.5 s a 22,826-dword
  graphics buffer and an 865-dword compute buffer timed out together (2 s); the kernel log ends with "Dumping IP State …
  device coredump file has been created" (07:49:43) and the machine froze. The next boot names the reset "a parity error
  occurred" (as exp 0160's run 785). No fault line, probe dump or wave dump survived; earlier in the session the host
  saw no fence wait over 0.3 s and no flip gap over 0.26 s (the maintainer's "first hang" left no trace).
- **Session 0808, catch at 08:14 (a slow frame, not a hang).** The trigger fired during a 1.22-s GPU job (a
  10,279-dword graphics buffer; 0.38 and 0.53-s jobs just before): 761 waves, none in `FATAL_HALT`, no memory
  violation (`TRAPSTS` 0x40000000), all in 0x11d03aa000, a straight-line screen-space image filter. The game went on.
- **Session 0808, the hang at 08:16:15 (emulator, not the machine).** The kernel logged GPU page faults from
  **SQC (inst)** — the shader instruction fetch — at **0x0000800000005000** (two printed, 87 suppressed), then
  `ring gfx_0.0.0 timeout`, "reset succeeded". The host's timeout probe dumped the timed-out buffer: a one-off
  328-dword graphics buffer (the only one of that size in the session, absent from runs F2/B0) with three
  `DISPATCH_DIRECT`s of 2×1×1 groups that set only user data; the program comes from the ring's earlier state (the
  probe knows none). Their user-data layout is exactly that of 0x11d039cd00 in exp 0160's dispatch journals — a
  28-instruction program without calls — so the dispatches started from a wrong program address: `COMPUTE_PGM_HI` 0x80
  (the title's tag, F109/F110) with `COMPUTE_PGM_LO` 0x50. The buffer's two `LOAD_*_REG_INDEX` already have table
  address 0 and count 0 in the title's own buffer (the "unmapped 2" are those, harmless). The host's default prefix
  (`BC5_DIRECT_PREFIX_ALL` = draws) goes in front of buffers that draw only, so this compute-only buffer ran on whatever
  program registers the ring was left with. Why they held 0x50 is open (TODO(verify): the full-state tracker's
  `COMPUTE_PGM_LO/HI` and other processes' work on the ring, F204).
- After that fault the host learned and saved an alias "0x80 0x0 0x6000000" (`~/bc5-work/direct-aliases-pkg.txt`):
  it would map guest 0x0–0x6000000 under the tag and let such calls run whatever lies there. Removed again (backup
  `~/bc5-work/exp0192/direct-aliases-pkg.txt.0816`).
- **Session 0933 (dispatch journal on): no GPU hang.** 4.5 min, 10.0 million dispatch lines, a 3.6-GB journal, no
  fence timeout, no new GPU fault (catch-4 never fired). The maintainer's "freezes" were three stalls of 7.9, 8.5 and
  12.3 s in which the game thread was outside the host (7.85–12.27 s) and the GPU idle (20–50 ms of work); the audio
  thread logged every second throughout, and the journal itself has no line in the 12.3-s gap. Sessions without the
  dispatch journal had none (longest flip gap 0.26 s in 0744, 1.24 s in 0808 before its hang), so the journal's own
  writes are the likely cause (TODO(verify): the journal blocking on writeback).
- **The "blocky reflections" are not the reflections.** The maintainer saw pixelated or square blocks on the water
  (session 0933). Screenshots taken remotely (`snap.sh`, spectacle; kept on the box in `~/bc5-work/exp0192/shots/`)
  at the same lake: with the fix (session 0956, 09:58:41/47, 09:59:03) the water is a patchwork of flat and detailed
  regions whose edges follow the water plane's perspective (world-space rectangles of several sizes, not screen
  tiles); with the normal launcher — the traversals and the compaction skipped, the TF ring on (session 1002,
  10:05:01/06; its environment checked: `BC5_DIRECT_SKIP_PGM=11d049aa00,11d04a6000,909974400,11d04bb900`,
  `BC5_DIRECT_GC_TF_RING=1`, no `flat aperture` line) — the same patchwork, if anything more pronounced. So it comes
  from something the default setup also runs. With the TF ring off as well (session 1011, 10:13:39/45, shortcut
  "BC5 emulator (bez TF)": `BC5_DIRECT_GC_TF_RING=0` and the normal skips, checked in the process environment) the
  patchwork is still there: it is older than F248 and has nothing to do with the tessellation ring or the reflections.
  Its shape — rectangles of several sizes fixed to the water surface, detailed or flat — suggests per-tile data that
  some tiles never receive (streamed or virtual texture pages, or a per-tile water simulation); not examined here.

**Verdict.**
- **The traversal fix does not make the reflections usable yet.** In play the GPU still hangs, though now for a
  different reason: once in 0808 a compute-only buffer of the reflection pipeline ran with a wrong program address
  (instruction fetch at 0x80'0000005000), and once in 0744 a hang took the machine down (cause lost); some frames take
  0.4–1.2 s of GPU time. The patchy water the maintainer took for broken reflections is there with the reflections
  off and with the TF ring off as well — a separate, older defect of the water.
- The skips stay in the launchers; the "refleksy" shortcuts are for diagnosis only, and the dispatch-journal one
  should not be used for play (multi-second stalls).
- Next, one at a time: the program registers a compute-only graphics buffer inherits (the host's state tracking and
  prefix for buffers without draws); the slow frames; the look of the reflections themselves. The patchy water is a
  task of its own.
