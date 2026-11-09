#!/usr/bin/env python3
"""BC5 experiment 0401: KYTY_BC5_AMM_SCATTER — scattered automatic maps.

NEW version (review round 4): reads pool0401_impl.inc from script's own directory
and inserts it verbatim into the ORIGINAL libAmpr.cpp between marker comments.

usage: mkpool0401.py <original libAmpr.cpp> <out dir>
"""
import hashlib
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MARKERS = ("// ---- BEGIN pool0401_impl.inc ----",
           "// ---- END pool0401_impl.inc ----")

HOOKS = """// ---- Hook functions for pool0401_impl.inc ----
static const int KERNEL_ERROR_EAGAIN = LibKernel::KERNEL_ERROR_EAGAIN; // the helpers use the unqualified name
// These bridge the shared helpers to the real kernel calls.

extern "C" void* Bc5PoolMapDirect(void** addr, uint64_t size, int memory_type,
                                   int prot, int flags, int64_t dmem, uint64_t page_size) {
\tif (addr == nullptr) return nullptr;
\t*addr = reinterpret_cast<void*>(reinterpret_cast<uint64_t>(*addr));
\tconst int rc = LibKernel::Memory::KernelMapDirectMemory2(
\t\taddr, size, memory_type, prot, flags, dmem, page_size);
\treturn rc == OK ? *addr : nullptr;
}

extern "C" int Bc5PoolUnmapDirect(void* addr, uint64_t size) {
\treturn LibKernel::Memory::KernelMunmap(reinterpret_cast<uint64_t>(addr), static_cast<size_t>(size));
}

extern "C" int Bc5PoolAllocDirect(int64_t search_start, int64_t search_end,
                                   uint64_t size, uint64_t align, int type,
                                   int64_t* allocated) {
\treturn LibKernel::Memory::KernelAllocateDirectMemory(
\t\tsearch_start, search_end, size, align, type, allocated);
}

extern "C" int Bc5PoolSetName(void* addr, uint64_t size, const char* name) {
\t(void)LibKernel::Memory::KernelSetVirtualRangeName(addr, size, name);
\treturn 0;
}

extern "C" void Bc5PoolTraceStamp() {
\tAmmTraceStamp();
}

// exp 0409: every scattered map is counted and journalled (the first 300, then every 50th; failures always).
static void Bc5PoolNoteScatter(int mode, uint64_t va, uint64_t size, int np) {
\tstatic std::atomic<uint64_t> n_ok {0}, n_fail {0}, n_pieces {0};
\tconst uint64_t k = np > 0 ? n_ok.fetch_add(1) + 1 : n_fail.fetch_add(1) + 1;
\tif (np > 0) n_pieces.fetch_add(static_cast<uint64_t>(np));
\tif (np <= 0 || k <= 300 || k % 50 == 0) {
\t\tAmmTraceStamp(), std::fprintf(stderr, "[bc5] exp 0401 pool: scatter %s mode %d va 0x%016" PRIx64 " size 0x%" PRIx64 " pieces %d (ok %" PRIu64 ", failed %" PRIu64 ", pieces %" PRIu64 ")\\n",
\t\t                              np > 0 ? "ok" : "FAILED", mode, va, size, np, n_ok.load(), n_fail.load(), n_pieces.load());
\t}
}

extern "C" void bc5_watch_surface(uint64_t va); // bc5LleAgc.cpp, experiment 0104 (declared again here, before its first use)

extern "C" void Bc5PoolWatchSurface(uint64_t va) {
\tbc5_watch_surface(va);
}

extern "C" int64_t Bc5PoolGetDirectMemorySize() {
\treturn LibKernel::Memory::KernelGetDirectMemorySize();
}
"""


