# 0370 — A safe instrument that names the program in F403's stuck dispatch (design)

**Date.** 2026-10-28 (23:0x–23:5x). **Branch.** `exp/0300-rt-dispatch-sync`. **Box.** None: a design written from the
repo, the kernel's sources and umr's documentation. Not built, not run, nothing on the box or in the launchers changed.
Numbers F496–F499. The maintainer's "Tak, zleć projekt" (through the top session) is the mandate; every step on the box
needs his yes and the top session's GO.

**Question.** F403's class (a GFX ring timeout with no fault, waves alive, the CP in the host's indirect-dispatch
check, F490) ends the box about once in 25 S6N RT-on runs (F476, F495). The devcoredump names no program (F490/F491).
An instrument must read the waves before the kernel's reset, must not halt waves on a stall that is not a hang (F229,
F208), must need no process start at the event (F112), and must be safe through hours of the maintainer's RT-on play:
the worst case a lost dump, never a reset of the instrument's making. What is it, what confirms a hang, what does the
maintainer install, and how is it tested?

## Known before this experiment (with sources)

- **K1 — the kernel's clock.** `lockup_timeout` is 2000 ms for every ring on 7.2.9-ogc3.1 (the parameter is empty and
  its description reads "default: 2000"; exp 0259 `raw/kernel-params.txt`). The clock is drm_sched's `work_tdr`:
  `drm_sched_job_begin` adds the job to the pending list and calls `drm_sched_start_timeout`, which is
  `mod_delayed_work(sched->timeout_wq, &sched->work_tdr, sched->timeout)` while the pending list is not empty
  (Linux v6.17 `drivers/gpu/drm/scheduler/sched_main.c`, `drm_sched_start_timeout` / `drm_sched_job_begin`, read
  2026-10-28; TODO(verify) the same lines in the box's 7.2.9 tree). So the deadline is re-armed at every push and at
  every completion: the reset comes 2 s after the ring last moved. Measured on the box: 2.0 s (exp 0058 run 267, the
  kernel at 10810.003 s, the host at 10810.05 s; exp 0160 run 784: fault 1270.37 s, timeout 1272.38 s; F316: 2.05 s).
  Of the box's ring resets 880 succeeded and 2 were followed by a dead box (`bc5-gpu-watch.sh`'s header); a failed
  reset goes to MODE1 about 4 s later (F420) and the machine-down follows.
- **K2 — what the two existing dump paths did, and why they fail the brief.** (a) The host's
  `BC5_DIRECT_UMR_ON_TIMEOUT` (exp 0058) spawns `distrobox-host-exec sudo bc5-gpu-hang-dump` at 0.9 s of a completion
  wait: a process start, the container hop, umr's own start, then 27 single-register umr starts before `halt_waves`
  (the top session's reading of the script); its dumps landed after the reset and showed an idle CP (F112). (b) The
  root watcher `bc5-gpu-hang-watch` (exp 0058; the maintainer's script, not in the repo) polls `amdgpu_fence_info`
  every 50 ms and runs `umr -O halt_waves -wa` at a 0.6-s stall for 10 minutes: it caught F113's waves, but ordinary
  play has 0.6-s stalls that recover (a 1.0-s GPU-busy frame at t 143 s of run 821 played on), and every halt at such
  a stall was followed ~1 s later by a ring timeout and reset (run 831: seven dumps, seven timeouts; 46 dumps on
  2026-10-19, also in the maintainer's sessions, F229, exp 0175). umr's own documentation: the halt "halts or resumes
  jobs currently being processed", is not deterministic, and waves stay halted if umr is killed
  (umr.readthedocs.io, "Halting Waves", "Wave Status", read 2026-10-28).
- **K3 — what root can read without halting.** amdgpu's debugfs (Linux master
  `drivers/gpu/drm/amd/amdgpu/amdgpu_debugfs.c`, read 2026-10-28): `amdgpu_fence_info` prints per ring "Last signaled
  fence", "Last emitted" (and for GFX the trailing, preempted and reset fences; `amdgpu_fence.c`
  `amdgpu_debugfs_fence_info_show`); `amdgpu_regs` reads MMIO by byte offset (bits 0–21 the offset, bit 62 a GRBM
  bank select, `RREG32` in a loop); `amdgpu_wave` reads one wave slot's registers (`*pos` bits 7–14 SE, 15–22 SH,
  23–30 CU, 31–36 wave, 37–44 SIMD) through `adev->gfx.funcs->read_wave_data` under `grbm_idx_mutex`, a version dword
  then the SQ_WAVE registers (STATUS, PC, EXEC, HW_ID, …; TODO(verify) the order in `gfx_v10_0.c`
  `gfx_v10_0_read_wave_data`); `amdgpu_gpr` reads a wave's SGPRs/VGPRs. None of these halt anything; each read is a
  `pread` on an open file, no process. umr reads waves "live" through these files and says SGPRs/VGPRs are guaranteed
  only for halted waves; STATUS, PC, EXEC and HW_ID are read either way ("Wave Status"). umr's one caveat: do not read
  waves often while GFX power gating is on. The box's runtime PM is off ("Runtime PM not available" at boot).
