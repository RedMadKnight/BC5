# 0373 — The stall sampler, stage T0: built and tested on the laptop

**Date.** 2026-10-29. **Branch.** `exp/0373-stall-sampler`. **Box.** None: laptop only (Windows, Git Bash, Python
3.14.0), no ssh, nothing on the box changed. Numbers F510–F516 (F500–F504 are exp 0372's, F505–F509 exp 0371's).

**Question.** Can exp 0370's design (D1–D8) be built as written: a resident root sampler that runs the kernel's
2-s clock on `amdgpu_fence_info`, reads CP/GRBM registers and every wave slot without halting at 0.5–1.7 s of a
stall, and writes an event at the kernel's timeout line or at 1.9 s? Does it behave right on synthetic fence traces,
does its wave decoder match the kernel's record layout, and what must T1 check first on the box?

**Setup.** Tool: `tools/scripts/gpu-stall-sampler/` — `bc5-gpu-stall-sampler` (Python 3, stdlib only; usage in its
header), `bc5-gpu-stall-sampler.service` (template), `install.sh` (also `--dry-run`), `undo.sh`,
`test_bc5_gpu_stall_sampler.py`. Here: `standin-install.sh` (install.sh's root path with shims for id, getent,
install, chown, systemctl, umr; no root), `bench_t0.py` (the tool's own Python cost), `raw/` (the outputs below,
scratch paths replaced by `$SCRATCH`). Sources read 2026-10-29 and cited in the code: Linux v7.2
(github.com/torvalds/linux `8d3ae59288f1e7d58d76558a6ee96d533bc5019f`, tag v7.2): `amdgpu_debugfs.c`,
`gfx_v10_0.c`, `amdgpu_fence.c`, `amdgpu_job.c`, `amdgpu_device.c`, `amdgpu_discovery.c`, `nv.c`,
`gc_10_1_0_offset.h`, `gc_10_1_0_sh_mask.h`, `cyan_skillfish_ip_offset.h`, `drm_debugfs.c`, `drm_drv.c`,
`sched_main.c`, `seq_file.c`, `Documentation/ABI/testing/dev-kmsg`; umr (gitlab.freedesktop.org/tomstdenis/umr
`aa7f72dcb8bd33af27c6a0b6a3e173644dc3a800`): `src/lib/scan_waves.c`, `src/lib/lowlevel/linux/read_gprwave.c`,
`src/app/main.c`, `src/app/scan.c`; Mesa `gfx10.json` vendored in `tools/bc5-agc/regdb/` (fe554882). The box runs
7.2.9-ogc3.1, not v7.2: every v7.2 citation is TODO(verify) against that tree.

Commands (from the repo root; `$SCRATCH/ksrc` holds the v7.2 files above, fetched by raw.githubusercontent.com URL):
```bash
python tools/scripts/gpu-stall-sampler/bc5-gpu-stall-sampler --test                        # raw/selftest.txt
python tools/scripts/gpu-stall-sampler/test_bc5_gpu_stall_sampler.py -v                     # raw/unittest-no-src.txt
BC5_LINUX_SRC=$SCRATCH/ksrc python -W error tools/scripts/gpu-stall-sampler/test_bc5_gpu_stall_sampler.py -v
                                                                                            # raw/unittest-v7.2-src.txt
python experiments/0373-stall-sampler-t0/bench_t0.py                                       # raw/bench.txt
(cd tools/scripts/gpu-stall-sampler && PYTHON=python bash install.sh --dry-run)            # raw/install-dry-run.txt
bash experiments/0373-stall-sampler-t0/standin-install.sh $SCRATCH/standin5 python         # raw/standin-install.txt
bash -n tools/scripts/gpu-stall-sampler/install.sh; bash -n tools/scripts/gpu-stall-sampler/undo.sh
```

## Result

