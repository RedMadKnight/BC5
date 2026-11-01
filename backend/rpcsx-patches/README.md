# RPCSX patches

Small patches against [RPCSX/rpcsx](https://github.com/RPCSX/rpcsx) kept here until they are
upstreamed. Each patch names the commit it was made against; re-check `git apply --check` after
pulling a newer RPCSX.

| Patch | Against | What it does |
| --- | --- | --- |
| `0001-agc-capture-tap.patch` | `e8ae1481` (2026-06-30) | Phase-1 tap (`docs/PHASES.md`, phase 1 task 3). Adds `rpcsx/gpu/bc5_capture.hpp` and two calls: every indirect buffer the graphics command processor is pointed at (`GraphicsPipe::indirectBuffer`) and every packet submitted through `DeviceCtl::submitGfxCommand` is written as raw little-endian dwords to `$BC5_AGC_DUMP_DIR/<seq>-<ib|submit>-lvl<L>-vm<V>-<addr>.pm4`. Off unless the variable is set; no effect on rendering. |

Apply and use:

```sh
cd ~/src/rpcsx
git apply --check /path/to/bc5/backend/rpcsx-patches/0001-agc-capture-tap.patch
git apply         /path/to/bc5/backend/rpcsx-patches/0001-agc-capture-tap.patch
# rebuild, then:
mkdir -p /tmp/agc && BC5_AGC_DUMP_DIR=/tmp/agc ./rpcsx ...
bc5-agc report /tmp/agc/*.pm4
bc5-agc dump   /tmp/agc/000003-ib-lvl0-vm1-*.pm4 --limit 200
```

The patch has not been compiled yet (no C++ toolchain on the machine it was written on); it is
plain C++17 (`<cstdio>`, `<atomic>`) so a build failure would be a typo, not a design problem.
Captured `.pm4` files are command streams, not game assets, but they reference guest addresses of
shader and data buffers; keep them out of the repository except as per-experiment excerpts.
