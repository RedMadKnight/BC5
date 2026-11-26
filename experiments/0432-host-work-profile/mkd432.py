#!/usr/bin/env python3
"""BC5 experiment 0432, item D (tag d432): no host wait for an idle GPU before a mapping change.
    mkd432.py <bc5LleAgc.cpp of patch bc39a035 (md5 b8afba59)> <out bc5LleAgc.cpp>
Every replacement must match exactly once.

What changes (switch BC5_DIRECT_UNMAP_NOWAIT, read with plain getenv so the lean build has it; unset or anything but
"0": the new path; "0": the old blocking path, byte for byte the old calls):
  - direct_sync_one: where the rebuild called wait_jobs() (Device::wait_idle, up to 2 s per ring, under g_dev_mutex),
    the new path only flushes the thread's chain (as wait_jobs did first) and goes on. The unmap is deferred by the
    kernel: amdgpu_vm_clear_freed() syncs the page-table clear to the same VM's command submissions
    (amdgpu_sync_resv(..., AMDGPU_SYNC_EQ_OWNER, vm), "Implicitly sync to command submissions in the same VM before
    unmapping"), the VA ioctl only schedules it, and later submissions depend on vm->last_update
    (amdgpu_cs_vm_handling). Source: torvalds/linux master, amdgpu_vm.c, amdgpu_gem.c, amdgpu_cs.c, read 2026-11-17;
    TODO(verify): the same lines in the box's kernel 7.3.3-ogc1.1.
  - lzr_confirm: on the new path a lazy-release cut stands without the idle test (the test only passed after the drain).
  - counters, one stderr line and one journal line at most every 10 s: rebuilds that would have drained, how many of
    them found a ring busy, mappings dropped and BOs retired while busy (the deferred unmaps), the old path's drains
    with their total and longest wait, and the longest sync+hints part of a submission ("prepare").
Nothing is recovered, dropped or learned; a GPU fault stays a fault with its record (BC5_FAULT_RECORD).
"""
import hashlib, sys

src, dst = sys.argv[1], sys.argv[2]
b = open(src, "rb").read()
assert hashlib.md5(b).hexdigest()[:8] == "b8afba59", "not the bc5LleAgc.cpp of patch bc39a035"
s = b.decode("utf-8")
assert "\r" not in s


def sub(old, new, n=1):
    global s
    got = s.count(old)
    assert got == n, "%d matches, wanted %d: %r" % (got, n, old[:80])
    s = s.replace(old, new)


# 1. the switch and the counters, in front of lzr_confirm
sub("static void lzr_confirm(DState& S, LzrPass& pass, std::vector<uint32_t>& retired) {\n"
    "\tif (pass.done.empty() || !g_dev) return;\n"
    "\tif (g_dev->wait_idle(0)) return;\n",
    "// exp 0432 item D (tag d432): BC5_DIRECT_UNMAP_NOWAIT. Unset or not \"0\": a mapping change does not wait for an idle GPU\n"
    "// (the kernel orders the page-table clear behind this VM's submissions: amdgpu_vm_clear_freed, AMDGPU_SYNC_EQ_OWNER;\n"
    "// TODO(verify) on the box's kernel). \"0\": the old blocking wait_jobs().\n"
    "namespace d432 {\n"
    "inline bool on() {\n"
    "\tstatic const bool v = [] {\n"
    "\t\tconst char* e = std::getenv(\"BC5_DIRECT_UNMAP_NOWAIT\");\n"
    "\t\treturn !(e != nullptr && e[0] == '0' && e[1] == 0);\n"
    "\t}();\n"
    "\treturn v;\n"
    "}\n"
    "inline std::atomic<uint64_t> g_rebuilds {0}, g_busy {0}, g_unmaps_busy {0}, g_bos_busy {0}, g_unmaps {0}, g_drains {0}, g_drain_ns {0}, g_drain_max_ns {0},\n"
    "    g_prep_max_ns {0}, g_prep_over20 {0}, g_last_ns {0};\n"
    "inline void maxed(std::atomic<uint64_t>& m, uint64_t v) {\n"
    "\tuint64_t was = m.load(std::memory_order_relaxed);\n"
    "\twhile (v > was && !m.compare_exchange_weak(was, v, std::memory_order_relaxed)) {\n"
    "\t}\n"
    "}\n"
    "} // namespace d432\n"
    "static void lzr_confirm(DState& S, LzrPass& pass, std::vector<uint32_t>& retired) {\n"
    "\tif (pass.done.empty() || !g_dev) return;\n"
    "\tif (d432::on()) return; // exp 0432 (tag d432): the cut stands, the kernel retires the old mappings behind the jobs in flight\n"
    "\tif (g_dev->wait_idle(0)) return;\n")

