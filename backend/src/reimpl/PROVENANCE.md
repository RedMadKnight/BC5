# Provenance of `backend/src/reimpl` (clean-room re-creations)

This directory holds our own re-creations of three PS5 system modules: `libSceAgc` (249 exports),
`libSceAgcDriver` (175 exports) and `libScePsml` (41 exports). They let the KytyPlus host run a
title without the firmware copies of these modules. Each module is behind its own switch,
`BC5_REIMPL_AGC`, `BC5_REIMPL_AGCDRIVER` and `BC5_REIMPL_PSML`, all off by default. With a switch
off, the maintainer's own firmware module stays the default. The host glue is
`backend/kytyplus-patches/0002-bc5-reimpl-agc-psml.patch`.

## How the code was made (two-phase clean room)

1. **Phase A, description.** The maintainer's own copies of the three modules were decompiled
   privately with Ghidra 11.4.3 (headless, NSA release) and with `llvm-objdump` from the Visual
   Studio LLVM toolchain. The Ghidra and objdump output stayed outside this repository, with the
   maintainer.
   - Separate writers turned that output into a behavioural description of every export: its
     signature, validation, error codes, memory writes, PM4 packets, ioctl request codes and
     argument layouts, import calls and locks.
   - The writers used their own names and their own wording. Decompiler text and decompiler
     identifiers were not allowed in the description, and a script checked for them.
   - Embedded data (GPU shader binaries, register-default tables) was described by meaning and
     location only.
2. **Phase B, implementation.** Separate implementers wrote the C++ here from the phase-A
   description alone. They never saw the binaries or the decompiler output, and they had no
   access to other emulators' implementations of these modules.
   - Their only hardware reference was Mesa's public `src/amd/common/sid.h` (Mesa @ `ab2374a`),
     for PM4 opcode and register names.
   - Packet layouts and register offsets that come from the original module's behaviour are
     marked as such in the comments. Names we chose ourselves carry `TODO(verify)`.
3. **Other projects' work** (open-source emulators' versions of these libraries) was not used to
   write this code. It may be compared against afterwards, as a cross-check only.

## What is not here

- No decompiled text, no disassembly, no symbol dumps, and no Sony data tables. The only
  exception is a small number of short interoperability constants (packet sizes, a few masks),
  each described in the code as such.
- Data the original modules embed is read at run time from the maintainer's own module files, in
  the directory named by `BC5_REIMPL_FW_DIR` (default `SHADPS4_SYSMODULES_PACK_DIR`). This covers
  `libSceAgc`'s internal shaders and register-default tables and `libScePsml`'s shader binaries.
  It follows the maintainer's port-then-load decision of 2026-11-04. When the directory or file is
  missing, the module fails cleanly with a named error.
- `libScePsml` is the PS5 Pro upscaler. Its network weights live in system-partition package
  files, not in the module, and every entry point refuses unless the kernel reports PS5 Pro mode.
  The re-creation implements the full API and these refusals. The upscale itself cannot run on
  the BC-250: it needs the Pro GPU's shader binaries and the package files.

## Tests

`backend/tests/reimpl/` checks each export against the description: packet dwords, sizes, error
paths, and ioctl sequences seen through fake imports. The tests use synthetic data only.
