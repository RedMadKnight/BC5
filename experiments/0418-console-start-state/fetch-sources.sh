#!/usr/bin/env bash
# BC5 exp 0418: fetch the public sources this experiment cites, at the pinned commits, into <dir>, and print the
# offset, base index and reset value of every register the README names (raw/linux-v7.2-gc-10.1-regs.txt).
# Public files only (Linux GPL-2.0, Mesa MIT, PAL MIT, RPCSX GPL-2.0); nothing is sent but the URLs below.
# usage: fetch-sources.sh <empty dir>
set -eu
D=${1:?an empty directory}
mkdir -p "$D"
LX=https://raw.githubusercontent.com/torvalds/linux/v7.2/drivers/gpu/drm/amd # tag v7.2 = 237a1c39e8df
MESA=https://gitlab.freedesktop.org/mesa/mesa/-/raw/0866ae7
PAL=https://raw.githubusercontent.com/GPUOpen-Drivers/pal/c5e800072a32f68b6ccc4422936d96167c6e0728
RPCSX=https://raw.githubusercontent.com/RPCSX/rpcsx/e8ae148
get() { curl -fsSL -o "$D/$1" "$2"; }
get gfx_v10_0.c "$LX/amdgpu/gfx_v10_0.c"
get gmc_v10_0.c "$LX/amdgpu/gmc_v10_0.c"
get amdgpu_ib.c "$LX/amdgpu/amdgpu_ib.c"
get gc_10_1_0_offset.h "$LX/include/asic_reg/gc/gc_10_1_0_offset.h"
get gc_10_1_0_default.h "$LX/include/asic_reg/gc/gc_10_1_0_default.h"
get mesa-ac_cmdbuf.c "$MESA/src/amd/common/ac_cmdbuf.c"
get mesa-radv_queue.c "$MESA/src/amd/vulkan/radv_queue.c"
get pal-gfx9QueueContexts.cpp "$PAL/src/core/hw/gfxip/gfx9/gfx9QueueContexts.cpp"
get pal-settings_gfx9.json "$PAL/src/core/hw/gfxip/gfx9/settings_gfx9.json"
get pal-gfx9_plus_merged_default.h "$PAL/src/core/hw/gfxip/gfx9/chip/gfx9_plus_merged_default.h"
get rpcsx-gc.cpp "$RPCSX/rpcsx/iodev/gc.cpp"
NAMES="GRBM_GFX_CNTL CP_COHER_START_DELAY SPI_SHADER_REQ_CTRL_PS GE_MIN_VTX_INDX GE_MAX_VTX_INDX GE_INDX_OFFSET
VGT_INSTANCE_BASE_ID GE_CNTL GE_PC_ALLOC GE_USER_VGPR_EN GE_STEREO_CNTL CP_STRMOUT_CNTL PA_SU_LINE_STIPPLE_VALUE
PA_SC_LINE_STIPPLE_STATE TA_CS_BC_BASE_ADDR VGT_TF_RING_SIZE_UMD VGT_HS_OFFCHIP_PARAM_UMD VGT_TF_MEMORY_BASE_UMD
VGT_TF_MEMORY_BASE_HI_UMD VGT_ESGS_RING_SIZE_UMD VGT_GSVS_RING_SIZE_UMD VGT_TF_RING_SIZE VGT_HS_OFFCHIP_PARAM
VGT_TF_MEMORY_BASE VGT_TF_MEMORY_BASE_HI VGT_ESGS_RING_SIZE VGT_GSVS_RING_SIZE SPI_CONFIG_CNTL SPI_CONFIG_CNTL_REMAP
GB_ADDR_CONFIG SQ_CONFIG SQ_ARB_CONFIG PA_SC_ENHANCE TA_CNTL_AUX GCR_GENERAL_CNTL DB_DEBUG DB_DEBUG3 DB_DEBUG4
CB_HW_CONTROL_3 CB_HW_CONTROL_4 UTCL1_CTRL GE_FAST_CLKS CP_SD_CNTL VGT_GS_MAX_WAVE_ID SPI_WCL_PIPE_PERCENT_GFX
SH_MEM_CONFIG SH_MEM_BASES GDS_VMID0_BASE GDS_VMID0_SIZE GDS_GWS_VMID0 GDS_OA_VMID0 PA_SC_TILE_STEERING_OVERRIDE"
echo "# Linux v7.2 include/asic_reg/gc: register, dword offset, BASE_IDX (gc_10_1_0_offset.h), reset value and its line (gc_10_1_0_default.h)"
for n in $NAMES; do
  o=$(awk -v r="mm$n" '$1 == "#define" && $2 == r {print $3}' "$D/gc_10_1_0_offset.h")
  b=$(awk -v r="mm${n}_BASE_IDX" '$1 == "#define" && $2 == r {print $3}' "$D/gc_10_1_0_offset.h")
  dl=$(awk -v r="mm${n}_DEFAULT" '$1 == "#define" && $2 == r {print NR ":" $3; exit}' "$D/gc_10_1_0_default.h")
  printf '%-30s %-8s %-3s default %s\n' "$n" "${o:-absent}" "${b:--}" "${dl:-absent}"
done
