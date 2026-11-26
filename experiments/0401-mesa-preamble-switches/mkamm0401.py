#!/usr/bin/env python3
"""BC5 experiment 0401, series e4 (the maintainer's rule: ports are judged for any title): AnyPS5's AMM PRT commands,
the other AMM commands this host lacks and the AMPR waits (exp 0402 survey section 2, Ampr row), ported from AnyPS5
(github.com/boykopovar/AnyPS5, GPL-2.0-only) at 4f41f4c375f5abb487dbd184fbc150f31994d762 with e3b5192cb, 79fc99774 and
37881a5da: core/libs/prx/libkernel/Apr/src/Apr.cpp, core/libs/prx/libkernel/DirectMemory/DirectMemory.cpp:1284-1293 and
core/libs/prx/libSceAmpr/Export.cpp. Three switches, each default off, on when set, non-empty and not "0", read once:
  KYTY_BC5_AMM_PRT_CMDS    MapAsPrt, AllocatePaForPrt, RemapIntoPrt, UnmapToPrt and the two PRT measures (6 NIDs)
  KYTY_BC5_AMM_EXTRA_CMDS  Remap, MultiMap, ModifyProtect, ModifyMtypeProtect, their GpuMaskId forms, 8 measures (16)
  KYTY_BC5_AMPR_WAITS      WaitOnAddress, WaitOnCounter and their measures (4), with AnyPS5's counters behind the
                           registered WriteCounter / WaitOnCounter / WriteAddressFromCounter forms
Off: the 26 NIDs stay unregistered (the loader's stub) and today's code runs; the only change is three stderr lines.
Edits src/libs/libAmpr.cpp only (tree md5 a0e2ff6e6fcbcae83847107243b35319). memory.cpp needs no change: the PRT zero
pages use KernelReserveVirtualRange, KernelSetVirtualRangeName and an mprotect of the reserved placeholder, so
--memory <memory.cpp> is accepted, read and left alone (a line on stderr says so). Every anchor must occur exactly once;
an edited input is refused. Each NID is checked against its name with exp 0327's calculator (nid0401.py's), and so is
every NID in amm0401.cpp when that file sits beside this script. Prints "<md5>  <relpath>" for the output.
Not ported, reasons in amm0401-notes.md: libkernel's sceKernelWriteMapCommand2, sceKernelWriteUnmapToPrtCommand and
sceKernelWriteRemapIntoPrtCommand (AnyPS5 has no sceKernelWriteMapAsPrtCommand).
usage: mkamm0401.py <tree root in> <out dir> [--memory <memory.cpp>]"""
import hashlib
import os
import pathlib
import re
import sys

REL = "src/libs/libAmpr.cpp"
TREE_MD5 = "a0e2ff6e6fcbcae83847107243b35319"
MARKS = (b"KYTY_BC5_AMM_PRT_CMDS", b"KYTY_BC5_AMM_EXTRA_CMDS", b"KYTY_BC5_AMPR_WAITS", b"Bc5AmmPage", b"series e4")

SALT = bytes.fromhex("518d64a635ded8c1e6b039b1c3e55230")
CODES = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-"


def nid(name):
    """exp 0327's calculator (nid0401.py): SHA-1 of the name and the salt, first 8 bytes little-endian, 64 symbols."""
    digest = int.from_bytes(hashlib.sha1(name.encode() + SALT).digest()[:8], "little")
    return "".join(CODES[(digest >> (58 - i * 6)) & 63] for i in range(10)) + CODES[(digest & 15) * 4]


# (NID, console name, our function, AnyPS5 Export.cpp @ 4f41f4c37 line of the definition). Registered only with the switch.
PRT = (
    ("ZJCgt+aPHAU", "sceAmprAmmCommandBufferMapAsPrt", "Bc5AmmCommandBufferMapAsPrt", 868),
    ("d3lKWPM6odc", "sceAmprAmmCommandBufferAllocatePaForPrt", "Bc5AmmCommandBufferAllocatePaForPrt", 875),
    ("0Xo9g4goDXU", "sceAmprAmmCommandBufferRemapIntoPrt", "Bc5AmmCommandBufferRemapIntoPrt", 883),
    ("3A2X6OCHtnA", "sceAmprAmmCommandBufferUnmapToPrt", "Bc5AmmCommandBufferUnmapToPrt", 891),
    ("4SSJ+cn+Pvg", "sceAmprAmmMeasureAmmCommandSizeMapAsPrt", "Bc5MeasureAmmCommandSizeMapAsPrt", 899),
    ("2yYv9QWB3hU", "sceAmprAmmMeasureAmmCommandSizeAllocatePaForPrt", "Bc5MeasureAmmCommandSizeAllocatePaForPrt", 903),
)
EXTRA = (
    ("ijvRMHfwwjc", "sceAmprAmmCommandBufferRemap", "Bc5AmmCommandBufferRemap", 795),
    ("Fo0Oaoqukg4", "sceAmprAmmCommandBufferRemapWithGpuMaskId", "Bc5AmmCommandBufferRemapWithGpuMaskId", 799),
    ("j2C9no3P4Nw", "sceAmprAmmCommandBufferMultiMap", "Bc5AmmCommandBufferMultiMap", 804),
    ("Qyz8VbxnaII", "sceAmprAmmCommandBufferMultiMapWithGpuMaskId", "Bc5AmmCommandBufferMultiMapWithGpuMaskId", 808),
    ("joNORJjCFhg", "sceAmprAmmCommandBufferModifyProtect", "Bc5AmmCommandBufferModifyProtect", 813),
    ("spjcxyNX-KE", "sceAmprAmmCommandBufferModifyProtectWithGpuMaskId", "Bc5AmmCommandBufferModifyProtectWithGpuMaskId", 817),
    ("rKq9nG+L9Xo", "sceAmprAmmCommandBufferModifyMtypeProtect", "Bc5AmmCommandBufferModifyMtypeProtect", 822),
    ("ie-UuLGbYXo", "sceAmprAmmCommandBufferModifyMtypeProtectWithGpuMaskId", "Bc5AmmCommandBufferModifyMtypeProtectWithGpuMaskId", 826),
    ("8sFq5s8eHnQ", "sceAmprAmmMeasureAmmCommandSizeRemap", "Bc5MeasureAmmCommandSizeRemap", 831),
    ("b50TWwRmzu8", "sceAmprAmmMeasureAmmCommandSizeRemapWithGpuMaskId", "Bc5MeasureAmmCommandSizeRemapWithGpuMaskId", 835),
    ("U6PxwrRchl4", "sceAmprAmmMeasureAmmCommandSizeMultiMap", "Bc5MeasureAmmCommandSizeRemap", 840),
    ("uGs4yyYTASM", "sceAmprAmmMeasureAmmCommandSizeMultiMapWithGpuMaskId", "Bc5MeasureAmmCommandSizeRemapWithGpuMaskId", 844),
    ("JPQagYw-y+4", "sceAmprAmmMeasureAmmCommandSizeModifyProtect", "Bc5MeasureAmmCommandSizeModifyProtect", 849),
    ("gdSoJ6dvztU", "sceAmprAmmMeasureAmmCommandSizeModifyProtectWithGpuMaskId", "Bc5MeasureAmmCommandSizeModifyProtectWithGpuMaskId", 853),
    ("Ok2Nxka7qI4", "sceAmprAmmMeasureAmmCommandSizeModifyMtypeProtect", "Bc5MeasureAmmCommandSizeModifyMtypeProtect", 858),
    ("c5D63Y35GjI", "sceAmprAmmMeasureAmmCommandSizeModifyMtypeProtectWithGpuMaskId", "Bc5MeasureAmmCommandSizeModifyMtypeProtectWithGpuMaskId", 863),
)
WAITS = (
    ("V7GQTEeUfhw", "sceAmprCommandBufferWaitOnAddress", "Bc5CommandBufferWaitOnAddress", 338),
    ("FrCNL9TQ8ms", "sceAmprCommandBufferWaitOnCounter", "Bc5CommandBufferWaitOnCounter", 343),
    ("jIlc4p5dSD0", "sceAmprMeasureCommandSizeWaitOnAddress", "Bc5MeasureCommandSizeWait", 382),
    ("6jLL5BIZ88U", "sceAmprMeasureCommandSizeWaitOnCounter", "Bc5MeasureCommandSizeWait", 383),
)
# Registered today; with KYTY_BC5_AMPR_WAITS on, the first is registered as a function of AnyPS5's signature
# (buffer, counter, value) and the others record what their names say (their bodies branch on the switch).
WAITS_SWAP = ("3wn42MWTzTs", "sceAmprCommandBufferWriteCounterOnCompletion", "Bc5WriteCounterOnCompletion", 332)
WAITS_CHANGED = (
    ("cQb8Zr8Q0Y0", "sceAmprCommandBufferWaitOnCounter_04_00"),
    ("jK+yuYCI7MA", "sceAmprCommandBufferWriteCounter_04_00"),
    ("t4ExS+SwLjs", "sceAmprCommandBufferWriteAddressFromCounter_04_00"),
    ("gSF5OsXdfIg", "sceAmprCommandBufferWriteAddressFromCounterOnCompletion"),
    ("enZm-6GjWqw", "sceAmprCommandBufferWriteAddressFromCounterPair_04_00"),
    ("ZLWtNUP6R5E", "sceAmprCommandBufferWriteAddressFromCounterPairOnCompletion"),
)

# ---- the include ------------------------------------------------------------------------------------------------------
INC_OLD = b"#include <unordered_map>\n#include <vector>\n"
INC_NEW = INC_OLD + b"#include <sys/mman.h> // experiment 0401 series e4: mprotect of the AMM PRT zero pages\n"

# ---- the command record: the new AMM kinds and fields, the counter commands --------------------------------------------
KIND_OLD = b"enum class AmmCommandKind : uint32_t {\n\tMapAuto,\n\tMapDirect,\n\tUnmap,\n};\n"
KIND_NEW = b"""enum class AmmCommandKind : uint32_t {
\tMapAuto,
\tMapDirect,
\tUnmap,
\t// experiment 0401 series e4 (comment before ExecuteAmmMapCommand): recorded only with their switch on
\tMapAsPrt,
\tUnmapToPrt,
\tAllocatePaForPrt,
\tRemapIntoPrt,
\tRemap,
\tMultiMap,
\tModifyProtect,
\tModifyMtypeProtect,
};
"""
FIELDS_OLD = b"\t\tuint8_t        gpu_mask_id   = 0;\n\t};\n"
FIELDS_NEW = (b"\t\tuint8_t        gpu_mask_id   = 0;\n"
              b"\t\tuint64_t       source        = 0; // experiment 0401 series e4: Remap, MultiMap, RemapIntoPrt\n"
              b"\t\tint32_t        mask          = 0; // experiment 0401 series e4: the protection mask; RemapIntoPrt's opcode\n"
              b"\t};\n")
