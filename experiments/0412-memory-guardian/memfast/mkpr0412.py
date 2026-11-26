#!/usr/bin/env python3
"""BC5 experiment 0412, tag pr412 (README section 67; the top's order of 2026-11-13: "make the test deterministic at
the address"): the HOST'S READ PROBE.
BC5_GUARD_K1R_PROBE=<hex guest GPU address>[,<seconds after the emulator's start>] (default unset: nothing is done;
default time 200 s). Once, at the first submission after that time, the host submits jobs OF ITS OWN, in a context of
its own (the title's context and its state are not touched; the address space is the title's, since it belongs to the
device file):
  1. a control: the IGT gfx10 buffer-copy program (the one e1-probe uses, cited there) copies 16 KiB from a pattern
     in the probe's own buffer to its destination; the host checks the pattern arrived. If not, the probe is not
     working and nothing more is done or concluded;
  2. the state of the address is journaled (the watched-address text of tag wa412);
  3. the read: the same program copies 16 KiB FROM the given address to the destination; the journal gets the first
     16 bytes, how many of the 16,384 bytes are zero and how many still hold the destination's fill, or that the job
     timed out, with the kernel's fault address and status.
With K1r on and the address under a read-only zero cover the read must return zeros with no kernel line. With K1r off
and the address in the state of the morning's fault (never written, not imported, no mapping) it must fault: a KNOWN
fault, which with BC5_FAULT_RECORD=1 goes through the fault record, the save guard and the exit (they had not fired
once). THE SECOND FORM IS A DELIBERATE GPU FAULT (a ring timeout and reset): only with the maintainer's word.
Backend: Device::probe_read (own context, one 64 KiB buffer at kProbeVa = 0xFDFF000000 holding four command slots, the
program, the destination and the control's pattern; a command slot is used once, as E1 found a rewritten buffer runs
the previous job's words; at most four probes per run).
usage: mkpr0412.py unit <bc5LleAgc.cpp in (after mkwa0412.py)> <out>
       mkpr0412.py backend <backend dir in (after mkk1r0412.py backend)> <backend dir out (a copy of it, or the same directory)>"""
import hashlib
import os
import sys

T = b" // exp 0412 (tag pr412)\n"

UNIT_GLUE = rb'''// Experiment 0412 (tag pr412): BC5_GUARD_K1R_PROBE, the host's own read at one guest GPU address. Default off.
namespace fr412 {
inline bool on();
}
[[noreturn]] static void fr412_record_and_exit(uint64_t fault, uint32_t status, bool timed_out, int rc);
namespace pr412 {
struct Cfg {
	bool     on   = false;
	uint64_t addr = 0;
	double   at_s = 200.0;
};
inline const Cfg& cfg() {
	static const Cfg c = [] {
		Cfg         o;
		const char* e = std::getenv("BC5_GUARD_K1R_PROBE");
		if (e == nullptr || e[0] == 0) return o;
		char* end = nullptr;
		o.addr    = std::strtoull(e, &end, 16);
		if (end == e || o.addr == 0) return o;
		if (*end == ',') {
			const double s = std::strtod(end + 1, nullptr);
			if (s > 0) o.at_s = s;
		}
		o.on = true;
		return o;
	}();
	return c;
}
} // namespace pr412
static void pr412_line(const char* what, const bc5::direct::Device::ProbeRead& p) {
	if (p.stage < 0) {
		journal("probe (exp 0412, tag pr412): %s: NOT RUN (stage %d, rc %d)\n", what, p.stage, p.rc);
	} else if (p.timed_out) {
		journal("probe (exp 0412, tag pr412): %s: THE JOB TIMED OUT after %.0f ms: fault address 0x%" PRIx64 ", status 0x%08x (%s)\n", what, p.ms, p.fault_addr, p.fault_status,
		        p.fault_addr == 0 ? "no fault address" : ((p.fault_status & (1u << 18u)) != 0 ? "a write" : "a read"));
	} else if (!p.ran) {
		journal("probe (exp 0412, tag pr412): %s: the kernel did not take or finish the job (rc %d)\n", what, p.rc);
	} else {
		journal("probe (exp 0412, tag pr412): %s: ran in %.2f ms; first 16 bytes %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x; of 16384 bytes %u are zero, %u still hold the "
		        "destination's fill, %u match the control's pattern\n",
		        what, p.ms, p.bytes[0], p.bytes[1], p.bytes[2], p.bytes[3], p.bytes[4], p.bytes[5], p.bytes[6], p.bytes[7], p.bytes[8], p.bytes[9], p.bytes[10], p.bytes[11], p.bytes[12], p.bytes[13],
		        p.bytes[14], p.bytes[15], p.zero, p.fill, p.pattern);
	}
}
static void pr412_tick(const DState& S, const std::vector<DView>& views, int fd) {
	const auto& c = pr412::cfg();
	if (!c.on || S.kind != 0 || !g_dev) return;
	static bool done = false;
	if (done || timing_now() < c.at_s) return;
	done = true;
	journal("probe (exp 0412, tag pr412): t %.1f s: BC5_GUARD_K1R_PROBE: the host reads 16 KiB at 0x%" PRIx64 " with a job of its own (own context)\n", timing_now(), c.addr);
	const auto ctl = g_dev->probe_read(0);
	pr412_line("control (the probe's own pattern)", ctl);
	if (!ctl.ran || ctl.pattern != 16384) {
		journal("probe (exp 0412, tag pr412): the control did not copy its pattern: the probe is NOT WORKING; the read is not made and nothing follows from this run\n");
		return;
	}
	char text[640];
	wa412_text(S, views, fd, c.addr, text, sizeof(text));
	journal("probe (exp 0412, tag pr412): the address before the read: 0x%" PRIx64 ": %s\n", c.addr, text);
	const auto p = g_dev->probe_read(c.addr);
	pr412_line("the read", p);
	if (p.ran) {
		journal("probe (exp 0412, tag pr412): verdict: the GPU read the address without a fault; %s\n",
		        p.zero == 16384 ? "all 16384 bytes are ZERO" : (p.fill == 16384 ? "the destination still holds its fill: NOTHING WAS STORED (not a valid read)" : "the bytes are not all zero (the title's data)"));
	} else if (p.timed_out) {
		journal("probe (exp 0412, tag pr412): verdict: the read FAULTED or hung; this is the known fault of this probe\n");
		if (fr412::on()) fr412_record_and_exit(p.fault_addr, p.fault_status, true, p.rc);
	}
}
'''

