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

**Result.** *(fill in from `raw/inventory.txt`: kernel version; Mesa version and whether
`vulkaninfo` names the device as gfx1013 / Cyan Skillfish; libdrm_amdgpu version; presence of
PSP/CCP lines in dmesg; RAM and VRAM split; disk type and free space; sclk range; toolchain
versions.)*

**Verdict.** *(pending the run)*