LISTS_OLD = b"\tstd::vector<WaitAddressCommand>  wait_address_commands;\n"
LISTS_NEW = LISTS_OLD + b"""\t// experiment 0401 series e4 (KYTY_BC5_AMPR_WAITS): a counter write, a counter wait or an address write from a
\t// counter, with AnyPS5's fields (Apr::WriteCounterCommand, Apr::WaitCommand, Apr::WriteAddressFromCounterCommand)
\tstruct Bc5CounterCommand {
\t\tuint64_t record_offset = 0;
\t\tuint8_t  kind          = 0; // 0 write, 1 wait, 2 address from the counter, 3 address from the counter pair
\t\tuint8_t  counter       = 0;
\t\tuint8_t  access        = 1; // Apr::CounterAccess: 0 64 bits, 1 32, 2-3 16, 4-7 8
\t\tuint8_t  operation     = 0; // Apr::CounterOperation: store, or, and-not, xor, add
\t\tuint8_t  compare       = 0; // _waitSatisfied's codes 0-6
\t\tuint64_t value         = 0; // what is written, or the wait's reference
\t\tuint64_t mask          = ~uint64_t {0};
\t\tuint64_t address       = 0;
\t};
\tstd::vector<Bc5CounterCommand> bc5_counter_commands;
"""
CLEAR_OLD = b"\tstate.wait_address_commands.clear();\n"
CLEAR_NEW = CLEAR_OLD + b"\tstate.bc5_counter_commands.clear(); // experiment 0401 series e4\n"

# ---- before ExecuteAmmMapCommand: the comment, the switches, the forward declarations ---------------------------------
EARLY_ANCHOR = b'extern "C" void bc5_watch_surface(uint64_t va); // bc5LleAgc.cpp, experiment 0104\n'
EARLY = b"""// ---- experiment 0401 series e4: the AMM commands this host lacked and the AMPR waits (exp 0402 survey, section 2) ----
// Ported from AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only; the ported semantics keep its authors' copyright) at
// 4f41f4c375f5abb487dbd184fbc150f31994d762, with e3b5192cb, 79fc99774 and 37881a5da:
//   core/libs/prx/libkernel/Apr/src/Apr.cpp, the executor: _clearPrt, _requirePrt, _zeroPrt, _ammUnmap, _ammMapAsPrt,
//     _ammUnmapToPrt and _ammAllocatePrt (407-478), _ammMap (480-505), _ammRemap (507-526), _ammProtect (528-546), the
//     counters and _waitSatisfied (196-267) and the waits in _execute (649-662);
//   core/libs/prx/libkernel/DirectMemory/DirectMemory.cpp:1284-1293 (DoMapZero: zero pages, readable only);
//   core/libs/prx/libSceAmpr/Export.cpp, the recorders, their checks and measures (148-166, 241-316, 326-384, 587-618,
//     795-906).
// Three switches, each default off: on when set, non-empty and not "0", read once at the library's registration, which
// writes one stderr line each, "[bc5] exp 0401: <switch> on|off". Off, their NIDs stay unregistered (the loader's stub
// answers, as before) and every function below runs today's code.
//   KYTY_BC5_AMM_PRT_CMDS: MapAsPrt, AllocatePaForPrt, RemapIntoPrt, UnmapToPrt and the two PRT measures. The unbacked
//     pages of a PRT range read 0 on the CPU: the range stays reserved ("AMM") in the host's books and its placeholder
//     is made PROT_READ, so its pages are the kernel's anonymous zero page (never writable; AnyPS5 37881a5da keeps one
//     read-only section for the same reason). The GPU side sees no mapping there, so BC5_DIRECT_AMM_PRT's PRT pages
//     answer the GPU (reads 0, writes dropped; AnyPS5's notes say GPU writes fault: F161, F257, neither proven).
//     AllocatePaForPrt backs only the unbacked runs (the backed ones take the new type and protection); a run whose
//     backing fails goes back to the pool and to zero pages (e3b5192cb, 79fc99774), runs backed before it in the same
//     command stay backed, as in AnyPS5. A plain map or unmap over a PRT range ends it; a PRT command outside one fails.
//   KYTY_BC5_AMM_EXTRA_CMDS: Remap, MultiMap, ModifyProtect, ModifyMtypeProtect (the GpuMaskId forms ignore the id) and
//     their eight measures. A remap moves a fully mapped range's pages and returns the source to the reservation; a
//     multimap maps them a second time; a pool page returns to the pool with its last mapping (AnyPS5's pooledUses).
//   KYTY_BC5_AMPR_WAITS: sceAmprCommandBufferWaitOnAddress and WaitOnCounter (the forms without _04_00) and their
//     measures, on AnyPS5's 256 32-bit counters; with it on WriteCounter_04_00, WriteCounterOnCompletion,
//     WaitOnCounter_04_00 and the four WriteAddressFromCounter forms do what they say (today: a no-op record, or 0).
// With PRT or EXTRA on, every AMM map, unmap and remap goes through one lock and a page table (AnyPS5's AmmState).
// Adapted: this host keeps the commands host-side, so the new kinds join AmmMapCommand and the counter commands get a
// list of their own; the record sizes are this host's (0x20 for a PRT range, as Unmap's; 0x30 for a remap or a
// protection change; 0x20 for the counter records, as today's; TODO(verify) the console's); pool pages come from
// today's first-fit pool, which borrows direct memory when no run is free (AnyPS5 maps scattered pool pages and never
// borrows). Not ported: libkernel's sceKernelWriteMapCommand2, sceKernelWriteUnmapToPrtCommand and
// sceKernelWriteRemapIntoPrtCommand, which write packed command bytes for a byte-decoding executor and libkernel's own
// submit, neither of which this host has (amm0401-notes.md). CPU tests: experiments/0401-mesa-preamble-switches/amm0401.cpp.
constexpr uint64_t BC5_AMM_PRT_RECORD_SIZE      = 0x20; // MapAsPrt, UnmapToPrt: an address and a size, as Unmap
constexpr uint64_t BC5_AMM_REMAP_RECORD_SIZE    = 0x30; // Remap, MultiMap, RemapIntoPrt: two addresses, size, protection
constexpr uint64_t BC5_AMM_PROTECT_RECORD_SIZE  = 0x30; // ModifyProtect, ModifyMtypeProtect, AllocatePaForPrt
constexpr uint64_t BC5_AMPR_COUNTER_RECORD_SIZE = 0x20; // the waits and the counter records, today's size
constexpr int32_t  BC5_PRT_ALLOCATION_MASK      = 1019; // AnyPS5 Export.cpp:277 PrtAllocationMask (recorded, unused)

static bool Bc5Exp0401Switch(const char* name) {
\tconst char* e = std::getenv(name);
\tconst bool  v = e != nullptr && e[0] != '\\0' && std::strcmp(e, "0") != 0;
\tstd::fprintf(stderr, "[bc5] exp 0401: %s %s\\n", name, v ? "on" : "off");
\treturn v;
}
static bool Bc5AmmPrtCmdsOn() {
\tstatic const bool on = Bc5Exp0401Switch("KYTY_BC5_AMM_PRT_CMDS");
\treturn on;
}
static bool Bc5AmmExtraCmdsOn() {
\tstatic const bool on = Bc5Exp0401Switch("KYTY_BC5_AMM_EXTRA_CMDS");
\treturn on;
}
static bool Bc5AmprWaitsOn() {
\tstatic const bool on = Bc5Exp0401Switch("KYTY_BC5_AMPR_WAITS");
\treturn on;
}
// The AMM page table (maps, unmaps and remaps through Bc5ExecuteAmm0401) runs with either AMM switch on.
static bool Bc5AmmPagesOn() {
\treturn Bc5AmmPrtCmdsOn() || Bc5AmmExtraCmdsOn();
}
static int ExecuteAmmMapCommandToday(const CommandBufferState::AmmMapCommand& command);
static int Bc5ExecuteAmmMap0401(const CommandBufferState::AmmMapCommand& command);
static int Bc5ExecuteAmm0401(const CommandBufferState::AmmMapCommand& command);
static int Bc5RunCounterCommand0401(const CommandBufferState::Bc5CounterCommand& command);
static int Bc5WaitOnCounter0401(void* command_buffer, uint8_t counter, uint8_t access, uint64_t reference, uint8_t compare,
                                uint8_t mask_operation, uint64_t mask, uint8_t flush);
static int Bc5WriteCounter0401(void* command_buffer, uint8_t counter, uint8_t access, uint64_t value, uint8_t operation,
                               uint32_t at_start);
static int Bc5WriteAddressFromCounter0401(void* command_buffer, volatile uint64_t* address, uint8_t counter, bool pair,
                                          bool completion);

"""

# ---- ExecuteAmmMapCommand: with an AMM switch on it goes through the page table first ----------------------------------
MAP_OLD = b"""static int ExecuteAmmMapCommand(const CommandBufferState::AmmMapCommand& command) {
\tif (!ValidateAmmMapArgs(command.va, command.size)) {
"""
MAP_NEW = b"""static int ExecuteAmmMapCommand(const CommandBufferState::AmmMapCommand& command) {
\tif (Bc5AmmPagesOn()) { // experiment 0401 series e4: AnyPS5's _ammMap order, then today's map, then the page table
\t\treturn Bc5ExecuteAmmMap0401(command);
\t}
\treturn ExecuteAmmMapCommandToday(command);
}

static int ExecuteAmmMapCommandToday(const CommandBufferState::AmmMapCommand& command) {
\tif (!ValidateAmmMapArgs(command.va, command.size)) {
"""

# ---- the ordered run: the counter commands, and the new AMM kinds --------------------------------------------------------
CKIND_OLD = b"\tAmmMap,\n\tWaitAddress,\n};\n"
CKIND_NEW = b"\tAmmMap,\n\tWaitAddress,\n\tBc5Counter, // experiment 0401 series e4 (KYTY_BC5_AMPR_WAITS)\n};\n"
RUN_OLD = b"""\t\t\tcase CommandKind::AmmMap: {
\t\t\t\tconst auto& command = state.amm_map_commands[entry.index];
\t\t\t\tint         result  = OK;
\t\t\t\tif (command.kind == AmmCommandKind::Unmap) {
"""
RUN_NEW = b"""\t\t\tcase CommandKind::Bc5Counter: { // experiment 0401 series e4 (KYTY_BC5_AMPR_WAITS): AnyPS5's counters
\t\t\t\tconst auto& command = state.bc5_counter_commands[entry.index];
\t\t\t\tconst int   run     = Bc5RunCounterCommand0401(command);
\t\t\t\tif (run == 1) { // a wait not met yet: the buffer stops here, as at a WaitOnAddress
\t\t\t\t\t*next = pos;
\t\t\t\t\treturn false;
\t\t\t\t}
\t\t\t\tif (run != 0) {
\t\t\t\t\t*execution_result = LibKernel::KERNEL_ERROR_EFAULT;
\t\t\t\t\t*error_offset     = static_cast<uint32_t>(command.record_offset);
\t\t\t\t\t*next             = ordered.size();
\t\t\t\t\treturn true;
\t\t\t\t}
\t\t\t} break;
\t\t\tcase CommandKind::AmmMap: {
\t\t\t\tconst auto& command = state.amm_map_commands[entry.index];
\t\t\t\tint         result  = OK;
\t\t\t\t// experiment 0401 series e4: the new kinds, and an unmap while the AMM page table runs
\t\t\t\tif (command.kind > AmmCommandKind::Unmap || (command.kind == AmmCommandKind::Unmap && Bc5AmmPagesOn())) {
\t\t\t\t\tresult = Bc5ExecuteAmm0401(command);
\t\t\t\t} else if (command.kind == AmmCommandKind::Unmap) {
"""
ORDER_OLD = b"""\tfor (size_t i = 0; i < state.wait_address_commands.size(); i++) {
\t\tif (state.wait_address_commands[i].record_offset < state.write_offset) {
\t\t\tordered.push_back({state.wait_address_commands[i].record_offset, CommandKind::WaitAddress, i});
\t\t}
\t}
"""
ORDER_NEW = ORDER_OLD + b"""\tfor (size_t i = 0; i < state.bc5_counter_commands.size(); i++) { // experiment 0401 series e4 (empty when off)
\t\tif (state.bc5_counter_commands[i].record_offset < state.write_offset) {
\t\t\tordered.push_back({state.bc5_counter_commands[i].record_offset, CommandKind::Bc5Counter, i});
\t\t}
\t}
"""

