# Vendored register and packet tables

- `gfx10.json`, `pkt3.json`: Mesa `src/amd/registers/` at commit `fe554882e4f06cdd2579a77b37b04de605111a28` (2026-09-29), unmodified. Copyright 2017-2019 Advanced Micro Devices, Inc. and Mesa contributors; MIT licence (see `LICENSE-MIT`, Mesa `docs/license.rst`).
- `gfx10.json` is parsed at run time (`src/regdb.rs`): every `register_mappings[]` entry with `"to": "mm"` gives a register at MMIO dword index `map.at / 4` (`map.at` is a byte address), with its `register_types` fields and `enums`.
- `pm4-opcodes.tsv`: derived from Mesa `src/amd/common/sid.h` (same commit, MIT) by `regen.sh` — every `PKT3_*` define with a value <= 0xff, first name per opcode.
- `extra-registers.tsv`: hand-written additions with a source comment per entry (currently the four `COMPUTE_STATIC_THREAD_MGMT_SE*` registers, taken from Mesa `src/amd/common/ac_cmdbuf.c` at the same commit).

These files are data, not code written for BC5; they keep their upstream licence.
