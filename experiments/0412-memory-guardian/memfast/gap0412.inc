// BC5 experiment 0412 (tag gp412, README section 23): what the host's threads were blocked on inside a frame gap.
// BC5_GUARD_GAP_STAT=<ms> (unset, empty, "0": off; "1": 100 ms). Every blocking point the host owns adds its time to
// a counter of its cause for the calling thread's slot (Render Thread, game-main, bc5-ring, bc5-cq0, bc5-chainwd,
// others). A Scope is exclusive: a scope opened inside another pauses the outer one, so a slot's causes never count
// one nanosecond twice. flip() is called at every flip; when more than <ms> passed since the last flip it writes one
// line through GP412_PRINT with the time on the journal's clock (GP412_NOW, at the gap's END), CLOCK_MONOTONIC at the
// same moment (for the outside sampler, gapsamp0412.py) and, per slot, the milliseconds each cause took since the
// last flip. No behaviour changes: with the switch off a Scope is one test of a constant, poll_sleep is the sleep.
// The text is included by the main unit (mkgap0412.py) and by the CPU test lock0412.cpp.
namespace gp412 {
enum Cause { kDevMutex, kChainMutex, kDrain, kLabel, kCap, kWaitIdle, kFence, kIdle, kSubmit, kSplit, kCauses };
inline const char* cause_name(int c) {
	static const char* const n[kCauses] = {"device mutex", "chain mutex", "flip drain", "label wait", "in-flight cap", "ring wait-idle", "gpu fence",
	                                       "idle (no work)", "host submit", "host split"};
	return n[c >= 0 && c < kCauses ? c : 0];
}
static constexpr int kSlots = 6;
inline const char* slot_name(int s) {
	static const char* const n[kSlots] = {"Render Thread", "game-main", "bc5-ring", "bc5-cq0", "bc5-chainwd", "others"};
	return n[s >= 0 && s < kSlots ? s : kSlots - 1];
}
inline uint64_t now_ns() {
	timespec ts {};
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return static_cast<uint64_t>(ts.tv_sec) * 1000000000ull + static_cast<uint64_t>(ts.tv_nsec);
}
inline uint64_t limit_ns() { // 0: off
	static const uint64_t v = []() -> uint64_t {
		const char* e = std::getenv("BC5_GUARD_GAP_STAT");
		if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) return static_cast<uint64_t>(0);
		const unsigned long ms = std::strtoul(e, nullptr, 10);
		return static_cast<uint64_t>(ms <= 1 ? 100 : ms) * 1000000ull;
	}();
	return v;
}
inline bool on() { return limit_ns() != 0; }
inline std::atomic<uint64_t> g_ns[kSlots][kCauses];
inline int slot() {
	thread_local int s = -1;
	if (s < 0) {
		char tn[32] = {};
		pthread_getname_np(pthread_self(), tn, sizeof(tn));
		s = kSlots - 1;
		for (int i = 0; i + 1 < kSlots; i++) {
			if (std::strcmp(tn, slot_name(i)) == 0) s = i;
		}
		if (tn[0] == 0) s = -1; // not named yet: ask again next time, count as others now
		if (s < 0) return kSlots - 1;
	}
	return s;
}
class Scope {
public:
	explicit Scope(Cause c) {
		if (!on()) return;
		cause_  = c;
		t0_     = now_ns();
		parent_ = cur();
		if (parent_ != nullptr) parent_->pause(t0_);
		cur()   = this;
		live_   = true;
	}
	~Scope() { end(); }
	void end() {
		if (!live_) return;
		live_ = false;
		const uint64_t now = now_ns();
		g_ns[slot()][cause_].fetch_add(acc_ + (now - t0_), std::memory_order_relaxed);
		cur() = parent_;
		if (parent_ != nullptr) parent_->t0_ = now;
	}
	Scope(const Scope&)            = delete;
	Scope& operator=(const Scope&) = delete;

private:
	static Scope*& cur() {
		thread_local Scope* c = nullptr;
		return c;
	}
	void pause(uint64_t now) {
		acc_ += now - t0_;
		t0_ = now;
	}
	Cause    cause_  = kDevMutex;
	uint64_t t0_ = 0, acc_ = 0;
	Scope*   parent_ = nullptr;
	bool     live_   = false;
};
inline void poll_sleep(int us, Cause c) {
	Scope s(c);
	std::this_thread::sleep_for(std::chrono::microseconds(us));
}
inline uint64_t g_gaps = 0; // for the CPU test; written under flip()'s mutex
inline void flip() {
	if (!on()) return;
	static std::mutex mu;
	static uint64_t   last_ns = 0;
	static uint64_t   seen[kSlots][kCauses] = {};
	std::lock_guard   lk(mu);
	const uint64_t    now = now_ns();
	uint64_t          d[kSlots][kCauses];
	for (int s = 0; s < kSlots; s++) {
		for (int c = 0; c < kCauses; c++) {
			const uint64_t v = g_ns[s][c].load(std::memory_order_relaxed);
			d[s][c]          = v - seen[s][c];
			seen[s][c]       = v;
		}
	}
	const uint64_t gap = last_ns != 0 ? now - last_ns : 0;
	last_ns            = now;
	if (gap < limit_ns()) return;
	g_gaps++;
	char line[1500];
	int  w = std::snprintf(line, sizeof(line), "gap (exp 0412, tag gp412): t %.3f s mono %.6f: %.1f ms since the last flip", GP412_NOW(), static_cast<double>(now) / 1e9,
	                       static_cast<double>(gap) / 1e6);
	for (int s = 0; s < kSlots && w < 1300; s++) {
		bool any = false;
		for (int c = 0; c < kCauses && w < 1300; c++) {
			if (d[s][c] < 100000ull) continue;
			w += std::snprintf(line + w, sizeof(line) - static_cast<size_t>(w), "%s %s %.1f", any ? "," : (std::string(" | ") + slot_name(s) + ":").c_str(), cause_name(c),
			                   static_cast<double>(d[s][c]) / 1e6);
			any = true;
		}
	}
	GP412_PRINT("%s\n", line);
}
} // namespace gp412