# ---- the registered counter functions: with KYTY_BC5_AMPR_WAITS on they record what they say ----------------------------
WOC_OLD = b"""\t\t             reinterpret_cast<uint64_t>(command_buffer), c0, c1, v, c3, c4, v2, c6);
\t}

\treturn AppendNoOpCommand(command_buffer, 0x20);
}
"""
WOC_NEW = b"""\t\t             reinterpret_cast<uint64_t>(command_buffer), c0, c1, v, c3, c4, v2, c6);
\t}
\tif (Bc5AmprWaitsOn()) { // experiment 0401 series e4: a counter wait (AnyPS5 Export.cpp:587-591)
\t\treturn Bc5WaitOnCounter0401(command_buffer, c0, c1, v, c3, c4, v2, c6);
\t}

\treturn AppendNoOpCommand(command_buffer, 0x20);
}
"""
WC_OLD = b"""static int KYTY_SYSV_ABI CommandBufferWriteCounter(void* command_buffer, uint8_t, uint8_t, uint64_t,
                                                   uint8_t, uint32_t) {
\tPRINT_NAME();

\treturn AppendNoOpCommand(command_buffer, 0x20);
}
"""
WC_NEW = b"""static int KYTY_SYSV_ABI CommandBufferWriteCounter(void* command_buffer, uint8_t counter, uint8_t access,
                                                   uint64_t value, uint8_t operation, uint32_t at_start) {
\tPRINT_NAME();
\tif (Bc5AmprWaitsOn()) { // experiment 0401 series e4: a counter write (AnyPS5 Export.cpp:614-618)
\t\treturn Bc5WriteCounter0401(command_buffer, counter, access, value, operation, at_start);
\t}

\treturn AppendNoOpCommand(command_buffer, 0x20);
}
"""
# (old, new) for the four WriteAddressFromCounter forms: (pair, completion) as AnyPS5 Export.cpp:306-316, 593-599 records them
WAFC = []
for name, pair, completion, sig_old, sig_new in (
    ("CommandBufferWriteAddressFromCounter", "false", "at_start == 0",
     b"""static int KYTY_SYSV_ABI CommandBufferWriteAddressFromCounter(void*              command_buffer,
                                                              volatile uint64_t* address, uint8_t,
                                                              uint32_t) {
""",
     b"""static int KYTY_SYSV_ABI CommandBufferWriteAddressFromCounter(void*              command_buffer,
                                                              volatile uint64_t* address, uint8_t counter,
                                                              uint32_t at_start) {
"""),
    ("CommandBufferWriteAddressFromCounterOnCompletion", "false", "true",
     b"""static int KYTY_SYSV_ABI CommandBufferWriteAddressFromCounterOnCompletion(
    void* command_buffer, volatile uint64_t* address, uint8_t) {
""",
     b"""static int KYTY_SYSV_ABI CommandBufferWriteAddressFromCounterOnCompletion(
    void* command_buffer, volatile uint64_t* address, uint8_t counter) {
"""),
    ("CommandBufferWriteAddressFromCounterPair", "true", "at_start == 0",
     b"""static int KYTY_SYSV_ABI CommandBufferWriteAddressFromCounterPair(void*              command_buffer,
                                                                  volatile uint64_t* address,
                                                                  uint8_t, uint32_t) {
""",
     b"""static int KYTY_SYSV_ABI CommandBufferWriteAddressFromCounterPair(void*              command_buffer,
                                                                  volatile uint64_t* address,
                                                                  uint8_t counter, uint32_t at_start) {
"""),
    ("CommandBufferWriteAddressFromCounterPairOnCompletion", "true", "true",
     b"""static int KYTY_SYSV_ABI CommandBufferWriteAddressFromCounterPairOnCompletion(
    void* command_buffer, volatile uint64_t* address, uint8_t) {
""",
     b"""static int KYTY_SYSV_ABI CommandBufferWriteAddressFromCounterPairOnCompletion(
    void* command_buffer, volatile uint64_t* address, uint8_t counter) {
"""),
):
    body = b"\tPRINT_NAME();\n\n\treturn AppendWriteAddressCommand(command_buffer, address, uint64_t {0}, 0x20);\n}\n"
    new_body = (b"\tPRINT_NAME();\n"
                b"\tif (Bc5AmprWaitsOn()) { // experiment 0401 series e4: the counter's value, not 0\n"
                b"\t\treturn Bc5WriteAddressFromCounter0401(command_buffer, address, counter, " + pair.encode() + b", "
                + completion.encode() + b");\n\t}\n\n"
                b"\treturn AppendWriteAddressCommand(command_buffer, address, uint64_t {0}, 0x20);\n}\n")
    WAFC.append((name, sig_old + body, sig_new + new_body))

