#!/usr/bin/env python3
"""BC5 experiment 0432, item S (tag s432): the job slot's buffer (Impl::scratch_reserve in backend/src/direct.cpp).
    mkbe432.py <backend/src/direct.cpp of main f98799a0 (md5 5016c2a4)> <out direct.cpp>
Every replacement must match exactly once.

Found in the journals of 2026-11-17 (README): a frame's "copy" part of the submit preparation took 491-1118 ms six
times in two runs. The only system calls of that part are here: a slot whose buffer is too small is CPU-unmapped,
GPU-unmapped, freed, allocated at exactly the new size, GPU-mapped at the same address and CPU-mapped. The 128 slots are
used round-robin and each grows on its own, so resizes go on through a whole play.

Changes:
  - every resize is timed by step; a resize over 20 ms prints its steps on stderr, and every 64th resize a summary
    (count, total, longest);
  - BC5_DIRECT_SLOT_GROW (plain getenv; unset or not "0": on): the new size is the next power of two at or above what
    is needed, at least 64 KiB, so a slot is resized a handful of times instead of at each larger job; "0": the exact
    size as before. Sizes stay page multiples; the mapping flags (MTYPE_UC) and the address are unchanged.
"""
import hashlib, sys

src, dst = sys.argv[1], sys.argv[2]
b = open(src, "rb").read().replace(b"\r\n", b"\n")
assert hashlib.md5(b).hexdigest()[:8] == "5016c2a4", "not main's direct.cpp 5016c2a4: " + hashlib.md5(b).hexdigest()[:8]
s = b.decode("utf-8")


def sub(old, new, n=1):
    global s
    got = s.count(old)
    assert got == n, "%d matches, wanted %d: %r" % (got, n, old[:80])
    s = s.replace(old, new)


sub("        if (scratch.bo != nullptr && scratch.size >= bytes) return true;\n"
    "        scratch_free();\n",
    "        if (scratch.bo != nullptr && scratch.size >= bytes) return true;\n"
    "        // exp 0432 (tag s432): the resize by step, and BC5_DIRECT_SLOT_GROW\n"
    "        static const bool s432_grow = [] {\n"
    "            const char *e = std::getenv(\"BC5_DIRECT_SLOT_GROW\");\n"
    "            return !(e != nullptr && e[0] == '0' && e[1] == 0);\n"
    "        }();\n"
    "        static std::uint64_t s432_n = 0, s432_bytes = 0;\n"
    "        static double s432_total = 0, s432_max = 0;\n"
    "        const std::uint64_t s432_old = scratch.size;\n"
    "        double s432_t[4] = {now_ms(), 0, 0, 0};\n"
    "        scratch_free();\n"
    "        s432_t[1] = now_ms();\n")
sub("        std::uint64_t size = (bytes + 4095) & ~std::uint64_t{4095};\n"
    "        if (size == 0) size = 4096;\n",
    "        std::uint64_t size = (bytes + 4095) & ~std::uint64_t{4095};\n"
    "        if (size == 0) size = 4096;\n"
    "        if (s432_grow) { // exp 0432 (tag s432): the next power of two, at least 64 KiB\n"
    "            std::uint64_t p = 65536;\n"
    "            while (p < size) p <<= 1;\n"
    "            size = p;\n"
    "        }\n")
sub("        if (amdgpu_bo_alloc(dev, &req, &scratch.bo) != 0) return false;\n",
    "        if (amdgpu_bo_alloc(dev, &req, &scratch.bo) != 0) return false;\n"
    "        s432_t[2] = now_ms();\n")
sub("        if (amdgpu_bo_cpu_map(scratch.bo, &scratch.cpu) != 0) return false;\n"
    "        scratch.size = size;\n"
    "        return true;\n",
    "        s432_t[3] = now_ms();\n"
    "        if (amdgpu_bo_cpu_map(scratch.bo, &scratch.cpu) != 0) return false;\n"
    "        scratch.size = size;\n"
    "        { // exp 0432 (tag s432)\n"
    "            const double end = now_ms(), all = end - s432_t[0];\n"
    "            s432_n++;\n"
    "            s432_total += all;\n"
    "            s432_bytes += size;\n"
    "            if (all > s432_max) s432_max = all;\n"
    "            if (all > 20.0)\n"
    "                std::fprintf(stderr, \"bc5-direct: exp 0432 (tag s432): slot %d resize %llu -> %llu bytes (asked %llu) took %.1f ms: unmap+free %.1f, alloc %.1f, gpu map %.1f, cpu map %.1f\\n\",\n"
    "                             cur, static_cast<unsigned long long>(s432_old), static_cast<unsigned long long>(size), static_cast<unsigned long long>(bytes), all,\n"
    "                             s432_t[1] - s432_t[0], s432_t[2] - s432_t[1], s432_t[3] - s432_t[2], end - s432_t[3]);\n"
    "            if (s432_n <= 2 || (s432_n & 63u) == 0)\n"
    "                std::fprintf(stderr, \"bc5-direct: exp 0432 (tag s432): slot grow %s; %llu resizes, %.1f ms in all, longest %.1f ms, %llu KiB allocated in all\\n\",\n"
    "                             s432_grow ? \"ON\" : \"off (exact size)\", static_cast<unsigned long long>(s432_n), s432_total, s432_max,\n"
    "                             static_cast<unsigned long long>(s432_bytes >> 10));\n"
    "        }\n"
    "        return true;\n")
