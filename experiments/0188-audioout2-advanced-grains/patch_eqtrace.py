import sys
root = sys.argv[1]
p = root + "/src/kernel/eventQueue.cpp"
b = open(p, "rb").read()


def rep(old, new):
    global b
    if b.count(new) == 1 and b.count(old) == 0:
        print("already"); return
    assert b.count(old) == 1, (old[:60], b.count(old))
    b = b.replace(old, new); print("ok")


rep(b"""static bool Bc5LevelEventOnce() { // experiment 0188
""", b"""// BC5 (experiment 0188): KYTY_BC5_EQUEUE_TRACE=1 (diagnostic) prints once a second, over all queues:
// the waits that returned events, the events returned, and the "level repeats" -- the same event copied
// into further slots of one wait because it stays triggered (no EV_CLEAR, no reset function), by filter
// and ident of the last one seen.
static std::atomic<uint32_t> g_bc5_eq_waits {0}, g_bc5_eq_events {0}, g_bc5_eq_repeats {0};
static std::atomic<int64_t>  g_bc5_eq_rep_filter {0};
static std::atomic<uint64_t> g_bc5_eq_rep_ident {0}, g_bc5_eq_rep_udata {0};
static void Bc5EqueueTraceTick() {
	static const bool on = BC5_DIAG_ENV("KYTY_BC5_EQUEUE_TRACE") != nullptr;
	if (!on) {
		return;
	}
	static std::atomic<uint64_t> last {0};
	const auto                   now = std::chrono::duration_cast<std::chrono::microseconds>(
                         std::chrono::steady_clock::now().time_since_epoch())
                         .count();
	uint64_t l = last.load();
	if (l == 0) {
		last.compare_exchange_strong(l, static_cast<uint64_t>(now));
		return;
	}
	if (static_cast<uint64_t>(now) - l < 1000000 || !last.compare_exchange_strong(l, static_cast<uint64_t>(now))) {
		return;
	}
	std::fprintf(stderr, "equeue trace: %u waits with events, %u events, %u level repeats (last filter %d ident 0x%" PRIx64 " udata 0x%" PRIx64 ")\\n",
	             g_bc5_eq_waits.exchange(0), g_bc5_eq_events.exchange(0), g_bc5_eq_repeats.exchange(0),
	             static_cast<int>(g_bc5_eq_rep_filter.load()), g_bc5_eq_rep_ident.load(), g_bc5_eq_rep_udata.load());
}

static bool Bc5LevelEventOnce() { // experiment 0188
""")
rep(b"""		auto& event = *it;
		bool  erase = false;
		while (event.triggered) {
			ev[ret++] = event.event;
""", b"""		auto& event = *it;
		bool  erase = false;
		int   bc5_n      = 0; // experiment 0188
		bool  bc5_popped = false;
		while (event.triggered) {
			if (bc5_n++ > 0 && !bc5_popped) {
				g_bc5_eq_repeats++;
				g_bc5_eq_rep_filter = event.event.filter;
				g_bc5_eq_rep_ident  = static_cast<uint64_t>(event.event.ident);
				g_bc5_eq_rep_udata  = reinterpret_cast<uint64_t>(event.event.udata);
			}
			bc5_popped = false;
			ev[ret++]  = event.event;
""")
rep(b"""				event.pending_events.pop_front();
				event.triggered = true;
			} else if (Bc5LevelEventOnce()) {""", b"""				event.pending_events.pop_front();
				event.triggered = true;
				bc5_popped      = true;
			} else if (Bc5LevelEventOnce()) {""")
rep(b"""		it = (erase ? m_events.erase(it) : std::next(it));
		if (ret >= num) {
			break;
		}
	}

	return ret;
}
""", b"""		it = (erase ? m_events.erase(it) : std::next(it));
		if (ret >= num) {
			break;
		}
	}

	if (ret > 0) { // experiment 0188
		g_bc5_eq_waits++;
		g_bc5_eq_events += static_cast<uint32_t>(ret);
	}
	Bc5EqueueTraceTick();
	return ret;
}
""")
if b"#include <atomic>" not in b:
    b = b.replace(b"#include <cinttypes>\n", b"#include <atomic>\n#include <chrono>\n#include <cinttypes>\n", 1)
    print("includes added")
open(p, "wb").write(b)
m = root + "/src/main.cpp"
c = open(m, "rb").read()
old = b'"KYTY_BC5_VIDEOOUT_EVENT_TRACE"};'
new = b'"KYTY_BC5_VIDEOOUT_EVENT_TRACE", "KYTY_BC5_EQUEUE_TRACE"};'
if c.count(new) == 0:
    assert c.count(old) == 1
    open(m, "wb").write(c.replace(old, new))
print("main ok")
