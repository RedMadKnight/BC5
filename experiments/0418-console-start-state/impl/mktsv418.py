import sys

# Writes backend/policy/start-state.tsv (tab-separated, LF). Run: python mktsv418.py <out path>
head = """# BC5 start-state table (experiment 0418 section 4): what the console's system sets up for a title, and how the host
# meets each item on the BC-250 under amdgpu. Rows of kind constant or request are written by the host from a user IB
# (backend/include/bc5/start_state.hpp holds the same rows; backend/tests/start_state_test.cpp checks that they agree).
# Rows of kind elsewhere are met by the kernel, the BO list or the code rewrite; they are here so that one file says how
# every item is met.
# The table is always on (the top session's dispositions of 2026-11-13). BC5_DIRECT_START_STATE_SKIP=<names> drops rows
# (a diagnostic). The switch column names a switch that still acts on a row; the old one-row switches are gone.
# Columns (tab-separated):
#   name	space	offset	value	kind	status	how	switch	source	finding
# space: uconfig (SET_UCONFIG_REG offset) | sh (SET_SH_REG offset) | - ; offset: hex packet offset of the first register
# value: hex for constant rows; the /dev/gc request for request rows; - otherwise
# kind: constant | request | elsewhere
# status: cited (a source says the console sets it, or the title asks) | measured (the umr read of 2026-11-13 in play,
#   exp 0418 impl/README.md result 1) | unknown (the console's value is not known)
# how: prefix (first in every job's prefix) | cam (the _UMD address the kernel remaps, written with the rings) |
#   kernel | bo-list | code-rewrite | host-answer
# Sources: Linux v7.2 (237a1c39) gfx_v10_0.c, gmc_v10_0.c, gc_10_1_0_offset.h, gc_10_1_0_default.h; Mesa 0866ae7
#   src/amd/common/ac_cmdbuf.c, src/amd/vulkan/radv_queue.c; PAL c5e80007; RPCSX e8ae148 rpcsx/iodev/gc.cpp;
#   shadPS4 60c42b9 src/core/libraries/gnmdriver/gnmdriver.cpp."""

