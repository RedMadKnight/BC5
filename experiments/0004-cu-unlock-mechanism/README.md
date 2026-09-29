# 0004 — how the 40-CU unlock works on the dev box

**Question.** Experiment 0003 recorded "24 of 40 CUs active" from the kernel log and RADV. The
maintainer applied the community CU unlock earlier. Is the unlock missing, or does the
measurement miss it?

**Setup.** BC-250 dev box, 2026-09-29, same boot as the second half of 0003 (booted 20:58:37).
Read-only inspection over SSH, no root:

```sh
systemctl cat bc250-cu-live-manager.service
journalctl -b <n> -u bc250-cu-live-manager.service      # n = 0, -1, -2, -3
cat /etc/bc250-cu-live-manager.conf
bc250-cu-live-manager --help; grep -n 'mm[A-Z_]*' /usr/local/bin/bc250-cu-live-manager
journalctl -k -b | grep active_cu_number
RADV_DEBUG=info vulkaninfo --summary | grep -E 'num_cu|num_se|cu_per_sh'
```

**Result.**

- An enabled oneshot unit `bc250-cu-live-manager.service` runs
  `/usr/local/bin/bc250-cu-live-manager --yes apply-service` after the render node appears. The tool
  (a 1 587-line bash script, installed by the maintainer, not part of this repository) uses `umr`
  (`UMR_ASIC=cyan_skillfish.gfx1013`) to write **`mmSPI_PG_ENABLE_STATIC_WGP_MASK`** per shader
  engine / shader array, and reads `mmCC_GC_SHADER_ARRAY_CONFIG`. The saved profile is
  `BC250_WGP_MASKS=0x1f,0x1f,0x1f,0x1f` (SE0.SH0, SE0.SH1, SE1.SH0, SE1.SH1): 5 WGPs × 2 CUs × 4
  arrays = 40 CUs.
- It reported success on all four boots of the day, including the current one:
  `[ OK ] dispatch registers updated (40/40 CUs target)` at 20:58:51, two seconds after amdgpu
  initialised.
- amdgpu logs `SE 2, SH per SE 2, CU per SH 10, active_cu_number 24` at 20:58:45 — before the
  service runs. RADV reports `num_cu = 24` but `num_cu_per_sh = 10`, `num_se = 2`.
- The tool can also restore stock dispatch (`stock-dispatch`), edit single WGPs, and unlock the two
  factory-disabled CPU cores via an SMU message (`bc250-8core-unlock.service` is enabled as well; the
  box reports 16 threads).

**Verdict.** The unlock is present and applied on every boot. It is a **live change of SPI dispatch
routing after the driver has enumerated the GPU**, so every enumeration API — the kernel's
`active_cu_number`, `AMDGPU_INFO_DEV_INFO`, RADV's `num_cu` — keeps reporting the 24 CUs that were
enabled when amdgpu probed the device. A (soft) reboot does not change that: the service re-applies
the masks, the driver still enumerates 24. Experiment 0003's line "24 of 40 CUs active" describes the
driver's view, not the dispatch state; HANDOFF Q8 and `CLAUDE.md` are corrected to point here.

Not yet verified: that waves actually land on all 40 CUs. Two ways, both open:
(a) `sudo bc250-cu-live-manager status` (reads the SPI masks through umr; needs root),
(b) a compute-throughput test whose result scales with CU count, run once with `stock-dispatch` and
once with the saved profile. Either becomes its own experiment.

Consequences for BC5:

- Decision D5 (36/4 split) should be implemented with the **same register family the unlock uses**
  (`SPI_PG_ENABLE_STATIC_WGP_MASK`, global, WGP granularity) or with per-dispatch CU masks
  (`COMPUTE_STATIC_THREAD_MGMT_SE*`, `SPI_SHADER_PGM_RSRC3_*.CU_EN`, HANDOFF F7). The per-dispatch
  masks are what the backend can write in its own IBs without root; the global mask needs umr/root
  and affects every process.
- Any code that sizes work from the driver's CU count (RADV, RPCSX's Vulkan path, our backend) sees
  24, not 40, while the hardware dispatches to 40. The backend should take the CU count from the
  dispatch configuration, not from `AMDGPU_INFO_DEV_INFO`.
