#!/usr/bin/env python3
"""BC5 experiment 0417: the counter that answers "can the EOP ring's wrap happen in practice" (the top session,
2026-11-13, after our own test confirmed Codex's mechanism: the old ring was wrong once 4,096 chained EOP publications
fell between ONE event's push and its callback).

BC5_R3_EOP_STAT=1, default off, measurement only (the owned copy of exp 0416 stays as it is): every chained EOP
publication gets a running number at its push; when its deferred callback runs, the number of publications made
since is taken. The journal gets a line at every new maximum:
  eop stat (exp 0417): <d> chained EOP publications between a push and its callback (a new maximum; <n> callbacks so
  far; the old ring wrapped at 4096)
One second-title run with BC5_R3_SUBMIT_EOP_EVENT=1 and this switch answers it: a maximum far below 4,096 means the
old defect could not have fired in such a run. With the switch off the pushed entry carries 0 and nothing is counted.
usage: mkeop0417.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import sys

src, dst = sys.argv[1:3]
s = open(src, "rb").read()
assert b"\r" not in s and b"BC5_R3_EOP_STAT" not in s


def rep(old, new):
    global s
    assert s.count(old) == 1, (old[:70], s.count(old))
    s = s.replace(old, new)


rep(b"\tstd::shared_ptr<const std::vector<uint32_t>> owned {}; // host-generated replay only; captured by value with e\n",
    b"\tstd::shared_ptr<const std::vector<uint32_t>> owned {}; // host-generated replay only; captured by value with e\n"
    b"\tuint64_t pub = 0; // exp 0417 (BC5_R3_EOP_STAT): the running number of this chained EOP publication, 0 when not counted\n")
rep(b"static void chain_post_soft_locked(ChainSlot& s) {\n",
    b"// Experiment 0417: BC5_R3_EOP_STAT=1, measurement only. How many chained EOP publications fall between one\n"
    b"// publication's push and its deferred callback; the ring that exp 0416 removed was wrong from 4,096 on.\n"
    b"static std::atomic<uint64_t> g_eop_stat_pub {0}, g_eop_stat_max {0}, g_eop_stat_seen {0};\n"
    b"static bool eop_stat_on() {\n"
    b"\tstatic const bool on = [] {\n"
    b"\t\tconst char* e = std::getenv(\"BC5_R3_EOP_STAT\");\n"
    b"\t\treturn e != nullptr && e[0] != '\\0' && !(e[0] == '0' && e[1] == '\\0');\n"
    b"\t}();\n"
    b"\treturn on;\n"
    b"}\n"
    b"static void eop_stat_callback(uint64_t pub) {\n"
    b"\tconst uint64_t d = g_eop_stat_pub.load(std::memory_order_relaxed) - pub;\n"
    b"\tconst uint64_t n = g_eop_stat_seen.fetch_add(1, std::memory_order_relaxed) + 1;\n"
    b"\tuint64_t       m = g_eop_stat_max.load(std::memory_order_relaxed);\n"
    b"\twhile (d > m && !g_eop_stat_max.compare_exchange_weak(m, d, std::memory_order_relaxed)) {\n"
    b"\t}\n"
    b"\tif (d > m || n == 1) {\n"
    b"\t\tjournal(\"eop stat (exp 0417): %\" PRIu64 \" chained EOP publications between a push and its callback (%s; %\" PRIu64 \" callbacks so far; the old ring wrapped at 4096)\\n\", d,\n"
    b"\t\t        d > m ? \"a new maximum\" : \"the first callback\", n);\n"
    b"\t}\n"
    b"}\n"
    b"static void chain_post_soft_locked(ChainSlot& s) {\n")
rep(b"\t\t\tSoftCp::t_gpu_done = failed ? std::vector<SoftCp::GpuDone>() : *marks;\n\t\t\tSoftCp::submit(e.dwords, e.n, e.kind);\n",
    b"\t\t\tSoftCp::t_gpu_done = failed ? std::vector<SoftCp::GpuDone>() : *marks;\n"
    b"\t\t\tif (e.pub != 0) eop_stat_callback(e.pub); // exp 0417\n"
    b"\t\t\tSoftCp::submit(e.dwords, e.n, e.kind);\n")
rep(b"\ts.soft.push_back({owned->data(), n, kind, owned});\n",
    b"\ts.soft.push_back({owned->data(), n, kind, owned, eop_stat_on() ? g_eop_stat_pub.fetch_add(1, std::memory_order_relaxed) + 1 : 0}); // exp 0417: its running number\n")
open(dst, "wb").write(s)
print("eop %s -> %s" % (hashlib.md5(open(src, "rb").read()).hexdigest()[:8], hashlib.md5(s).hexdigest()[:8]))