**Tests.** `--test`: 10/10 passed — the wave decoder and debugfs positions; a healthy 30-s run of 60-Hz jobs on two
rings with a 5-s idle gap (0 samples, 0 census lines, 0 register or wave reads); a stall resolving at 0.7 s (one
census line, `samples=1`, `event=-`, no event directory); a stall reaching the kernel's timeout line at clock 2.03 s
(one event written at 1.90 s, the line, the `bc5-gpu-watch` quote filtered out, the reset lines and an earlier page
fault in `kmsg.txt`, five samples); the timeout line first at clock 1.82 s (event written on the line); a stall past
1.9 s with no kernel line (event at 1.90–1.95 s, shape "standing still in every interval"); two rings stalling
0.1 s apart (one event, 6 shared samples, 5 per ring, not 10); a second ring stalled through the first ring's reset
(no read between clock 1.85 s and the reset's end line, comp's 1.1 and 1.4 counted missed); a timeout line with no
sampled stall (a standalone event, no read after the line); a second stall while an event is being written (the
writer blocked in its first file; the second ring's five samples taken meanwhile; event 2 written after event 1).
Unit tests: 29 run, all OK; 8 skip without `BC5_LINUX_SRC` and pass with it — they parse the cited source text
itself: the `amdgpu_wave` GENMASK bits, the gfx10 record order and `WARN_ON(simd != 0)`, the `amdgpu_regs` offset
mask and bank bits, every register's `mm`/`BASE_IDX` in `gc_10_1_0_offset.h`, `GC_BASE` in
`cyan_skillfish_ip_offset.h`, the field masks in `gc_10_1_0_sh_mask.h`, the `amdgpu_fence_info` formats and the
`amdgpu_job_timedout` lines. The others include a scan through a model of the kernel's read path (1,600 distinct
positions, simd field always 0, HW_ID1 round trip), offsets against Mesa (all 19 that Mesa lists agree), debugfs
discovery on v7.2 and numbered layouts, the forced-sample requests, the GFXOFF/pending gates, the header-history
period check and the umr comparison table.

**Install path.** `--dry-run` renders the unit (`ExecStart=/usr/bin/python3 -I -B /usr/local/sbin/bc5-gpu-stall-sampler
--owner … --out …/bc5-data/captures/gpu-stall`). The stand-in ran install.sh's root path end to end (exit 0): self-test
gate, 31 `umr -r "*.gfx1013.^mmNAME$"` calls (none on the header histories), the `umr -lr gfx1013` filter, the table
`totals: addr ok 35, not read 4, same 31`, the unit, the first `stalls.log` line.

**Cost on the laptop** (`raw/bench.txt`; the box's Zen 2 differs, T2 measures): a healthy poll 96 µs (0.39 % of a
core at 40 Hz); the user-space side of a 1,600-slot scan 5.7 ms (3.6 µs per slot, the kernel's 17 SQ_IND reads per
slot come on top); an event summary of 5 × 800 waves 30 ms once, in the writer thread; the event's sample files
651 KB at 800 valid waves (the design guessed ~200 KB).

**Not exercised.** The service loop itself (`select.poll` on `/dev/kmsg`, `os.pread` on debugfs, `mlockall`,
`fchown`, SIGTERM): Windows has neither `os.pread` nor `poll` on files, and WSL is out of this worktree's reach. Its
first run is T1.

### Deviations from exp 0370's design (intent kept)

1. **Wave addressing.** D3's "2 SE × 2 SH × 10 CU × 2 SIMD × 20" becomes 2 SE × 2 SA × 5 WGP × 4 SIMD × 20 = the
   same 1,600 slots, addressed as umr does on gfx10: INSTANCE = `wgp << 2 | simd`, the debugfs simd field 0
   (`gfx_v10_0_read_wave_data` WARN_ONs otherwise). The scan ignores the fused INACTIVE_WGPS masks (umr skips those
   WGPs) because the 40-CU unlock enables them; the masks are read per SA in forced samples, for T1.
2. **No reads near or inside a reset.** Added: no sample starts once any stalled ring's clock is ≥ 1.85 s, nor
   between a timeout/reset-begin kernel line and the reset's end line (10 s cap, 30 s after a failed reset).
   Thresholds that fall there count as `missed`. Reason F513.