# Item P (tag s432, BC5_DIRECT_SLOT_PREALLOC; on unless "0"). Found in build 1's runs: "slot 0 resize 524288 -> 4194304
# bytes took 683.0 ms: unmap+free 0.1, alloc 682.7, ...": the stall is amdgpu_bo_alloc in the middle of play. Build 2
# (a4ee7fd6) also moved a job that did not fit its slot to a free larger slot of its pool. THAT WAS A BUG AND IS REMOVED:
# the rotation later reached such a slot while it was busy, Device::submit returned -EBUSY and the host lost the job
# (142 submissions "FAILED rc -16" in 45 s), a later job waited for work that never ran, the gfx ring timed out, its
# reset failed and the box rebooted (run d432T13, 2026-11-17 16:15:24, fault record 20261117-161524). Build 3: every
# slot's buffer is made once at Device::open; no job changes its slot.
# Build 3 made every slot 256 KiB: the small allocations went, but a job of 3.3-4.1 MB still allocated in play
# ("slot 16 resize 262144 -> 4194304 bytes took 958.5 ms: ... alloc 958.3", "slot 24 ... 1354.1 ms"). Every such resize
# seen in builds 1 and 3 was on a GFX-ring slot (0, 16, 20, 24, 26, 27, 28, 29, 6), and those placed in time were at the
# title's start (t 40-51 s), while the box reclaims and swaps for the title's first pins. Default 256:256 (32 MiB of
# GTT, said on stderr; the top session, 2026-11-17: 4 MiB for each GFX slot is not worth 120 MiB more pinned on a box
# that swaps at start). BC5_DIRECT_SLOT_PREALLOC=<GFX KiB>:<other KiB> sets other sizes for a later test (2048:256);
# "0" turns the item off.
# A job larger than its slot grows it as before (counted and timed).
sub("    void scratch_free() {\n",
    "    // exp 0432 (tag s432): see mkbe432.py, item P\n"
    "    static bool s432_prealloc() {\n"
    "        static const bool v = [] {\n"
    "            const char *e = std::getenv(\"BC5_DIRECT_SLOT_PREALLOC\");\n"
    "            return !(e != nullptr && e[0] == '0' && e[1] == 0);\n"
    "        }();\n"
    "        return v;\n"
    "    }\n"
    "\n"
    "    void scratch_free() {\n")
sub("        if (wrc != 0) d->impl_->gws = nullptr;\n"
    "    }\n"
    "    return d;\n",
    "        if (wrc != 0) d->impl_->gws = nullptr;\n"
    "    }\n"
    "    if (Impl::s432_prealloc()) { // exp 0432 (tag s432): the large slot buffers, once, before the title maps anything\n"
    "        const double t0 = now_ms();\n"
    "        int made = 0, failed = 0;\n"
    "        std::uint64_t gfx_kib = 256, comp_kib = 256, total_kib = 0; // BC5_DIRECT_SLOT_PREALLOC=<GFX KiB>:<other KiB> sets other sizes\n"
    "        if (const char *e = std::getenv(\"BC5_DIRECT_SLOT_PREALLOC\"); e != nullptr) {\n"
    "            unsigned long long a = 0, b = 0;\n"
    "            if (std::sscanf(e, \"%llu:%llu\", &a, &b) == 2 && a <= 16384 && b <= 16384) {\n"
    "                gfx_kib = a;\n"
    "                comp_kib = b;\n"
    "            }\n"
    "        }\n"
    "        for (int k = 0; k < Impl::kSlots; ++k) {\n"
    "            d->impl_->cur = k;\n"
    "            const std::uint64_t want = k < Impl::kGfxSlots ? gfx_kib : comp_kib;\n"
    "            if (want == 0) continue;\n"
    "            (d->impl_->scratch_reserve(want << 10) ? made : failed)++;\n"
    "            total_kib += want;\n"
    "        }\n"
    "        d->impl_->cur = Impl::pool_first(kGfxRing);\n"
    "        std::fprintf(stderr, \"bc5-direct: exp 0432 (tag s432): slot prealloc: %d buffers made (%d failed) in %.1f ms: %llu KiB for each of the %d GFX-ring slots, %llu KiB for each of the others, %llu MiB of GTT in all\\n\", made, failed,\n"
    "                     now_ms() - t0, static_cast<unsigned long long>(gfx_kib), Impl::kGfxSlots, static_cast<unsigned long long>(comp_kib),\n"
    "                     static_cast<unsigned long long>(total_kib >> 10));\n"
    "    }\n"
    "    return d;\n")
open(dst, "w", encoding="utf-8", newline="\n").write(s)
print("wrote", dst, hashlib.md5(s.encode("utf-8")).hexdigest()[:8])