HPP = rb'''    // Experiment 0412 (tag pr412): the host's own read probe. One job in a context of the device's own (the
    // title's context is not touched): the IGT gfx10 buffer-copy program copies 16 KiB from src_va (0: the probe's
    // own pattern, the control) to the probe's destination. At most four per device; a command slot is used once.
    struct ProbeRead {
        int stage = 0;            // < 0: not run (-1 buffer, -2 map, -3 cpu map, -4 context, -5 program, -6 list, -9 used up)
        int rc = 0;
        bool ran = false;         // the fence signalled
        bool timed_out = false;
        double ms = 0;
        std::uint8_t bytes[16]{}; // the destination's first 16 bytes
        std::uint32_t zero = 0, fill = 0, pattern = 0; // of the 16384 destination bytes: zero, still the fill, equal to the control's pattern
        std::uint64_t fault_addr = 0;
        std::uint32_t fault_status = 0;
    };
    ProbeRead probe_read(std::uint64_t src_va);
    static constexpr std::uint64_t kProbeVa = 0xFD'FF00'0000ull;
'''

CPP = rb'''// Experiment 0412 (tag pr412): Device::probe_read. The program is IGT's lib/amdgpu/amd_shaders.c:321-324 @ 9d4b6ef
// (buffercopy_cs_shader_gfx10; MIT, Advanced Micro Devices), as in experiments/0412-memory-guardian/e1/e1-probe.cpp;
// the IB is build_memset_ib() for the source with the four "value" dwords replaced by the destination's V#.
Device::ProbeRead Device::probe_read(std::uint64_t src_va) {
    ProbeRead p;
    std::lock_guard lock(impl_->mutex);
    constexpr std::uint64_t kSize = 65536, kShOff = 0x1000, kDstOff = 0x4000, kCtlOff = 0x8000, kSlot = 0x400;
    constexpr std::uint32_t kBytes = 16384, kSentinel = 0x5e1f0244u;
    static constexpr std::uint32_t kCopy[8] = {0xD7460001, 0x04010C08, 0xE00C2000, 0x80000201, 0xBF8C3F70, 0xE01C2000, 0x80010201, 0xBF810000};
    if (impl_->probe_bo == nullptr) {
        amdgpu_bo_alloc_request req{};
        req.alloc_size = kSize;
        req.phys_alignment = 65536;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_GTT;
        amdgpu_bo_handle bo = nullptr;
        if ((p.rc = amdgpu_bo_alloc(impl_->dev, &req, &bo)) != 0) { p.stage = -1; return p; }
        const std::uint64_t flags = AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE | AMDGPU_VM_PAGE_EXECUTABLE;
        if ((p.rc = amdgpu_bo_va_op_raw(impl_->dev, bo, 0, kSize, kProbeVa, flags, AMDGPU_VA_OP_MAP)) != 0) {
            amdgpu_bo_free(bo);
            p.stage = -2;
            return p;
        }
        void *cpu = nullptr;
        if ((p.rc = amdgpu_bo_cpu_map(bo, &cpu)) != 0) {
            amdgpu_bo_va_op_raw(impl_->dev, bo, 0, kSize, kProbeVa, 0, AMDGPU_VA_OP_UNMAP);
            amdgpu_bo_free(bo);
            p.stage = -3;
            return p;
        }
        amdgpu_context_handle ctx = nullptr;
        if ((p.rc = amdgpu_cs_ctx_create(impl_->dev, &ctx)) != 0) {
            amdgpu_bo_cpu_unmap(bo);
            amdgpu_bo_va_op_raw(impl_->dev, bo, 0, kSize, kProbeVa, 0, AMDGPU_VA_OP_UNMAP);
            amdgpu_bo_free(bo);
            p.stage = -4;
            return p;
        }
        auto *b = static_cast<std::uint8_t *>(cpu);
        std::memset(b, 0, kSize);
        std::memcpy(b + kShOff, kCopy, sizeof(kCopy));
        for (std::uint32_t i = 0; i < kBytes; ++i) b[kCtlOff + i] = static_cast<std::uint8_t>((i * 7u + 1u) | 1u); // never zero
        impl_->probe_bo = bo;
        impl_->probe_cpu = cpu;
        impl_->probe_ctx = ctx;
    }
    if (impl_->probe_n >= 4) { p.stage = -9; return p; }
    auto *b = static_cast<std::uint8_t *>(impl_->probe_cpu);
    const std::uint64_t src = src_va == 0 ? kProbeVa + kCtlOff : src_va;
    const std::uint64_t dst = kProbeVa + kDstOff;
    std::memset(b + kDstOff, 0xA5, kBytes);
    std::vector<std::uint32_t> ib;
    try {
        dispatch_min::MemsetParams mp;
        mp.shader_va = kProbeVa + kShOff;
        mp.dst_va = src;
        mp.dst_bytes = kBytes;
        mp.value = kSentinel;
        mp.gfx_ring = true;
        ib = dispatch_min::build_memset_ib(mp);
    } catch (...) { ib.clear(); }
    std::size_t at = ib.size(), found = 0, singles = 0;
    for (std::size_t i = 0; i + 4 <= ib.size(); ++i) {
        if (ib[i] == kSentinel && ib[i + 1] == kSentinel && ib[i + 2] == kSentinel && ib[i + 3] == kSentinel) {
            at = i;
            found++;
            i += 3;
        }
    }
    for (const std::uint32_t w : ib) singles += w == kSentinel ? 1u : 0u;
    if (found != 1 || singles != 4 || ib.size() * 4 > kSlot) { p.stage = -5; return p; }
    ib[at] = static_cast<std::uint32_t>(dst);
    ib[at + 1] = static_cast<std::uint32_t>(dst >> 32) | 0x100000u; // stride 16, as the source's V#
    ib[at + 2] = kBytes / 16;
    ib[at + 3] = dispatch_min::kIgtVsharpWord3;
    const std::uint64_t slot = static_cast<std::uint64_t>(impl_->probe_n) * kSlot; // a slot is written once (E1's finding)
    impl_->probe_n++;
    std::memcpy(b + slot, ib.data(), ib.size() * 4);
    std::vector<amdgpu_bo_handle> bos = {impl_->probe_bo};
    for (const auto &m : impl_->shared_maps) {
        if (m.bo != nullptr && src < m.va + m.size && src + kBytes > m.va && std::find(bos.begin(), bos.end(), m.bo) == bos.end()) bos.push_back(m.bo);
    }
    amdgpu_bo_list_handle list = nullptr;
    if ((p.rc = amdgpu_bo_list_create(impl_->dev, static_cast<std::uint32_t>(bos.size()), bos.data(), nullptr, &list)) != 0) { p.stage = -6; return p; }
    amdgpu_cs_ib_info info{};
    info.ib_mc_address = kProbeVa + slot;
    info.size = static_cast<std::uint32_t>(ib.size());
    amdgpu_cs_request req{};
    req.ip_type = AMDGPU_HW_IP_GFX;
    req.ring = 0;
    req.resources = list;
    req.number_of_ibs = 1;
    req.ibs = &info;
    const double t0 = now_ms();
    p.stage = 1;
    p.rc = amdgpu_cs_submit(impl_->probe_ctx, 0, &req, 1);
    if (p.rc == 0) {
        amdgpu_cs_fence fence{};
        fence.context = impl_->probe_ctx;
        fence.ip_type = AMDGPU_HW_IP_GFX;
        fence.ring = 0;
        fence.fence = req.seq_no;
        std::uint32_t expired = 0;
        p.rc = amdgpu_cs_query_fence_status(&fence, 2'000'000'000ull, 0, &expired);
        if (p.rc == 0 && expired != 0) {
            p.ran = true;
        } else if (p.rc == 0) {
            p.timed_out = true;
#ifdef AMDGPU_INFO_GPUVM_FAULT
            drm_amdgpu_info_gpuvm_fault fault{};
            if (amdgpu_query_info(impl_->dev, AMDGPU_INFO_GPUVM_FAULT, sizeof(fault), &fault) == 0) {
                p.fault_addr = fault.addr;
                p.fault_status = fault.status;
            }
#endif
        }
    }
    p.ms = now_ms() - t0;
    amdgpu_bo_list_destroy(list);
    if (p.ran) {
        std::memcpy(p.bytes, b + kDstOff, 16);
        for (std::uint32_t i = 0; i < kBytes; ++i) {
            p.zero += b[kDstOff + i] == 0 ? 1u : 0u;
            p.fill += b[kDstOff + i] == 0xA5 ? 1u : 0u;
            p.pattern += b[kDstOff + i] == b[kCtlOff + i] ? 1u : 0u;
        }
    }
    return p;
}

'''