3. **CP header histories read 8× per sample** (the kernel's count), not once; never read once by umr at install.
   Reason F512.
4. **Forced samples through a request file** (`echo once > ~/bc5-data/captures/gpu-stall/force`; `30` for one every
   30 s; `regs`, `idle`), so T1's forced scans and T2's every-30-s samples need no root and no sudoers line (D7).
   Forced samples wait for a pending job (D5) unless `idle`, and never read when `amdgpu_gfxoff` reads 1 with no job.
5. **Extra cheap registers** from the kernel's own devcoredump list (GRBM_STATUS3, CPF/CPC busy and stall, RB0_WPTR,
   IB1_CMD_BUFSZ, IB2, MEC1/2 pointers, GCVM fault status): 31 single reads plus 2 × 8 history reads per sample.
6. **Census also for stalls that became events** (`event=<dir>`), and a `start` line, so `stalls.log` counts every
   kernel-side stall ≥ 0.5 s.
7. **Size.** ~1,850 lines with the self-test and replay instead of ~300; the text wave line carries D3's fields only
   (all 17 raw dwords go to `waves-N.bin`).

### Proposed findings

- **F510 — On gfx10 a wave slot is read through `amdgpu_wave` with the SIMD inside the GRBM instance
  (`wgp << 2 | simd`) and the debugfs simd field 0; any other simd value trips `WARN_ON(simd != 0)` in
  `gfx_v10_0_read_wave_data`. The record is a version dword (2) and 16 SQ_WAVE registers, STATUS first, PC, EXEC,
  HW_ID1/2 among them; umr scans 20 slots per SIMD on GC 10.1.x, so the chip's 40 CU are 1,600 slots.** (v7.2
  `amdgpu_debugfs.c:1136-1224`, `gfx_v10_0.c:4498-4524`; umr `scan_waves.c:30,598,671-672`.) High for the source;
  the box at T1.
- **F511 — The sampler's register offsets agree three ways: v7.2 `gc_10_1_0_offset.h` (which `gfx_v10_0.c` uses for
  IP_VERSION(10, 1, 3) too) with `GC_BASE` {0x1260, 0xA000} from `cyan_skillfish_ip_offset.h`, and Mesa `gfx10.json`
  for the 19 registers it lists.** The box may take its bases from IP discovery (`amdgpu_discovery.c:3050-3061`):
  install.sh compares with `umr -lr gfx1013`. High offline; TODO(verify) on the box.
- **F512 — The CP packet-header registers are a history read cyclically, 8 entries: the kernel's devcoredump reads
  each 8 times per gfx queue, the box's dumps repeat the same eight headers per queue (exp 0368 F490) and show an
  empty MEC history as 0xdef0def0…0xdef7def7 (exp 0279 raw).** A single read (umr -r, the old hang dump) moves the
  window the devcoredump later shows; 8 reads leave it. Medium: inferred from dumps, checked at install (16 reads).
- **F513 — In v7.2 a debugfs register or wave read does not wait for a GPU reset: neither `amdgpu_regs` nor
  `amdgpu_wave` takes the reset lock, and RREG32's `amdgpu_device_skip_hw_access` skips the hardware only after PCI
  error or unplug (`amdgpu_device.c:827-852, 6753`).** So any user-space reader must keep out of the reset window
  itself; the sampler does (deviation 2). High for the source.
- **F514 — The timeout line comes after the devcoredump and the soft-recovery attempt and right before the ring
  reset (`amdgpu_job.c:111-136`); v7.2's drm_sched re-arms the timeout at every push and completion
  (`sched_main.c:198-302, 923-948`), as exp 0370 K1 read in v6.17.** The 1.9-s write is the primary path, the line a
  backup. High for the source.
- **F515 — v7.2 names the device's debugfs directory after the PCI address (`/sys/kernel/debug/dri/0000:01:00.0/`)
  with numbered symlinks to it, and its `name` file reads "amdgpu dev=… unique=…"** (`drm_drv.c:785`,
  `drm_debugfs.c:54-73, 401-441`). The sampler matches either layout. Card1's index: T1.
- **F516 — T0 passed: the sampler (D1–D7) is built; 10/10 self-test scenarios and 29/29 unit tests pass on Python
  3.14, the install path runs end to end in a stand-in, and a healthy poll costs ~0.4 % of a laptop core.** Its
  service loop, the scan's real duration and every box fact above are for T1.

### TODO(verify) left (all for T1 unless noted)

