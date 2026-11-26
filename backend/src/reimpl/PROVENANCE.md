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
  reproduces them. By default (`BC5_REIMPL_NAME_TABLES=anyps5`) the 16 tables of the new-API
  descriptors come from AnyPS5 (GPL-2.0), file
  `core/libs/prx/libSceAgc/Command/include/RegisterDefaultsData.hpp` at commit `bdff4874`
  (only its name-table arrays; `agc_name_tables_anyps5.cpp` has the full citation). They were
  checked equal to the original module's tables entry for entry. The new-API V0_3 pair
  (descriptors 0x282C0 / 0x28240) holds the same entries as the SoC pair and is served from its
  ported tables (checked equal against the module file).
- **The other 24 name tables follow by rule from the ported 16** (checked equal to the module
  file's tables, all 40, byte for byte, 2026-11-23; fixed checks in
  `agc_system_test.cpp`: entry counts and CRC-32 of every rule-built table). (1) An old-API
  table (20 descriptors) is the new-API table of the same group and kind, entry for entry, same
  hash, the code cut to its low 10 bits (list and cell; no block size), with 8-byte entries
  {hash, code} instead of 12; the old-API and the new-API descriptor of a pair share their list
  fields, so the old one's cells are its partner's. (2) The new-API V11 pair is OTHER's with two
  edits and the cells renumbered in table order: the internal table gains one single-pair context
  block at table position 1, named 0x9E0FEB34; the public table loses the context blocks named
  0xB994AD29 and 0x9E0FEB34 (both hashes are entries of the ported OTHER table; the rules add no
  other constant). In every table the entries come in list order and a list's cells are numbered
  0, 1, 2, ... in table order. What was wrong before (90373b2d to e88782ec): the old-API tables
  were read with a 12-byte stride, which made them look like other names and codes and made a
  register-matching generator "differ" in 1526 entries; read with 8 bytes they are the new-API
  tables. The V11 pair is selected only when the shader-transcoder query answers non-zero; on
  this host it answers 0 (no host function or loaded module provides `wDAAPuG6uN4`; the import
  binds to the module's own foreign-NID stub, which returns 0), and no selector returns the
  old-API V11 pair: both are built for completeness. The hash function itself (64-bit FNV-1a over
  a CamelCase register-group name, folded to 32 bits) was found on the way and is not needed: no
  new name is hashed. With `BC5_REIMPL_NAME_TABLES=module` and `BC5_REIMPL_FW_DATA=1` all 40 are
  read from the module file instead (old-API ones with 8-byte entries).
- **The fourth list has a cell array too** (descriptor + 0x18, internal sets only: 2 or 3 slots,
  one per named block of the 4- or 6-pair shape). Until 2026-11-23 the re-creation pointed the
  field at the pairs, from a misread of run rFV4 (2026-11-21): its probe read four "slots" of a
  three-slot array and took the first pair for the fourth; the module's relocations show the slot
  array.
- `libScePsml`'s shader binaries and format tables are still read from the maintainer's module
  file (port-then-load decision of 2026-11-04). They are only reached past its PS5 Pro gate.
- `libScePsml` is the PS5 Pro upscaler. Its network weights live in system-partition package
  files, not in the module, and every entry point refuses unless the kernel reports PS5 Pro mode.
  The re-creation implements the full API and these refusals. The upscale itself cannot run on
  the BC-250: it needs the Pro GPU's shader binaries and the package files.

## Foreign-NID exports

Each original module's export table also lists NIDs of other libraries, all defined at one
local stub: libSceAgc 9 (4 of `libkernel`, 5 of `libSceShaderTranscode_minimal`, among them
`wDAAPuG6uN4`, the transcoder check the module also imports), libSceAgcDriver 4
(`libSceDbgThreadSanitizer_for_agc_driver`, `libSceLibcInternal`, two of `libkernel`, among them
`aj7wRdAWFeM`, which the driver also imports) and libScePsml 51 (`libSceLibcInternal`,
`libkernel`, `libSceAgc`, `libSceAgcDriver`). The pairs (NID, library) and each one's address
come from the modules' dynamic symbol tables, like the own exports: all 64 point at the
module's stub. The stub's code was read at that address in each module: `xor eax, eax; ret`,
so a call returns 0 and changes nothing. 59 of the 64 are functions; the re-creations export
them at a function that returns 0 (`foreign_nid_stub`, entries flagged `foreign`). 5 of
libScePsml's (libc NIDs) are data objects at the same address: a reader sees the stub's bytes,
the instruction encoding `31 c0 c3` and int3 padding (`cc`) up to the next function 16 bytes
on; ours is a 16-byte object with those bytes (`kForeignStubBytes`).

The host glue (patch 0002) registers foreign entries in a second pass, after every module's own
exports, and only while no HLE function, no loaded module (a game's own copy) and no BC5 module
provides the NID: the stub stays a fallback and never shadows the real provider. A module's own
imports are bound only to an export of the library's owner module, so they never reach the
stub. `export_coverage_test.cpp` compares every export table with the originals' list
(`original_exports.inc`: NIDs, libraries and kinds only) and fails on any missing, extra or
differently-kinded entry: libSceAgc 258/258, libSceAgcDriver 179/179 rows (177 NIDs),
libScePsml 92/92.

## Tests

`backend/tests/reimpl/` checks each export against the description: packet dwords, sizes, error
paths, and ioctl sequences seen through fake imports. The tests use synthetic data only.