def once(s, old, new):
    assert s.count(old) == 1, ("an anchor does not occur exactly once", old[:70], s.count(old))
    return s.replace(old, new)


def unit(src, out):
    s = open(src, "rb").read()
    assert b"\r" not in s and b"tag wa412" in s and b"static void wa412_text(" in s and b"tag pr412" not in s, "refused: not the unit after mkwa0412.py, or already edited"
    UNIT_GLUE.decode("ascii")
    a = b"static void direct_sync_one(DState& S, bool force) {\n"
    s = once(s, a, UNIT_GLUE + a)
    a = b"\twa412_look(S, views, fd); // exp 0412 (tag wa412)\n"
    s = once(s, a, a + b"\tpr412_tick(S, views, fd);" + T)
    assert s.index(b"static void wa412_text(") < s.index(b"static void pr412_tick(") < s.index(b"[[noreturn]] static void fr412_record_and_exit(uint64_t fault, uint32_t status, bool timed_out, int rc) {")
    assert s.count(b"inline bool on() {\n\tstatic const bool v = [] {\n\t\tconst char* e = std::getenv(\"BC5_FAULT_RECORD\");") == 1
    open(out, "wb").write(s)
    print(f"bc5LleAgc.cpp {hashlib.md5(s).hexdigest()}")