The box's 7.2.9-ogc3.1 against every v7.2 line cited; the GC base and GC 10.1.3 offsets (install-check.txt);
card1's debugfs index; the header-history period 8; `SPI_CSQ_WF_ACTIVE_STATUS` per SE or not (read unbanked); 5 WGPs
per SA and readable slots in the unlocked WGPs; `amdgpu_gfxoff`'s value at idle and in play; the scan's duration
(must leave margin before 2.0 s; `sample_until` 1.85 s assumes tens of ms); no `WARNING` in `sudo dmesg` from the
reads; no SELinux denial for the unit; T2: the cost against the soak's 34.7–36.5 flips/s.

**Verdict.** T0 passed. The design is buildable as written with the deviations above; none weakens its rule that
the instrument never halts and never causes a reset. Next: T1 (below), on GO.

## T1 checklist (for the top session; GO, BOX-LOCK, not during the maintainer's play)

1. Laptop → box: copy `tools/scripts/gpu-stall-sampler/` from this branch to `~/bc5-work/gpu-stall-sampler/`.
2. As the user, no root: `python3 ~/bc5-work/gpu-stall-sampler/bc5-gpu-stall-sampler --test` (expect
   `selftest: 10/10 passed` on the box's Python 3.14) and `bash ~/bc5-work/gpu-stall-sampler/install.sh --dry-run`.
3. **The maintainer, once:** `sudo bash ~/bc5-work/gpu-stall-sampler/install.sh` (undo:
   `sudo bash ~/bc5-work/gpu-stall-sampler/undo.sh`).
4. Read-only, as the user:
   - `cat ~/bc5-data/captures/gpu-stall/install-check.txt` — compare against umr: every row `addr ok (dword)` (umr's
     `-lr` address = byte offset / 4); values `same` for the idle-stable ones (CP_IB1_BASE_LO/HI, CP_RB0_RPTR/WPTR,
     CP_PFP/ME/MEC1/MEC2_INSTR_PNTR, GRBM_STATUS); a `MISMATCH` or `ADDR DIFF` row stops T1 (wrong offset/base);
     `changing` is inconclusive. The `## find` line gives the directory and card1's numbered link. Both
     `# CP_PFP_HEADER_DUMP period 8` and `# CP_ME_HEADER_DUMP period 8` must say `yes`; if `NO`, the maintainer
     adds `--header-dump-reads 0` to ExecStart. If the section says "no value comparison (… GFXOFF …)", record
     `amdgpu_gfxoff` = 1 at idle; the address rows still count.
   - `systemctl status bc5-gpu-stall-sampler --no-pager`; `journalctl -u bc5-gpu-stall-sampler -b --no-pager`;
     `head -1 ~/bc5-data/captures/gpu-stall/stalls.log` (the `start` line: debugfs, gfxoff, `mlockall=True`).
   - `sudo dmesg | grep -iE 'warn|bc5|amdgpu' | tail -20` (no WARNING from `gfx_v10_0_read_wave_data`);
     `journalctl -b | grep -i avc | grep -i stall` (no SELinux denial).
5. Idle scan: `echo "once idle" > ~/bc5-data/captures/gpu-stall/force`, wait 3 s, read the newest
   `forced-*/summary.txt`: 0 kept waves expected, the scan duration in ms, 0 read errors, the
   CC/GC_USER_SHADER_ARRAY_CONFIG masks per SA in `regs-1.txt`. If it says skipped (GFXOFF), go to 6.
6. Load scan: start ASTRO BOT (`~/bc5-work/play-astro.sh`) to its start screen, `echo once > …/force`, read the
   summary: kept waves > 0, `HW_ID1 mismatches 0`, waves in all five WGP indices (the unlocked ones included), the
   scan duration (it must leave margin before 2.0 s with `sample_until` 1.85 s; if a scan exceeds ~100 ms, lower
   `sample_until` before T2), the PCs inside ASTRO BOT's programs. Then the `dmesg` check again.
7. Record the box's 7.2.9 lines for the citations (sched_main, amdgpu_debugfs wave/regs, gfx_v10 read_wave_data) if
   its source is at hand; otherwise leave them TODO(verify).
