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

*The game live on the new backing* (11:13, run 89 in experiment 0016's numbering; capture
`kytyplus-20261001-1113`, the journal survived, `raw/run89-direct-tail.log`): 7,206 submissions
and 493 flips in 42 s, then one submission timed out and **the machine went down** (reset; the
kernel log of that boot did not reach the disk).

What the 42 seconds show. The backing works under the game: 820 imported BOs, 5,012 MiB pinned,
893 GPU mappings, no failed import or map, no failed submission before the last, the picture as
before (119 distinct display-buffer contents: the fade-in and what follows). And it does what it
was built for:

| | anonymous backing (run 82) | dma-buf backing (run 89) |
|---|---|---|
| CS ioctl, submission that draws | 26.9 ms (1,953 BOs, 5.4 GB userptr) | **2.6 ms** (937 BOs: imports plus 370 MiB userptr) |
| forced mapping sync | 11 ms | 1.8 ms |
| a flip every | 0.35 s | **0.083 s** |
| GPU time per flip (fence waits) | 9.7 ms | 9.1 ms |

Twelve frames a second instead of three, and the game got further than in any run before: at
34 s it opened its first video (the log names an `.mp4` under its own data and starts
`AvPlayerVideoDecoder`), and from then on every frame carries a new 79-dword compute IB that
uploads the decoded frame: one `DMA_DATA` of 12,441,600 bytes (3840×2160 NV12) from a host buffer
to a texture in direct memory, header 0x66304000 — memory to memory, **no `CP_SYNC`**. 182 frames
of that ran; after the 182nd upload IB (fence after 0.02 ms, far less than a 12 MB copy takes)
the next submission, the per-frame state header that had run 490 times, never finished.

The reading: CP DMA is asynchronous, the IB ends and its fence signals with the copy still
running, and `amdgpu` does not wait for it — Mesa says so in as many words and ends every IB with
a zero-byte `DMA_DATA` carrying `CP_SYNC` for that reason (radeonsi `si_cp_dma_wait_for_idle`,
`si_gfx_cs.c`: "Make sure CP DMA is idle at the end of IBs ... because the kernel doesn't wait for
it"; RADV `radv_cp_dma_wait_for_idle`; Mesa 0866ae7). The console's stream relies on its own
kernel. Here the next IB (with its `CLEAR_STATE` and register loads) ran into a copy in flight,
with nothing holding the copy's buffers either. Not the backing's doing: the anonymous backing
never got as far as the video. Fix: `Device::set_dma_idle` (on by default) appends that
zero-byte `DMA_DATA` with `CP_SYNC` to every IB. Unverified until the next GPU run.

Also lost with the machine: the dumps of the last submissions (since run 78 only the journal is
synced per submission), which is why the upload IB above was read from an earlier instance.

**Verdict.** Open: import, GPU access and the cost of a CS are settled (a CS forty times cheaper, the game four times faster); a clean live run with the DMA wait is still owed.