# ---- after the library's functions: the page table, the commands, the recorders ----------------------------------------
LATE_ANCHOR = b"} // namespace Ampr\n\nLIB_DEFINE(InitAmpr_1_Ampr) {\n"
LATE = b"""// ---- experiment 0401 series e4: the AMM page table, the PRT ranges, the new commands, the counters and the recorders
// (the comment before ExecuteAmmMapCommand). AnyPS5 Apr.cpp / Export.cpp @ 4f41f4c37 names in brackets. ----

struct Bc5AmmPage {
\tuint64_t dmem  = 0; // the direct memory behind the page
\tint32_t  type  = 0;
\tint32_t  prot  = 0;
\tuint8_t  owner = 0; // BC5_PAGE_TITLE, BC5_PAGE_AUTO or BC5_PAGE_COUNTED
};
constexpr uint8_t BC5_PAGE_TITLE   = 0; // the title's own direct memory (MapDirect): never returned to the pool
constexpr uint8_t BC5_PAGE_AUTO    = 1; // a pool page held by today's g_amm_auto_maps (one mapping)
constexpr uint8_t BC5_PAGE_COUNTED = 2; // a pool page held by g_bc5_pool_uses since a remap or a multimap [pooledUses]

static std::recursive_mutex           g_bc5_amm_mutex; // [AmmState::lock]
static std::map<uint64_t, Bc5AmmPage> g_bc5_amm_pages; // the va of each mapped 16 KiB page -> its backing [pages]
static std::map<uint64_t, uint32_t>   g_bc5_pool_uses; // the dmem of a counted pool page -> its mappings [pooledUses]
static std::map<uint64_t, uint64_t>   g_bc5_prt;       // the PRT ranges, start -> end, merged [prt]
static std::atomic<uint32_t>          g_bc5_fail_backing {0}; // test seam (amm0401.cpp): the n-th next PRT backing fails
static uint64_t                       g_bc5_journal_zero = 0; // under g_bc5_amm_mutex
static uint64_t                       g_bc5_journal_back = 0;
static uint64_t                       g_bc5_journal_fail = 0;

static bool Bc5JournalDue(uint64_t n) { // the first 32, then every 256th
\treturn n <= 32 || n % 256 == 0;
}

// Today's rule for an AMM page's host protection (ExecuteAmmMapCommand, experiment 0035): no CPU bits means host read/write.
static int Bc5HostProt(int32_t prot) {
\tint host = NormalizeAmmProtection(prot);
\tif ((host & (PROT_CPU_READ | PROT_CPU_WRITE)) == 0) {
\t\thost |= PROT_CPU_READ | PROT_CPU_WRITE;
\t}
\treturn host;
}

static bool Bc5ValidProt(int32_t prot) { // [Apr::ValidAmmProtection]: CPU, GPU, AMPR and ACP read and write only
\treturn (static_cast<uint32_t>(prot) & 0xFFFFFC0Cu) == 0;
}

static bool Bc5ValidRemap(uint64_t va, uint64_t source, uint64_t size, int32_t prot) { // [Apr::ValidRemap]
\treturn ValidateAmmMapArgs(va, size) && ValidateAmmMapArgs(source, size) && Bc5ValidProt(prot);
}

static bool Bc5ValidProtect(uint64_t va, uint64_t size, int32_t prot, int32_t mask) { // [Apr::ValidProtect]
\treturn ValidateAmmMapArgs(va, size) && Bc5ValidProt(prot) && Bc5ValidProt(mask);
}

static bool Bc5InAmmWindow(uint64_t va, uint64_t size) { // [_ammCheckRange]: inside the reserved AMM window
\tconst uint64_t start = AmmWindowStartIfReserved();
\treturn start != 0 && ValidateAmmMapArgs(va, size) && va >= start && size <= AMM_VA_SIZE &&
\t       va - start <= AMM_VA_SIZE - size;
}

// ---- the PRT ranges [prt] ----
static void Bc5PrtAdd(uint64_t start, uint64_t end) {
\tauto it = g_bc5_prt.upper_bound(start);
\tif (it != g_bc5_prt.begin()) {
\t\tconst auto prev = std::prev(it);
\t\tif (prev->second >= start) {
\t\t\tstart = prev->first;
\t\t\tend   = std::max(end, prev->second);
\t\t\tit    = g_bc5_prt.erase(prev);
\t\t}
\t}
\twhile (it != g_bc5_prt.end() && it->first <= end) {
\t\tend = std::max(end, it->second);
\t\tit  = g_bc5_prt.erase(it);
\t}
\tg_bc5_prt[start] = end;
}

static void Bc5PrtRemove(uint64_t start, uint64_t end) {
\tauto it = g_bc5_prt.upper_bound(start);
\tif (it != g_bc5_prt.begin()) {
\t\t--it;
\t}
\twhile (it != g_bc5_prt.end() && it->first < end) {
\t\tconst uint64_t s = it->first;
\t\tconst uint64_t e = it->second;
\t\tif (e <= start) {
\t\t\t++it;
\t\t\tcontinue;
\t\t}
\t\tit = g_bc5_prt.erase(it);
\t\tif (s < start) {
\t\t\tg_bc5_prt[s] = start;
\t\t}
\t\tif (e > end) {
\t\t\tg_bc5_prt[end] = e;
\t\t\tbreak;
\t\t}
\t}
}

static bool Bc5PrtCovers(uint64_t start, uint64_t end) { // [_requirePrt]
\tauto it = g_bc5_prt.upper_bound(start);
\tif (it == g_bc5_prt.begin()) {
\t\treturn false;
\t}
\t--it;
\treturn it->first <= start && it->second >= end;
}

static void Bc5PrtParts(uint64_t start, uint64_t end, std::vector<std::pair<uint64_t, uint64_t>>* out) {
\tout->clear();
\tauto it = g_bc5_prt.upper_bound(start);
\tif (it != g_bc5_prt.begin()) {
\t\t--it;
\t}
\tfor (; it != g_bc5_prt.end() && it->first < end; ++it) {
\t\tif (it->second > start) {
\t\t\tout->emplace_back(std::max(start, it->first), std::min(end, it->second));
\t\t}
\t}
}

// The host pages of a reserved span: the anonymous PROT_NONE placeholder the host keeps there made readable (zero pages)
// or unreadable again. MapBacking's MAP_FIXED view replaces either; nothing else in the host reads the placeholder's mode.
static bool Bc5HostReadable(uint64_t va, uint64_t size, bool readable) {
#if defined(__linux__)
\treturn mprotect(reinterpret_cast<void*>(va), static_cast<size_t>(size), readable ? PROT_READ : PROT_NONE) == 0;
#else
\t(void)va;
\t(void)size;
\t(void)readable;
\treturn false;
#endif
}

// [_clearPrt]: the range stops being PRT and its zero pages stop being readable. Only the unbacked pages are touched: a
// backed page's host view stays as it is (the caller unmaps or replaces it, or it stays mapped if that fails).
static void Bc5PrtEnd(uint64_t start, uint64_t end) {
\tstd::vector<std::pair<uint64_t, uint64_t>> parts;
\tBc5PrtParts(start, end, &parts);
\tfor (const auto& [a, b]: parts) {
\t\tfor (uint64_t pos = a; pos < b;) {
\t\t\tconst auto it = g_bc5_amm_pages.lower_bound(pos);
\t\t\tif (it != g_bc5_amm_pages.end() && it->first == pos) {
\t\t\t\tpos += AMM_PAGE_SIZE;
\t\t\t\tcontinue;
\t\t\t}
\t\t\tconst uint64_t stop = (it == g_bc5_amm_pages.end()) ? b : std::min(b, it->first);
\t\t\t(void)Bc5HostReadable(pos, stop - pos, false);
\t\t\tpos = stop;
\t\t}
\t}
\tBc5PrtRemove(start, end);
}

// ---- the page table [pages, pooledUses] ----
static void Bc5PoolReturn(uint64_t dmem, uint64_t size) {
\tstd::scoped_lock lock(g_amm_auto_pool_mutex);
\tAmmAutoFreeLocked(dmem, size);
}

static void Bc5PoolUse(uint64_t dmem) {
\tg_bc5_pool_uses[dmem]++;
}

static void Bc5PoolUnuse(uint64_t dmem) { // [_releasePage]
\tconst auto it = g_bc5_pool_uses.find(dmem);
\tif (it == g_bc5_pool_uses.end()) {
\t\treturn;
\t}
\tif (--it->second == 0) {
\t\tg_bc5_pool_uses.erase(it);
\t\tBc5PoolReturn(dmem, AMM_PAGE_SIZE);
\t}
}

static void Bc5RecordPages(uint64_t va, uint64_t dmem, uint64_t size, int32_t type, int32_t prot, uint8_t owner) { // [_addPage]
\tfor (uint64_t off = 0; off < size; off += AMM_PAGE_SIZE) {
\t\tg_bc5_amm_pages[va + off] = Bc5AmmPage {dmem + off, type, prot, owner};
\t\tif (owner == BC5_PAGE_COUNTED) {
\t\t\tBc5PoolUse(dmem + off);
\t\t}
\t}
}

// [_forgetPages]: the range's entries go, a counted page loses a use, and today's AmmAutoReleaseVa returns the automatic
// maps' pool pages.
static void Bc5ForgetPages(uint64_t va, uint64_t size) {
\tfor (auto it = g_bc5_amm_pages.lower_bound(va); it != g_bc5_amm_pages.end() && it->first < va + size;) {
\t\tif (it->second.owner == BC5_PAGE_COUNTED) {
\t\t\tBc5PoolUnuse(it->second.dmem);
\t\t}
\t\tit = g_bc5_amm_pages.erase(it);
\t}
\tAmmAutoReleaseVa(va, size);
}

// A remap or a multimap of automatic pages: today's g_amm_auto_maps lets go of them without freeing (AmmAutoReleaseVa's
// split without AmmAutoFreeLocked) and each becomes a counted page with one use.
static void Bc5DetachAuto(uint64_t va, uint64_t size) {
\t{
\t\tstd::scoped_lock lock(g_amm_auto_pool_mutex);
\t\tconst uint64_t   end = va + size;
\t\tauto             it  = g_amm_auto_maps.lower_bound(va);
\t\tif (it != g_amm_auto_maps.begin()) {
\t\t\t--it;
\t\t}
\t\twhile (it != g_amm_auto_maps.end() && it->first < end) {
\t\t\tconst uint64_t m_va   = it->first;
\t\t\tconst uint64_t m_end  = m_va + it->second.size;
\t\t\tconst uint64_t m_dmem = it->second.dmem;
\t\t\tif (m_end <= va) {
\t\t\t\t++it;
\t\t\t\tcontinue;
\t\t\t}
\t\t\tconst uint64_t o0 = std::max(va, m_va);
\t\t\tconst uint64_t o1 = std::min(end, m_end);
\t\t\tg_amm_auto_maps.erase(it);
\t\t\tif (m_va < o0) {
\t\t\t\tg_amm_auto_maps[m_va] = AmmAutoMapping {m_dmem, o0 - m_va};
\t\t\t}
\t\t\tif (o1 < m_end) {
\t\t\t\tg_amm_auto_maps[o1] = AmmAutoMapping {m_dmem + (o1 - m_va), m_end - o1};
\t\t\t}
\t\t\tit = g_amm_auto_maps.lower_bound(o1);
\t\t}
\t}
\tfor (auto it = g_bc5_amm_pages.lower_bound(va); it != g_bc5_amm_pages.end() && it->first < va + size; ++it) {
\t\tif (it->second.owner == BC5_PAGE_AUTO) {
\t\t\tit->second.owner = BC5_PAGE_COUNTED;
\t\t\tBc5PoolUse(it->second.dmem);
\t\t}
\t}
}

static bool Bc5MappedPages(uint64_t va, uint64_t size, std::vector<Bc5AmmPage>* out) { // [_mappedPages]
\tout->clear();
\tauto it = g_bc5_amm_pages.lower_bound(va);
\tfor (uint64_t off = 0; off < size; off += AMM_PAGE_SIZE, ++it) {
\t\tif (it == g_bc5_amm_pages.end() || it->first != va + off) {
\t\t\treturn false;
\t\t}
\t\tout->push_back(it->second);
\t}
\treturn true;
}

// ---- the host side ----
static int Bc5Reserve(uint64_t va, uint64_t size) { // [_reserve]: back to the AMM reservation, whatever was mapped there
\tvoid*     addr   = reinterpret_cast<void*>(va);
\tconst int result = LibKernel::Memory::KernelReserveVirtualRange(&addr, size, AMM_MAP_FIXED, 0);
\tif (result == OK) {
\t\t(void)LibKernel::Memory::KernelSetVirtualRangeName(reinterpret_cast<void*>(va), size, "AMM");
\t}
\treturn result;
}

static int Bc5ZeroPages(uint64_t va, uint64_t size, const char* why) { // [_zeroPrt], DoMapZero
\tint result = Bc5Reserve(va, size);
\tif (result == OK && !Bc5HostReadable(va, size, true)) {
\t\tresult = LibKernel::KERNEL_ERROR_ENOMEM;
\t}
\tconst uint64_t n = ++g_bc5_journal_zero;
\tif (Bc5JournalDue(n) || result != OK) {
\t\tstd::fprintf(stderr, "[bc5] exp 0401 prt: zero pages #%" PRIu64 " va 0x%016" PRIx64 " size 0x%" PRIx64 " (%s) -> 0x%08x\\n",
\t\t             n, va, size, why, static_cast<unsigned>(result));
\t}
\treturn result;
}

static int Bc5MapRun(uint64_t va, uint64_t dmem, uint64_t size, int32_t type, int32_t prot) { // [_mapRun]
\tvoid*     addr   = reinterpret_cast<void*>(va);
\tconst int result = LibKernel::Memory::KernelMapDirectMemory2(&addr, size, type, Bc5HostProt(prot), AMM_MAP_FIXED,
\t                                                             static_cast<int64_t>(dmem), AMM_PAGE_SIZE);
\tif (result == OK) {
\t\t(void)LibKernel::Memory::KernelSetVirtualRangeName(reinterpret_cast<void*>(va), size, "AMM");
\t}
\treturn result;
}

static void Bc5JournalBacking(const char* why, uint64_t va, uint64_t dmem, uint64_t size, int32_t type, int32_t prot,
                              int result) {
\tconst uint64_t n = ++g_bc5_journal_back;
\tif (Bc5JournalDue(n) || result != OK) {
\t\tstd::fprintf(stderr,
\t\t             "[bc5] exp 0401 prt: backing #%" PRIu64 " (%s) va 0x%016" PRIx64 " size 0x%" PRIx64 " dmem 0x%" PRIx64
\t\t             " type %d prot 0x%x -> 0x%08x\\n",
\t\t             n, why, va, size, dmem, static_cast<int>(type), static_cast<unsigned>(prot), static_cast<unsigned>(result));
\t}
}

static bool Bc5BackingFails() { // test seam: true for the n-th backing after bc5_exp0401_amm_fail_backing(n)
\tuint32_t n = g_bc5_fail_backing.load();
\twhile (n != 0) {
\t\tif (g_bc5_fail_backing.compare_exchange_weak(n, n - 1)) {
\t\t\treturn n == 1;
\t\t}
\t}
\treturn false;
}

// ---- the commands ----
static int Bc5MapAsPrt(const CommandBufferState::AmmMapCommand& c) { // [_ammMapAsPrt]
\tif (!Bc5InAmmWindow(c.va, c.size)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\tconst int result = Bc5ZeroPages(c.va, c.size, "MapAsPrt");
\tif (result != OK) {
\t\treturn result;
\t}
\tBc5ForgetPages(c.va, c.size);
\tBc5PrtAdd(c.va, c.va + c.size);
\treturn OK;
}

static int Bc5UnmapToPrt(const CommandBufferState::AmmMapCommand& c) { // [_ammUnmapToPrt]
\tif (!Bc5InAmmWindow(c.va, c.size) || !Bc5PrtCovers(c.va, c.va + c.size)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\tconst int result = Bc5ZeroPages(c.va, c.size, "UnmapToPrt");
\tif (result == OK) {
\t\tBc5ForgetPages(c.va, c.size);
\t}
\treturn result;
}

// [_ammAllocatePrt] with e3b5192cb and 79fc99774: each run of backed pages takes the type and protection; each run of
// unbacked pages gets pool pages, and a run whose backing fails returns them and goes back to zero pages.
static int Bc5AllocatePaForPrt(const CommandBufferState::AmmMapCommand& c) {
\tif (!Bc5InAmmWindow(c.va, c.size) || !Bc5PrtCovers(c.va, c.va + c.size)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\tconst uint64_t end = c.va + c.size;
\tfor (uint64_t pos = c.va; pos < end;) {
\t\tauto       it      = g_bc5_amm_pages.lower_bound(pos);
\t\tconst bool backed  = it != g_bc5_amm_pages.end() && it->first == pos;
\t\tuint64_t   run_end = pos;
\t\tif (backed) {
\t\t\twhile (it != g_bc5_amm_pages.end() && it->first == run_end && run_end < end) {
\t\t\t\tit->second.type = c.type;
\t\t\t\tit->second.prot = c.prot;
\t\t\t\t++it;
\t\t\t\trun_end += AMM_PAGE_SIZE;
\t\t\t}
\t\t\tconst int result = LibKernel::Memory::KernelMprotect(reinterpret_cast<void*>(pos), run_end - pos, Bc5HostProt(c.prot));
\t\t\tif (result != OK) {
\t\t\t\treturn result;
\t\t\t}
\t\t} else {
\t\t\trun_end              = (it == g_bc5_amm_pages.end()) ? end : std::min(end, it->first);
\t\t\tconst uint64_t bytes = run_end - pos;
\t\t\tuint64_t       dmem  = 0;
\t\t\tif (!AllocateAmmAutoDirectMemory(bytes, c.type, &dmem)) {
\t\t\t\tBc5JournalBacking("AllocatePaForPrt, no direct memory", pos, 0, bytes, c.type, c.prot, LibKernel::KERNEL_ERROR_EAGAIN);
\t\t\t\treturn LibKernel::KERNEL_ERROR_EAGAIN; // nothing of this run changed: it still reads 0
\t\t\t}
\t\t\tconst int result = Bc5BackingFails() ? LibKernel::KERNEL_ERROR_EAGAIN : Bc5MapRun(pos, dmem, bytes, c.type, c.prot);
\t\t\tif (result != OK) {
\t\t\t\tBc5PoolReturn(dmem, bytes);
\t\t\t\t(void)Bc5ZeroPages(pos, bytes, "AllocatePaForPrt, rolled back");
\t\t\t\tBc5JournalBacking("AllocatePaForPrt, failed", pos, dmem, bytes, c.type, c.prot, result);
\t\t\t\treturn result;
\t\t\t}
\t\t\tAmmAutoRecordVa(pos, dmem, bytes);
\t\t\tBc5RecordPages(pos, dmem, bytes, c.type, c.prot, BC5_PAGE_AUTO);
\t\t\tBc5JournalBacking("AllocatePaForPrt", pos, dmem, bytes, c.type, c.prot, OK);
\t\t}
\t\tpos = run_end;
\t}
\treturn OK;
}

// [_ammRemap]: a remap moves the source's pages (the source goes back to the reservation), a multimap (alias) maps them
// a second time, a PRT remap moves them into a PRT range. The source must be fully mapped; an alias or a PRT remap may
// not overlap its source. Each counted page holds a use while the ranges change [AmmPageReferences].
static int Bc5Remap(const CommandBufferState::AmmMapCommand& c, bool alias, bool into_prt) {
\tconst uint64_t dst  = c.va;
\tconst uint64_t src  = c.source;
\tconst uint64_t size = c.size;
\tif (!Bc5InAmmWindow(dst, size) || !Bc5InAmmWindow(src, size)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\tif ((alias || into_prt) && dst < src + size && src < dst + size) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\tif (into_prt && !Bc5PrtCovers(dst, dst + size)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\tstd::vector<Bc5AmmPage> pages;
\tif (!Bc5MappedPages(src, size, &pages)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\tBc5DetachAuto(src, size);
\t(void)Bc5MappedPages(src, size, &pages);
\tfor (auto& p: pages) {
\t\tp.prot = c.prot;
\t\tif (p.owner == BC5_PAGE_COUNTED) {
\t\t\tBc5PoolUse(p.dmem);
\t\t}
\t}
\tint result = OK;
\tif (!alias) {
\t\tresult = Bc5Reserve(src, size);
\t\tif (result == OK) {
\t\t\tBc5PrtEnd(src, src + size);
\t\t\tBc5ForgetPages(src, size);
\t\t}
\t}
\tif (result == OK) {
\t\tresult = Bc5Reserve(dst, size);
\t}
\tif (result == OK) {
\t\tBc5ForgetPages(dst, size);
\t\tif (!into_prt) {
\t\t\tBc5PrtEnd(dst, dst + size);
\t\t}
\t\tfor (size_t first = 0; first < pages.size() && result == OK;) {
\t\t\tsize_t last = first + 1;
\t\t\twhile (last < pages.size() && pages[last].dmem == pages[last - 1].dmem + AMM_PAGE_SIZE &&
\t\t\t       pages[last].type == pages[first].type && pages[last].owner == pages[first].owner) {
\t\t\t\tlast++;
\t\t\t}
\t\t\tconst uint64_t at    = dst + first * AMM_PAGE_SIZE;
\t\t\tconst uint64_t bytes = (last - first) * AMM_PAGE_SIZE;
\t\t\tresult               = Bc5MapRun(at, pages[first].dmem, bytes, pages[first].type, c.prot);
\t\t\tif (result == OK) {
\t\t\t\tBc5RecordPages(at, pages[first].dmem, bytes, pages[first].type, c.prot, pages[first].owner);
\t\t\t} else if (into_prt) {
\t\t\t\t(void)Bc5ZeroPages(at, (pages.size() - first) * AMM_PAGE_SIZE, "RemapIntoPrt, map failed");
\t\t\t}
\t\t\tif (into_prt) {
\t\t\t\tBc5JournalBacking("RemapIntoPrt", at, pages[first].dmem, bytes, pages[first].type, c.prot, result);
\t\t\t}
\t\t\tfirst = last;
\t\t}
\t}
\tfor (const auto& p: pages) {
\t\tif (p.owner == BC5_PAGE_COUNTED) {
\t\t\tBc5PoolUnuse(p.dmem);
\t\t}
\t}
\treturn result;
}

// [_ammProtect]: the masked bits of every page of a fully mapped range; the type too for ModifyMtypeProtect.
static int Bc5Protect(const CommandBufferState::AmmMapCommand& c, bool with_type) {
\tstd::vector<Bc5AmmPage> pages;
\tif (!Bc5InAmmWindow(c.va, c.size) || !Bc5MappedPages(c.va, c.size, &pages)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\tauto it = g_bc5_amm_pages.lower_bound(c.va);
\tfor (size_t i = 0; i < pages.size(); i++, ++it) {
\t\tit->second.prot = (it->second.prot & ~c.mask) | (c.prot & c.mask);
\t\tif (with_type) {
\t\t\tit->second.type = c.type;
\t\t}
\t\tpages[i] = it->second;
\t}
\tfor (size_t first = 0; first < pages.size();) {
\t\tconst int host = Bc5HostProt(pages[first].prot);
\t\tsize_t    last = first + 1;
\t\twhile (last < pages.size() && Bc5HostProt(pages[last].prot) == host) {
\t\t\tlast++;
\t\t}
\t\tconst int result = LibKernel::Memory::KernelMprotect(reinterpret_cast<void*>(c.va + first * AMM_PAGE_SIZE),
\t\t                                                     (last - first) * AMM_PAGE_SIZE, host);
\t\tif (result != OK) {
\t\t\treturn result;
\t\t}
\t\tfirst = last;
\t}
\treturn OK;
}

// An unmap with the page table on: today's KernelMunmap, then [_clearPrt] and [_forgetPages] (with today's
// AmmAutoReleaseVa). Unlike AnyPS5's, the range is not returned to the reservation (today's unmap does not either).
static int Bc5Unmap(const CommandBufferState::AmmMapCommand& c) {
\tconst int result = LibKernel::Memory::KernelMunmap(c.va, c.size);
\tif (result == OK) {
\t\tBc5PrtEnd(c.va, c.va + c.size);
\t\tBc5ForgetPages(c.va, c.size);
\t}
\tif (AmmTrace()) {
\t\tAmmTraceStamp(), std::fprintf(stderr, "amm trace: unmap va 0x%016" PRIx64 " size 0x%" PRIx64 " -> 0x%08x\\n", c.va,
\t\t                              c.size, static_cast<unsigned>(result));
\t}
\treturn result;
}

static const char* Bc5AmmKindName(AmmCommandKind kind) {
\tswitch (kind) {
\t\tcase AmmCommandKind::Unmap: return "Unmap";
\t\tcase AmmCommandKind::MapAsPrt: return "MapAsPrt";
\t\tcase AmmCommandKind::UnmapToPrt: return "UnmapToPrt";
\t\tcase AmmCommandKind::AllocatePaForPrt: return "AllocatePaForPrt";
\t\tcase AmmCommandKind::RemapIntoPrt: return "RemapIntoPrt";
\t\tcase AmmCommandKind::Remap: return "Remap";
\t\tcase AmmCommandKind::MultiMap: return "MultiMap";
\t\tcase AmmCommandKind::ModifyProtect: return "ModifyProtect";
\t\tcase AmmCommandKind::ModifyMtypeProtect: return "ModifyMtypeProtect";
\t\tdefault: return "map";
\t}
}

// The new kinds, and an unmap while the page table runs (RunOrderedAprCommands). A kind whose switch is off fails.
static int Bc5ExecuteAmm0401(const CommandBufferState::AmmMapCommand& command) {
\tstd::scoped_lock lock(g_bc5_amm_mutex);
\tconst bool       prt    = Bc5AmmPrtCmdsOn();
\tconst bool       extra  = Bc5AmmExtraCmdsOn();
\tint              result = LibKernel::KERNEL_ERROR_EINVAL;
\tswitch (command.kind) {
\t\tcase AmmCommandKind::Unmap: result = Bc5Unmap(command); break;
\t\tcase AmmCommandKind::MapAsPrt: result = prt ? Bc5MapAsPrt(command) : result; break;
\t\tcase AmmCommandKind::UnmapToPrt: result = prt ? Bc5UnmapToPrt(command) : result; break;
\t\tcase AmmCommandKind::AllocatePaForPrt: result = prt ? Bc5AllocatePaForPrt(command) : result; break;
\t\tcase AmmCommandKind::RemapIntoPrt: result = prt ? Bc5Remap(command, false, true) : result; break;
\t\tcase AmmCommandKind::Remap: result = extra ? Bc5Remap(command, false, false) : result; break;
\t\tcase AmmCommandKind::MultiMap: result = extra ? Bc5Remap(command, true, false) : result; break;
\t\tcase AmmCommandKind::ModifyProtect: result = extra ? Bc5Protect(command, false) : result; break;
\t\tcase AmmCommandKind::ModifyMtypeProtect: result = extra ? Bc5Protect(command, true) : result; break;
\t\tdefault: break;
\t}
\tif (result != OK && Bc5JournalDue(++g_bc5_journal_fail)) {
\t\tstd::fprintf(stderr,
\t\t             "[bc5] exp 0401 amm: %s va 0x%016" PRIx64 " source 0x%016" PRIx64 " size 0x%" PRIx64
\t\t             " prot 0x%x -> 0x%08x, the buffer stops here (#%" PRIu64 ")\\n",
\t\t             Bc5AmmKindName(command.kind), command.va, command.source, command.size, static_cast<unsigned>(command.prot),
\t\t             static_cast<unsigned>(result), g_bc5_journal_fail);
\t}
\treturn result;
}

// A map with the page table on [_ammMap]: the range's old pages are forgotten and a PRT range there ends, then today's
// map runs, then its pages enter the table (an automatic map's direct memory read back from today's g_amm_auto_maps).
static int Bc5ExecuteAmmMap0401(const CommandBufferState::AmmMapCommand& command) {
\tstd::scoped_lock lock(g_bc5_amm_mutex);
\tif (ValidateAmmMapArgs(command.va, command.size)) {
\t\tBc5PrtEnd(command.va, command.va + command.size);
\t\tBc5ForgetPages(command.va, command.size);
\t}
\tconst int result = ExecuteAmmMapCommandToday(command);
\tif (result == OK) {
\t\tif (command.kind == AmmCommandKind::MapAuto) {
\t\t\tuint64_t dmem  = 0;
\t\t\tbool     found = false;
\t\t\t{
\t\t\t\tstd::scoped_lock pool_lock(g_amm_auto_pool_mutex);
\t\t\t\tconst auto       it = g_amm_auto_maps.find(command.va);
\t\t\t\tif (it != g_amm_auto_maps.end() && it->second.size == command.size) {
\t\t\t\t\tdmem  = it->second.dmem;
\t\t\t\t\tfound = true;
\t\t\t\t}
\t\t\t}
\t\t\tif (found) {
\t\t\t\tBc5RecordPages(command.va, dmem, command.size, command.type, command.prot, BC5_PAGE_AUTO);
\t\t\t}
\t\t} else {
\t\t\tBc5RecordPages(command.va, command.dmem_offset, command.size, command.type, command.prot, BC5_PAGE_TITLE);
\t\t}
\t}
\treturn result;
}

// ---- the counters [g_counters, _counterField, _readCounter, _applyCounterOperation, _writeCounter, _waitSatisfied] ----
static std::array<std::atomic<uint32_t>, 256> g_bc5_counters {};
static std::mutex                               g_bc5_counter_writes;

static void Bc5CounterField(uint8_t access, uint32_t* bits, uint32_t* shift) {
\tif (access == 0) {
\t\t*bits  = 64;
\t\t*shift = 0;
\t} else if (access == 1) {
\t\t*bits  = 32;
\t\t*shift = 0;
\t} else if (access < 4) {
\t\t*bits  = 16;
\t\t*shift = (access - 2u) * 16u;
\t} else {
\t\t*bits  = 8;
\t\t*shift = (static_cast<uint32_t>(access & 7u) - 4u) * 8u;
\t}
}

static uint64_t Bc5FieldMask(uint32_t bits) {
\treturn bits == 64 ? ~uint64_t {0} : (uint64_t {1} << bits) - 1u;
}

static uint32_t Bc5Counter(uint32_t index) {
\treturn g_bc5_counters[index % g_bc5_counters.size()].load(std::memory_order_acquire);
}

static uint64_t Bc5ReadCounter(uint32_t index, uint8_t access) {
\tuint32_t bits  = 0;
\tuint32_t shift = 0;
\tBc5CounterField(access, &bits, &shift);
\tif (bits == 64) {
\t\treturn Bc5Counter(index) | static_cast<uint64_t>(Bc5Counter(index + 1u)) << 32u;
\t}
\treturn (Bc5Counter(index) >> shift) & Bc5FieldMask(bits);
}

static uint64_t Bc5ApplyCounterOperation(uint8_t operation, uint64_t current, uint64_t value) {
\tswitch (operation) {
\t\tcase 0: return value;
\t\tcase 1: return current | value;
\t\tcase 2: return current & ~value;
\t\tcase 3: return current ^ value;
\t\tdefault: return current + value;
\t}
}

static void Bc5WriteCounterValue(uint32_t index, uint8_t access, uint8_t operation, uint64_t value) {
\tuint32_t bits  = 0;
\tuint32_t shift = 0;
\tBc5CounterField(access, &bits, &shift);
\tstd::scoped_lock lock(g_bc5_counter_writes);
\tconst uint64_t   next = Bc5ApplyCounterOperation(operation, Bc5ReadCounter(index, access), value) & Bc5FieldMask(bits);
\tauto&            low  = g_bc5_counters[index % g_bc5_counters.size()];
\tif (bits == 64) {
\t\tg_bc5_counters[(index + 1u) % g_bc5_counters.size()].store(static_cast<uint32_t>(next >> 32u), std::memory_order_release);
\t\tlow.store(static_cast<uint32_t>(next), std::memory_order_release);
\t\treturn;
\t}
\tconst auto mask  = static_cast<uint32_t>(Bc5FieldMask(bits) << shift);
\tconst auto field = static_cast<uint32_t>(next << shift);
\tlow.store((low.load(std::memory_order_relaxed) & ~mask) | field, std::memory_order_release);
}

static bool Bc5CompareSatisfied(uint8_t compare, uint64_t value, uint64_t reference) {
\tconstexpr uint64_t SIGN = uint64_t {1} << 63u;
\tswitch (compare) {
\t\tcase 0: return value == reference;
\t\tcase 1: return value > reference;
\t\tcase 2: return value < reference;
\t\tcase 3: return value != reference;
\t\tcase 4: return value - reference < SIGN;
\t\tcase 5: return (value ^ SIGN) > (reference ^ SIGN);
\t\tdefault: return (value ^ SIGN) < (reference ^ SIGN);
\t}
}

// 0 done, 1 a wait not met yet, -1 an address write failed.
static int Bc5RunCounterCommand0401(const CommandBufferState::Bc5CounterCommand& command) {
\tswitch (command.kind) {
\t\tcase 0: Bc5WriteCounterValue(command.counter, command.access, command.operation, command.value); return 0;
\t\tcase 1: {
\t\t\tuint32_t bits  = 0;
\t\t\tuint32_t shift = 0;
\t\t\tBc5CounterField(command.access, &bits, &shift);
\t\t\tconst uint32_t unused    = 64u - bits;
\t\t\tconst uint64_t now       = (Bc5ReadCounter(command.counter, command.access) & command.mask) << unused;
\t\t\tconst uint64_t reference = (command.value & command.mask) << unused;
\t\t\treturn Bc5CompareSatisfied(command.compare, now, reference) ? 0 : 1;
\t\t}
\t\tdefault: {
\t\t\tuint64_t value = Bc5Counter(command.counter);
\t\t\tif (command.kind == 3) {
\t\t\t\tvalue |= static_cast<uint64_t>(Bc5Counter(command.counter + 1u)) << 32u;
\t\t\t}
\t\t\treturn AprShared::WriteGuest(command.address, value) ? 0 : -1;
\t\t}
\t}
}

// ---- the recorders ----
static bool Bc5AppendCounterRecord(void* command_buffer, CommandBufferState::Bc5CounterCommand command) {
\tconst auto            cb = reinterpret_cast<uint64_t>(command_buffer);
\tstd::scoped_lock      lock(g_command_buffer_mutex);
\tCommandBufferIterator it;
\tif (!GetOrCreateCommandBufferStateLocked(cb, &it)) {
\t\treturn false;
\t}
\tauto& state = it->second;
\tif (!EnsureCommandBufferRecordSpace(cb, &state, BC5_AMPR_COUNTER_RECORD_SIZE)) {
\t\treturn false;
\t}
\tcommand.record_offset = state.write_offset;
\tstd::memset(reinterpret_cast<void*>(state.buffer + state.write_offset), 0, static_cast<size_t>(BC5_AMPR_COUNTER_RECORD_SIZE));
\tstate.bc5_counter_commands.push_back(command);
\treturn CommitCommandBufferRecord(cb, &state, BC5_AMPR_COUNTER_RECORD_SIZE);
}

static bool Bc5InMap(void* command_buffer) { // [InMap]: an APR map group (MapBegin ... MapEnd) is open
\tuint32_t type = 0;
\treturn AprShared::ReadGuest(reinterpret_cast<uint64_t>(command_buffer) + COMMAND_BUFFER_TYPE_OFFSET, &type) &&
\t       (type & APR_TYPE_MAP_ACTIVE) != 0;
}

static int Bc5WaitOnCounter0401(void* command_buffer, uint8_t counter, uint8_t access, uint64_t reference, uint8_t compare,
                                uint8_t mask_operation, uint64_t mask, uint8_t flush) { // [Export.cpp:587-591]
\tif (command_buffer == nullptr || access >= 8 || compare > 6 || mask_operation >= 2 || flush >= 2) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\tCommandBufferState::Bc5CounterCommand c {};
\tc.kind    = 1;
\tc.counter = counter;
\tc.access  = access;
\tc.compare = compare;
\tc.value   = reference;
\tc.mask    = mask_operation != 0 ? mask : ~uint64_t {0};
\treturn Bc5AppendCounterRecord(command_buffer, c) ? OK : LibKernel::KERNEL_ERROR_EBUSY;
}

static int Bc5WriteCounter0401(void* command_buffer, uint8_t counter, uint8_t access, uint64_t value, uint8_t operation,
                               uint32_t at_start) { // [Export.cpp:614-618]
\tif (command_buffer == nullptr || (counter & 0x80u) != 0 || access >= 8 || operation >= 5) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\tif (at_start == 0 && Bc5InMap(command_buffer)) {
\t\treturn LibKernel::KERNEL_ERROR_EPERM;
\t}
\tCommandBufferState::Bc5CounterCommand c {};
\tc.kind      = 0;
\tc.counter   = counter;
\tc.access    = access;
\tc.operation = operation;
\tc.value     = value;
\treturn Bc5AppendCounterRecord(command_buffer, c) ? OK : LibKernel::KERNEL_ERROR_EBUSY;
}

static int Bc5WriteAddressFromCounter0401(void* command_buffer, volatile uint64_t* address, uint8_t counter, bool pair,
                                          bool completion) { // [Export.cpp:306-316]
\tconst auto addr = reinterpret_cast<uint64_t>(address);
\tif (command_buffer == nullptr || addr == 0 || (addr & 7u) != 0 || (pair ? (counter & 0x81u) != 0 : counter >= 128)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\tif (completion && Bc5InMap(command_buffer)) {
\t\treturn LibKernel::KERNEL_ERROR_EPERM;
\t}
\tCommandBufferState::Bc5CounterCommand c {};
\tc.kind    = pair ? 3 : 2;
\tc.counter = counter;
\tc.address = addr;
\treturn Bc5AppendCounterRecord(command_buffer, c) ? OK : LibKernel::KERNEL_ERROR_EBUSY;
}

static int KYTY_SYSV_ABI Bc5WriteCounterOnCompletion(void* command_buffer, uint8_t counter, uint32_t value) { // [Export.cpp:332-336]
\tPRINT_NAME();
\tif (command_buffer == nullptr || counter >= 128) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\tif (Bc5InMap(command_buffer)) {
\t\treturn LibKernel::KERNEL_ERROR_EPERM;
\t}
\tCommandBufferState::Bc5CounterCommand c {};
\tc.kind    = 0;
\tc.counter = counter;
\tc.access  = 1;
\tc.value   = value;
\treturn Bc5AppendCounterRecord(command_buffer, c) ? OK : LibKernel::KERNEL_ERROR_EBUSY;
}

static int KYTY_SYSV_ABI Bc5CommandBufferWaitOnAddress(void* command_buffer, volatile uint64_t* address, uint64_t reference,
                                                       uint8_t compare, uint8_t flush) { // [Export.cpp:338-341]
\tPRINT_NAME();
\t// AnyPS5 lets a null address through its alignment check; the wait would then read address 0, so it is refused here.
\tconst auto addr = reinterpret_cast<uint64_t>(address);
\tif (command_buffer == nullptr || addr == 0 || (addr & 7u) != 0 || compare >= 4 || flush >= 2) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\treturn AppendWaitAddressRecord(reinterpret_cast<uint64_t>(command_buffer), addr, reference, compare,
\t                               BC5_AMPR_COUNTER_RECORD_SIZE)
\t           ? OK
\t           : LibKernel::KERNEL_ERROR_EBUSY;
}

static int KYTY_SYSV_ABI Bc5CommandBufferWaitOnCounter(void* command_buffer, uint8_t counter, uint32_t reference, uint8_t compare,
                                                       uint8_t flush) { // [Export.cpp:343-346]
\tPRINT_NAME();
\tif (command_buffer == nullptr || counter >= 128 || compare >= 4 || flush >= 2) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\tCommandBufferState::Bc5CounterCommand c {};
\tc.kind    = 1;
\tc.counter = counter;
\tc.access  = 1;
\tc.compare = compare;
\tc.value   = reference;
\treturn Bc5AppendCounterRecord(command_buffer, c) ? OK : LibKernel::KERNEL_ERROR_EBUSY;
}

static uint64_t KYTY_SYSV_ABI Bc5MeasureCommandSizeWait() { // [Export.cpp:382-383], this host's record size
\tPRINT_NAME();
\treturn BC5_AMPR_COUNTER_RECORD_SIZE;
}

static int Bc5RecordAmm(void* command_buffer, AmmCommandKind kind, uint64_t va, uint64_t source, uint64_t size, int32_t type,
                        int32_t prot, int32_t mask, uint8_t gpu_mask_id, uint64_t record_size) {
\tCommandBufferState::AmmMapCommand command {};
\tcommand.kind        = kind;
\tcommand.va          = va;
\tcommand.source      = source;
\tcommand.size        = size;
\tcommand.type        = type;
\tcommand.prot        = prot;
\tcommand.mask        = mask;
\tcommand.gpu_mask_id = gpu_mask_id;
\treturn AppendAmmMapRecord(reinterpret_cast<uint64_t>(command_buffer), command, record_size) ? OK
\t                                                                                             : LibKernel::KERNEL_ERROR_EBUSY;
}

static int KYTY_SYSV_ABI Bc5AmmCommandBufferMapAsPrt(void* command_buffer, uint64_t va, uint64_t size) { // [Export.cpp:868-873]
\tPRINT_NAME();
\tif (command_buffer == nullptr || !ValidateAmmMapArgs(va, size)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\treturn Bc5RecordAmm(command_buffer, AmmCommandKind::MapAsPrt, va, 0, size, 0, 0, 0, 0, BC5_AMM_PRT_RECORD_SIZE);
}

static int KYTY_SYSV_ABI Bc5AmmCommandBufferAllocatePaForPrt(void* command_buffer, uint64_t va, uint64_t size, int32_t type,
                                                             int32_t prot) { // [Export.cpp:875-881]
\tPRINT_NAME();
\tif (!Bc5ValidProt(prot) || command_buffer == nullptr || !ValidateAmmMapArgs(va, size)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\treturn Bc5RecordAmm(command_buffer, AmmCommandKind::AllocatePaForPrt, va, 0, size, type, prot, BC5_PRT_ALLOCATION_MASK, 0,
\t                    BC5_AMM_PROTECT_RECORD_SIZE);
}

static int KYTY_SYSV_ABI Bc5AmmCommandBufferRemapIntoPrt(void* command_buffer, uint64_t va, uint64_t source, uint64_t size,
                                                         int32_t prot, uint32_t opcode) { // [Export.cpp:883-889]
\tPRINT_NAME();
\tif (command_buffer == nullptr || !Bc5ValidRemap(va, source, size, prot)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\t// the opcode argument is recorded (1011 when 0, as AnyPS5 and ampr_emu do) and not used
\treturn Bc5RecordAmm(command_buffer, AmmCommandKind::RemapIntoPrt, va, source, size, 0, prot,
\t                    static_cast<int32_t>(opcode != 0 ? opcode : 1011u), 0, BC5_AMM_REMAP_RECORD_SIZE);
}

static int KYTY_SYSV_ABI Bc5AmmCommandBufferUnmapToPrt(void* command_buffer, uint64_t va, uint64_t size) { // [Export.cpp:891-897]
\tPRINT_NAME();
\tif (command_buffer == nullptr || !ValidateAmmMapArgs(va, size)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\treturn Bc5RecordAmm(command_buffer, AmmCommandKind::UnmapToPrt, va, 0, size, 0, 0, 0, 0, BC5_AMM_PRT_RECORD_SIZE);
}

static int64_t KYTY_SYSV_ABI Bc5MeasureAmmCommandSizeMapAsPrt(uint64_t va, uint64_t size) { // [Export.cpp:899-901]
\tPRINT_NAME();
\treturn ValidateAmmMapArgs(va, size) ? static_cast<int64_t>(BC5_AMM_PRT_RECORD_SIZE) : LibKernel::KERNEL_ERROR_EINVAL;
}

static int64_t KYTY_SYSV_ABI Bc5MeasureAmmCommandSizeAllocatePaForPrt(uint64_t va, uint64_t size, int32_t type,
                                                                      int32_t prot) { // [Export.cpp:903-906]
\tPRINT_NAME();
\t(void)type;
\treturn ValidateAmmMapArgs(va, size) && Bc5ValidProt(prot) ? static_cast<int64_t>(BC5_AMM_PROTECT_RECORD_SIZE)
\t                                                          : LibKernel::KERNEL_ERROR_EINVAL;
}

static int KYTY_SYSV_ABI Bc5AmmCommandBufferRemap(void* command_buffer, uint64_t va, uint64_t source, uint64_t size,
                                                  int32_t prot) { // [Export.cpp:795-797]
\tPRINT_NAME();
\tif (command_buffer == nullptr || !Bc5ValidRemap(va, source, size, prot)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\treturn Bc5RecordAmm(command_buffer, AmmCommandKind::Remap, va, source, size, 0, prot, 0, 0, BC5_AMM_REMAP_RECORD_SIZE);
}

static int KYTY_SYSV_ABI Bc5AmmCommandBufferRemapWithGpuMaskId(void* command_buffer, uint64_t va, uint64_t source,
                                                               uint64_t size, int32_t prot, uint8_t gpu_mask_id) { // [799-802]
\tPRINT_NAME();
\tif (command_buffer == nullptr || !Bc5ValidRemap(va, source, size, prot)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\treturn Bc5RecordAmm(command_buffer, AmmCommandKind::Remap, va, source, size, 0, prot, 0, gpu_mask_id,
\t                    BC5_AMM_REMAP_RECORD_SIZE);
}

// MultiMap(buffer, address, alias, size, protection): the pages already mapped at "alias" are mapped at "address" too
// (AnyPS5 records alias as the source and maps the source's pages at address; its test maps at a multimap-range address).
static int KYTY_SYSV_ABI Bc5AmmCommandBufferMultiMap(void* command_buffer, uint64_t va, uint64_t source, uint64_t size,
                                                     int32_t prot) { // [Export.cpp:804-806]
\tPRINT_NAME();
\tif (command_buffer == nullptr || !Bc5ValidRemap(va, source, size, prot)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\treturn Bc5RecordAmm(command_buffer, AmmCommandKind::MultiMap, va, source, size, 0, prot, 0, 0, BC5_AMM_REMAP_RECORD_SIZE);
}

static int KYTY_SYSV_ABI Bc5AmmCommandBufferMultiMapWithGpuMaskId(void* command_buffer, uint64_t va, uint64_t source,
                                                                  uint64_t size, int32_t prot, uint8_t gpu_mask_id) { // [808-811]
\tPRINT_NAME();
\tif (command_buffer == nullptr || !Bc5ValidRemap(va, source, size, prot)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\treturn Bc5RecordAmm(command_buffer, AmmCommandKind::MultiMap, va, source, size, 0, prot, 0, gpu_mask_id,
\t                    BC5_AMM_REMAP_RECORD_SIZE);
}

static int KYTY_SYSV_ABI Bc5AmmCommandBufferModifyProtect(void* command_buffer, uint64_t va, uint64_t size, int32_t prot,
                                                          int32_t mask) { // [Export.cpp:813-815]
\tPRINT_NAME();
\tif (command_buffer == nullptr || !Bc5ValidProtect(va, size, prot, mask)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\treturn Bc5RecordAmm(command_buffer, AmmCommandKind::ModifyProtect, va, 0, size, 0, prot, mask, 0, BC5_AMM_PROTECT_RECORD_SIZE);
}

static int KYTY_SYSV_ABI Bc5AmmCommandBufferModifyProtectWithGpuMaskId(void* command_buffer, uint64_t va, uint64_t size,
                                                                       int32_t prot, int32_t mask, uint8_t gpu_mask_id) { // [817-820]
\tPRINT_NAME();
\tif (command_buffer == nullptr || !Bc5ValidProtect(va, size, prot, mask)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\treturn Bc5RecordAmm(command_buffer, AmmCommandKind::ModifyProtect, va, 0, size, 0, prot, mask, gpu_mask_id,
\t                    BC5_AMM_PROTECT_RECORD_SIZE);
}

static int KYTY_SYSV_ABI Bc5AmmCommandBufferModifyMtypeProtect(void* command_buffer, uint64_t va, uint64_t size, int32_t type,
                                                               int32_t prot, int32_t mask) { // [Export.cpp:822-824]
\tPRINT_NAME();
\tif (command_buffer == nullptr || !Bc5ValidProtect(va, size, prot, mask)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\treturn Bc5RecordAmm(command_buffer, AmmCommandKind::ModifyMtypeProtect, va, 0, size, type, prot, mask, 0,
\t                    BC5_AMM_PROTECT_RECORD_SIZE);
}

static int KYTY_SYSV_ABI Bc5AmmCommandBufferModifyMtypeProtectWithGpuMaskId(void* command_buffer, uint64_t va, uint64_t size,
                                                                            int32_t type, int32_t prot, int32_t mask,
                                                                            uint8_t gpu_mask_id) { // [826-829]
\tPRINT_NAME();
\tif (command_buffer == nullptr || !Bc5ValidProtect(va, size, prot, mask)) {
\t\treturn LibKernel::KERNEL_ERROR_EINVAL;
\t}
\treturn Bc5RecordAmm(command_buffer, AmmCommandKind::ModifyMtypeProtect, va, 0, size, type, prot, mask, gpu_mask_id,
\t                    BC5_AMM_PROTECT_RECORD_SIZE);
}

static int64_t KYTY_SYSV_ABI Bc5MeasureAmmCommandSizeRemap(uint64_t va, uint64_t source, uint64_t size, int32_t prot) { // [831-842]
\tPRINT_NAME();
\treturn Bc5ValidRemap(va, source, size, prot) ? static_cast<int64_t>(BC5_AMM_REMAP_RECORD_SIZE) : LibKernel::KERNEL_ERROR_EINVAL;
}

static int64_t KYTY_SYSV_ABI Bc5MeasureAmmCommandSizeRemapWithGpuMaskId(uint64_t va, uint64_t source, uint64_t size, int32_t prot,
                                                                        uint8_t gpu_mask_id) { // [835-847]
\tPRINT_NAME();
\t(void)gpu_mask_id;
\treturn Bc5ValidRemap(va, source, size, prot) ? static_cast<int64_t>(BC5_AMM_REMAP_RECORD_SIZE) : LibKernel::KERNEL_ERROR_EINVAL;
}

static int64_t KYTY_SYSV_ABI Bc5MeasureAmmCommandSizeModifyProtect(uint64_t va, uint64_t size, int32_t prot, int32_t mask) { // [849]
\tPRINT_NAME();
\treturn Bc5ValidProtect(va, size, prot, mask) ? static_cast<int64_t>(BC5_AMM_PROTECT_RECORD_SIZE) : LibKernel::KERNEL_ERROR_EINVAL;
}

static int64_t KYTY_SYSV_ABI Bc5MeasureAmmCommandSizeModifyProtectWithGpuMaskId(uint64_t va, uint64_t size, int32_t prot,
                                                                                int32_t mask, uint8_t gpu_mask_id) { // [853]
\tPRINT_NAME();
\t(void)gpu_mask_id;
\treturn Bc5ValidProtect(va, size, prot, mask) ? static_cast<int64_t>(BC5_AMM_PROTECT_RECORD_SIZE) : LibKernel::KERNEL_ERROR_EINVAL;
}

static int64_t KYTY_SYSV_ABI Bc5MeasureAmmCommandSizeModifyMtypeProtect(uint64_t va, uint64_t size, int32_t type, int32_t prot,
                                                                        int32_t mask) { // [Export.cpp:858-861]
\tPRINT_NAME();
\t(void)type;
\treturn Bc5ValidProtect(va, size, prot, mask) ? static_cast<int64_t>(BC5_AMM_PROTECT_RECORD_SIZE) : LibKernel::KERNEL_ERROR_EINVAL;
}

static int64_t KYTY_SYSV_ABI Bc5MeasureAmmCommandSizeModifyMtypeProtectWithGpuMaskId(uint64_t va, uint64_t size, int32_t type,
                                                                                     int32_t prot, int32_t mask,
                                                                                     uint8_t gpu_mask_id) { // [863-866]
\tPRINT_NAME();
\t(void)type;
\t(void)gpu_mask_id;
\treturn Bc5ValidProtect(va, size, prot, mask) ? static_cast<int64_t>(BC5_AMM_PROTECT_RECORD_SIZE) : LibKernel::KERNEL_ERROR_EINVAL;
}

// ---- test seams for amm0401.cpp (read-only but the first; nothing calls them in the emulator) ----
extern "C" void bc5_exp0401_amm_fail_backing(uint32_t n) {
\tg_bc5_fail_backing.store(n);
}

extern "C" void bc5_exp0401_amm_stats(uint64_t* pool_free, uint64_t* pages, uint64_t* prt_bytes) {
\tstd::scoped_lock lock(g_bc5_amm_mutex);
\tuint64_t         free_bytes = 0;
\t{
\t\tstd::scoped_lock pool_lock(g_amm_auto_pool_mutex);
\t\tfor (const auto& r: g_amm_auto_free) {
\t\t\tfree_bytes += r.second;
\t\t}
\t}
\tuint64_t prt = 0;
\tfor (const auto& [a, b]: g_bc5_prt) {
\t\tprt += b - a;
\t}
\tif (pool_free != nullptr) {
\t\t*pool_free = free_bytes;
\t}
\tif (pages != nullptr) {
\t\t*pages = g_bc5_amm_pages.size();
\t}
\tif (prt_bytes != nullptr) {
\t\t*prt_bytes = prt;
\t}
}

// 1: the page is in the page table, 2: it is in a PRT range, 4: a counted pool page.
extern "C" int bc5_exp0401_amm_page(uint64_t va, uint64_t* dmem, int32_t* type, int32_t* prot) {
\tstd::scoped_lock lock(g_bc5_amm_mutex);
\tint              flags = 0;
\tif (const auto it = g_bc5_amm_pages.find(va); it != g_bc5_amm_pages.end()) {
\t\tflags |= 1;
\t\tif (it->second.owner == BC5_PAGE_COUNTED) {
\t\t\tflags |= 4;
\t\t}
\t\tif (dmem != nullptr) {
\t\t\t*dmem = it->second.dmem;
\t\t}
\t\tif (type != nullptr) {
\t\t\t*type = it->second.type;
\t\t}
\t\tif (prot != nullptr) {
\t\t\t*prot = it->second.prot;
\t\t}
\t}
\tif (Bc5PrtCovers(va, va + AMM_PAGE_SIZE)) {
\t\tflags |= 2;
\t}
\treturn flags;
}

"""

