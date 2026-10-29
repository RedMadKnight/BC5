# 0374 — The stall sampler, stage T1: installed on the box, and a GPU hang after a forced wave scan

**Date.** T1 ran 2026-10-29 06:26–06:35 (the top session, with the maintainer's install); this write-up is from the
box's records, read 07:46–08:00 the same morning. **Branch.** `exp/0374-stall-sampler-t1` (from exp 0373's branch,
with main merged in). **Box.** Reads only, under `top exp 0374 | reads only` BOX-LOCK lines (no emulator running, lock
empty before each). No GPU work, nothing installed, nothing changed on the box. Numbers F517–F522 (F500–F504 are exp
0372's, F505–F509 exp 0371's, F510–F516 exp 0373's).

**Question.** Exp 0373's T1 checklist: does `bc5-gpu-stall-sampler` (exp 0370's design, built in exp 0373) install
and read the right registers on the box, and what do its idle and load scans cost and show? T1 was stopped by a GPU
hang two seconds after the second forced wave scan under ASTRO BOT. So also: what do the records show about that hang,
did the sampler cause it, and which sampler mode is safe to run next?

## Setup

- **Tool under test:** `tools/scripts/gpu-stall-sampler/` at exp 0373's commit 723e83e (`VERSION = "0373-t0"`;
  the box's copy `~/bc5-work/gpu-stall-sampler/bc5-gpu-stall-sampler` hashes `dd6376af74390054`, md5, first 16).
  Kernel 7.2.9-ogc3.1.fc44 (the install check's header and the devcoredump's `kernel:` line).
- **T1 as run (from BOX-QUEUE, the journal and the capture directory):**
  - 06:26 the non-root part on the box host: `--test` 10/10, unit tests 29/29 (8 skipped), `install.sh --dry-run`.
  - 06:31:17 the maintainer's `sudo bash ~/bc5-work/gpu-stall-sampler/install.sh`. The service started 06:31:21.
  - 06:33:04 ASTRO BOT through `play-astro.sh`, on the shared normal build (play log header: "emulator 2026-10-28
    16:03:45"; that this is F465's 1000ad2a is TODO(verify)). `BC5_GC_MODE=direct`, `BC5_DIRECT_RINGS=1`: every job
    on `gfx_0.0.0`.
  - Two forced samples (`force` file, request text "once"): 06:33:08 and 06:34:21.
  - 06:34:23 the GFX ring timeout, a failed ring reset, and `bc5-gpu-watch`'s SysRq crash. The box rebooted at 06:34:55.
  - The service came up again at 06:35:07. The maintainer's `undo.sh` stopped and removed it at 07:42:56.
- **Here:**
  - `extract0374.sh`: the read-only extraction, run once from the laptop
    (`ssh bc250 bash -s < extract0374.sh > raw/extract.txt`). It stops if an emulator runs or the lock is someone
    else's. From the devcoredumps it prints only the header fields, named registers and the gfx queue's two header
    histories, never their command buffers.
  - `decode0374.py`: field and opcode names from the repo's vendored tables (`tools/bc5-agc/regdb/`: Mesa
    `gfx10.json`, `pm4-opcodes.tsv`) → `raw/decode.txt`.
  - The proposed sampler change: the diff in this commit to `tools/scripts/gpu-stall-sampler/`, not deployed
    (below).
