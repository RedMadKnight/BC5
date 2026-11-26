# 0439 design: presenting the third title's DCC display buffers on the direct path

Status: accepted by the top session 2026-11-21 (option (a)); built privately (README result 10). The top session asked for (b) first, (a) as the fallback, a switch,
an offline test, and what a wrong result looks like.

## 1. What the title registers (box run n4, KytyPlus's own LOGF, normal `b1b57df9`)

- `sceVideoOutRegisterBuffers2` twice: `pixel_format` 0x8000000022000000 (a second set 0x8100000022000000), 3840×2160,
  `tiling_mode` 0, `option` 8, `category` 1 (compressed), `dcc_control` 0x208, `dcc_cb_register_clear_color` 0.
- Buffers: data 0x5005160000 / metadata 0x5007168000, data 0x5007190000 / metadata 0x5009198000. The metadata sits
  0x2008000 bytes behind its surface. Both are in the title's 3.4 GB direct view at 0x5000000000 (batch map, prot 0xf3,
  GPU ReadWrite), so the GPU writes them and the CPU never does.
- KytyPlus f266548 `src/graphics/host_gpu/renderer/image/imageInfo.h:357-375` (`ClassifyVideoOutCompression`) maps
  0x208 to `Dcc256_64_64` and 0x48 to `Dcc256_256_0`. Anything else is `Unsupported`.
- 0x208 against Mesa's gfx10 register file (Mesa `0866ae7085c1`, `src/amd/registers/gfx10.json`,
  `CB_COLOR0_DCC_CONTROL`, which is also the `dcc_control` layout here; TODO(verify) that the video-out attribute uses
  the CB register's layout):
  - MAX_UNCOMPRESSED_BLOCK_SIZE (bits 3:2) = 2: 256B;
  - MAX_COMPRESSED_BLOCK_SIZE (bits 6:5) = 0: 64B;
  - INDEPENDENT_64B_BLOCKS (bit 9) = 1;
  - INDEPENDENT_128B_BLOCKS (bit 20) = 0.
- Why it stops today: the present path in direct mode (patch 0001, `FlipQueue::Prepare`) invalidates only the
  surface range, not the metadata. It then calls the stock `PrepareFrame`, which reaches KytyPlus's TextureCache VideoOut
  lookup. That lookup refuses a compressed surface it did not render itself (`textureCache.cpp:1240-1249`, exit 65). On
  the direct path amdgpu wrote the surface, so no native image exists. Nothing in the patch handles DCC (no decompress,
  no guest-memory import).
- Still open: does the title leave the surface compressed at flip? TODO(verify) in step L1 below, from the CB_COLOR*
  block of its last draw into the surface (CB_COLOR0_INFO.DCC_ENABLE bit 28, ATTRIB3 COLOR_SW_MODE bits 18:14,
  META_LINEAR bit 13, DCC_PIPE_ALIGNED bit 30; offsets in `gfx10.json`: CB_COLOR0_BASE 0x28c60, INFO 0x28c70, DCC_CONTROL
  0x28c78, DCC_BASE 0x28c94, ATTRIB2 0x28ec0, ATTRIB3 0x28ee0, CB_COLOR_CONTROL 0x28808).

## 2. (b) sampling or scanning out the guest surface with its DCC: not open on this chip

- Sampling: Mesa `src/amd/common/ac_surface.c`, `is_dcc_supported_by_L2`, around line 2460, says that on
  `CHIP_NAVI10 || CHIP_GFX1013` "Only independent 128B blocks are supported". The title's surface uses independent 64B
  blocks with no 128B blocks. So the texture path of our chip cannot read it compressed, and RADV would not make such an
  image samplable.
- Scan-out: the same file, `gfx10_DCN_requires_independent_64B_blocks` (around line 2495), says that for 4K, DCN wants
  exactly this shape (64B independent, 64B max compressed). That is what the console's display engine reads. We present
  through a Vulkan swapchain under KWin, not by our own DCN plane, so scan-out of guest memory is out of reach. An
  import would also need a dma-buf of the guest memory, which is in userptr/memfd-backed BOs. TODO(verify) that amdgpu
  refuses to export those.
- Verdict: (b) is closest to the console, but this GPU's texture path cannot do it and our display path cannot reach
  DCN. No (b) build.

## 3. (a) one in-place DCC decompress on the GFX ring before the present

