# 0058 — what the GPU is doing when the second title hangs with its multi-draw packets

**Question.** With all indirect draws (`BC5_DIRECT_INDIRECT_DRAWS=multi`) and the code aliased
under 0x80 (0056), the second title hangs the GPU at ~150 s in every run. Which work hangs, and
where?

**Setup.** The maintainer gave the account read-only root access for three things, all in
`/etc/sudoers.d/bc5-claude`:
- `/usr/local/bin/bc5-gpu-hang-dump`: umr's wave dump, CP and GRBM registers, the gfx ring and
  `amdgpu_fence_info`;
- `/usr/local/bin/bc5-gpu-hang-watch`: a 10-minute watcher. It polls the ring's fences every 50 ms
  and, when the ring has stalled for 0.6 s, dumps waves and CP registers to `/var/tmp`;
- `cat` of the kernel's `devcoredump/data`.

The scripts are root-owned and not in the repo.

Host (patch 0001): `BC5_DIRECT_UMR_ON_TIMEOUT=1` runs the dump script at a job's timeout, later
0.9 s after its submission (through `distrobox-host-exec`).

Runs 264–272, 2026-10-12 20:01–21:31, 210–300 s. Waves were matched to the title's dumped programs
(disassembly with `llvm-mc -mcpu=gfx1013`, kept private). Raw summaries are in `raw/summary.txt`;
the dumps themselves stay private (they hold the title's code).

**Result.**

1. **Dumps taken by the host come too late.** The kernel resets the gfx ring about 2 s after a job
   hangs, at the same moment the host's own 2 s fence wait gives up (run 267: kernel 10810.003 s,
   host 10810.05 s). The host's dump, even 0.9 s after submission, runs after that reset, because
   starting umr through the container costs time. These dumps showed an idle CP, an empty ring and
   signalled fences (runs 264–269). The readings drawn from them — "no waves", "the job never
   reached the ring", "a lost fence" — were artefacts.
2. **The kernel's devcoredump holds the state before the reset** (runs 270, 271):
   - GRBM_STATUS 0xa0403028 — GUI_ACTIVE, CP_BUSY, SPI_BUSY;
   - CP_STALLED_STAT2 0x00210400 — EOPD_FIFO_NEEDS_SC_EOP_DONE, ME_WAIT_ON_AVAIL_BUFFER,
     MEQ_TO_ME_NOT_RDY_TO_RCV;
   - CP_BUSY_STAT 0x00440000 — EOP_DONE_BUSY, CE_PARSING_PACKETS.

   Field names are from the kernel's `gc_10_1_0_sh_mask.h`. The guilty IB is the 922-dword
   graphics buffer that carries compute work (1,064 dwords after the filter), submitted from the
   `bc5-ring` thread. Shaders were still running.
3. **The host-side watcher catches the waves in time** (run 272, two stalls):
   - 193 and 336 waves, every one in the title's compute program at 0x11d049aa00;
   - their program counters sit within 0x11d049c6fc–0x11d049c790, the tail of a loop that
     branches back to 0x11d049bcf4 (`s_cbranch_execnz`, −680 dwords).

   The loop is a software BVH traversal:
   - a stack in LDS and scratch;
   - nodes read from a buffer descriptor (`buffer_load_dwordx2 … idxen`), the node type in the low
     3 bits, the index above them;
   - repeat while any lane has nodes left.

   It has no iteration bound. On a tree with a cycle or garbage indices it never ends.
4. That program is dispatched indirectly by the 922-dword buffer, whose markers name ray-traced
   reflections.

**Verdict.** Passed for the question. The hang is the title's own reflection traversal looping on
a bad acceleration structure, once the multi-draw packets run. This is the same failure mode as the
tree refit of experiment 0050. Open: which trees go bad, and why; the next suspects are the trees
built from what the multi-draw packets draw (characters) and the producers of their data. For
future hangs, use the host-side watcher or the devcoredump, never a dump triggered by the host's
timeout.
