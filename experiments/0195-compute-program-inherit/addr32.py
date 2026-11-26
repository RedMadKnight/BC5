#!/usr/bin/env python3
# Experiment 0195: the 32-bit VA window a Mesa process gets from libdrm on this box (read-only:
# amdgpu_device_initialize + amdgpu_query_sw_info / DEV_INFO, no command submission).
# libdrm amdgpu.h: amdgpu_sw_info_address32_hi = 0; amdgpu_device_initialize(fd, &major, &minor, &dev).
import ctypes
import os

lib = ctypes.CDLL("libdrm_amdgpu.so.1")
fd = os.open("/dev/dri/renderD128", os.O_RDWR)
major, minor = ctypes.c_uint32(), ctypes.c_uint32()
dev = ctypes.c_void_p()
r = lib.amdgpu_device_initialize(fd, ctypes.byref(major), ctypes.byref(minor), ctypes.byref(dev))
val = ctypes.c_uint32()
r2 = lib.amdgpu_query_sw_info(dev, 0, ctypes.byref(val))
print("amdgpu_device_initialize rc %d (drm %d.%d); address32_hi rc %d = 0x%08x" % (r, major.value, minor.value, r2, val.value))
print("COMPUTE_PGM_HI as Mesa writes it: S_00B834_DATA(0x%x >> 8) = 0x%x" % (val.value, (val.value >> 8) & 0xFF))
print("window start: 0x%016x; +0x5000 seen by the GPU (48 bits): 0x%012x" % (val.value << 32 & 0xFFFF000000000000 | (val.value << 32 & 0xFFFFFFFF00000000), ((val.value << 32) + 0x5000) & 0xFFFFFFFFFFFF))
lib.amdgpu_device_deinitialize(dev)
os.close(fd)
