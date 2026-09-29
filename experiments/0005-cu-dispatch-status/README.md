# 0005 — CU dispatch status and GPU firmware versions

**Question.** Does the SPI dispatch configuration on the dev box actually route all 40 CUs
(HANDOFF Q8, follow-up of experiment 0004), and which GPU firmware versions does it run?

**Setup.** BC-250 dev box, 2026-09-29, current boot. The maintainer added a narrow sudoers rule
(`/etc/sudoers.d/bc5-claude`: `dmesg`, `tee /proc/sys/vm/drop_caches`,
`bc250-cu-live-manager [--yes] status`, `cat /sys/kernel/debug/dri/1/amdgpu_firmware_info`). All
three commands below only read:

```sh
sudo -n bc250-cu-live-manager --yes status        # reads SPI/CC registers through umr
sudo -n cat /sys/kernel/debug/dri/1/amdgpu_firmware_info
sudo -n dmesg | grep -iE 'ccp|psp|active_cu|cyan-skillfish'
```

Raw output: [`raw/status.txt`](raw/status.txt).

**Result.**

| SE.SH | WGP0–2 (CU 0–5) | WGP3–4 (CU 6–9) | `SPI_PG_ENABLE_STATIC_WGP_MASK` | `CC_GC_SHADER_ARRAY_CONFIG` | CUs |
| --- | --- | --- | --- | --- | --- |
| SE0.SH0 | driver + routed | SPI-routed | 0x1f | 0xffe00000 | 10/10 |
| SE0.SH1 | driver + routed | SPI-routed | 0x1f | 0xffe00000 | 10/10 |
| SE1.SH0 | driver + routed | SPI-routed | 0x1f | 0xffe00000 | 10/10 |
| SE1.SH1 | driver + routed | SPI-routed | 0x1f | 0xffe00000 | 10/10 |

Tool summary: `CUs active & routed: 40/40`; `amdgpu: bc250_cc_write_mode=not exposed,
active_cu_number=24`; CPU 16/16 threads online (8c/16t unlock active).

GPU firmware (`amdgpu_firmware_info`): ME 0x63 (feature 32), PFP 0x94 (32), CE 0x25 (32),
MEC and MEC2 0x90 (32), RLC 0x0d, SDMA0/SDMA1 0x34 (feature 50), SMC 88.6.0; VCE, UVD, VCN, PSP
SOS/ASD and TA components report 0 (not loaded on this board).

Kernel log: amdgpu uses its PSP IP block `psp_v11_0_8` (reserves the PSP TMR); no `ccp` message,
i.e. the separate crypto function `1022:143e` is not driven (confirms 0003).

**Verdict.** Answers Q8 at register level: all 40 CUs are enabled for dispatch — 24 known to the
driver (WGP0–2 per shader array) plus 16 added by the SPI mask (WGP3–4). The driver-visible CU map
stays at 24 by design. What remains unmeasured is performance: a throughput test that scales with
CU count would show whether the extra 16 CUs execute waves at full rate; not a phase gate, deferred
to phase 3 where the 36/40 CU switch is measured anyway (D5). Firmware versions recorded for phases
2–3 (PM4 support depends on the CP microcode: ME/PFP/CE/MEC).