# ---- the registration ---------------------------------------------------------------------------------------------------
REG_HEAD_OLD = b"LIB_DEFINE(InitAmpr_1_Ampr) {\n"
REG_HEAD_NEW = (REG_HEAD_OLD +
                b"\t// experiment 0401 series e4: the three switches, read here first, one stderr line each\n"
                b"\t(void)Ampr::Bc5AmmPrtCmdsOn();\n\t(void)Ampr::Bc5AmmExtraCmdsOn();\n\t(void)Ampr::Bc5AmprWaitsOn();\n")
SWAP_OLD = b'\tLIB_FUNC("3wn42MWTzTs", Ampr::CommandBufferWriteCounterOnCompletion);\n'
SWAP_NEW = (b"\tif (Ampr::Bc5AmprWaitsOn()) { // experiment 0401 series e4: AnyPS5's (buffer, counter, value) and a real write\n"
            b'\t\tLIB_FUNC("3wn42MWTzTs", Ampr::Bc5WriteCounterOnCompletion);\n'
            b"\t} else {\n"
            b'\t\tLIB_FUNC("3wn42MWTzTs", Ampr::CommandBufferWriteCounterOnCompletion);\n'
            b"\t}\n")
REG_TAIL_OLD = b'\tLIB_FUNC("HXymib4T8gc", Ampr::AmmWaitCommandBufferCompletion);\n}\n'


