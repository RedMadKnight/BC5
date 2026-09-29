#!/usr/bin/env bash
# Phase 0b, task 1: record the dev box (docs/PHASES.md, HANDOFF Q7). Run on the
# BC-250 inside the `fedora` distrobox; changes no system setting. Output goes
# to raw/inventory.txt next to this script.
set -u
OUT="$(cd "$(dirname "$0")" && pwd)/raw"
mkdir -p "$OUT"
F="$OUT/inventory.txt"
: > "$F"
run() { echo "## $*" >> "$F"; ("$@" 2>&1 || true) >> "$F"; echo >> "$F"; }
run date -u +%Y-%m-%dT%H:%M:%SZ
run uname -a
run cat /etc/os-release
run sh -c 'cat /run/host/etc/os-release 2>/dev/null || echo "(host os-release not visible)"'
run glxinfo -B
run vulkaninfo --summary
run pkg-config --modversion libdrm_amdgpu
run pkg-config --modversion libdrm
run sh -c 'lspci -nn | grep -Ei "vga|display|3d|1022:143e|psp|ccp"'
run free -h
run lsblk -o NAME,TYPE,SIZE,ROTA,MODEL,MOUNTPOINT
run df -h /
run nproc
run sh -c 'grep -m1 "model name" /proc/cpuinfo'
run sh -c 'dmesg 2>/dev/null | grep -Ei "amdgpu|psp|ccp|bc-250|bc250|gfx1013|cyan" | head -80 || echo "(dmesg not readable without root)"'
run sh -c 'cat /sys/class/drm/card*/device/vbios_version 2>/dev/null'
run sh -c 'cat /sys/class/drm/card*/device/mem_info_vram_total 2>/dev/null'
run sh -c 'for c in /sys/class/drm/card*/device/pp_dpm_sclk; do echo "$c"; cat "$c"; done 2>/dev/null'
run rustc --version
run cargo --version
run gcc --version
run clang --version
run cmake --version
echo "written: $F"