# 2. the drain (chain_flush is declared further down in the unit: one more declaration beside wait_jobs')
sub("static void wait_jobs();\n", "static void wait_jobs();\nstatic void chain_flush(int why); // exp 0432 (tag d432)\n")
sub("\t\twait_jobs(); // mappings are about to go or be replaced\n"
    "\t\tg_dprof_drains++;\n"
    "\t}\n",
    "\t\td432::g_rebuilds++;\n"
    "\t\tif (d432::on()) { // exp 0432 (tag d432): no wait; the chain is flushed as wait_jobs() did first\n"
    "\t\t\tchain_flush(5);\n"
    "\t\t\td432_busy = !g_dev->wait_idle(0); // a count only: was anything in flight\n"
    "\t\t\tif (d432_busy) d432::g_busy++;\n"
    "\t\t} else {\n"
    "\t\t\twait_jobs(); // mappings are about to go or be replaced\n"
    "\t\t\tg_dprof_drains++;\n"
    "\t\t\tconst uint64_t w = SoftCp::now_ns() - t_drain0;\n"
    "\t\t\td432::g_drains++;\n"
    "\t\t\td432::g_drain_ns += w;\n"
    "\t\t\td432::maxed(d432::g_drain_max_ns, w);\n"
    "\t\t}\n"
    "\t}\n")
sub("\tconst uint64_t t_drain0 = SoftCp::now_ns(); // experiment 0169\n",
    "\tconst uint64_t t_drain0 = SoftCp::now_ns(); // experiment 0169\n"
    "\tbool           d432_busy = false;           // exp 0432 (tag d432)\n")

# 3. what went while a ring was busy
sub("\tfor (const uint32_t id: retired) g_dev->free_shared(id);\n"
    "\tguard0412_after_cuts(lzr.done.size()); // exp 0412 (tag g412c): BC5_GUARD_SPLIT\n",
    "\td432::g_unmaps += unmapped; // exp 0432 (tag d432)\n"
    "\tif (d432_busy) {\n"
    "\t\td432::g_unmaps_busy += unmapped;\n"
    "\t\td432::g_bos_busy += retired.size();\n"
    "\t}\n"
    "\tfor (const uint32_t id: retired) g_dev->free_shared(id);\n"
    "\tguard0412_after_cuts(lzr.done.size()); // exp 0412 (tag g412c): BC5_GUARD_SPLIT\n")

# 4. the prepare time of a submission and the line
sub("\thint_targets(ib, num_dwords);\n"
    "\tconst uint64_t t2 = SoftCp::now_ns();\n",
    "\thint_targets(ib, num_dwords);\n"
    "\tconst uint64_t t2 = SoftCp::now_ns();\n"
    "\t{ // exp 0432 (tag d432): the longest sync + hints part (\"prepare\"), and the counters at most every 10 s\n"
    "\t\td432::maxed(d432::g_prep_max_ns, t2 - t0);\n"
    "\t\tif (t2 - t0 > 20'000'000ull) d432::g_prep_over20++;\n"
    "\t\tuint64_t was = d432::g_last_ns.load(std::memory_order_relaxed);\n"
    "\t\tif (t2 - was >= 10'000'000'000ull && d432::g_last_ns.compare_exchange_strong(was, t2)) {\n"
    "\t\t\tchar line[512];\n"
    "\t\t\tstd::snprintf(line, sizeof(line),\n"
    "\t\t\t              \"exp 0432 (tag d432): t %.1f s: unmap-nowait %s; rebuilds that change mappings %\" PRIu64 \", with a ring busy %\" PRIu64 \"; mappings dropped %\" PRIu64\n"
    "\t\t\t              \", while busy (deferred to the kernel) %\" PRIu64 \", BOs retired while busy %\" PRIu64 \"; blocking drains %\" PRIu64 \", %.1f ms in all, longest %.1f ms\"\n"
    "\t\t\t              \"; prepare (sync+hints) longest %.1f ms, over 20 ms %\" PRIu64,\n"
    "\t\t\t              timing_now(), d432::on() ? \"ON\" : \"off (old wait)\", d432::g_rebuilds.load(), d432::g_busy.load(), d432::g_unmaps.load(), d432::g_unmaps_busy.load(),\n"
    "\t\t\t              d432::g_bos_busy.load(), d432::g_drains.load(), static_cast<double>(d432::g_drain_ns.load()) / 1e6, static_cast<double>(d432::g_drain_max_ns.load()) / 1e6,\n"
    "\t\t\t              static_cast<double>(d432::g_prep_max_ns.load()) / 1e6, d432::g_prep_over20.load());\n"
    "\t\t\tstd::fprintf(stderr, \"[bc5] %s\\n\", line);\n"
    "\t\t\tjournal(\"%s\\n\", line);\n"
    "\t\t}\n"
    "\t}\n")
open(dst, "w", encoding="utf-8", newline="\n").write(s)
print("wrote", dst, hashlib.md5(s.encode("utf-8")).hexdigest()[:8])