- **Box records cited (private, by path):**
  - `~/bc5-data/captures/gpu-stall/`: `stalls.log`, `install-check.txt`, `forced-20261029-063308/`,
    `forced-20261029-063421/`, `event-20261029-063423-gfx_0.0.0/`;
  - `~/bc5-data/captures/devcoredump/20261029-063423-devcd1.txt` (this hang) and `20261028-233612-devcd1.txt` (F506,
    for comparison);
  - `~/bc5-data/captures/play-20261029-0633/gc/direct.log` (the host's submit lines);
  - the efi-pstore records of 06:35 (`~/bc5-data/captures/pstore/`, 19 parts);
  - the journal of boot −1 (`ca3a824a…`, 2026-10-28 23:36:42 – 2026-10-29 06:34:23).

## Result

### Install check (checklist step 4): passed

From `install-check.txt` (06:31:18):
- **Debugfs:** `/sys/kernel/debug/dri/0000:01:00.0`, named "amdgpu dev=0000:01:00.0 unique=0000:01:00.0". The
  numbered links are 1 and 128. All four files are present: fence_info, regs, wave, gfxoff. This is F515's PCI-named
  layout.
- **Offsets:** all 35 rows `addr ok (dword)` against `umr -lr gfx1013`, so the GC base and the 10.1.0 offsets hold on
  GC 10.1.3 (F511's TODO). The idle values were `same` for the 31 registers read three ways (sampler, `umr -r`,
  sampler). 4 were not read: the two header histories, which by design umr never reads, and the two banked
  shader-array configs.
- **Header histories:** `CP_PFP_HEADER_DUMP period 8: yes` and `CP_ME_HEADER_DUMP period 8: yes` (reads 0–7 ==
  reads 8–15). F512's period is confirmed on the box.
- **Start line** (`stalls.log`): `gfxoff=0` at idle, `mlockall=True`, `slots=2x2x5x4x20`, `header_dump_reads=8`.
- **Kernel log:** no WARNING from the reads in boot −1. The journal's kernel log has only the two boot-time display
  WARNs at 23:36:48 (`dal_irq_service_ack`/`_set`), the source of the pstore's `[W]` taint. There are 0 lines naming
  `read_wave` or `amdgpu_debugfs`.
- **Not checked from the records:** SELinux AVC lines. The unit ran and wrote its files as the owner.

### Idle scan (step 5): not taken

No forced sample was taken at idle: `stalls.log` has no `pending=-` line. Both forced samples have request text
"once" and were taken with a job pending.

The first forced sample came at mono 24986.898. The host's clock line ("journal t 0 = monotonic 24985.426 s") puts
that 1.47 s after the emulator's start. This fits a request written at idle that waited for the first job (exp 0370
D5).

With exp 0373's code a waiting request also blocks every later one. The service re-reads the `force` file only while
no request is pending (`run_service`: `if eng.force_req is None`), so an "idle" written after a waiting "once" was
never seen. Whether an idle request was written during T1 is not in the records. The flaw is in the code either way.
The proposal fixes it.

### Load scans (step 6), forced, under ASTRO BOT

| | 06:33:08 (host t 1.47 s, the title's start) | 06:34:21 (t 74.30 s, start-screen frames at ~16 ms) |
| --- | --- | --- |
| kept waves of 1,600 slots | 134 | 268 |
| scan / registers | 26.9 ms / 0.1 ms, 0 read errors | 39.3 ms / 0.1 ms, 0 read errors |
| HW_ID1 mismatches | 23, all 23 naming SE 2 or 3 | 47, 26 of them naming SE 2 or 3 |
| PCs containing `beef` | 22 (e.g. 0x5bebebeef ×9, 0xbeefbebebeef ×3) | 34 (0x5bebebeef ×13, 0xbeefbebebeef ×10) |
| queues | me0 pipe0 q0/q6–q9 vmid 6, me2 pipe2 q15 vmid 14 | the same, plus 24 slots `me0 pipe0 q0 vmid0` |
| after it | nothing | the GPU hang below, 106 ms after the scan started |

The chip has 2 SEs (`slots=2x2x…`, F510). A HW_ID1 that names SE 2 or 3 cannot describe the slot that was
addressed. So these records are torn: some of the 17 dwords of a record come from different moments, or from no wave
at all. 0xbebebeef is umr's no-data pattern (umr `scan_waves.c:603-605`, cited in the tool). It appears here inside
the PC dwords of slots marked VALID. So the scan did not name programs reliably while the waves ran. The PCs that
look clean (0x500849…, 0x500994…, 0x50070c…) are the title's (vmid 6). Matching them to programs (exp 0370 K4) was
not attempted.

### The hang (06:34:23)

**Timeline** (CLOCK_MONOTONIC unless marked; host t + 24985.426):

| mono | what | source |
| --- | --- | --- |
| 25059.726 | forced sample 2 starts (registers 0.1 ms, then the 1,600-slot scan) | forced summary |
| 25059.739 | the host sees #45159 done | direct.log t 74.313 |
| 25059.740–.741 | the host prepares dcb #45160 (26,897 dwords) and acb #45161 (1,563 dwords), the two jobs that never complete | t 74.314–74.315 |
| ≈25059.766 | the scan ends (39.3 ms) | forced summary |
| 25059.767 | the host gives up a CPU wait (WAIT_REG_MEM64 after 16.4 ms) | t 74.341 |
| 25059.832 | `gfx_0.0.0`'s fences last change (signaled 0x1447af, emitted 0x1447b1): the stall clock starts | event summary |
| 25059.869 | the host prepares the next dcb (26,863 dwords); no submit line follows | t 74.443 |
| 25060.333 … 25061.548 | the stall samples at clocks 0.50, 0.82, 1.11, 1.42, 1.72 (registers and a full scan each, 40–41 ms) | event summary |
| ≈25061.742 | the event is written at stall clock 1.91 s (journal 06:34:23.279) | sampler journal line |
| 25061.769 | the devcoredump's `time:` (the kernel's timeout handler) | devcd header |
| [25061.426] printk | `ring gfx_0.0.0 timeout, signaled seq=1329071, emitted seq=1329073`, kyty_emulator thread bc5-ring | kmsg / pstore |
| [25061.615] printk | `Ring gfx_0.0.0 reset failed`; `GPU reset begin!` | kmsg / pstore |
| [25061.713–.716] printk | `bc5-gpu-watch`: a ring reset failed → SysRq s, c; panic at [25062.718] | pstore |