What RADV does: Mesa `src/amd/vulkan/meta/radv_meta_fast_clear.c`, `radv_decompress_dcc` (around line 573). On the
general queue it draws over the image with `custom_blend_mode = V_028808_CB_DCC_DECOMPRESS_GFX8` (lines 127-130), which
is CB_COLOR_CONTROL.MODE = 6 (`CBMode` CB_DCC_DECOMPRESS in `gfx10.json`). Then it flushes CB and CB metadata
(`AC_BARRIER_SYNC_AND_INV_CB | AC_BARRIER_SYNC_AND_INV_CB_META`). The CB reads the compressed data itself, so the L2
limit of section 2 does not apply. The pixels' values are unchanged and only their encoding changes, so the title can
keep rendering into the buffer the next frame. TODO(verify) the metadata state after a graphics-queue decompress: RADV
re-clears DCC to "uncompressed" only on its compute path (line ~595).

The steps, each behind `BC5_DIRECT_DCC_PRESENT` (unset/0 = today's behaviour; 1 = L1 log only; 2 = L1 + decompress;
lean: only 0 and 2):

- **L1 (catcher, log only).**
  - In the direct path's packet walk of dcb/acb submits (where the DCC base registers 0xa325/0xa3a8 are already scanned
    for VA windows), remember for each registered video-out surface the last full CB_COLOR*n* register block whose BASE
    is data>>8: BASE, VIEW, INFO, ATTRIB, DCC_CONTROL, DCC_BASE, ATTRIB2, ATTRIB3.
  - At each flip, log once per surface: DCC_ENABLE, COMPRESSION, COLOR_SW_MODE, META_LINEAR, DCC_PIPE_ALIGNED, and
    whether DCC_BASE equals the registered metadata. This answers the open question in section 1 with no GPU risk.
- **D (decompress).**
  - At the flip, after `Bc5Gc::Direct::drain()` and before `VideoOutSubmitFlip`, submit one small IB on the GFX ring.
  - The IB writes the captured CB_COLOR0 block (MRT0 only), CB_TARGET_MASK 0xf, CB_SHADER_MASK 0xf, CB_COLOR_CONTROL
    MODE 6, and a full-surface viewport and scissor. It draws one RECTLIST through a 3-vertex VS that makes the corners
    from the vertex id, and a PS that exports nothing useful (as RADV's noop fragment shader).
  - Then it does an EVENT_WRITE with CB and CB metadata flush and invalidate, and waits for its own fence.
  - The two shaders are assembled for gfx1013 with the distrobox's `llvm-mc` (21.1.8). Their bytes go in the source
    with the assembly beside them.
  - The present then treats the surface as uncompressed: in direct mode, `FlipQueue::Prepare` invalidates the surface
    and its metadata, and the ImageInfo handed to `PrepareFrame` carries `compression = Uncompressed`. The surface's
    bytes are now plain.
- **Cost.** One 4K pass over ~33 MB, read and write at the CB. The order is well under 1 ms of GPU time at this chip's
  memory bandwidth (TODO(measure) in the first run, from its fence). Plus one fence wait at a flip that has already
  drained. It runs once per presented frame, on the GFX ring, after the title's work and before the CPU upload.
- **Where it sits.** `Bc5LleVideoOut::SubmitEopFlip` (patch 0001), both the drain path and the
  `BC5_DIRECT_FLIP_DEFER` path. With the defer, the decompress goes in the posted flip, after the frame's last job.

## 4. Tests

- Offline (laptop, no GPU):
  - (1) the CB-block catcher on synthetic packet streams: SET_CONTEXT_REG runs that set MRT0..7 with and without the
    surface's base, a later rebinding, packets cut at the end;
  - (2) the IB builder: the register writes and their order, MODE 6, the draw packet's dword count, and that nothing
    is written outside CB/PA/SPI state;
  - (3) the classification: 0x208 and 0x48 decompress, anything else keeps the refusal;
  - (4) `llvm-mc --arch=amdgcn --mcpu=gfx1013 -show-encoding` gives the shader bytes in the source (run in the
    distrobox).
- Box: the first run of D lasts 30 s with the fault record on (the top's rule for GPU risk), normal build, the private
  anon-eager env (fix 1's stopgap), the kernel log streamed, and reset lines before and after. L1 goes first in the same
  build, as its own run.

## 5. What a wrong result looks like on screen

- Compressed bytes read as plain (decompress missing or ineffective): a mosaic of 8×8-pixel tiles. 256 B uncompressed
  blocks at 4 bytes a pixel are 64 pixels. Smooth areas are partly right, edges are noise. Blocks the DCC keys mark as
  constant show whatever the memory held (black under the eager zero pages).
- The wrong swizzle or metadata alignment for the decompress (pipe-aligned vs not): scrambled tiles with correct colours,
  or a fault/timeout on the GFX ring (the fault record names it).
- Correct: the title's frames, unchanged from frame to frame in static scenes. A second decompress of an uncompressed
  surface must change nothing (a check for the first run: two decompresses in a row, the same bytes).

## 6. Separate, not part of this design

- The title renders at 3840×2160 because that is the resolution we report. A 1080p report would shrink its targets and
  their memory. A separate item for the top session.
