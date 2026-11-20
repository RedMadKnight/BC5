# BC5 exp 0436, the bake: the candidate's host unit (bc5LleAgc.cpp 57ce0f37, made by mkhost436.py from the shared
# 6f4bf71a) with BC5_DIRECT_SUBMIT_UNLOCK removed: no switch, no getenv, no ON/off line; the unlocked kernel submit is
# the only path in async mode (the maintainer, 2026-11-20: "Wdróż od razu"; his standing "usuń przełączniki i wybuduj w
# kod"). Sync mode (g_async off) keeps the call under both locks as before, since there the job is waited for at
# submission and nothing runs beside it. Every replacement must match exactly once, or nothing is written.
#   python -I mkbake436.py <candidate bc5LleAgc.cpp> <out>
import sys

src, dst = sys.argv[1:3]
s = open(src, encoding="utf-8", newline="").read()


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, (old[:70], n)
    s = s.replace(old, new)


rep("""// Experiment 0436 (tag su436): BC5_DIRECT_SUBMIT_UNLOCK (on in this test build unless "0"), the kernel submit (DRM_IOCTL_AMDGPU_CS) outside the device
// mutex (exp 0432 note 8).""", """// Experiment 0436 (tag su436): the kernel submit (DRM_IOCTL_AMDGPU_CS) outside the device mutex (exp 0432 note 8;
// built in with no switch, 2026-11-20).""")
rep("""// still there when the kernel takes it. Async mode only (g_async); off, nothing changes.
static bool su436_on() {
	static const bool v = [] {
		const char* e  = std::getenv("BC5_DIRECT_SUBMIT_UNLOCK"); // the test build: on unless "0" (the candidate's arm is the binary)
		const bool  on = e == nullptr || e[0] == 0 || bc5::env_on(e);
		std::fprintf(stderr, "[bc5] exp 0436 (tag su436): BC5_DIRECT_SUBMIT_UNLOCK %s: the kernel submit runs %s the device mutex\\n", on ? "ON" : "off",
		             on ? "outside" : "inside");
		return on;
	}();
	return v;
}
""", """// still there when the kernel takes it. Async mode only (g_async); in sync mode the call stays under both locks.
""")
rep("""	const bool su = su436_on() && g_async && (""", """	const bool su = g_async && (""")
assert "SUBMIT_UNLOCK" not in s and "su436_on" not in s
open(dst, "w", encoding="utf-8", newline="").write(s)
print("mkbake436: ok")