The two clocks are offset. The printk stamps of this boot run 0.343 s behind CLOCK_MONOTONIC: the timeout line is
[25061.426] in printk time, and the devcoredump that the same handler writes just before it has `time:
25061.769243355`. The journal's monotonic column puts the line at 25061.770. (That amdgpu stamps the dump with
`ktime_get()` is TODO(verify) in `amdgpu_dev_coredump.c`.) So the event's "written before the kernel's 2-s timeout"
is right in wall time (06:34:23.279 vs 06:34:23.310 in the journal), though its summary prints a printk stamp beside
CLOCK_MONOTONIC values. The kernel timed out 1.94 s after the sampler's stall start. The sampler's clock ran ~60 ms
behind the kernel's: the scan held the poll from .726 to ~.766. The 1.9-s write had ~27 ms of margin.

**State** (the devcoredump, `raw/extract.txt`; fields and opcodes in `raw/decode.txt`):
- `GRBM_STATUS` 0xe5f100ac: CP, GE, SX, SPI, BCI, SC, DB and CB busy, TA idle, not CB/DB clean.
- `GRBM_STATUS_SE0` 0x08000000 (SPI only); `GRBM_STATUS_SE1` 0xec400000 (BCI, SX, SPI, SC, DB, CB);
  `GRBM_STATUS2` 0x50000008 (CPF, CPG); `GRBM_STATUS3` 0x00002000 (PH).
- `CP_PFP_INSTR_PNTR` 0xe9f (the sampler saw 0xea1 in four samples and 0xe9f in one); `CP_ME_INSTR_PNTR` 0xb8b.
- IB1 at base hi 0x1008, `BUFSZ` 0x5cf0 left of `CMD_BUFSZ` 0x8a10.
- `GCVM_L2_PROTECTION_FAULT_STATUS` 0. The dump's "[gfxhub] Page fault observed" header says address 0, status 0.
  It is present in every dump in the directory, so there was no VM fault.
- **The gfx queue's PFP history:** ACQUIRE_MEM ×2, WAIT_REG_MEM, and five `0xffff1000`, the one-dword NOP padding
  (exp 0011, ADR 0009). **The ME history:** SET_SH_REG ×3, DRAW_INDEX_OFFSET_2, SET_UCONFIG_REG_INDEX,
  LOAD_UCONFIG_REG_INDEX, LOAD_SH_REG_INDEX, and opcode 0x53, which the repo's tables do not name.
- The sampler's five stall samples read the same `GRBM_STATUS`, ME pointer, IB1 registers and both eight-entry
  histories as the dump (`regs-1.txt` = `regs-5.txt` = the dump). So its register path read correctly through the
  stall.
- **Its wave scans during the stall:** 3 kept slots at clock 0.50 (se1 sa0 wgp1, vmid 0, EXEC 0, PC 0 or 0x84953c,
  each a HW_ID1 mismatch, so probably torn too), then 0, 0, 0, 0. Shape "draining": no wave stayed resident.

