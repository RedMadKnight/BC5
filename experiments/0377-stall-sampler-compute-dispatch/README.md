# 0377 — The stall sampler reads the compute dispatch registers (F529)

**Date.** 2026-10-29 10:10–10:31. **Box.** Read-only checks on a free box (no emulator, BOX-LOCK empty before and
after); no GPU load, nothing installed. Lock and queue lines: `top exp 0377 | …` in `~/bc5-work/BOX-LOCK` (cleared)
and `~/bc5-work/BOX-QUEUE`; claim in `~/bc5-work/exp0377/CLAIM.txt`.

**Question.** Exp 0376 (F527–F529) puts the ME of an F403-class hang just past one of three indirect dispatches. Can
the resident sampler's registers-only read also take the compute dispatch registers (program address, grid,
initiator), without a register write, a halt or a reset? And does a plain MMIO read of these SH registers return the
gfx pipe's values or some selected queue's?

## Setup

- Code: `tools/scripts/gpu-stall-sampler/` on branch `exp/0377-stall-sampler-compute-dispatch`, from main 676aa09.
  `VERSION = "0377"`.
- Sources, read 2026-10-29:
  - Linux v7.2 (tag object 237a1c39, commit 8d3ae59288f1, the commit the sampler already cites), fetched from
    `git.kernel.org/…/torvalds/linux.git/plain/<path>?h=v7.2`: `gc_10_1_0_offset.h`, `gc_10_1_0_sh_mask.h`,
    `amdgpu_debugfs.c`, `nv.c`, `gfx_v10_0.c`, `gfx_v9_0.c`, `v10_structs.h`, `cyan_skillfish_ip_offset.h`,
    `amdgpu_fence.c`, `amdgpu_job.c`. They are kept outside the repo; the unit tests read them through
    `BC5_LINUX_SRC`.
  - Mesa `src/amd/registers/gfx10.json` in three copies: the repo's vendored copy (`tools/bc5-agc/regdb`, fe554882),
    the box's `~/src/mesa` (0866ae7), and Mesa main as fetched today (main was at fc8ba437). All three give the same byte offsets.
  - umr 1.0.11-2.fc44's database on the box (`/usr/share/umr/database`: `cyan_skillfish.asic`,
    `cyan_skillfish.soc15`, `ip/gc_10_1_0.reg`): the files as text, with no device access.
- Laptop: Windows 11, Python 3.14.0. Box: kernel 7.2.9-ogc3.1.fc44, Python 3.14.8.
- Commands:
  - Laptop: `python bc5-gpu-stall-sampler --test`; `BC5_LINUX_SRC=<dir> python -W error test_bc5_gpu_stall_sampler.py -v`;
    the same without the sources; `PYTHON=python bash install.sh --dry-run` (`raw/laptop-test.txt`).
  - Box, on a copy in `~/bc5-work/exp0377/sampler/` (not over `~/bc5-work/gpu-stall-sampler/`, the installed copy's
    source): `/usr/bin/python3 -I -B bc5-gpu-stall-sampler --test`, the unit tests with
    `BC5_MESA_GFX10=~/src/mesa/src/amd/registers/gfx10.json`, and `bash install.sh --dry-run` (`raw/box-test.txt`).
  - The address check: `umr -lr gfx1013`, as `install.sh` runs it, then the umr database files
    (`raw/umr-lr-as-user.txt`, `raw/umr-database.txt`, `raw/umr-database-compare.txt`).

## What changed in the sampler

- **Reads.** Each register sample now reads 16 more registers after the existing 33: `COMPUTE_DISPATCH_INITIATOR`,
  `COMPUTE_DIM_X/Y/Z`, `COMPUTE_START_X/Y/Z`, `COMPUTE_NUM_THREAD_X/Y/Z`, `COMPUTE_PGM_LO/HI`, `COMPUTE_PGM_RSRC1/2/3`
  and `COMPUTE_DISPATCH_ID`. These are all of F529's names; `COMPUTE_PGM_RSRC3` and the Y/Z registers were added to
  complete the sets. `GRBM_GFX_CNTL` is read just before and just after the block.
  - Each offset cites its line in `gc_10_1_0_offset.h` (4535–4629; `GRBM_GFX_CNTL` 2089), with GC_BASE 0x1260.
  - The byte offsets are 0xb800–0xb8a0, and `GRBM_GFX_CNTL` is 0x8088. `COMPUTE_PGM_LO` is 0xb830 and
    `COMPUTE_PGM_HI` 0xb834, as F529 says.
  - That is 18 more `pread`s of 4 bytes per sample, the kind F523 found safe under load.
- **Nothing else changes.** No register is written, no `amdgpu_regs` position carries a bank or queue select
  (bit 61 or 62) for these reads, and wave scans stay off (F520, F522).
