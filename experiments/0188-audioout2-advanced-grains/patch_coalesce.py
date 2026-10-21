import sys
root = sys.argv[1]


def patch(path, pairs):
    b = open(path, "rb").read()
    for old, new in pairs:
        done = False
        for nl in (b"\n", b"\r\n"):
            o = old.replace(b"\n", nl); n = new.replace(b"\n", nl)
            if b.count(n) == 1 and b.count(o) == 0:
                print("already:", old[:50]); done = True; break
            if b.count(o) == 1:
                b = b.replace(o, n); print("ok:", old[:50]); done = True; break
        assert done, ("not found", old[:80])
    open(path, "wb").write(b)


vo = root + "/src/graphics/presentation/videoOut.cpp"
patch(vo, [
(b"""static intptr_t MakeVideoOutEventData(intptr_t current_data, void* trigger_data) {
""", b"""// BC5 (experiment 0188): KYTY_BC5_VIDEOOUT_COALESCE=1 keeps one VideoOut event per (ident, filter),
// as FreeBSD's kqueue does and as shadPS4 (src/core/libraries/kernel/equeue.h TriggerDisplay), fpPS4
// (kernel/ps4_queue.pas), the original Kyty (src/Kernel/EventQueue.cpp) and RPCSX's kernel
// (kernel/orbis/src/event.cpp) implement it: a trigger that comes while the event is still unread
// updates it in place (count + 1, the latest time and payload). Without it a copy is queued per
// trigger and the title gets one event per flip with counts 1, 2, 2... (F246,
// docs/ports/related-projects-review.md section 2). KYTY_BC5_VIDEOOUT_EVENT_TRACE=1 (diagnostic)
// prints once a second how the flip events reached the title.
static bool Bc5VideoOutCoalesce() {
	static const bool on = [] {
		const char* e = std::getenv("KYTY_BC5_VIDEOOUT_COALESCE");
		return e != nullptr && std::atoi(e) != 0;
	}();
	return on;
}
static std::atomic<uint32_t> g_bc5_ev_triggers {0}, g_bc5_ev_unread {0}, g_bc5_ev_pending_max {0};
static std::atomic<uint32_t> g_bc5_ev_getcount {0}, g_bc5_ev_getcount_sum {0}, g_bc5_ev_getdata {0};
static std::atomic<uint32_t> g_bc5_ev_delivered[16];
static void Bc5VideoOutEventTraceTick() {
	static const bool on = BC5_DIAG_ENV("KYTY_BC5_VIDEOOUT_EVENT_TRACE") != nullptr;
	if (!on) {
		return;
	}
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
	char hist[256];
	int  o = 0;
	hist[0] = 0;
	for (int i = 0; i < 16; i++) {
		const uint32_t v = g_bc5_ev_delivered[i].exchange(0);
		if (v != 0 && o < static_cast<int>(sizeof(hist)) - 16) {
			o += std::snprintf(hist + o, sizeof(hist) - o, " %d:%u", i, v);
		}
	}
	std::fprintf(stderr,
	             "vo events: t %.3f s: %u flip triggers, %u while unread (%s), pending max %u, delivered counts%s, "
	             "GetEventCount %u calls (sum %u), GetEventData %u calls\\n",
	             static_cast<double>(now) / 1e6, g_bc5_ev_triggers.exchange(0), g_bc5_ev_unread.exchange(0),
	             Bc5VideoOutCoalesce() ? "merged" : "queued", g_bc5_ev_pending_max.exchange(0), hist[0] != 0 ? hist : " none",
	             g_bc5_ev_getcount.exchange(0), g_bc5_ev_getcount_sum.exchange(0), g_bc5_ev_getdata.exchange(0));
}

static intptr_t MakeVideoOutEventData(intptr_t current_data, void* trigger_data) {
"""),
(b"""static void ResetVideoOutEvent(EventQueue::KernelEqueueEvent* event) {
	EXIT_IF(event == nullptr);
	event->triggered    = false;
""", b"""static void ResetVideoOutEvent(EventQueue::KernelEqueueEvent* event) {
	EXIT_IF(event == nullptr);
	if (event->event.ident == VIDEO_OUT_EVENT_FLIP && event->triggered) {
		g_bc5_ev_delivered[(static_cast<uint64_t>(event->event.data) >> 12u) & 0xfu]++; // experiment 0188
	}
	event->triggered    = false;
"""),
(b"""	triggered_event.data = MakeVideoOutEventData(triggered_event.data, trigger_data);
	if (event->triggered) {
		event->pending_events.push_back(triggered_event);
		return;
	}
""", b"""	triggered_event.data = MakeVideoOutEventData(triggered_event.data, trigger_data);
	const bool flip = event->event.ident == VIDEO_OUT_EVENT_FLIP; // experiment 0188
	if (flip) {
		g_bc5_ev_triggers++;
		Bc5VideoOutEventTraceTick();
	}
	if (event->triggered) {
		if (flip) {
			g_bc5_ev_unread++;
		}
		if (Bc5VideoOutCoalesce()) {
			event->event = triggered_event; // experiment 0188: one event, updated in place
			return;
		}
		event->pending_events.push_back(triggered_event);
		if (flip) {
			const auto n = static_cast<uint32_t>(event->pending_events.size());
			uint32_t   m = g_bc5_ev_pending_max.load();
			while (n > m && !g_bc5_ev_pending_max.compare_exchange_weak(m, n)) {
			}
		}
		return;
	}
"""),
])
b = open(vo, "rb").read()
# GetEventCount / GetEventData counters
for nl in (b"\n", b"\r\n"):
    old = (b"\treturn static_cast<int>((static_cast<uint64_t>(ev->data) >> 12u) & 0xfu);" + nl + b"}")
    if b.count(old) == 1:
        new = (b"\tconst int bc5_count = static_cast<int>((static_cast<uint64_t>(ev->data) >> 12u) & 0xfu);" + nl +
               b"\tif (ev->ident == VIDEO_OUT_EVENT_FLIP) { // experiment 0188" + nl +
               b"\t\tg_bc5_ev_getcount++;" + nl + b"\t\tg_bc5_ev_getcount_sum += static_cast<uint32_t>(bc5_count);" + nl + b"\t}" + nl +
               b"\treturn bc5_count;" + nl + b"}")
        b = b.replace(old, new); print("ok: GetEventCount"); break