rows = [
    ("CP_COHER_START_DELAY", "uconfig", "0x07b", "0x00000020", "constant", "measured", "prefix",
     "-",
     "reset 0x20 gc_10_1_0_default.h:3638; Mesa ac_cmdbuf.c:60; PAL gfx9QueueContexts.cpp:155-165",
     "exp 0401; measured 0x20 in play (umr 2026-11-13); the reset value"),
    ("SPI_SHADER_REQ_CTRL_PS", "sh", "0x030", "0x00000007", "constant", "measured", "prefix",
     "-",
     "reset 0 :2074; Mesa ac_cmdbuf.c:444-446; PAL settings_gfx9.json:1386-1397",
     "exp 0401; measured 0x7 in play (umr 2026-11-13): the Mesa clients on the shared gfx ring write it"),
    ("GE_MIN_VTX_INDX", "uconfig", "0x249", "0x00000000", "constant", "measured", "prefix", "-",
     "reset 0 :3745; Mesa ac_cmdbuf.c:599; PAL gfx9QueueContexts.cpp:1827-1830",
     "exp 0418 section 2"),
    ("GE_MAX_VTX_INDX", "uconfig", "0x259", "0xffffffff", "constant", "measured", "prefix", "-",
     "reset 0 :3761; Mesa ac_cmdbuf.c:608; PAL gfx9QueueContexts.cpp:1817-1826",
     "measured ~0 in play (umr 2026-11-13): the Mesa clients write it; the reset value is 0"),
    ("VGT_INSTANCE_BASE_ID", "uconfig", "0x25a", "0x00000000", "constant", "measured", "prefix", "-",
     "reset 0 :3762; Mesa ac_cmdbuf.c:609",
     "exp 0418 section 2"),
    ("VGT_TF_RING", "uconfig", "0x24e", "0x80108128", "request", "cited", "cam", "-",
     "VGT_TF_RING_SIZE_UMD 0x224e, VGT_TF_MEMORY_BASE_UMD 0x2250, _HI_UMD 0x2261; CAM gfx_v10_0.c:7296-7475",
     "F207, F208, F248: without it every tessellated patch is culled"),
    ("VGT_HS_OFFCHIP_PARAM", "uconfig", "0x24f", "0x8004812a", "request", "cited", "cam", "-",
     "VGT_HS_OFFCHIP_PARAM_UMD 0x224f; CAM gfx_v10_0.c:7296-7475",
     "F785, F786: the night lake's holes"),
    ("VGT_GS_RINGS", "uconfig", "0x240", "0xc00c8110", "request", "cited", "cam", "-",
     "VGT_ESGS_RING_SIZE_UMD 0x2240, VGT_GSVS_RING_SIZE_UMD 0x2241; RPCSX gc.cpp:295-307; radv_queue.c:372-374",
     "exp 0418: the ports rule; no title of ours asks (exps 0189, 0418 traces); unit taken as bytes (TODO(verify))"),
    ("SH_MEM_BASES", "-", "-", "-", "elsewhere", "cited", "code-rewrite", "BC5_DIRECT_FLAT_APERTURE",
     "amdgpu private 0x1000, shared 0x2000: gmc_v10_0.c:623-626, gfx_v10_0.c:5366-5375",
     "F249, F250: per VMID, privileged; the title's FLAT code is rewritten instead"),
    ("SH_MEM_CONFIG", "-", "-", "-", "elsewhere", "unknown", "kernel", "-",
     "gfx_v10_0.c:3668-3672, written at :5369",
     "none known; UNALIGNED is the permissive mode (inferred)"),
    ("GDS_GWS_OA", "-", "-", "-", "elsewhere", "cited", "bo-list", "-",
     "none at init gfx_v10_0.c:5236-5253; per IB :7794-7821; backend/include/bc5/direct.hpp:85-95",
     "F32: 64 KiB GDS, 16 OA, 64 GWS on every BO list"),
    ("GB_ADDR_CONFIG", "-", "-", "-", "elsewhere", "unknown", "kernel", "-",
     "golden 0x44 gfx_v10_0.c:3596; driver copy 0x00100044 :3675, :4620",
     "exp 0237: 16 pipes decode the title's depth"),
    ("GOLDEN_SET", "-", "-", "-", "elsewhere", "unknown", "kernel", "-",
     "the other 33 golden registers of GC 10.1.3, gfx_v10_0.c:3581-3616",
     "none known; the console's set cannot be known without a console"),
    ("SPI_CONFIG_CNTL", "-", "-", "-", "elsewhere", "unknown", "kernel", "-",
     "reset 0xc062c688 :1298; the CAM's seventh row, SPI_CONFIG_CNTL_REMAP 0x2440",
     "none known; the console's value is not known, so no row writes it"),
    ("PA_SC_TILE_STEERING_OVERRIDE", "-", "-", "-", "elsewhere", "cited", "kernel", "-",
     "gfx_v10_0.c:5134-5170, clear state :6416-6418",
     "computed for this chip's RBs; the kernel's value is the right one"),
    ("CLEAR_STATE", "-", "-", "-", "elsewhere", "unknown", "kernel", "-",
     "gfx10_cs_data, gfx_v10_0.c:6396-6425",
     "the title or host sets 602 of the 603 context registers (exp 0401's audit)"),
    ("CU_MASKS", "-", "-", "0xc010810b", "elsewhere", "cited", "host-answer", "-",
     "RPCSX gc.cpp:322-337",
     "answered with all ones; the host masks the CU registers itself (F7, F39a, pm4-policy.tsv)"),
]

out = [head]
for r in rows:
    assert len(r) == 10, r
    assert all("\t" not in c and "\n" not in c for c in r), r
    out.append("\t".join(r))
data = ("\n".join(out) + "\n").encode("utf-8")
open(sys.argv[1], "wb").write(data)
print(len(rows), "rows,", len(data), "bytes")
