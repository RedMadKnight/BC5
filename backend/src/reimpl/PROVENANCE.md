# Provenance of `backend/src/reimpl` (clean-room re-creations)

This directory holds our own re-creations of three PS5 system modules: `libSceAgc` (249 exports),
`libSceAgcDriver` (175 exports) and `libScePsml` (41 exports). They let the KytyPlus host run a
title without the firmware copies of these modules. The maintainer's rule (2026-11-20) is: by
default BC5's own, unless the game has its own (`select.hpp`):

- BC5's re-creation is used by default, so no module from another game is needed.
- If a title ships its own copy of a module (in its root, `sce_module/` or `sce_modules/`), that copy
  is used for that module instead.
- `BC5_REIMPL_AGC=0`, `BC5_REIMPL_AGCDRIVER=0` or `BC5_REIMPL_PSML=0` opts out and brings back the
  host's previous behaviour (a module pack, else KytyPlus's HLE).

The host logs its choice for each module at start. The host glue is
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
- `libSceAgc` and `libSceAgcDriver` need no module files. Their embedded data is replaced by own
  sources: the register-default tables, CU-ROWS and PRIM-CLASS (`agc_tables.cpp`, written from a
  description of each table's meaning with names from Mesa's `gfx10.json` through the generated
  `agc_regdb.hpp`, `gen_agc_regdb.py`); the driver's default context state (AMD's public MIT
  `amd/clearstate_gfx10.h`, see `amd/README.md`); a one-instruction trap handler
  (`agc_driver_tables.cpp`); and our own fill shader (`shaders/fill16.s`, header in
  `agc_fill_shader.cpp`; machine code still to be assembled on the box, until then the fill
  shader is absent). `BC5_REIMPL_FW_DATA=1` reads the maintainer's own module files instead, where
  present, from the directory named by `BC5_REIMPL_FW_DIR` (default
  `SHADPS4_SYSMODULES_PACK_DIR`); `BC5_REIMPL_FW_COMPARE=1` logs every entry where they differ
  from ours (`data_source.hpp`).
- The register-defaults name tables (register-name hashes with their list/pair codes, which
  titles use to look registers up by name) are not ours to compute: no known hash function
  reproduces them. By default (`BC5_REIMPL_NAME_TABLES=module`) they are read from the module
  file at run time, as above. With the build word `BC5_REIMPL_NAME_TABLES=anyps5` the 16 tables
  of the new-API descriptors come from AnyPS5 (GPL-2.0), file
  `core/libs/prx/libSceAgc/Command/include/RegisterDefaultsData.hpp` at commit `bdff4874`
  (only its name-table arrays; `agc_name_tables_anyps5.cpp` has the full citation). They were
  checked equal to the original module's tables entry for entry; the other 24 descriptors still
  need the module file.
- `libScePsml`'s shader binaries and format tables are still read from the maintainer's module
  file (port-then-load decision of 2026-11-04). They are only reached past its PS5 Pro gate.
- `libScePsml` is the PS5 Pro upscaler. Its network weights live in system-partition package
  files, not in the module, and every entry point refuses unless the kernel reports PS5 Pro mode.
  The re-creation implements the full API and these refusals. The upscale itself cannot run on
  the BC-250: it needs the Pro GPU's shader binaries and the package files.

## Tests

`backend/tests/reimpl/` checks each export against the description: packet dwords, sizes, error
paths, and ioctl sequences seen through fake imports. The tests use synthetic data only.
