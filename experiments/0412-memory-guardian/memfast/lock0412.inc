// BC5 experiment 0412 (tag lk412, README section 20): who holds the device mutex. A mutex with std::mutex's interface;
// with BC5_GUARD_LOCK_STAT unset, empty or "0" it is a std::mutex behind one test of a constant. With the switch on it
// counts, per thread name: acquisitions, the time held (sum, longest, holds of 2 ms and more), the time waited, and
// for every waiter the time waited behind each holder (the thread that held the mutex when the wait began). One block
// of lines every 10 s through LK412_PRINT (printf-like). All counters are written by the thread that holds the mutex.
// The text is included by the main unit (mklock0412.py) and by the CPU test lock0412.cpp.
namespace lk412 {
inline uint64_t now_ns() {
	timespec ts {};
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return static_cast<uint64_t>(ts.tv_sec) * 1000000000ull + static_cast<uint64_t>(ts.tv_nsec);
}
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_GUARD_LOCK_STAT");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
class Mutex {
public:
	static constexpr int N = 48; // thread names; further ones share the last slot, "(others)"
	void lock() {
		if (!on()) {
			m_.lock();
			return;
		}
		uint64_t waited = 0;
		int      behind = -1;
		if (!m_.try_lock()) {
			behind = holder_.load(std::memory_order_relaxed);
			const uint64_t t0 = now_ns();
			m_.lock();
			waited = now_ns() - t0;
		}
		const int me = slot();
		holder_.store(me, std::memory_order_relaxed);
		acq_[me]++;
		if (behind >= 0) {
			waits_[me]++;
			wait_ns_[me] += waited;
			behind_ns_[me][behind < N ? behind : N - 1] += waited;
		}
		t_acq_ = now_ns();
	}
	bool try_lock() {
		if (!m_.try_lock()) return false;
		if (on()) {
			const int me = slot();
			holder_.store(me, std::memory_order_relaxed);
			acq_[me]++;
			t_acq_ = now_ns();
		}
		return true;
	}
	void unlock() {
		if (on()) {
			const int      me   = holder_.load(std::memory_order_relaxed);
			const uint64_t now  = now_ns();
			const uint64_t held = now - t_acq_;
			hold_ns_[me] += held;
			if (held > max_ns_[me]) max_ns_[me] = held;
			if (held >= 2000000ull) long_[me]++;
			if (t_report_ == 0) t_report_ = now;
			if (now - t_report_ >= 10000000000ull) {
				report(static_cast<double>(now - t_report_) / 1e9);
				t_report_ = now;
			}
		}
		m_.unlock();
	}
	// For the CPU test: the sums since the last report (the caller holds the mutex or no thread uses it).
	uint64_t total_acq() const { uint64_t s = 0; for (int i = 0; i < N; i++) s += acq_[i]; return s; }
	uint64_t total_wait_ns() const { uint64_t s = 0; for (int i = 0; i < N; i++) s += wait_ns_[i]; return s; }
	uint64_t total_behind_ns() const { uint64_t s = 0; for (int i = 0; i < N; i++) for (int j = 0; j < N; j++) s += behind_ns_[i][j]; return s; }
	uint64_t total_hold_ns() const { uint64_t s = 0; for (int i = 0; i < N; i++) s += hold_ns_[i]; return s; }
	int      names() const { return n_names_; }

private:
	int slot() { // the calling thread's slot, by its name; the caller holds m_
		char tn[32] = {};
		pthread_getname_np(pthread_self(), tn, sizeof(tn));
		for (int i = 0; i < n_names_; i++) {
			if (std::strncmp(name_[i], tn, sizeof(name_[i])) == 0) return i;
		}
		if (n_names_ < N - 1) {
			std::snprintf(name_[n_names_], sizeof(name_[n_names_]), "%s", tn);
			return n_names_++;
		}
		std::snprintf(name_[N - 1], sizeof(name_[N - 1]), "(others)");
		return N - 1;
	}
	void report(double secs) { // the caller holds m_
		for (int i = 0; i < N; i++) {
			if (acq_[i] == 0) continue;
			char who[400] = {};
			int  at       = 0;
			for (int k = 0; k < 4; k++) { // the four holders this thread waited behind most
				int best = -1;
				for (int j = 0; j < N; j++) {
					if (behind_ns_[i][j] != 0 && (best < 0 || behind_ns_[i][j] > behind_ns_[i][best])) best = j;
				}
				if (best < 0) break;
				at += std::snprintf(who + at, sizeof(who) - static_cast<size_t>(at), "%s %s %.1f ms", k == 0 ? "" : ",", name_[best], static_cast<double>(behind_ns_[i][best]) / 1e6);
				behind_ns_[i][best] = 0;
				if (at >= static_cast<int>(sizeof(who)) - 60) break;
			}
			LK412_PRINT("lock stat (exp 0412, tag lk412): %.1f s: %s: %" PRIu64 " locks, held %.1f ms (%.1f %% of the time; longest %.2f ms; %" PRIu64 " of 2 ms or more), waited %.1f ms in %" PRIu64 " waits (%.1f %%)%s%s\n",
			            secs, name_[i][0] != 0 ? name_[i] : "(no name)", acq_[i], static_cast<double>(hold_ns_[i]) / 1e6, static_cast<double>(hold_ns_[i]) / 1e7 / secs,
			            static_cast<double>(max_ns_[i]) / 1e6, long_[i], static_cast<double>(wait_ns_[i]) / 1e6, waits_[i], static_cast<double>(wait_ns_[i]) / 1e7 / secs,
			            who[0] != 0 ? "; behind:" : "", who);
			acq_[i] = waits_[i] = long_[i] = hold_ns_[i] = wait_ns_[i] = max_ns_[i] = 0;
			for (int j = 0; j < N; j++) behind_ns_[i][j] = 0;
		}
	}
	std::mutex       m_;
	std::atomic<int> holder_ {0};
	uint64_t         t_acq_ = 0, t_report_ = 0;
	int              n_names_ = 0;
	char             name_[N][32] = {};
	uint64_t         acq_[N] = {}, waits_[N] = {}, long_[N] = {}, hold_ns_[N] = {}, wait_ns_[N] = {}, max_ns_[N] = {};
	uint64_t         behind_ns_[N][N] = {};
};
} // namespace lk412