def backend(src, out):
    for rel, fn in (("include/bc5/direct.hpp", lambda s: once(s, b"    void *code_area();\n", b"    void *code_area();\n" + HPP)),
                    ("src/direct.cpp", backend_cpp)):
        s = open(os.path.join(src, rel), "rb").read()
        assert b"\r" not in s and b"tag pr412" not in s and b"tag k1r412" in s, "refused: not the backend after mkk1r0412.py backend, or already edited"
        s = fn(s)
        open(os.path.join(out, rel), "wb").write(s)
        print(f"{rel} {hashlib.md5(s).hexdigest()}")


def backend_cpp(s):
    HPP.decode("ascii")
    CPP.decode("ascii")
    s = once(s, b'#include "bc5/direct.hpp"\n', b'#include "bc5/direct.hpp"\n#include "bc5/dispatch_min.hpp" // exp 0412 (tag pr412)\n')
    s = once(s, b"    std::mutex mutex;\n", b"    std::mutex mutex;\n    amdgpu_bo_handle probe_bo = nullptr; // exp 0412 (tag pr412): Device::probe_read\n    void *probe_cpu = nullptr;\n"
             b"    amdgpu_context_handle probe_ctx = nullptr;\n    int probe_n = 0;\n")
    a = b"bool Device::wait_idle(std::uint64_t timeout_ns) {\n"
    return once(s, a, CPP + a)


def main():
    assert len(sys.argv) == 4 and sys.argv[1] in ("unit", "backend") and (sys.argv[1] == "backend" or sys.argv[2] != sys.argv[3]), __doc__
    (unit if sys.argv[1] == "unit" else backend)(sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()