def registration():
    out = b'\tLIB_FUNC("HXymib4T8gc", Ampr::AmmWaitCommandBufferCompletion);\n'
    out += (b"\t// Experiment 0401 series e4 (the comment before Ampr::ExecuteAmmMapCommand): each switch's NIDs only with it on;\n"
            b"\t// off they stay unregistered and the loader's stub answers them, as before.\n")
    for switch, rows in (("Bc5AmmPrtCmdsOn", PRT), ("Bc5AmmExtraCmdsOn", EXTRA), ("Bc5AmprWaitsOn", WAITS)):
        out += f"\tif (Ampr::{switch}()) {{\n".encode()
        for n, name, fn, _ in rows:
            out += f'\t\tLIB_FUNC("{n}", Ampr::{fn}); // {name}\n'.encode()
        out += b"\t}\n"
    return out + b"}\n"


def once(s, anchor, new, what):
    assert s.count(anchor) == 1, (what, anchor[:80], s.count(anchor))
    return s.replace(anchor, new)


def check_nids():
    for name, want in (("strcmp", "Ovb2dSJOAuE"), ("strncmp", "aesyjrHVWy4"), ("strcpy_s", "5Xa2ACNECdo")):
        assert nid(name) == want, ("calculator self-check", name, nid(name), want)
    rows = [(n, name) for n, name, _, _ in PRT + EXTRA + WAITS] + [WAITS_SWAP[:2]] + list(WAITS_CHANGED)
    for n, name in rows:
        assert nid(name) == n, ("NID", name, nid(name), n)
    assert len({n for n, _ in rows}) == len(rows) == 33
    assert len(PRT) == 6 and len(EXTRA) == 16 and len(WAITS) == 4
    test = pathlib.Path(__file__).resolve().parent / "amm0401.cpp"
    checked = 0
    if test.exists():
        pairs = re.findall(rb'\{"([A-Za-z0-9+-]{11})", "(sce\w+)"', test.read_bytes())
        for n, name in pairs:
            assert nid(name.decode()) == n.decode(), ("amm0401.cpp NID", name, nid(name.decode()), n)
        checked = len(pairs)
        assert checked >= 26, ("amm0401.cpp names too few NIDs", checked)
    return checked