else:
    assert b"bc5_count" in b, "GetEventCount not found"
for nl in (b"\n", b"\r\n"):
    old = b"\t*data = static_cast<int64_t>(event_data);" + nl
    if b.count(old) == 1:
        b = b.replace(old, old + b"\tif (ev->ident == VIDEO_OUT_EVENT_FLIP) {" + nl + b"\t\tg_bc5_ev_getdata++; // experiment 0188" + nl + b"\t}" + nl)
        print("ok: GetEventData"); break
else:
    assert b"g_bc5_ev_getdata++; //" in b, "GetEventData not found"
open(vo, "wb").write(b)

eq = root + "/src/kernel/eventQueue.cpp"
patch(eq, [
(b"""			if (!event.pending_events.empty()) {
				event.event = event.pending_events.front();
				event.pending_events.pop_front();
				event.triggered = true;
			}

			if (ret >= num) {
""", b"""			if (!event.pending_events.empty()) {
				event.event = event.pending_events.front();
				event.pending_events.pop_front();
				event.triggered = true;
			} else if (Bc5LevelEventOnce()) {
				// BC5 (experiment 0188): a level event (no EV_CLEAR, no reset function) stays triggered and is
				// delivered again by the next wait, not copied into every slot of this one (KytyPlus 3eee96a,
				// src/kernel/eventQueue.cpp, GPL-2.0). KYTY_BC5_EQUEUE_LEVEL_ONCE=1.
				break;
			}

			if (ret >= num) {
"""),
(b"""namespace Libs::LibKernel::EventQueue {
""", b"""namespace Libs::LibKernel::EventQueue {

static bool Bc5LevelEventOnce() { // experiment 0188
	static const bool on = [] {
		const char* e = std::getenv("KYTY_BC5_EQUEUE_LEVEL_ONCE");
		return e != nullptr && std::atoi(e) != 0;
	}();
	return on;
}
"""),
])

m = root + "/src/main.cpp"
c = open(m, "rb").read()
old = b'"KYTY_BC5_FLIP_STATUS_TRACE"};'
new = b'"KYTY_BC5_FLIP_STATUS_TRACE", "KYTY_BC5_VIDEOOUT_EVENT_TRACE"};'
if c.count(new) == 0:
    assert c.count(old) == 1
    open(m, "wb").write(c.replace(old, new))
print("main ok")
