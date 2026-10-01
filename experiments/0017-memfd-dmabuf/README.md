# 0017 — A memfd range as GPU memory: udmabuf, dma-buf import, GPU VA == guest VA (ADR 0006)

**Question.** Can the pages of a memfd — how upstream KytyPlus backs the guest's direct memory —
be given to `amdgpu` on the BC-250 as imported dma-bufs mapped at the address of a `MAP_SHARED`
view, so that the GPU and the guest work on the same pages without userptr BOs, and does a
submission that lists such BOs avoid the per-submission page walk that costs 27 ms per CS with
5.4 GB of userptr mappings (experiment 0016, runs 80–81, F38)?

**Setup.** BC-250 dev box, 2026-10-01, kernel `7.2.4-ogc3.1.fc44`, libdrm 2.4.134, Mesa 26.2.2,
VRAM carve-out 512 MiB, GTT 7,966,150,656 bytes, `ttm.pages_limit` 1,944,861; `/dev/udmabuf`
`crw-rw----+` (uaccess ACL; readable and writable for the user, also inside the `ubuntu`
distrobox), udmabuf `list_limit` 1024, `size_limit_mb` 64.

- `backend/experiments/dmabuf-min` (built with `BC5_WITH_AMDGPU=ON` in the `fedora` distrobox): a
  memfd (`MFD_ALLOW_SEALING`, sealed `F_SEAL_SHRINK`) viewed `MAP_SHARED` at 0x6000000000, one page
  touched per chunk; per chunk `UDMABUF_CREATE` → `amdgpu_bo_import` (dma-buf fd) →
  `amdgpu_bo_va_op(MAP)` at the view's address. `--import` stops there (no ring is touched);
  `--submit` runs the ADR 0004 memset dispatch into chunk 0 through its guest address, verifies it
  through the view, fills half of it again next to CPU-written data, and times a 16-NOP CS that
  lists every chunk against one that lists as many userptr BOs over anonymous memory.
- The host: `KYTY_BC5_DMABUF=1` (KytyPlus seals its direct-memory memfd and hands out the fd;
  `bc5LleAgc.cpp` imports 2 MiB chunks holding data, merged into BOs of up to 32 MiB, and maps
  them at the views' addresses; `Device::import_memfd` / `map_shared`), first in `maponly` (no
  submission), then live.

**Result.**

*Import only* (`raw/import-only.txt`, no submission): the import works. 8 × 32 MiB: `UDMABUF_CREATE`
7.0 ms per chunk (it allocates and pins the chunk: 0.22 ms per MiB), amdgpu import 0.03 ms, VA map
0.03 ms; the imported BO reports heap GTT (0x2). 128 × 2 MiB: 0.45 ms, 0.01 ms, 0.006 ms. The
view's contents are untouched by the import.

*Chunk size* (experiment 0016 host, `BC5_DIRECT_CHUNK_STATS=1`, anonymous backing, `maponly`, no
hint windows, 150 s into the game, 3,634 MiB resident): memory pinned if every chunk with a
resident page is backed in full — 64 KiB: 3,640 MiB (58,232 chunks); 1 MiB: 3,870 MiB; 2 MiB:
4,062 MiB (2,031 chunks); 8 MiB: 4,944 MiB; 32 MiB: 8,032 MiB. 2 MiB it is (ADR 0006).

*The game on the new backing, no submission* (`KYTY_BC5_DMABUF=1`, `maponly`, 150 s; capture
`kytyplus-20261001-1033`): KytyPlus runs on its upstream memfd views; the host imports 290 BOs,
4,922 MiB pinned (the game's data plus the learned regions and hint windows), 364 GPU mappings
over 80 views, no failed import or map. The userptr path is left with 73 anonymous VMAs, 652 MiB,
370 MiB resident. The forced mapping sync takes 2.2 ms on average (11 ms on the anonymous
backing). 48 flips, as on the anonymous backing in `maponly`.

*`dmabuf-min --submit`* (11:10–11:14, `raw/submit.txt`, `raw/submit-2.txt`): the GPU writes the
imported memory and the guest-side view sees it — the ADR 0004 memset dispatch through the view's
address fills chunk 0 with 0 of 8,388,608 (32 MiB) or 524,288 (2 MiB) dwords wrong; a second fill
of half the chunk next to data the CPU wrote through the view leaves both halves right. (The
first version of the tool reused one command BO for both fills and, with 2 MiB chunks, the GPU
ran the first IB again from a stale copy — F25 once more; `raw/submit.txt` shows that failure,
`raw/submit-2.txt` the fixed tool with one command BO per IB.) What a 16-NOP CS costs, median of
50, by what is on its BO list:

| listed | 256 MiB in 8 BOs | 256 MiB in 128 BOs | 2,048 MiB in 1,024 BOs |
|---|---|---|---|
| nothing else | 0.004 ms | 0.007 ms | 0.007 ms |
| imported dma-bufs | 0.006 ms | 0.049 ms | **0.257 ms** |
| userptr BOs | 1.05 ms | 1.13 ms | **10.5 ms** |

Userptr costs about 5 ms per GiB whatever the BO count (the page walk); an imported dma-buf
costs about 0.25 µs per BO and nothing per byte. The first CS that lists the imports is slow once
(3–48 ms: the binding).

*The game live on the new backing* (11:15, run 89 in experiment 0016's numbering): **the machine
went down** — the SSH session was reset during the run and the box stopped answering. Post-mortem
pending its power cycle.

**Verdict.** Open: the mechanism works in isolation (import, GPU access both ways, a CS forty times cheaper); the game on it took the machine down, cause not yet known.
