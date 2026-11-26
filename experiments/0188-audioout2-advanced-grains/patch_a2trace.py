import sys, re
root = sys.argv[1]
p = root + "/src/libs/libAudio2.cpp"
b = open(p, "rb").read()
if b"Bc5Audio2Count" in b:
    print("already"); sys.exit(0)
helper = b"""
// BC5 (experiment 0188): KYTY_BC5_AUDIO2_TRACE=1 (diagnostic) prints once a second how often the title
// calls the AudioOut2 context and port functions, and the queue level it was told (sum and max).
static std::atomic<uint32_t> g_bc5_a2[6];
static std::atomic<uint32_t> g_bc5_a2_level_sum {0}, g_bc5_a2_level_max {0};
static void Bc5Audio2Count(int which) {
	static const bool on = BC5_DIAG_ENV("KYTY_BC5_AUDIO2_TRACE") != nullptr;
	if (!on) {
		return;
	}
	g_bc5_a2[which]++;
	static std::atomic<uint64_t> last {0};
	const uint64_t               now = LibKernel::KernelGetProcessTime();
	uint64_t                     l   = last.load();
	if (l == 0) {
		last.compare_exchange_strong(l, now);
		return;
	}
	if (now - l < 1000000 || !last.compare_exchange_strong(l, now)) {
		return;
	}
	std::fprintf(stderr, "audio2 trace: t %.3f s: context create %u, port create %u, advance %u, push %u, get queue level %u (level sum %u, max %u), port set attributes %u\\n",
	             static_cast<double>(now) / 1e6, g_bc5_a2[0].exchange(0), g_bc5_a2[1].exchange(0), g_bc5_a2[2].exchange(0),
	             g_bc5_a2[3].exchange(0), g_bc5_a2[4].exchange(0), g_bc5_a2_level_sum.exchange(0), g_bc5_a2_level_max.exchange(0),
	             g_bc5_a2[5].exchange(0));
}
"""
# insert the helper before the first of the counted functions
first = b"int KYTY_SYSV_ABI AudioOut2ContextCreate(const AudioOut2ContextParam* params, void* buffer,"
assert b.count(first) == 1
b = b.replace(first, helper.lstrip(b"\n") + b"\n" + first)
marks = [
    (b"int KYTY_SYSV_ABI AudioOut2ContextCreate(", 0),
    (b"int KYTY_SYSV_ABI AudioOut2PortCreate(", 1),
    (b"int KYTY_SYSV_ABI AudioOut2ContextAdvance(", 2),
    (b"int KYTY_SYSV_ABI AudioOut2ContextPush(", 3),
    (b"int KYTY_SYSV_ABI AudioOut2ContextGetQueueLevel(", 4),
    (b"int KYTY_SYSV_ABI AudioOut2PortSetAttributes(", 5),
]
for sig, k in marks:
    i = b.index(sig)
    j = b.index(b"{", i)  # the function body's opening brace
    b = b[:j + 1] + (b"\n\tBc5Audio2Count(%d); // experiment 0188" % k) + b[j + 1:]
    print("ok", sig[18:50])
# record the reported level in GetQueueLevel: after "*queue_level = state->queued;"
old = b"\t\t\t*queue_level = state->queued;\n"
assert b.count(old) == 1
b = b.replace(old, old + b"\t\t\tg_bc5_a2_level_sum += state->queued; // experiment 0188\n\t\t\tfor (uint32_t m = g_bc5_a2_level_max.load(); state->queued > m && !g_bc5_a2_level_max.compare_exchange_weak(m, state->queued);) {\n\t\t\t}\n")
if b"#include <cstdio>" not in b:
    b = b.replace(b"#include <atomic>\n", b"#include <atomic>\n#include <cstdio>\n", 1)
open(p, "wb").write(b)
m = root + "/src/main.cpp"
c = open(m, "rb").read()
old = b'"KYTY_BC5_EQUEUE_TRACE"};'
new = b'"KYTY_BC5_EQUEUE_TRACE", "KYTY_BC5_AUDIO2_TRACE"};'
if c.count(new) == 0:
    assert c.count(old) == 1
    open(m, "wb").write(c.replace(old, new))
print("main ok")
