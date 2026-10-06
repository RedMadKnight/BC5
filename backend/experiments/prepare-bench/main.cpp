// prepare-bench — experiment 0027: where the host's `prepare` pass over a command buffer spends
// its time, offline. Loads raw command buffers (the host's BC5_GC_DUMP_DIR dumps: little-endian
// dwords, one file per buffer) and runs the steps of Device::submit that precede the CS ioctl, each
// timed on its own: the policy filter, the executed-offsets scan, the state-stack tracker, the
// CU-mask tables, and the copy into a destination buffer — ordinary memory here, where the device
// writes into its uncached scratch. Nested INDIRECT_BUFFER targets are not available offline and
// count as unmapped. Nothing here touches a GPU.
//
//   prepare-bench [--repeat N] [--no-mapped] <buffer.bin>...
//
// Output: one line per buffer with the phase times in ms (median over the repetitions), then a
// total line. GPL-2.0.

#include "bc5/cu_tables.hpp"
#include "bc5/policy.hpp"
#include "bc5/state_stack.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

namespace {

double now_ms() {
    return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

// As Device::submit's helper: which type-3 packets survived the filter.
void executed_offsets_of(std::span<const std::uint32_t> src, const std::uint32_t *dst,
                         std::vector<std::uint32_t> &out) {
    for (std::size_t i = 0; i < src.size();) {
        const std::uint32_t h = src[i];
        const std::uint32_t type = h >> 30;
        std::size_t len = 1;
        if (type == 3) {
            const std::uint32_t count = (h >> 16) & 0x3fff;
            len = count == 0x3fff ? 1 : count + 2;
            const std::uint32_t op_in = (h >> 8) & 0xff;
            const std::uint32_t op_out = (dst[i] >> 8) & 0xff;
            if (op_in != 0x10 && (dst[i] >> 30) == 3 && op_out != 0x10)
                out.push_back(static_cast<std::uint32_t>(i));
        } else if (type == 0) {
            len = ((h >> 16) & 0x3fff) + 2;
        } else if (type == 2) {
            len = 1;
        } else {
            break;
        }
        i += len;
    }
}

struct Phases {
    double filter = 0, offsets = 0, tracker = 0, cu = 0, copy = 0, repoint = 0;
    std::size_t in = 0, out = 0;
    bc5::policy::FilterStats fs;
    bc5::state_stack::Stats ss;
    bc5::cu_tables::Stats cs;
};

Phases run_once(const std::vector<std::uint32_t> &ib, bool mapped_all, std::vector<std::uint32_t> &dst,
                bc5::state_stack::Tracker &tracker) {
    Phases p;
    bc5::policy::FilterOptions opt;
    // The host's mapped() answers from its mapping table; offline everything the IB names is
    // either taken as mapped (--no-mapped off) or as unmapped. Both are bounds for the real cost.
    opt.mapped = [mapped_all](std::uint64_t, std::uint64_t) { return mapped_all; };
    opt.cu_mask = 0xffffffffu;

    std::vector<std::uint32_t> main_out(ib.size());
    double t = now_ms();
    bc5::policy::filter(bc5::policy::Policy::builtin(), ib, main_out, opt, p.fs);
    p.filter = now_ms() - t;

    std::vector<std::uint32_t> offsets;
    t = now_ms();
    executed_offsets_of(ib, main_out.data(), offsets);
    p.offsets = now_ms() - t;

    t = now_ms();
    main_out = tracker.apply(ib, main_out, opt.mapped, p.ss);
    p.tracker = now_ms() - t;

    t = now_ms();
    main_out = bc5::cu_tables::apply(main_out, opt.cu_mask, opt.mapped, p.cs);
    p.cu = now_ms() - t;

    // the copy into the scratch (here: a plain buffer; the device's is MTYPE_UC)
    const std::size_t padded = (main_out.size() + 7) & ~std::size_t{7};
    if (dst.size() < padded) dst.resize(padded);
    t = now_ms();
    for (std::size_t i = 0; i < main_out.size(); ++i) dst[i] = main_out[i];
    for (std::size_t i = main_out.size(); i < padded; ++i) dst[i] = bc5::policy::kNop;
    p.copy = now_ms() - t;

    // the second pass over the destination: INDIRECT_BUFFER packets re-pointed (none resolve offline)
    t = now_ms();
    for (std::size_t i = 0; i < main_out.size();) {
        const std::uint32_t h = dst[i];
        const std::uint32_t type = h >> 30;
        std::size_t len = 1;
        if (type == 3 || type == 0) {
            const std::uint32_t count = (h >> 16) & 0x3fff;
            len = count == 0x3fff ? 1 : count + 2;
        }
        if (i + len > main_out.size()) break;
        const std::uint32_t op = (h >> 8) & 0xff;
        if (type == 3 && (op == 0x3f || op == 0x33) && len >= 4) {
            for (std::size_t q = 0; q < len; ++q) dst[i + q] = bc5::policy::kNop;
        }
        i += len;
    }
    p.repoint = now_ms() - t;
    p.in = ib.size();
    p.out = main_out.size();
    return p;
}

double median(std::vector<double> v) {
    std::sort(v.begin(), v.end());
    return v.empty() ? 0.0 : v[v.size() / 2];
}

} // namespace

int main(int argc, char **argv) {
    int repeat = 7;
    bool mapped_all = true;
    std::vector<std::string> files;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a == "--repeat" && i + 1 < argc) {
            repeat = std::atoi(argv[++i]);
        } else if (a == "--no-mapped") {
            mapped_all = false;
        } else {
            files.push_back(a);
        }
    }
    if (files.empty()) {
        std::fprintf(stderr, "usage: prepare-bench [--repeat N] [--no-mapped] <buffer.bin>...\n");
        return 2;
    }
    std::printf("%-28s %7s %7s | %7s %7s %7s %7s %7s %7s | %7s | pops/restored/inserted\n", "buffer", "dwords", "out", "filter",
                "offsets", "tracker", "cu", "copy", "repoint", "total");
    double sum = 0;
    std::vector<std::uint32_t> dst;
    for (const auto &f : files) {
        std::ifstream in(f, std::ios::binary);
        std::vector<char> bytes((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
        std::vector<std::uint32_t> ib(bytes.size() / 4);
        std::memcpy(ib.data(), bytes.data(), ib.size() * 4);
        if (ib.empty()) continue;
        std::vector<double> t_filter, t_offsets, t_tracker, t_cu, t_copy, t_repoint;
        Phases last;
        for (int r = 0; r < repeat; ++r) {
            bc5::state_stack::Tracker tracker; // fresh per run, as the device's is per context
            last = run_once(ib, mapped_all, dst, tracker);
            t_filter.push_back(last.filter);
            t_offsets.push_back(last.offsets);
            t_tracker.push_back(last.tracker);
            t_cu.push_back(last.cu);
            t_copy.push_back(last.copy);
            t_repoint.push_back(last.repoint);
        }
        const double total = median(t_filter) + median(t_offsets) + median(t_tracker) + median(t_cu) + median(t_copy) + median(t_repoint);
        sum += total;
        std::string name = f;
        if (const auto s = name.find_last_of('/'); s != std::string::npos) name = name.substr(s + 1);
        std::printf("%-28s %7zu %7zu | %7.3f %7.3f %7.3f %7.3f %7.3f %7.3f | %7.3f | %u/%u/%u\n", name.c_str(), last.in, last.out,
                    median(t_filter), median(t_offsets), median(t_tracker), median(t_cu), median(t_copy), median(t_repoint), total,
                    last.ss.pops, last.ss.restored_regs, last.ss.inserted_dwords);
    }
    std::printf("total over %zu buffers: %.3f ms\n", files.size(), sum);
    return 0;
}
