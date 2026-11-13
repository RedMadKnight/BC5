// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0418 section 3b: who in the title's driver sends each /dev/gc request.
//
// The KytyPlus unit (patch 0001, src/bc5/gc_trace.hpp, an identical copy) traces the first calls of each /dev/gc request
// code (BC5_GC_IOCTL_TRACE=1, diagnostic, compiled out of the lean build). For each it writes the bytes passed in and
// the guest return addresses, each with its module and the nearest exported function before it, by NID. The NIDs are
// named afterwards from public tables (experiments/0418-console-start-state/impl/nid-names.py); nothing here reads
// the title's code, only the stack and the module's dynamic symbol table that the loader already parsed.
//
// The pure parts are here so they can be unit-tested: the frame-pointer walk with its stop rules, the stack-word scan,
// the nearest-export search and the NID of a symbol name. The reads of guest memory are the caller's (the unit uses
// process_vm_readv on its own pid, so a bad address is an error, not a fault).
#pragma once

#include <cstddef>
#include <cstdint>
#include <string_view>

namespace bc5::gc_trace {

// How many calls of each request code are traced, and how many frames each.
inline constexpr int kCallsPerCode = 8;
inline constexpr int kMaxFrames = 8;
// A frame chain longer than this from the first frame is not trusted (a guest thread's stack is far smaller).
inline constexpr std::uint64_t kMaxSpan = 1ull << 20;

// The frame-pointer walk. `fp` is a frame address whose two quadwords are {the caller's frame pointer, the return
// address}: on x86-64 with frame pointers, [rbp] and [rbp + 8]. `read(addr, two)` reads two quadwords and returns false
// when it cannot. Stops at a null, misaligned, non-increasing or too-distant frame, a failed read or a zero return
// address, so a caller without frame pointers ends the walk instead of misleading it. Returns the count written.
template <class Read>
int walk_frames(std::uint64_t fp, Read read, std::uint64_t *ret, int max) {
    const std::uint64_t first = fp;
    int n = 0;
    while (n < max) {
        if (fp == 0 || (fp & 7u) != 0 || fp < first || fp - first > kMaxSpan) break;
        std::uint64_t w[2] = {0, 0};
        if (!read(fp, w)) break;
        if (w[1] == 0) break;
        ret[n++] = w[1];
        if (w[0] <= fp) break;
        fp = w[0];
    }
    return n;
}

// The stack-word scan, for callers built without frame pointers: of `count` words read above the first frame, those
// `is_code(word)` accepts (an address inside a loaded module's executable segment), at most `max`, in stack order.
template <class IsCode>
int scan_words(const std::uint64_t *words, std::size_t count, IsCode is_code, std::uint64_t *out, int max) {
    int n = 0;
    for (std::size_t i = 0; i < count && n < max; ++i)
        if (words[i] != 0 && is_code(words[i])) out[n++] = words[i];
    return n;
}

struct Export {
    std::uint64_t addr; // absolute address of an exported function
    std::string_view name; // its symbol name as the module's dynamic string table has it ("NID#L#M")
};

// The exported function at or before `addr`: the one with the greatest address not above it. `exports` need not be
// sorted. Returns nullptr when none is at or below `addr`.
inline const Export *nearest_export(const Export *exports, std::size_t count, std::uint64_t addr) {
    const Export *best = nullptr;
    for (std::size_t i = 0; i < count; ++i)
        if (exports[i].addr <= addr && (best == nullptr || exports[i].addr > best->addr)) best = &exports[i];
    return best;
}

// The NID of a dynamic symbol name: the part before the first '#' ("NID#library#module" in the loader's reading,
// RuntimeLinker::CreateSymbolDatabase). A name without '#' is returned whole.
inline std::string_view nid_of(std::string_view symbol_name) {
    const std::size_t h = symbol_name.find('#');
    return h == std::string_view::npos ? symbol_name : symbol_name.substr(0, h);
}

} // namespace bc5::gc_trace
