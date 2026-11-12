#!/usr/bin/env python3
"""BC5 experiment 0413: the set-buffer guard. src/libs/libAmpr.cpp (exp 0409's unit, md5 a4760fe6) with
CommandBufferSetBuffer's "map flavour" refused when its target is already mapped guest memory.

The fault it fixes (exp 0413 README, "The cause"): the function decides between "attach this buffer" and "map fresh
zeroed pool memory at va" from its 4th and 5th arguments (exp 0035's heuristic, a3 != va and a4 == -1). ASTRO BOT calls it
with three arguments, so a3-a5 are whatever earlier host code left in rcx, r8 and r9 (the AMM trace shows a host heap
pointer in a5). When r8 happens to hold -1, the host mapped a zeroed 16 KiB page FIXED over the title's own heap page
that held the command buffer, and the title crashed on the zeros.

With KYTY_BC5_AMM_SETBUFFER_GUARD on, a call with the map signature whose first page is committed memory is taken as the
buffer flavour (exp 0035's own description: the buffer flavour attaches existing storage, the map flavour commits pool
pages in an AMM range that is not mapped yet). One stderr line names the first 16 such calls. Off: the old heuristic.
usage: mkset0413.py <libAmpr.cpp in> <out>"""
import hashlib
import sys

IN_MD5 = "a4760fe6"
FUNC = (b"static int KYTY_SYSV_ABI CommandBufferSetBuffer(void* command_buffer, void* buffer, uint32_t size,\n"
        b"                                                uint64_t a3, uint64_t a4, uint64_t a5) {\n")
COND = b"\tif (SetBufferIsMapFlavour(va, a3, a4)) {\n"
HELP = (b"// Experiment 0413 (KYTY_BC5_AMM_SETBUFFER_GUARD): a set-buffer call with the map signature whose target is already\n"
        b"// committed guest memory is the buffer flavour. A title that passes three arguments leaves rcx, r8 and r9 to chance;\n"
        b"// with r8 == -1 the map flavour below replaced a page of ASTRO BOT's own heap with zeroed memory (exp 0413).\n"
        b"static bool Bc5SetBufferGuardOn() {\n"
        b"\tstatic const bool on = Bc5Exp0401Switch(\"KYTY_BC5_AMM_SETBUFFER_GUARD\");\n"
        b"\treturn on;\n"
        b"}\n"
        b"static bool Bc5SetBufferTargetMapped(uint64_t va, uint32_t size, uint64_t a3, uint64_t a4, uint64_t a5) {\n"
        b"\tif (!Bc5SetBufferGuardOn()) {\n"
        b"\t\treturn false;\n"
        b"\t}\n"
        b"\tLibKernel::Memory::VirtualQueryInfo info {};\n"
        b"\tconst uint64_t                      first = va & ~(AMM_PAGE_SIZE - 1u);\n"
        b"\tif (LibKernel::Memory::KernelVirtualQuery(reinterpret_cast<const void*>(first), 0, &info, sizeof(info)) != OK ||\n"
        b"\t    info.is_committed == 0) {\n"
        b"\t\treturn false;\n"
        b"\t}\n"
        b"\tstatic int told = 0;\n"
        b"\tif (told < 16) {\n"
        b"\t\ttold++;\n"
        b"\t\tstd::fprintf(stderr,\n"
        b"\t\t             \"[bc5] exp 0413: set-buffer with the map signature on mapped memory (va 0x%016\" PRIx64 \" len 0x%x a3 0x%\" PRIx64\n"
        b"\t\t             \" a4 0x%\" PRIx64 \" a5 0x%\" PRIx64 \"): taken as the buffer flavour, nothing mapped\\n\",\n"
        b"\t\t             va, size, a3, a4, a5);\n"
        b"\t}\n"
        b"\treturn true;\n"
        b"}\n\n")


def edit(s):
    assert hashlib.md5(s).hexdigest().startswith(IN_MD5), hashlib.md5(s).hexdigest()
    assert s.count(FUNC) == 1 and s.count(COND) == 1 and b"KYTY_BC5_AMM_SETBUFFER_GUARD" not in s
    assert s.index(b"static bool Bc5Exp0401Switch(const char* name) {") < s.index(FUNC) < s.index(COND)
    s = s.replace(FUNC, HELP + FUNC)
    s = s.replace(COND, b"\tif (SetBufferIsMapFlavour(va, a3, a4) && !Bc5SetBufferTargetMapped(va, size, a3, a4, a5)) { // + exp 0413\n")
    return s


if __name__ == "__main__":
    out = edit(open(sys.argv[1], "rb").read())
    open(sys.argv[2], "wb").write(out)
    print(hashlib.md5(out).hexdigest())