This is **not F403's signature**. F490's state (here from F506's dump, 20261028-233612): `GRBM_STATUS` 0xa0407028
(TA, SPI busy, CB/DB clean), SE0/SE1 0x0a000016 (TCP/TA/SPI), ME 0x77a–0x77b, the host's GFX-form indirect-dispatch
check in the PFP history, with a compute dispatch running. Here no wave runs. The graphics pipe of SE1 (SC, DB, CB,
SX) and the CP are busy, and the ME stands in draw-state packets at 0xb8b. The PFP pointer is the same (0xe9f–0xea1)
in both, so the PFP pointer alone does not identify the class.

**Earlier ASTRO BOT hangs:** F169 (2026-10-15: CB/DB and SQC faults at 0x80-tagged addresses, two with a failed gfx
ring reset) had faults; this one has none. F465 (2026-10-28, the integrated build, first level) had no TIMEOUT. No
earlier record has this state (a repo search for 0xe5f100ac, 0xec400000 and ME 0xb8b finds nothing). On this build it
is the first ASTRO BOT ring timeout on record. Whether ASTRO BOT's start screen hangs like this without the sampler
is unknown: no baseline run of that screen exists for this build.

### Causality: the wave scan is suspected, not proven

**For:**
- **Timing.** The two jobs that never completed were handed over while the scan ran: prepared 14–15 ms after it
  began, and it lasted 39 ms. The ring's fences stopped 66 ms after the scan ended, 106 ms after it began.
- **No precedent.** No ASTRO BOT ring timeout is on record for this build. The only one in this boot came after this
  scan.
- **Torn records.** The scan read `SQ_IND` registers of running waves without halting them: `amdgpu_wave` →
  `gfx_v10_0_read_wave_data` selects the slot through `GRBM_GFX_INDEX` and `SQ_IND_INDEX`. The records it got back
  are torn (above). So the reads interleaved with the waves' own state changes. Whether such reads can upset the SQ,
  or the CP's own use of `GRBM_GFX_INDEX` (the ME history has SET_UCONFIG_REG_INDEX), is unknown:
  TODO(verify) whether the CP's and the MMIO path's `GRBM_GFX_INDEX` are one register on gfx10, and whether umr halts
  waves before its scan by default (umr `scan_waves.c`, option `halt_waves`).

**Against:**
- **The first scan passed.** The scan at 06:33:08 (134 waves, 26.9 ms) passed, with no hang. That was during the
  title's start, not the same frames, so it is not quite the same load.
- **Scans inside the stall were harmless.** Five more full scans ran during the stall itself. The state they
  sampled did not change, and the machine stayed up until the reset failed.
- **The hang is n = 1.** One hang a few seconds after one scan is a single coincidence. ASTRO BOT's hang rate on this
  start screen is unmeasured.
- **The kernel noticed nothing.** The kernel logged no warning for any read.

**Verdict on causality:** the wave scan is the leading suspect. The hang state (a graphics-pipe stop with no waves)
does not show a mechanism, and the evidence cannot separate a scan-caused hang from a coincidence. The register-only
path is not implicated: the sampler's registers matched the kernel's own dump. But register-only sampling under load
was never tried on its own, because every T1 sample also scanned.

### Proposed sampler change (this commit, NOT deployed)

`tools/scripts/gpu-stall-sampler/bc5-gpu-stall-sampler` (`VERSION = "0374"`) and its unit tests:
1. **No wave scan by default.** Stall samples and forced samples read the registers and the fences only
   (`Config.wave_scan = False`). The service's census line says `wave_scan=off`, the event summary says "no wave
   scan", and `waves-N.*` files are written only for samples that scanned.
2. **Any wave scan needs an explicit flag.** The service or `--once` must run with `--wave-scan`. Even then, a forced
   sample scans only with the request token `waves` (`echo "once waves" > …/force`). Without the flag, `waves` is
   refused and logged ("waves refused (no --wave-scan)"). `--once` no longer scans without `--wave-scan`
   (`--regs-only` stays for install.sh). The unit file and install.sh are unchanged, so the installed service would
   run without the flag.
3. **A new request replaces a waiting one.** The service passes the `force` file to `Engine.offer_force` every
   second. A request still waiting for a job is replaced when the file says something else (so "once idle" no longer
   waits behind "once"). The same text keeps a periodic request's rhythm, and removing the file ends any request.

Commands (laptop, Windows, Git Bash, Python 3.14.0, from `tools/scripts/gpu-stall-sampler/`):
```bash
python bc5-gpu-stall-sampler --test                    # selftest: 11/11 passed (the old ten with --wave-scan,
                                                       #   plus "the default: registers only, no wave read, forced waves refused")
python -W error test_bc5_gpu_stall_sampler.py          # Ran 33 tests, OK (skipped=8: the BC5_LINUX_SRC source checks,
                                                       #   which this change does not touch; not rerun)
bash -n install.sh && bash -n undo.sh                  # ok
```
New unit tests: the default regs-only scenario, the flag × token matrix (only `--wave-scan` with `waves` reads the
1,600 slots), stall samples scanning only with the flag, and a waiting "once" replaced by "once idle".

### Proposed findings

- **F517 — The stall sampler installs and reads correctly on the box.** On 7.2.9-ogc3.1, all 35 register addresses
  agree with `umr -lr gfx1013`. All 31 registers read at idle have the same value through the sampler and `umr -r`.
  Both CP header histories have period 8. The debugfs directory is `dri/0000:01:00.0` with links 1 and 128, and
  `amdgpu_gfxoff` reads 0 at idle. Under a real hang, its five register samples equal the kernel's devcoredump
  (GRBM, ME pointer, IB1, both histories). This settles F511, F512 and F515's TODO(verify) for the box. Exp 0374
  (`install-check.txt`, the event). High.
- **F518 — An unhalted wave scan under load returns torn records, and a full scan costs ~40 ms.** The two forced
  scans under ASTRO BOT (134 and 268 kept slots, 26.9 and 39.3 ms) had 23 and 47 HW_ID1 mismatches. 23 and 26 of
  them name SE 2 or 3 on the 2-SE chip, and 22 and 34 PCs carry `beef` bytes (umr's 0xbebebeef no-data pattern)
  inside VALID slots. The stall scans cost 40–41 ms with 0–3 waves resident: ~25 µs per slot, regardless of
  occupancy. *This narrows F498:* the per-slot fields can be read without a halt, but not consistently while waves
  run. Exp 0374. High for the records; the mechanism is TODO(verify).
- **F519 — The T1 hang (2026-10-29 06:34:23, ASTRO BOT start screen) is a graphics-pipe stop with no waves, not
  F403's class.** The state: `GRBM_STATUS` 0xe5f100ac (CP/GE/SX/SPI/BCI/SC/DB/CB busy, TA idle), SE0 0x08000000,
  SE1 0xec400000, PFP 0xe9f–0xea1, ME 0xb8b, no VM fault. The PFP history is ACQUIRE_MEM, WAIT_REG_MEM and the NOP
  padding; the ME history is SET_SH_REG, DRAW_INDEX_OFFSET_2 and SET/LOAD_*_REG_INDEX. The resident waves drained
  to 0 within 0.8 s of the stall. The jobs that never completed were dcb #45160 (26,897 dwords) and acb #45161
  (1,563 dwords) on the one gfx ring. The ring reset failed and `bc5-gpu-watch` rebooted the box. It shares only the
  PFP pointer with F490's state, which F506 matched exactly. Exp 0374. High for the state.
- **F520 — The sampler's wave scan is the leading suspect for that hang, not a proven cause.** The hung jobs were
  handed over during the 39-ms scan, and the fences stopped 106 ms after it began. No other ASTRO BOT ring timeout
  is on record for this build. But the first scan (06:33:08) passed, five scans inside the stall changed nothing,
  the kernel logged no warning, and the hang is n = 1 against an unmeasured base rate. Register reads are not
  implicated. Exp 0374. Medium.
- **F521 — The printk stamps of that boot lag CLOCK_MONOTONIC by 0.343 s, and the kernel's 2-s clock ran ~60 ms
  ahead of the sampler's.** The timeout line is [25061.426] in printk time. The devcoredump that the same handler
  writes just before it says `time: 25061.769`, and the journal's monotonic column 25061.770. The kernel timed out
  1.94 s after the sampler's stall start, because the 39-ms scan held the 25-ms poll. The 1.9-s event write had
  ~27 ms of margin. Exp 0374. Medium; the dump's clock source is TODO(verify).
- **F522 — T1 is stopped. The safe mode to run next is registers and fences only, with no wave scan; any wave scan
  is opt-in behind `--wave-scan` and a per-request token. A newer forced request must replace a waiting one.** The
  proposal is in this branch, not deployed. T1's idle scan was never taken: with exp 0373's code a waiting "once"
  hides every later request. Exp 0374.

**Verdict.** T1 is **stopped, not passed**. Passed: the install check (F517) and the register path, which agrees with
the kernel's own dump under a hang. Failed: the wave path. Its records are unreliable under load (F518), and it is
the leading suspect for a hang that took the machine down (F519, F520). Not reached: the idle scan, T2's cost
measurement, and any program name for F403.

**Recommendation.** Keep the sampler uninstalled until the maintainer decides. If he reinstalls it, use this
branch's version with the default (no `--wave-scan`): every stall still gets five register and fence samples and an
event before the kernel's timeout. That is the F403 instrument minus the PCs. For a T1b on a GO:
1. idle `echo "once idle"` (registers);
2. ASTRO BOT start screen with `echo 30 > …/force`, registers only, for 10–15 min attended, with the kernel stream
   to the laptop;
3. the same with the second title, RT on.

Run no wave scan until the open TODOs are answered offline: whether the CP's and the MMIO `GRBM_GFX_INDEX` are one
register on gfx10, and whether umr halts before scanning. If a scan is ever retried, it should be a halted scan in a
separate experiment, never a resident default. Consider lowering `write_at` to 1.8 s (F521). Not done here: with no
scan, a sample takes 0.2 ms and the poll is no longer held.

Merging this branch and reinstalling are the maintainer's decisions.
