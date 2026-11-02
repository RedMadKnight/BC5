#!/usr/bin/env python3
# BC5 exp 0381: puts the F687 and F688 catchers into a copy of test build 2's unit. Every anchor must be there exactly once, or
# nothing is written. usage: mkcatch0381r.py <bc5LleAgc.cpp in> <out> <dir of the two .inc files>
import os
import sys

src, dst, inc = sys.argv[1:4]
with open(src, encoding="utf-8", newline="") as f:
    text = f.read()
eol = "\r\n" if "\r\n" in text else "\n"


def read(name):
    with open(os.path.join(inc, name), encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\n", eol)


def line(s):
    return s.replace("\n", eol)


EDITS = [
    # The system headers, once, with the unit's own.
    (line("#include <pthread.h>\n"), line("#include <pthread.h>\n#include <dirent.h>\n#include <fcntl.h>\n#include <sys/uio.h>\n#include <unistd.h>\n#include <thread>\n"), "after"),
    # The two files, before their first use; the check runs at the end of learned_apply, which comes earlier.
    (line("static void learned_apply() {\n"), line("static void c0381r_page_run(const char* why); // exp 0381\n"), "before"),
    (line("	if (la_t5 - la_t0 > 5'000'000ull) {\n"), line('	c0381r_page_run("apply"); // exp 0381\n'), "before"),
    (line("static void recover_after_timeout(const bc5::direct::SubmitResult& r) {\n"), read("catch0381r_pure.inc") + read("catch0381r_host.inc"), "before"),
    (line('		journal("timeout: fault 0x%" PRIx64 " status 0x%08x\\n", r.fault_addr, r.fault_status);\n'), line("		c0381r_fault(r.fault_addr); // exp 0381\n"), "after"),
    (line('			journal("reopen: %s\\n", g_dev ? "ok" : "FAILED");\n'), line('			c0381r_trace_start(g_dev ? "ok" : "FAILED"); // exp 0381\n'), "after"),
    (line("						if (n_writes++ < 200)\n"), line("						c0381r_label(a, v); // exp 0381\n"), "before"),
    (line("static void frame_profile_flip(double drain_ms) {\n"), line("	g_c0381r_flips++; // exp 0381\n"), "after"),
]
for anchor, new, where in EDITS:
    n = text.count(anchor)
    if n != 1:
        sys.exit("anchor %d times: %r" % (n, anchor))
    text = text.replace(anchor, anchor + new if where == "after" else new + anchor)
with open(dst, "w", encoding="utf-8", newline="") as f:
    f.write(text)
print("catchers in: %d edits" % len(EDITS))