- **K4 — what names the program.** F113 named 0x11d049aa00 from the waves' PCs alone (PC inside the program's text,
  matched to the title's dumped programs); the timeout probe's dispatch list (F491) and the dispatch journal give the
  program bases of the stuck IB, so a PC maps to a program offline without any GPR. HW_ID gives the queue, pipe and
  VMID of the wave (TODO(verify) the gfx10 field layout, Mesa's register JSON).
- **K5 — how often a healthy run stalls (the false-positive census so far, from the laptop's whole-session logs).**
  Host-side fence waits (`timing:` lines, `BC5_DIRECT_TIMING`); jobs within 0.1 s merged into one stall:

  | session (RT on) | length | stalls ≥ 0.3 s | ≥ 0.6 s | ≥ 0.9 s | ≥ 1.2 s | ≥ 1.5 s | ≥ 2 s | kernel line |
  |---|---|---|---|---|---|---|---|---|
  | exp 0218 play (compaction skipped) | 15.5 min | 19 | 9 | 3 | 1 (2.27 s) | 1 | 1 | none |
  | exp 0210 play (reflections on) | 15 min | 7 | 3 | 2 | 2 | 2 (1.58, 4.23 s) | 1 | none |
  | exp 0192 session 0808 (until its hang) | 8 min | 7 | 4 | 3 | 3 | 2 | 2 (the hang) | one timeout |

  Per hour of play, then: ~25–35 stalls over 0.6 s, ~8–12 over 0.9 s, ~4–8 over 1.2 s, ~4 over 1.5 s. These are upper
  bounds for the GPU: the host's wait includes holds on the host side (F415's 22-s hold with no kernel line, 0210's
  4.23-s wait with no kernel line), which a kernel-side fence watch never sees. The event the instrument is for comes
  about once in 4 h of S6N (F476). The S6N soak of exp 0368 (16 runs) has no `timing:` lines; its census needs a box
  read (asked for below).

## Design

**D1 — the instrument: a resident root sampler, `bc5-gpu-stall-sampler`.** One process, started by systemd at boot
beside `bc5-gpu-watch` (the same shape: a root service, `Restart=always`), running whether or not a game runs, with
nothing in the launchers, no switch in the host, no per-game start. It keeps open file descriptors on
`amdgpu_fence_info`, `amdgpu_regs`, `amdgpu_wave` and `/dev/kmsg`, and at the event it only `pread`s and writes: no
fork, no umr, no container hop (the brief's rule 1; K2's failure). Written in Python 3 on the host (Bazzite ships
it; `os.pread`, `mlockall` through ctypes), ~300 lines, with a `--test` mode that replays a recorded fence trace and
touches no device.

**D2 — the trigger (the stall clock).** Every 25 ms the sampler reads `amdgpu_fence_info` and, per ring (gfx_0.0.0 and
every comp_1.*), notes the time of the last change of either "Last emitted" or "Last signaled". A ring is *stalled*
when emitted ≠ signaled and nothing changed for 0.5 s. The stall clock is "time since the last change": the kernel's
own clock (K1) within one poll, so the sampler knows when the reset will come without reading the kernel's timer.

**D3 — the order of reads at a stall (nothing halts).** Samples at clock 0.5, 0.8, 1.1, 1.4 and 1.7 s, each:
1. fence_info again (the stall still stands, or it resolved: then stop, see D4);
2. the CP and GRBM registers through `amdgpu_regs`: GRBM_STATUS, GRBM_STATUS2, GRBM_STATUS_SE0/SE1, CP_STAT,
   CP_STALLED_STAT1/2/3, CP_BUSY_STAT, CP_CPF_STATUS, CP_RB_RPTR, CP_IB1_BASE_LO/HI, CP_IB1_BUFSZ, CP_PFP_INSTR_PNTR,
   CP_ME_INSTR_PNTR, CP_PFP_HEADER_DUMP, CP_ME_HEADER_DUMP, SPI_CSQ_WF_ACTIVE_STATUS (byte offsets from the kernel's
   public `asic_reg/gc/gc_10_1_0_offset.h`, checked once at install against umr's register listing; TODO(verify)
   the umr option that lists them) — a few hundred `pread`s, under a millisecond;
3. the wave scan through `amdgpu_wave`: every SE/SH/CU/SIMD/wave slot of the chip (2 SE × 2 SH × 10 CU × 2 SIMD ×
   20 slots = 1,600 reads on the unlocked 40 CU; CLAUDE.md's layout; TODO(verify) the slot count per SIMD on gfx1013),
   keeping the slots whose STATUS has VALID; raw dwords plus a decoded line (slot, STATUS, PC, EXEC, HW_ID, TRAPSTS)
   — ~1,600 `pread`s of ~100 bytes, tens of milliseconds (to be measured in T1);
4. no GPRs: they need the halt (K3) and the PC names the program (K4).
Each sample is stamped with the stall clock and goes to a RAM buffer. Nothing touches the GPU beyond the register and
SQ-index reads that the devcoredump and umr make anyway.

**D4 — the confirmation rule, and the files.** The hang is confirmed by the kernel, not by us:
- the sampler follows `/dev/kmsg`; on `amdgpu … ring … timeout` it writes the buffered samples of that ring's stall as
  an event (`~/bc5-data/captures/gpu-stall/event-<date>-<time>/`: `fence.txt`, `regs-N.txt`, `waves-N.bin`,
  `waves-N.txt`, `kmsg.txt`, `summary.txt`), `fsync`s and `chown`s them to the maintainer's user (mode 600);
- a stall clock past 1.9 s writes the same before the line, so that a reset which takes the machine down (K1: MODE1
  ~4 s after the timeout) still leaves the dump on disk — the write is ~200 KB and takes milliseconds;
- a stall that resolves (signaled advances) before 1.9 s discards its samples and appends one line to
  `stalls.log` (ring, duration, wave count and the top PCs at 0.5 s): the kernel-side false-stall census, free, in
  every run and every play (K5's missing column).
`summary.txt` says per sample how many waves, the distinct PCs and their programs' bases (matched offline against
the host journal's dispatch/timeout-probe lists), and whether the PCs stood still across the five samples (F249's
halted shape), moved inside one program (a loop: arm A) or drained (progress: not a stuck shader). The sampler
writes nothing to `/dev/kmsg` (F420's feedback lesson) and never runs the existing `bc5-gpu-hang-watch` or
`bc5-gpu-hang-dump`; those stay unarmed while it is installed.

**D5 — the risks, each with its worst case.**
- *Wave reads while GFX is power-gated* (umr's caveat): the sampler reads waves only while a job is pending on a ring
  (GFX is up); worst case a failed read, logged, no retry inside the stall.
- *A slot read while its wave retires*: a garbage line for that slot; VALID filters most; five samples show the rest.
- *The sampler itself stalling* (exp 0203 O2: a 1-s stall of every thread under memory pressure): `mlockall`,
  `Nice=-10`, `MemoryMin=32M`, `OOMScoreAdjust=-900`; worst case a missed sample, never a reset.
- *CPU cost in play*: 40 small `pread`s a second idle; at a stall five bursts of ~50 ms on one core, during a frame
  the GPU is not finishing anyway. To be measured against the soak's 35.8 flips/s (F494) in T2.
- *A second hang while the event is being written*: one event at a time; the next stall's samples go to the buffer
  and are written after the first `fsync`.
- *What it cannot do*: SGPRs/VGPRs (halt only), and the program's name beyond its base (offline matching as F113).

**D6 — why not the alternatives.**
- *Raise `amdgpu.lockup_timeout`* (the maintainer's kernel command line, a reboot): exp 0160 run 785 ran 10 s and a
  repeated fault then took the box down ("the 2-s timeouts were the safe path"); every real hang would freeze the
  title 10 s instead of 2; the machine-down class would get a longer window, not a shorter one. The sampler needs
  no extra time: five samples fit in the 2 s. Not recommended.
- *umr at the event*: a process start and umr's own initialisation at the moment the kernel is already counting
  (K2a); the register reads alone cost 27 starts today. Out.
- *Halt after confirmation*: confirmation is the kernel's timeout, after which the halt has nothing left to read
  (the reset follows); before it, every halt at a false stall was a reset (F229). The design never halts. A later arm
  may halt at clock ≥ 1.9 s only — when the reset is certain anyway — to add SGPRs; it needs its own yes.
- *A fixed threshold with a halt* (0.6, 0.9, 1.2 or 1.5 s): K5 shows 4–35 false stalls an hour at every one of them,
  so any halting design costs resets in play; a non-halting one costs nothing at any threshold.

**D7 — what the maintainer runs (sudo), and what is new on the box.**
```bash
sudo bash tools/scripts/gpu-stall-sampler/install.sh
```
installs `/usr/local/sbin/bc5-gpu-stall-sampler` (root-owned, 755), the unit `bc5-gpu-stall-sampler.service`
(root; `After=systemd-modules-load.service`; `Restart=always`), creates `~/bc5-data/captures/gpu-stall/` owned by
his user, enables and starts the unit, and prints its first `stalls.log` line. Undo: `sudo bash
tools/scripts/gpu-stall-sampler/undo.sh` (stop, disable, remove the unit and the script; the captures stay). No
sudoers line: the output is his user's, and `systemctl status` needs no root. No change to `bc5-gpu-watch`,
`bc5-gpu-hang-watch`, `bc5-gpu-hang-dump`, the launchers or the shared builds.

**D8 — the test plan (box time).**
- *T0, laptop, no box:* the script, its `--test` replay against a recorded fence trace, the wave decoder against a
  known dump layout. 0 box.
- *T1, the box idle, read-only (GO + the maintainer's install):* the sampler's five registers against `umr -r` of
  the same names; a wave scan at idle (expect 0 valid slots) and its duration; a forced scan while ASTRO BOT's
  start screen runs (valid slots > 0, the PCs inside its programs). ~10 min.
- *T2, under healthy load:* one S6N RT-on 600-s run with the sampler in census mode plus a forced full sample every
  30 s regardless of stalls (20 samples): flips/s within the soak's 34.7–36.5, no kernel line, every `stalls.log`
  line sane. Any cost or any kernel line → stop, reduce to registers only, back to the design. ~15 min.
- *T3, the soak:* repeated S6N RT-on 600-s runs with the sampler resident until the first event or the slot's end, as
  exp 0368's loop; the census gives the kernel-side false-stall rates (the missing K5 column) and the event, if it
  comes, the program. 3 h exclusive.
- *T4, the maintainer's play:* nothing to do; the sampler is on. His call when.
Box time asked for: ~3.5 h (T1–T3) under the usual lock, plus one read-only GO now: the 16 soak journals' frame
profiles (`GPU busy` per frame ≥ 600 ms) for a host-side census of tonight's S6N runs before T2.

## Result (design findings)

- **F496 — the kernel's 2-s clock is re-armed at every push and every completion, so it expires 2 s after the ring
  last moved; a user-side watcher that times "since the last change of emitted or signaled" in `amdgpu_fence_info`
  runs the same clock within one poll and needs no kernel change.** (K1: `sched_main.c` v6.17; exp 0259's
  `lockup_timeout` 2000; the 2.0 s measured in exps 0058, 0160 and F316.)
- **F497 — healthy RT-on play stalls past 0.6 s about 25–35 times an hour, past 1.2 s 4–8 times, past 1.5 s ~4 times
  (host-side upper bounds from three whole sessions, K5); the F403 event comes about once in 4 h. Any design that
  halts at a threshold therefore manufactures resets in play; only a non-halting read is safe at any threshold.**
- **F498 — root can read, without halting and without a process start, everything that names the program: the
  per-ring fences, the CP/GRBM registers by MMIO offset, and every wave slot's STATUS/PC/EXEC/HW_ID through
  `amdgpu_wave`; only SGPRs/VGPRs need the halt (K3).** The PC named F113's program (K4).
- **F499 — the design: a resident root sampler that runs the kernel's clock on the fences, reads registers and waves
  five times between 0.5 and 1.7 s of a stall without halting, keeps the samples in RAM, and writes them only when the
  kernel's own timeout line comes or the clock passes 1.9 s; stalls that resolve leave one census line.** Worst case a
  lost or inconsistent dump; the instrument cannot cause a reset. Installed once by the maintainer (D7), tested in
  ~3.5 h of box time (D8), then simply resident for his play.

**Verdict.** Recommended: build the sampler (D1–D4) as `tools/scripts/gpu-stall-sampler/` with its installer and
undo, test T0 offline, then T1–T3 on GO, then leave it resident. Not recommended: a longer `lockup_timeout`, umr at
the event, any halt before the kernel's own timeout. Open until T3: the kernel-side false-stall rate (the census),
the wave scan's duration on 40 CU, and whether the five non-halted samples read consistently (T2's forced samples
answer it on healthy frames).
