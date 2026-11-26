# Third-party file: AMD gfx10 clear state

`clearstate_gfx10.h` is copied unchanged from the Linux kernel, `drivers/gpu/drm/amd/amdgpu/clearstate_gfx10.h`, at tag `v6.12`:

- source: <https://raw.githubusercontent.com/torvalds/linux/v6.12/drivers/gpu/drm/amd/amdgpu/clearstate_gfx10.h>
- tag object: `06090c9b622a7e1f797e775db4c035e0d779b76e`
- sha256: `e6ca3544dd51a657d9200243be9e6d05c4dcfa052a239dadebbc6cd7409e64cd`

The file is Copyright 2019 Advanced Micro Devices, Inc. and keeps its MIT licence header, which is in the file.

The re-created libSceAgcDriver uses it as the default context-register state. That state is the
input to `sceAgcDriverTmpInitIdhs` / `sceAgcDriverPatchClearState`: 8 ranges, 921 registers.
The file was downloaded with the maintainer's approval on 2026-11-20. A private check that day
found all 921 values equal to the defaults the maintainer's own driver module embeds, so no
Sony data is needed. The comparison itself is not in this repository.
