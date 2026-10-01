# 0006 — The guest's direct memory reaches the GPU as dma-bufs of KytyPlus's memfd, not as userptr

**Status.** Accepted, 2026-10-01: the maintainer chose "option 3" of experiment 0016's
frame-time verdict (get rid of the per-submission userptr walk); this ADR picks the variant and
amends ADR 0005 §1 (the BO/VA mapper) for direct memory. Experiment 0017 passed the same day:
`KYTY_BC5_DMABUF=1` is the backing to run with; the userptr path of ADR 0005
(`KYTY_BC5_ANON_BACKING=1`) remains for comparison.

**Context.** With the game's first screens on the BC-250 (F37), a frame costs 0.35 s and the GPU
is busy for 10 ms of it (F38, F39). A submission that draws lists every mapping, and
`DRM_IOCTL_AMDGPU_CS` revalidates each listed userptr BO by walking its user pages: 27 ms with
5.4 GB mapped, seven times a frame. The walk is inherent to userptr (the pages are ordinary
anonymous memory that may move between submissions); it cannot be skipped safely, only avoided.
Two facts about the track-B host make that possible:

- 12.4 GB of the guest's 13.1 GB are *direct memory* (experiment 0016, range survey: 68 direct
  ranges; flexible, stack, module and runtime memory together are 0.65 GB). Everything the GPU
  is given by the game — command buffers, render targets, textures, buffers, labels — lives there.
- Upstream KytyPlus already keeps direct memory in one object: a memfd of the pool's size, with
  `MAP_SHARED | MAP_FIXED` views at the guest's addresses, one per mapped range, at the range's
  physical offset. Track B replaced the views by anonymous mappings only because userptr refuses
  file-backed pages (experiment 0014), and paid for it: no aliases between views, a workaround for
  views that are re-protected, `KYTY_BC5_ALL_RW` for read-only views.

**Decision.** Keep KytyPlus's memfd and its views as they are upstream, and give the GPU the
memfd's pages directly:

1. KytyPlus creates the memfd with `MFD_ALLOW_SEALING` and seals it `F_SEAL_SHRINK`
   (`KYTY_BC5_DMABUF=1`), and hands the fd to the host.
2. The host turns ranges of the memfd into dma-bufs with `/dev/udmabuf` (`UDMABUF_CREATE`) and
   imports each into amdgpu (`amdgpu_bo_import`, dma-buf fd): a GTT-domain BO backed by the very
   pages the guest's views map (`Device::import_memfd`).
3. Each imported range is mapped into the GPU VM at the address of every view that covers it
   (`Device::map_shared`; `amdgpu_bo_va_op_raw` with an offset into the BO): GPU VA == guest VA,
   as in ADR 0005, aliases included.
4. A submission lists those BOs like any other. Nothing is walked: an imported dma-buf's pages
   are pinned by the exporter for the BO's lifetime.

What is imported, and in which pieces: udmabuf pins — and so allocates — every page of a range it
exports, so the unit must be small enough not to materialise the pool's untouched parts and large
enough to keep the BO count down. Measured on the game at 150 s (3,634 MiB resident, no hint
windows): backing every chunk that has a resident page costs 3,640 MiB at 64 KiB, 3,870 MiB at
1 MiB, **4,062 MiB at 2 MiB (2,031 chunks)**, 4,944 MiB at 8 MiB, 8,032 MiB at 32 MiB. The host
imports 2 MiB chunks that hold data inside a view (`lseek(SEEK_DATA)` on the memfd, skipping what
is already imported) and merges adjacent chunks into BOs of at most 32 MiB (the udmabuf module's
`size_limit_mb` is 64). Render-target hint windows and learned fault regions (ADR 0005 xii–xiii)
force the chunks they cover, since the GPU writes there before the CPU does. Once imported, a
chunk needs no further attention however the guest writes into it.

The anonymous rest of the guest — stacks, module data, flexible memory, the host's own register
shadow area — stays on the userptr path. With the direct views file-backed, that path no longer
sees them: its scan covers 0.65 GB of VMAs instead of 13 GB.

**Alternatives considered.**

- *GEM BOs mapped into the guest* (BOs allocated from amdgpu, `mmap`ed at the guest's addresses
  from the DRM fd). TTM populates a BO as a whole, so chunks would have to be created on first
  touch, i.e. behind `PROT_NONE` and a fault handler or `userfaultfd` — and a guest `read()` into
  untouched direct memory then fails with `EFAULT` inside the kernel instead of faulting the page
  in. It also replaces KytyPlus's memory backing instead of using it. Rejected.
- *Leaving BOs off the list.* Done where it is safe (ADR 0005 xx: submissions without draws).
  For a submission that draws, an unlisted userptr BO's GPU page-table entries may point at pages
  the kernel has since taken back. Rejected.
- *`mlock` and hoping pages do not move.* Compaction and khugepaged still migrate. Rejected.

**Consequences.**

- Needs `/dev/udmabuf` readable and writable by the user (on the dev box: `uaccess` ACL, also
  inside the `ubuntu` distrobox) and a kernel whose amdgpu imports udmabuf dma-bufs (7.2 here;
  experiment 0017).
- Imported chunks are pinned: they cannot be swapped, and they count against the GTT domain
  (7.97 GB here, `ttm.pages_limit` 7.4 GiB). At the opening card the game pins 4.9 GB including
  ~1.3 GB of hint and learned windows. A level that touches more than the limit needs smaller
  windows, unmapping of what is no longer used, or a higher limit (a boot parameter: the
  maintainer's call).
- The track-B workarounds for anonymous views (`KYTY_BC5_ANON_BACKING`, the re-protection fix,
  `KYTY_BC5_ALL_RW` for direct memory) are not needed in this mode; aliases work again.
- A device reopen after a ring reset (ADR 0005 xiii) drops the imports; the host imports again.
- `policy::FilterOptions::mapped` and the short lists (ADR 0005 xx) see imported ranges and
  userptr mappings alike (`Device::mappings`).
- Still a userptr walk per drawing submission for the anonymous rest (0.37 GB resident here).
  If it shows in the numbers, the next step is to find out which of it the GPU needs at all.