def edit(s):
    for m in MARKS:
        assert m not in s, ("libAmpr.cpp has the edit already", m)
    for n, _, fn, _ in PRT + EXTRA + WAITS:
        assert f'LIB_FUNC("{n}"'.encode() not in s, ("the unit registers it already", n)
        assert fn.encode() not in s, ("the unit has the function already", fn)
    for n, _ in WAITS_CHANGED + (WAITS_SWAP[:2],):
        assert s.count(f'LIB_FUNC("{n}"'.encode()) == 1, ("a changed NID is not registered once", n)
    s = once(s, INC_OLD, INC_NEW, "the includes")
    s = once(s, KIND_OLD, KIND_NEW, "AmmCommandKind")
    s = once(s, FIELDS_OLD, FIELDS_NEW, "AmmMapCommand's fields")
    s = once(s, LISTS_OLD, LISTS_NEW, "CommandBufferState's lists")
    s = once(s, CLEAR_OLD, CLEAR_NEW, "WriteCommandBufferPointers' clears")
    s = once(s, EARLY_ANCHOR, EARLY + EARLY_ANCHOR, "before ExecuteAmmMapCommand")
    s = once(s, MAP_OLD, MAP_NEW, "ExecuteAmmMapCommand")
    s = once(s, CKIND_OLD, CKIND_NEW, "CommandKind")
    s = once(s, RUN_OLD, RUN_NEW, "RunOrderedAprCommands' AMM case")
    s = once(s, ORDER_OLD, ORDER_NEW, "ExecuteAprCommandBuffer's order")
    s = once(s, WOC_OLD, WOC_NEW, "WaitOnCounter_04_00")
    s = once(s, WC_OLD, WC_NEW, "WriteCounter_04_00")
    for name, old, new in WAFC:
        s = once(s, old, new, name)
    s = once(s, LATE_ANCHOR, LATE + LATE_ANCHOR, "the end of namespace Ampr")
    s = once(s, REG_HEAD_OLD, REG_HEAD_NEW, "InitAmpr_1_Ampr's head")
    s = once(s, SWAP_OLD, SWAP_NEW, "3wn42MWTzTs")
    s = once(s, REG_TAIL_OLD, registration(), "InitAmpr_1_Ampr's tail")
    # every switch line and every new NID once; the stub NIDs untouched
    for n, _, _, _ in PRT + EXTRA + WAITS:
        assert s.count(f'LIB_FUNC("{n}"'.encode()) == 1, n
    assert s.count(b'LIB_FUNC("3wn42MWTzTs"') == 2
    # its definition, WaitOnCounter_04_00, WriteCounter_04_00, the four WriteAddressFromCounter forms, three in the registration
    assert s.count(b"Bc5AmprWaitsOn()") == 10, s.count(b"Bc5AmprWaitsOn()")
    return s


def main():
    args = sys.argv[1:]
    memory = None
    if "--memory" in args:
        k = args.index("--memory")
        assert k + 1 < len(args), __doc__
        memory = args[k + 1]
        del args[k:k + 2]
    assert len(args) == 2, __doc__
    root, out = args
    checked = check_nids()
    with open(os.path.join(root, REL), "rb") as f:
        s = f.read()
    if hashlib.md5(s).hexdigest() != TREE_MD5:
        print(f"mkamm0401: note: {REL} is {hashlib.md5(s).hexdigest()}, not the tree's {TREE_MD5}", file=sys.stderr)
    o = edit(s)
    p = os.path.join(out, REL)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(o)
    if memory is not None:
        with open(memory, "rb") as f:
            mem = f.read()
        print(f"mkamm0401: memory.cpp {hashlib.md5(mem).hexdigest()} read and left alone: this port needs no change there",
              file=sys.stderr)
    print(f"mkamm0401: 26 NIDs and 7 changed ones checked against their names; amm0401.cpp: {checked}", file=sys.stderr)
    print(f"{hashlib.md5(o).hexdigest()}  {REL}")


if __name__ == "__main__":
    main()
