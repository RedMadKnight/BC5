# 0003 — dev box inventory

**Question.** What kernel, Mesa/RADV, libdrm and toolchain versions does the BC-250 dev box run,
does the kernel carry the BC-250 PSP/CCP patch series, and what memory, storage and clocks are
available? (HANDOFF Q7; docs/PHASES.md phase 0b task 1.)

**Setup.** BC-250 on Bazzite, `fedora` distrobox. Run [`collect.sh`](collect.sh) from inside the
container; it only reads (`uname`, `glxinfo -B`, `vulkaninfo --summary`, `pkg-config`, `lspci`,
`free`, `lsblk`, `dmesg` filtered for amdgpu/psp/ccp, sysfs clock and VRAM files, compiler
versions) and writes `raw/inventory.txt`. Nothing is changed on the system.

```sh
distrobox enter fedora -- experiments/0003-dev-box-inventory/collect.sh
```

Run 2026-09-29 over SSH, without root. `dmesg` is not readable without root, so the kernel log was
read with `journalctl -k -b` (allowed for the user); CU and SE counts were read with
`RADV_DEBUG=info vulkaninfo --summary`. Tools installed in the container for the run:
`mesa-demos vulkan-tools pciutils` (and the build tools used by experiment 0002). `glxinfo` is not in
`mesa-demos` on Fedora 44, so the GL line is missing; Vulkan covers the same ground.

**Result.** Raw output in [`raw/inventory.txt`](raw/inventory.txt); the kernel-log and RADV lines
below were collected with the commands named above.

| Item | Value |
| --- | --- |
| Host OS | Bazzite 44.20260919.0 (Kinoite), immutable |
| Kernel | `7.2.4-ogc3.1.fc44.x86_64` (PREEMPT_DYNAMIC, 2026-09-13) |
| Container | Fedora 44 (`fedora` distrobox) |
| Mesa / RADV | Mesa 26.2.3; Vulkan 1.4.354; device name **`AMD BC-250 (RADV GFX1013)`**, integrated GPU; `gfx_level = 12` (GFX10, not GFX10.3), `family = 79` |
| libdrm / libdrm_amdgpu | 2.4.134 |
| GPU PCI | `01:00.0` `1002:13fe` "Cyan Skillfish [BC-250]" |
| Shader engines / CUs | kernel: `SE 2, SH per SE 2, CU per SH 10, active_cu_number 24`; RADV: `num_se = 2`, `num_cu = 24`, `num_cu_per_sh = 10`, `num_rb = 16` → **24 of 40 CUs active** |
| PSP | amdgpu's own IP block `psp_v11_0_8` is initialised (reserves the PSP TMR); the separate crypto function `01:00.2` `1022:143e` has **no driver bound** (`ccp` loaded but not attached) |
| SMU / VBIOS | SMU fw 88.6.0 (if version 8); VBIOS `113-AMDRBN-003` |
| Memory | 7.5 GiB visible to Linux + 3.7 GiB zram swap; VRAM carve-out 8192 MiB (BAR 8192 MiB) |
| GPU clocks (`pp_dpm_sclk`) | 100 MHz (idle, current) / 1000 MHz / 2000 MHz |
| CPU | 16 threads |
| Storage | NVMe Fanxiang S501Q 512 GB; 307 GB free on `/var/home` |
| Toolchain (container) | rustc/cargo 1.98.1, GCC 16.2.1, CMake 4.3.0, fuse3 3.18.2 |
| Kernel oddity | `pci 0000:00:00.0: cyan-skillfish-: Unexpected write to kernel-exclusive config offset b8` at boot |

**Verdict.** Answers Q7. Two findings change assumptions in `CLAUDE.md` and the roadmap:

1. **Only 24 of 40 CUs are active**, not the 40 assumed at handoff ("GPU unlocked to 40 CU"). The
   36/4 CU split of decision D5 is not possible until the unlock works again; with 24 CUs the PS5's
   36-CU timing cannot be matched. Recorded as HANDOFF Q8. Changing this is a firmware/kernel
   configuration matter for the maintainer, not for a script.
2. **The PSP crypto function has no driver**: the "BC-250 PSP/CCP patch series" is either absent from
   this kernel or not binding `1022:143e`. Nothing in phases 0–3 depends on it.

Everything else matches the plan: RADV identifies the chip as GFX1013 with GFX10 (not 10.3) rules
(HANDOFF F1), libdrm_amdgpu 2.4.134 is recent enough for phases 2–3, and the container builds both
the Rust tools and the C++ backend.
