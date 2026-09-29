# Vendored register and packet tables

- `gfx10.json`, `pkt3.json`: Mesa `src/amd/registers/` at commit `fe554882e4f06cdd2579a77b37b04de605111a28` (2026-09-29), unmodified. Copyright 2017-2019 Advanced Micro Devices, Inc. and Mesa contributors; MIT licence (see `LICENSE-MIT`, Mesa `docs/license.rst`).
- `gfx10-registers.tsv`: derived from `gfx10.json` by `regen.sh` — every `register_mappings[]` entry with `"to": "mm"` as `<dword offset>\t<name>`; `map.at` in the JSON is a byte address, the TSV stores `at / 4` (the MMIO dword index PM4 packets use).
- `pm4-opcodes.tsv`: derived from Mesa `src/amd/common/sid.h` (same commit, MIT) by `regen.sh` — every `PKT3_*` define with a value <= 0xff, first name per opcode.
- `extra-registers.tsv`: hand-written additions with a source comment per entry (currently the four `COMPUTE_STATIC_THREAD_MGMT_SE*` registers, taken from Mesa `src/amd/common/ac_cmdbuf.c` at the same commit).

These files are data, not code written for BC5; they keep their upstream licence.
