# 0340 — the RT-on machine-down classes: devcd1 (10-27 07:28) and devcd8 (10-26 21:43) read, and the next RT-on arms

**Question.** With one ring the base (exp 0339, F412), what took the machine down in the two RT-on cases of the last
two days — the lean build's 07:28:38 (a gfxhub TCP read permission fault on vmid 6, then the machine down) and exp
0334 arm D's 21:43 (F360's stray store, then the machine down) — and how do they relate to F399/F403 (the runaway
dispatch), F405 (an SQC fetch at 0) and F360 (a stray store over a sync label)? Read-only on the box (the guard
`pgrep '^kyty_emulator'` + an empty BOX-LOCK before every command; grep/sed on the dumps and the kernel journal; only
register values and short extracts left the box, never the ring or IB contents). Then a design for the next RT-on
arms, offline, with the supervisor's two candidates: a product limit in the CP's argument check (F403), and a guard
against F360's stray store.

**Sources.** `~/bc5-data/captures/devcoredump/20261027-072841-devcd1.txt` and `20261026-214349-devcd8.txt` (cited by
path; `raw/registers.txt` holds the values read); `journalctl -k -b -3` (boot f3ef3a42, 21:46:12 → 07:28:38) and
`-b -5` (boot 98f7b5f9, 00:03:16 → 21:42:50) on the box; exp 0334's readings on main (`raw/r0-registers.txt`,
`raw/arm-d/r0-registers-devcd8.txt`, `raw/lean-1835/r0-registers-devcd7.txt`); the PM4 opcodes of
`tools/bc5-agc/regdb/pm4-opcodes.tsv`; bc5-ops `STATE.md` (the 07:28 context); `backend/include/bc5/policy.hpp:110`
and `bc5/indirect_check.hpp` (the CP check as it is), `backend/src/policy.cpp:414–574` (the label bookkeeping of
the filter). The faulting address's place in the title's map could not be read: the lean build keeps no journal,
and the normal build's journal (exp 0339 R1, `BC5_DIRECT_JOURNAL=min`) prints guest and host addresses, never the
GPU virtual addresses the faults are in (the IBs at 0x10xx00000000, the earlier faults at 0xa8256950000 and
0xb20407c00000, this one at 0xd5200001000 are amdgpu VAs of the backend's BOs, `direct.cpp:313`).

**Reading.**

| | devcd1, 10-27 07:28:41 | devcd8, 10-26 21:43:49 |
|---|---|---|
| build / setting | shared lean 379a92b8, RT on (his `input.cfg`), the normal two-ring launcher | exp 0332's acb1cfd7, RT on, one ring (arm D) |
| timed-out ring, thread | gfx_0.0.0, Render Thread | gfx_0.0.0, bc5-ring |
| CP microcode position | PFP 0xea1, ME 0x77a — **F403's** | PFP 0xea1, ME 0x77a — the same positions |
| PFP history | ACQUIRE_MEM, EVENT_WRITE, two COND_WRITE, COND_EXEC, PFP_SYNC_ME, WRITE_DATA, **DISPATCH_INDIRECT** — the host's GFX-form indirect dispatch with its CP argument check, packet for packet F403's | 40 empty slots, two ACQUIRE_MEM, **WAIT_REG_MEM** — a label wait (F406) |
| shaders | SE0 and SE1 busy (GRBM_STATUS_SE 0x08000006; F403's 0x0a000016/36) — waves alive | every SE idle (0x06) |
| host IB | 0x101100000000, 10584 dw, fetched to within 568 dw of the end (95 %) | 0x100a00000000, 8920 dw (F406's 8,913-dw dcb), fetched 21 % |
| fault record | **fresh**: page 0xd5200001000, status 0x601031 (TCP, a read, PERMISSION_FAULTS 0x3, MORE_FAULTS), vmid 6 pasid 36 — the kernel's 07:28:38.818750 line is the journal's last | **stale**: address 0, status 0x6012b1 = the 18:35:44 SQC-instruction fault of F405 in the same boot; no fault line after 18:37, no kernel line between 21:39 and the journal's end 21:42:50 |
| MEC | instruction pointers 0x447 / 0x491 in both (the same idle positions), the compute queues' registers alike | the same |
| then | the dump saved at 07:28:41; the box dead by then (the journal ends at the fault line); a 23-s boot without a shutdown at 07:29:14 | the dump saved at 21:43:49, a minute after the journal's last line; the box dead; the next boot 21:44:22 |

So devcd1 is **F403's class on the lean build with RT on and two rings**: the same CP position and the same eight
packets as the three freezes of 10-26 — a runaway `DISPATCH_INDIRECT` whose waves stay alive — but this time the
waves also **read through an unmapped page** (a TCP fault, 85 suppressed, on the title's vmid), and the machine went
down instead of a ring reset. F403's three were fault-free and were reset; the runaway grid here walked out of its
buffers. devcd8 is **F360's class** (as F406 read it): the CP waiting on a label nobody will ever write to the
expected value, the shaders idle, no fault of its own — the fault field of the dump is the driver's last recorded
fault (as F403 found for devcd5), not this event's. Two different classes, both on the GFX ring, both ending the same
way: a GFX-ring timeout after which the box does not come back. The four recovered F399 resets and exp 0290's six
were GFX-ring timeouts too; what makes a reset fail is not in the dumps (they are written before the reset), and the
journal never holds the reset's lines because the box dies with them unwritten. That is the first thing to fix (arm 0
below).

Against the other classes: F405 (the SQC fetch at 0, lean, RT off, 18:35) recovered; devcd5 (the compute ring,
00:01) is the class one ring removes (F412); F403's runaway dispatch is what devcd1 is, now with a fault; F360's
stray store is what devcd8 is. With one ring, the remaining RT-on killers are these two, and they are two different
mechanisms: a bad **argument triple** (stale or garbage group counts the CP check lets through: 818 × 820 × 819 passed
2^20/2^10/2^10) and a bad **store address** (a V#/T# from the 0x11d03a… family's resource table, F363/F365).

**Design — the next RT-on arms (one ring the base; every one needs the maintainer's yes, and 0, 1 and 2 a build).**

- **Arm 0 — keep the kernel's last lines.** Both machine-downs lost the reset path's lines (the journal stops at or
  before the dump). `netconsole` to the laptop (a kernel module parameter, no build of ours: the kernel log goes out
  over UDP as it is written) or `pstore`/`ramoops` keeps `amdgpu_gpu_recover`'s lines — `reset failed`, `MODE1`, a
  `soft reset`, a `Fatal error` — through the death. Without them every RT-on run stays a coin toss between a reset and
  a machine-down for reasons nobody reads. The maintainer's watchdog (the supervisor's) sits beside this, not instead.
- **Arm 1 — the product limit** (F403's class, devcd1). The CP compares one 32-bit value per `COND_WRITE` and cannot
  multiply, so the product is bounded as a staircase: the three per-dimension limits stay (2^20, 2^10, 2^10), and two
  more rules refuse **y > 1 with x > 2^16** and **z > 1 with x > 2^16** — expressible as `COND_WRITE` (y > 1 → a second
  flag word) followed by a `COND_EXEC` over a `COND_WRITE` (x > 2^16 → the dispatch flag 0), the same machinery
  `indirect_check.hpp` already inserts; a dispatch of 818 × 820 × 819 is refused, a 1-D builder of 2^20 groups is not.
  The limit's shape needs the legitimate triples first: a journal line per distinct (x, y, z) class at filter time
  (stale values make a histogram, not a verdict) in one RT-on play on the normal build — a build of its own, read-only
  for the GPU. Then the staircase, `BC5_DIRECT_GPU_CHECK_PRODUCT=1`, a counter of refusals in the journal, and his
  play: F403's state should not come back; a refused dispatch that the tree needed shows as the lab's or the lake's
  reflections (F370's white, or missing).
- **Arm 2 — the label guard** (F360's class, devcd8). The title's end-of-pipe syncs are `WRITE_DATA` 0,
  `RELEASE_MEM` EOP 1, `WAIT_REG_MEM` == 1 on a label in the title's memory, where a stray store can land. The guard:
  the filter already finds every label a dcb writes and waits on (`policy.cpp:414–574`); for each such triple it adds
  a second `RELEASE_MEM` of the same event to a **host-owned shadow** word (the job's scratch, 0x10xx00000000, far from
  the title's buffers) and rewrites the `WAIT_REG_MEM` to wait on the shadow. The title's label is still written
  (the CPU polls it); the CP's wait no longer depends on memory a shader can reach by a garbage pointer. Cost: one
  `RELEASE_MEM` per sync (the dcb's ~32 per frame); a stray store can still hit the shadow page, but with ~1 GiB of
  the title's mappings against one page the odds move by three orders of magnitude. Verification: his RT-on play on
  one ring; the timeout probe's "unmet wait" reading names a shadow label if the class survives.
- **Arm 3 — the writer** (F360's cause). At a timeout the probe can scan the acb in flight for the dispatches whose
  descriptor tables (F363: 16-byte V#/T# slots at user SGPRs 12–13) cover the corrupted label's address, naming the
  program and the slot; with one ring the acb and the dcb are in one queue, so the writer is in the same submission.
  Read-only for the GPU, a build for the probe.
- **Arm 4 — the fault's address** (devcd1's class, the other half). A journal line per BO at creation (`direct.cpp:313`:
  GPU VA, size, the guest range it pins) would place 0xd5200001000 and the earlier 0xa8256950000 / 0xb20407c00000
  in the title's map — which buffer the runaway or the garbage pointer reached. Cheap, journal only.

Order: 0 first (it costs no run), then 1 and 2 together in one build (they touch different packets: the check's
inserts and the sync triples), his play with RT on, one ring; 3 and 4 ride along in the same build as journal lines.

**Verdict.** Read-only, no run: devcd1 = F403's runaway indirect dispatch (RT on, two rings, the lean build), now with
a TCP read fault that the three resets of 10-26 did not have; devcd8 = F360's stray store over a sync label (RT on,
one ring), its fault record stale. Both are GFX-ring timeouts whose reset killed the box, and the reset's own lines
are lost every time. One ring already removes the compute-ring class (F412); the two RT-on classes need the product
staircase in the CP check and the shadow labels, after the kernel's last lines are made to survive. Nothing was built
or run; the box was only read with the guard, and it stayed free.