def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <original libAmpr.cpp> <out dir>", file=sys.stderr)
        sys.exit(1)

    lib_path = sys.argv[1]
    out_dir = sys.argv[2]

    # Read input libAmpr.cpp
    with open(lib_path, "r") as f:
        lines = f.readlines()

    # REVIEW4.6: Detect BEGIN marker — if present, exit 1
    for line in lines:
        if MARKERS[0] in line:
            print("has the edit already", file=sys.stderr)
            sys.exit(1)

    # Read pool0401_impl.inc from script's own directory
    inc_path = os.path.join(SCRIPT_DIR, "pool0401_impl.inc")
    with open(inc_path, "r") as f:
        inc_content = f.read()

    # EDIT 1: Insert HOOKS + markers + .inc before AllocateAmmAutoDirectMemory
    edit1_anchor = "static bool AllocateAmmAutoDirectMemory"
    edit1_indices = [i for i, line in enumerate(lines) if edit1_anchor in line]
    if len(edit1_indices) != 1:
        print(f"edit1: expected 1 match for '{edit1_anchor}', got {len(edit1_indices)}",
              file=sys.stderr)
        sys.exit(1)
    insert_idx = edit1_indices[0]

    replacement = (HOOKS + "\n" +
                   f"{MARKERS[0]}\n" + inc_content.rstrip('\n') +
                   f"\n{MARKERS[1]}\n")

    new_lines = lines[:insert_idx] + [replacement + "\n"] + lines[insert_idx:]

    # EDIT 2: Call-site change in ExecuteAmmMapCommandToday
    # The original block:
    #   if (command.kind == AmmCommandKind::MapAuto &&
    #       !AllocateAmmAutoDirectMemory(command.size, command.type, &dmem_offset)) {
    #       return LibKernel::KERNEL_ERROR_EAGAIN;
    #   }
    #
    # Replaced with mode-aware logic:
    #   if (command.kind == AmmCommandKind::MapAuto) {
    #       if (mode == 3) { first: try scatter first, fall back to borrow }
    #       else { borrow first; if fails and mode==2, try scatter }
    #   }
    edit2_anchor = "if (command.kind == AmmCommandKind::MapAuto &&"
    edit2_indices = [i for i, lines_obj in enumerate(new_lines) if edit2_anchor in lines_obj]
    if len(edit2_indices) != 1:
        print(f"edit2: expected 1 match for '{edit2_anchor}', got {len(edit2_indices)}",
              file=sys.stderr)
        sys.exit(1)
    edit2_start = edit2_indices[0]

    # Find the end of the block (the closing brace + semicolon after EAGAIN return)
    # The block is 4 lines: if-line, !Allocate..., return EAGAIN, }
    edit2_end = edit2_start + 4  # lines[edit2_start..edit2_end-1] is the block

    # Build replacement based on mode logic
    # We need to read the mode env var. For mode==3 (first), we try scatter before borrow.
    # For mode==2 (rescue), we try borrow first, then scatter on failure.
    # For mode==1 (journal), we log on borrow failure and return EAGAIN.
    # For mode==0 (off), we keep original behavior.

    replacement = """\t\tif (command.kind == AmmCommandKind::MapAuto) {
\t\t\t// experiment 0401: journal(1)=log-only, rescue(2)=scatter on EAGAIN, first(3)=scatter first.
\t\t\tconst int mode = Bc5AmmScatterMode();
\t\t\tif (mode == 3) {
\t\t\t\t// first: try scattered map before contiguous borrow.
\t\t\t\tconst int np = Bc5MapAutoScattered(command.va, command.size, command.type, command.prot);
\t\t\t\tBc5PoolNoteScatter(3, command.va, command.size, np);
\t\t\t\tif (np > 0) {
\t\t\t\t\t// Scattered map succeeded — skip the original contiguous path.
\t\t\t\t\treturn OK;
\t\t\t\t}
\t\t\t\t// Scatter failed, fall through to contiguous borrow.
\t\t\t\tif (!AllocateAmmAutoDirectMemory(command.size, command.type, &dmem_offset)) {
\t\t\t\t\treturn LibKernel::KERNEL_ERROR_EAGAIN;
\t\t\t\t}
\t\t\t} else if (mode == 2) {
\t\t\t\t// rescue: try contiguous borrow; if it fails, try scattered map.
\t\t\t\tif (!AllocateAmmAutoDirectMemory(command.size, command.type, &dmem_offset)) {
\t\t\t\t\tconst int np = Bc5MapAutoScattered(command.va, command.size, command.type, command.prot);
\t\t\t\t\tBc5PoolNoteScatter(2, command.va, command.size, np);
\t\t\t\t\tif (np > 0) {
\t\t\t\t\t\t// Scattered map succeeded — skip the original contiguous path.
\t\t\t\t\t\treturn OK;
\t\t\t\t\t}
\t\t\t\t\treturn LibKernel::KERNEL_ERROR_EAGAIN;
\t\t\t\t}
\t\t\t} else {
\t\t\t\t// journal(1) or off(0): original behavior.
\t\t\t\tif (!AllocateAmmAutoDirectMemory(command.size, command.type, &dmem_offset)) {
\t\t\t\t\tif (mode == 1) {
\t\t\t\t\t\tAmmTraceStamp(), std::fprintf(stderr,
\t\t\t\t\t\t\t"[bc5] exp 0401 pool: journal — contiguous borrow failed, scattered map refused\\n");
\t\t\t\t\t}
\t\t\t\t\treturn LibKernel::KERNEL_ERROR_EAGAIN;
\t\t\t\t}
\t\t\t}
\t\t}
"""

    final_lines = new_lines[:edit2_start] + [replacement] + new_lines[edit2_end:]

    # Write output
    out_path = os.path.join(out_dir, "libAmpr.cpp")
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w") as f:
        f.writelines(final_lines)

    print(f"patched -> {out_path}")


if __name__ == "__main__":
    main()