- **Output.**
  - `regs-N.txt` gets the raw `gfx1013.mm<REG> => 0x…` lines plus four decoded lines. The first of them reads
    `program address = PGM_HI:PGM_LO << 8 = 0x…`. In code: `((PGM_HI & 0xff) << 40) | (PGM_LO << 8)`, from
    `COMPUTE_PGM_HI` DATA [7:0] (`gc_10_1_0_sh_mask.h:17128`) and the kernel's own `>> 8` (`gfx_v9_0.c:4758-4764`,
    as in the backend's `dispatch_min.cpp:52`).
  - Each sample in `summary.txt` gets a `compute: program=… dim=[x y z] threads=[x y z] initiator=… id=…` line.
  - The census lines get `pgm@first=` (stall) and `pgm=` (forced).
  - `--list-regs` marks `GRBM_GFX_CNTL` as `sampled-x2`, so `install.sh` never runs `umr -r` on it. The 16
    `COMPUTE_*` registers are "sampled", so `install.sh`'s idle check will also compare their values with `umr -r`.
  - `raw/example-replay/` shows the format on a synthetic stall (FakeDevice values, not hardware).
- **Tests.**
  - New self-test entry: the block sits between two witness reads, the decode is right, and a select seen by the
    witness is flagged. 12 entries in all.
  - New unit class `ComputeDispatch` (11 tests; 44 in all). The kernel model now fails any bit-61 position, the Mesa check
    covers at least 31 registers, and `BC5_MESA_GFX10` can name another Mesa copy. The other test classes are
    unchanged.

## Result

### The banking question

**A plain read returns the gfx ME's values (ME 0, pipe 0, queue 0: the `gfx_0.0.0` ring) as long as no kernel
select is in place. That ring is the one the F403 class stops, so the feature is useful for this hang. Compute
rings' `COMPUTE_*` values cannot be read without a select, and the sampler does not make one.** From Linux v7.2:

- `amdgpu_debugfs_process_reg_op` selects a ME/pipe/queue only for a position with bit 61 (`amdgpu_debugfs.c:109-116`,
  `145-147`). Without it, the read is a bare `RREG32` (`:157`) of whatever `GRBM_GFX_CNTL` selects at that moment.
- `GRBM_GFX_CNTL` holds PIPEID, MEID, VMID and QUEUEID (`gc_10_1_0_sh_mask.h:5925-5932`). The kernel writes it only
  through `nv_grbm_select` (`nv.c:317-327`), under `srbm_mutex`, and always puts it back to ME 0, pipe 0, queue 0,
  VMID 0: after the debugfs select (`amdgpu_debugfs.c:179-181`) and after its own selects (`gfx_v10_0.c:3867, 5218,
  5378, 6875, 7165`). A unit test checks these lines in the source.
- ME 0 is the gfx ME, and compute rings are ME 1 and 2: `ring->me = mec + 1` (`gfx_v10_0.c:4689-4690`).
- The title's dispatches run on the gfx ring. F527 has the gfx ME waiting after the stuck dispatch, and F251/F253
  found another client's `COMPUTE_PGM_HI` left on that ring.
- **No select.** A bit-61 read would make the kernel write `GRBM_GFX_CNTL` in the middle of a stall; nothing shows
  that safe, and the gfx ring needs no select. So the sampler stays with plain reads, and reads `GRBM_GFX_CNTL` before
  and after the block as a witness.
  - Zero ME/pipe/queue/VMID bits in both witness reads mean no select was in place at either end of the block.
  - Anything else is written as `UNKNOWN bank (GRBM_GFX_CNTL a/b …)`.
  - A select made and undone between the two reads would go unseen. The kernel selects at queue setup, reset and
    MQD work, not per submission, and the sampler keeps out of reset windows.
- **TODO(verify) on the hardware:**
  - that these SH registers read back at all on gfx1013;
  - that the gfx ME has its own instance under MEID 0. The MQD keeps a copy of every one of them except RSRC3 for
    each compute queue (`v10_structs.h:675-709`; a unit test), which says they are per-queue state.
  - whether a `DISPATCH_INDIRECT` leaves its arguments in `COMPUTE_DIM_X/Y/Z`. This decides whether DIM can answer
    F528's x = 0.

### Tests

- **Laptop** (Python 3.14.0): `--test` 12/12. 44 unit tests OK with the v7.2 sources (`-W error`), including the 12
  source-checked ones; 44 OK (12 skipped) without them. `install.sh --dry-run` renders the unit (`raw/laptop-test.txt`).
- **Box** (Python 3.14.8, kernel 7.2.9-ogc3.1), on the staged copy:
  - `--test` 12/12, and 44 unit tests OK (12 skipped: no kernel sources on the box), with Mesa = the box's
    `~/src/mesa` at 0866ae7.
  - `install.sh --dry-run` passes (its self-test 12/12, `ExecStart` for user kjaniszewski) (`raw/box-test.txt`).
  - The first box run, before the last format change, failed one unit test only because the flat copy has no
    `tools/bc5-agc/regdb`. `BC5_MESA_GFX10` was added for that.
  - The staged files' sha256 are in `raw/box-test.txt` (sampler ff65042a…); they match the branch.
