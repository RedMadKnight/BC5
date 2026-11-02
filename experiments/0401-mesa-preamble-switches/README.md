# 0401 — Two registers of Mesa's preamble on their own switches

**Status: built, not run.** Written on 2026-11-02 on the top session's GO, on the maintainer's yes to a test build. The build is CPU only. No game has run on it.

**Question.** A static audit of Mesa's gfx10 start state against 1,347 captured buffers (notes `static-register-audit.md`) found five live registers that neither the title nor the host sets. The direct read needs root, so their values are unknown. Does writing Mesa's value change the hang classes or the frame rate? This experiment only builds the switches for two of the five.

**Setup.** One private normal binary, `~/bc5-work/exp0401/bin/kyty_emulator`: main 029e0d6b's `src/libs/bc5LleAgc.cpp` plus `mesa_preamble_prefix()` (`mkunit0401.py`), compiled with the shared build's own command and linked with the shared objects and archive (`build0401.py`). Shared binaries, archive, tree and launcher are pinned and only read. Private launcher `~/bc5-work/exp0401/play-pkg-0401.sh`: `play-pkg.sh` with its binary and two logs moved (`launcher0401.py`). Saves and settings stay the shared ones.

| Switch, default off | Register | Value | Packet | Source |
|---|---|---|---|---|
| `BC5_DIRECT_CP_COHER_START_DELAY=1` | CP_COHER_START_DELAY, uconfig 0x7b | 0x20 | `SET_UCONFIG_REG` `C0017900 0000007B 00000020` | Mesa 0866ae7 `src/amd/common/ac_cmdbuf.c:60`, `src/amd/registers/gfx10.json` |
| `BC5_DIRECT_SPI_REQ_CTRL_PS=1` | SPI_SHADER_REQ_CTRL_PS, SH 0x30 | 0x7 | `SET_SH_REG` `C0017600 00000030 00000007` | Mesa 0866ae7 `ac_cmdbuf.c:444-446`, `gfx10.json` |

Both go in `prefix_of()` right after `tf_ring_prefix()`, so every drawing job's prefix carries them, in the same packet form as the rings. Unset, empty and `0` are off (`bc5::env_on`). Each writes one journal line at the first prefix, on or off.

**Why the packet is allowed.** `CP_COHER_START_DELAY` sits in the uconfig range, and Mesa's `ac_pm4_set_reg` sends that range as plain `SET_UCONFIG_REG` from a user IB (`src/amd/common/ac_pm4.c:382-383`). It is not in Mesa's privileged list (`ac_pm4.c:34`, `is_privileged_reg`, which uses `COPY_DATA`). This is the same packet the prefix uses for `VGT_HS_OFFCHIP_PARAM` (F785), and `backend/src/dispatch_min.cpp:45` sends this very write. No `COPY_DATA` and no kernel path.

**How it will be read.** Pending. See the top session's plan.

**Result.** Pending.

**Verdict.** Pending.