- **Addresses against umr.**
  - `umr -lr gfx1013` as the user prints only "ASIC not found or compatible" and "UMR was not invoked as root"
    (`raw/umr-lr-as-user.txt`). On this box even the register list needs root: as the user, umr cannot find the ASIC.
  - Instead, umr's own database files: `cyan_skillfish.asic` maps GC to `gfx1010` = `ip/gc_10_1_0.reg`, and
    `cyan_skillfish.soc15` gives GC bases 0x1260 and 0xa000, the sampler's `GC_BASE`.
  - **All 52 registers (the 33 old ones, the witness, the 16 new ones and the 2 banked ones) have the sampler's dword
    offset and BASE_IDX** (`raw/umr-database-compare.txt`).
  - `install.sh` will repeat the check as root with `umr -lr` and compare the values with `umr -r`.
- Not touched: the installed sampler (0374) and its source `~/bc5-work/gpu-stall-sampler/` (directory mtime still 06:26), the shared
  builds, `play-pkg.sh`, `backend/kytyplus-patches`.

## Verdict

**Built and tested; not installed.** The sampler 0377 reads F529's compute dispatch registers in its registers-only
sample, with no write, no halt and no select. It decodes the program address for matching against F527/F528's three
candidates (0x11d028dd00, 0x11d02a1600, 0x11d02a1800). Laptop and box tests pass, and the offsets agree with the
v7.2 header, three Mesa copies and umr's database.

The values belong to the gfx ring (ME 0, pipe 0, queue 0) by the kernel's own code. Whether these SH registers read
back, and per ME, on gfx1013 is the open hardware question (TODO(verify)). Two things will answer it:

- `install.sh`'s idle `umr -r` comparison (root);
- forced samples under the second title: a healthy frame parked at PFP 0xea1 / ME 0x77b must show a program from its
  own dispatch list (F529's T1).

### The install is the maintainer's

From the staging directory `~/bc5-work/exp0377/sampler/` (sha256 in `raw/box-test.txt`):

```
sudo bash ~/bc5-work/exp0377/sampler/install.sh
```

It replaces `/usr/local/sbin/bc5-gpu-stall-sampler` (0374) and restarts the service; the captures stay. Its install
check (`~/bc5-data/captures/gpu-stall/install-check.txt`) then shows the 16 new registers against umr.

Undo:

- back to 0374: `sudo bash ~/bc5-work/gpu-stall-sampler/install.sh`;
- remove the sampler entirely: `sudo bash ~/bc5-work/exp0377/sampler/undo.sh`.

## Findings (for HANDOFF)

- **F530 — The stall sampler 0377 reads F529's compute dispatch registers in its registers-only sample, with no
  register write and no bank or queue select.**
  - It reads 16 `COMPUTE_*` registers between two reads of `GRBM_GFX_CNTL`.
  - Their offsets (bytes 0xb800–0xb8a0) agree with v7.2 `gc_10_1_0_offset.h` + GC_BASE 0x1260, with Mesa
    `gfx10.json` (fe554882, 0866ae7, fc8ba437) and with umr 1.0.11's database on the box (52/52 registers).
  - `regs-N.txt` gets the line "program address = PGM_HI:PGM_LO << 8", and the summary and census lines carry the
    program address.
  - Laptop (Python 3.14.0) and box (3.14.8): self-test 12/12 and 44 unit tests OK; `install.sh --dry-run` passes.
  - Staged in `~/bc5-work/exp0377/sampler/`, not installed.
  - Experiment 0377. High for the code and the offsets.
- **F531 — A plain `amdgpu_regs` read of the `COMPUTE_*` registers returns the gfx ME's pipe-0 queue-0 instance,
  which belongs to the `gfx_0.0.0` ring the F403 class stops, so the feature can name that ring's program. Compute
  rings' values are out of reach without a select.**
  - Only a bit-61 position makes the kernel select a ME/pipe/queue (`amdgpu_debugfs.c:109-116, 145-147`).
  - The kernel always restores `GRBM_GFX_CNTL` to ME 0/pipe 0/queue 0/VMID 0 (`nv.c:317-327`;
    `amdgpu_debugfs.c:179-181`; `gfx_v10_0.c:3867, 5218, 5378, 6875, 7165`), and ME 0 is the gfx ME
    (`gfx_v10_0.c:4689-4690`).
  - The sampler never makes that select: it would be a kernel write to `GRBM_GFX_CNTL` mid-stall. It reads
    `GRBM_GFX_CNTL` before and after the block as a witness instead.
  - TODO(verify): readback of these SH registers on gfx1013, a gfx-ME instance under MEID 0 (the MQD keeps
    per-queue copies, `v10_structs.h:675-709`), and whether `DISPATCH_INDIRECT` leaves its arguments in
    `COMPUTE_DIM_*`.
  - Experiment 0377. High for the kernel path; the hardware behaviour unverified.
- **F532 — On the box, `umr -lr gfx1013` (the register list) needs root: as the user umr cannot find the ASIC.** As the user it prints "ASIC not
  found or compatible" and "UMR was not invoked as root" (umr 1.0.11-2.fc44). For read-only address checks without
  root, read umr's database files (`/usr/share/umr/database/cyan_skillfish.asic` maps GC to `ip/gc_10_1_0.reg`; the
  GC bases are in `cyan_skillfish.soc15`). Experiment 0377 (`raw/umr-lr-as-user.txt`, `raw/umr-database.txt`). High.
