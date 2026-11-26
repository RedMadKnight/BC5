// BC5 experiment 0430 (tag ho430): the fix of the second title's cross-queue GPU hangs (F848, F852, F858), built in on
// 2026-11-18 (the maintainer: all four fixes go in, built into the code with their switches removed). No switch.
// The hang: a compute buffer (acb) waits for a label == V that a graphics or compute buffer on another ring releases. The
// host decides such a wait at submit. When the label still held last frame's V, the wait passed, the acb ran ahead of its
// writer and overwrote memory the writer's passes still read (junk indirect grids, then a ring timeout). On the console
// the queue decides the wait when it reaches the packet. Four parts, measured on the R-on tree (h430M1-M3 clean, the
// maintainer's 57-minute play clean of the class; the arms without F16 faulted, h430J1):
// - F10 (the targeted flush): at an acb's wait on L, every other thread's open chain (ADR 0010 section B) whose own packets
//   write L goes to the device first: made due for the watchdog, or flushed by its owner at its call's end when the owner
//   is inside its submit call; a chain being submitted is waited for until its writes are registered. bc5-ring polls, at
//   most 2 ms, through F10's own registry of the slots (g_f10_reg_mu, which nothing submits under), with try_locks only
//   (LESSONS R62); a busy list is looked at again, a busy slot is waited for as a possible writer.
// - F2 + F4: a wait found satisfied while a job not yet completed on ANOTHER ring has a registered pending write to L is
//   ordered behind that job by the kernel (a CS dependency of this buffer's submission), unless that job holds a kept GPU
//   wait on a label this buffer writes (a cycle: left as it is).
// - F16: at F10's bound, a writer in flight (inside its submit_now) is waited for until its submit returns, at most 50 ms;
//   a writer in back-pressure (phase 1) or draining the GPU (phase 4) may wait on work only bc5-ring submits, so it is
//   not waited for past 2 ms more.
// - F18: a bound F16 did not settle: each pending slot is looked at again for up to 200 us; an open writer of L is made
//   due and waited for, a slot still busy is waited for as a possible writer, a slot that writes nothing of L is dropped;
//   50 ms bound and the same phase gate.
// A bound that still stands decides the wait as before. The normal build counts all of it (a 60-s line, the first 64
// waits of F16/F18 and every one that did not settle); the lean build has none of the counting.
namespace ho430 {
struct Store {
	std::mutex                                                m;
	std::map<std::pair<int, uint64_t>, std::vector<uint64_t>> job_waits; // (ring, seq) -> the labels of its kept GPU waits (the cycle check)
#ifndef BC5_LEAN
	uint64_t f2_cycle = 0, f4_fence = 0;
	uint64_t f10_calls = 0, f10_hit = 0, f10_gone = 0, f10_bound = 0, f10_busy = 0, f10_ns = 0;
	uint64_t f16_wait = 0, f16_ok = 0, f16_bound = 0, f16_stop[5] {}, f16_ns = 0, f16_max = 0;
	uint64_t f18_wait = 0, f18_ok = 0, f18_none = 0, f18_bound = 0, f18_stop[5] {}, f18_cls[3] {}, f18_ns = 0, f18_max = 0;
	uint64_t stands = 0; // bounds that still stood after F16 and F18
#endif
};
inline Store& st() {
	static Store s;
	return s;
}
inline uint32_t pkt_len(uint32_t h) {
	const uint32_t type = h >> 30u;
	if (type != 3 && type != 0) return 1;
	const uint32_t c = (h >> 16u) & 0x3fffu;
	return c == 0x3fffu ? 1 : c + 2;
}
// One pass over a submitted job: its kept GPU waits on memory, for the cycle check of the waits after it.
// executed: the offsets the filter kept, in order.
inline void job_submitted(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& executed, uint64_t seq, int ring, const char* kind) {
	(void)kind;
	std::vector<uint64_t> waits;
	size_t                e = 0;
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h = ib[q], len = pkt_len(h);
		if (q + len > num_dwords) break;
		while (e < executed.size() && executed[e] < q) e++;
		const bool ran = e < executed.size() && executed[e] == q;
		if ((h >> 30u) == 3) {
			const uint32_t  op = (h >> 8u) & 0xffu;
			const uint32_t* w  = ib + q;
			if ((op == 0x3c || op == 0x93) && len >= 4 && ((w[1] >> 4u) & 1u) != 0 && ran)
				waits.push_back((static_cast<uint64_t>(w[2]) & ~3ull) | (static_cast<uint64_t>(w[3] & 0xffffu) << 32u));
		}
		q += len;
	}
	Store&          s = st();
	std::lock_guard lk(s.m);
	if (!waits.empty()) {
		s.job_waits[{ring, seq}] = std::move(waits);
		if (s.job_waits.size() > 4096) s.job_waits.erase(s.job_waits.begin());
	}
#ifndef BC5_LEAN
	static uint64_t last_line = 0;
	const uint64_t  now       = SoftCp::now_ns();
	if (now - last_line > 60'000'000'000ull) {
		last_line = now;
		journal("ho430 (exp 0430): t %.1f s: F4 fences %" PRIu64 ", F2 cycles left as they are %" PRIu64 "; F10 acb waits %" PRIu64 ", with a chain writing the label %" PRIu64 ", gone %" PRIu64 ", bound %" PRIu64 ", list busy %" PRIu64 " (%.1f ms in all); "
		        "F16 in-flight waits %" PRIu64 ": returned %" PRIu64 ", 50 ms bound %" PRIu64 ", not waited (back-pressure/draining) %" PRIu64 "/%" PRIu64 ", %.1f ms in all, longest %.3f ms; "
		        "F18 bounds looked at %" PRIu64 ": writers went %" PRIu64 ", no writer %" PRIu64 ", 50 ms bound %" PRIu64 ", not waited (back-pressure/draining) %" PRIu64 "/%" PRIu64 ", slots open writer/not a writer/still busy %" PRIu64 "/%" PRIu64 "/%" PRIu64 ", %.1f ms in all, longest %.3f ms; "
		        "bounds that stood %" PRIu64 "\n",
		        timing_now(), s.f4_fence, s.f2_cycle, s.f10_calls, s.f10_hit, s.f10_gone, s.f10_bound, s.f10_busy, static_cast<double>(s.f10_ns) / 1e6,
		        s.f16_wait, s.f16_ok, s.f16_bound, s.f16_stop[1], s.f16_stop[4], static_cast<double>(s.f16_ns) / 1e6, static_cast<double>(s.f16_max) / 1e6,
		        s.f18_wait, s.f18_ok, s.f18_none, s.f18_bound, s.f18_stop[1], s.f18_stop[4], s.f18_cls[0], s.f18_cls[1], s.f18_cls[2], static_cast<double>(s.f18_ns) / 1e6, static_cast<double>(s.f18_max) / 1e6,
		        s.stands);
	}
#endif
}
inline void job_done(uint64_t seq, int ring, bool all) {
	Store&          s = st();
	std::lock_guard lk(s.m);
	if (all) s.job_waits.clear();
	else s.job_waits.erase({ring, seq});
}
// F10: true while one of `mine` still has L open (unsubmitted) or in flight (its writes not registered yet), or is busy.
inline bool f10_pending(uint64_t label, const std::vector<ChainSlot*>& mine) {
	if (!g_f10_reg_mu.try_lock()) return true;
	bool pending = false;
	for (ChainSlot* cs: mine) {
		if (std::find(g_f10_reg.begin(), g_f10_reg.end(), cs) == g_f10_reg.end()) continue; // its thread is gone
		if (!cs->mu.try_lock()) { pending = true; break; }
		if ((!cs->c.segs.empty() && std::find(cs->f10_writes.begin(), cs->f10_writes.end(), label) != cs->f10_writes.end()) ||
		    std::find(cs->f10_flight.begin(), cs->f10_flight.end(), label) != cs->f10_flight.end()) pending = true;
		cs->mu.unlock();
		if (pending) break;
	}
	g_f10_reg_mu.unlock();
	return pending;
}
// The phase gate of F16 and F18: true when one of the slots has been in back-pressure (1) or draining the GPU (4) for 2 ms.
inline bool phase_gate(const std::vector<ChainSlot*>& sl, uint64_t& t_ph, int& ph_out) {
	if (!g_f10_reg_mu.try_lock()) return false;
	int ph = 0;
	for (ChainSlot* cs: sl)
		if (std::find(g_f10_reg.begin(), g_f10_reg.end(), cs) != g_f10_reg.end()) {
			const int p = cs->f16_phase.load();
			if (p == 1 || p == 4) ph = p;
		}
	g_f10_reg_mu.unlock();
	const uint64_t now = SoftCp::now_ns();
	if (ph == 0) t_ph = 0;
	else if (t_ph == 0) t_ph = now;
	else if (now - t_ph >= 2'000'000ull) {
		ph_out = ph;
		return true;
	}
	return false;
}
inline void f10_observe(uint64_t label) {
	if (g_chain_mode < 2) return;
	const uint64_t          t0 = SoftCp::now_ns();
	std::vector<ChainSlot*> mine, seen;
	bool                    list_busy = false;
	for (;;) { // a busy list is looked at again until F10's 2 ms bound; slots already seen are not looked at twice
		list_busy = false;
		if (!g_f10_reg_mu.try_lock()) list_busy = true;
		else {
			for (ChainSlot* cs: g_f10_reg) {
				if (cs == &g_chain_tl || std::find(seen.begin(), seen.end(), cs) != seen.end()) continue;
				seen.push_back(cs);
				if (!cs->mu.try_lock()) { // mid-append or at its swap: its write may be pending, so it is waited for below
					mine.push_back(cs);
					continue;
				}
				const bool writes = !cs->c.segs.empty() && std::find(cs->f10_writes.begin(), cs->f10_writes.end(), label) != cs->f10_writes.end();
				if (writes && cs->hold.empty()) {
					mine.push_back(cs);
					if (cs->in_submit) cs->f10_wanted = true; // its owner flushes at its call's end
					else cs->open_ns = 1;                     // due now for the watchdog
				} else if (std::find(cs->f10_flight.begin(), cs->f10_flight.end(), label) != cs->f10_flight.end()) {
					mine.push_back(cs); // being submitted now: wait for its writes' registration
				} // a writer under the ADR 0013 hold is left to it
				cs->mu.unlock();
			}
			g_f10_reg_mu.unlock();
		}
		if (!list_busy || SoftCp::now_ns() - t0 >= 2'000'000ull) break;
		std::this_thread::yield();
	}
	bool bound = false;
	if (!mine.empty()) {
		chainwd_wake();
		for (;;) {
			if (!f10_pending(label, mine)) break;
			if (SoftCp::now_ns() - t0 >= 2'000'000ull) {
				bound = true;
				break;
			}
			std::this_thread::sleep_for(std::chrono::microseconds(20));
		}
	}
	// F16: the writers still in flight at the bound: wait for their submit_now to return.
	int      f16_res = 0, f16_ph = 0; // 1 returned, 2 50 ms bound, 3 given up by phase
	uint64_t f16_t   = 0;
	if (bound && g_f10_reg_mu.try_lock()) {
		struct W {
			ChainSlot* cs;
			uint64_t   done;
		};
		std::vector<W>          fl;
		std::vector<ChainSlot*> fls;
		for (ChainSlot* cs: mine) {
			if (std::find(g_f10_reg.begin(), g_f10_reg.end(), cs) == g_f10_reg.end() || !cs->mu.try_lock()) continue;
			if (std::find(cs->f10_flight.begin(), cs->f10_flight.end(), label) != cs->f10_flight.end()) fl.push_back({cs, cs->f16_done.load()});
			cs->mu.unlock();
		}
		g_f10_reg_mu.unlock();
		if (!fl.empty()) {
			const uint64_t t1   = SoftCp::now_ns();
			uint64_t       t_ph = 0;
			for (;;) {
				if (g_f10_reg_mu.try_lock()) {
					std::erase_if(fl, [](const W& w) { return std::find(g_f10_reg.begin(), g_f10_reg.end(), w.cs) == g_f10_reg.end() || w.cs->f16_done.load() != w.done; });
					g_f10_reg_mu.unlock();
					if (fl.empty()) {
						f16_res = 1;
						break;
					}
					fls.clear();
					for (const W& w: fl) fls.push_back(w.cs);
					if (phase_gate(fls, t_ph, f16_ph)) {
						f16_res = 3;
						break;
					}
				}
				if (SoftCp::now_ns() - t1 >= 50'000'000ull) {
					f16_res = 2;
					break;
				}
				std::this_thread::sleep_for(std::chrono::microseconds(20));
			}
			f16_t = SoftCp::now_ns() - t1;
			if (f16_res == 1) bound = false;
		}
	}
	// F18: a bound still standing.
	int      f18_res = 0, f18_ph = 0; // 1 the writers went, 2 50 ms bound, 3 given up by phase, 4 no writer of L left
	uint64_t f18_t   = 0;
	uint32_t c18[3] {};
	if (bound) {
		std::vector<ChainSlot*> left = mine, w18;
		bool                    fl18 = false, due = false;
		const uint64_t          t1   = SoftCp::now_ns();
		for (;;) {
			if (g_f10_reg_mu.try_lock()) {
				std::erase_if(left, [&](ChainSlot* cs) {
					if (std::find(g_f10_reg.begin(), g_f10_reg.end(), cs) == g_f10_reg.end()) return true; // its thread is gone
					if (!cs->mu.try_lock()) return false;
					const bool open = !cs->c.segs.empty() && std::find(cs->f10_writes.begin(), cs->f10_writes.end(), label) != cs->f10_writes.end();
					const bool fl   = std::find(cs->f10_flight.begin(), cs->f10_flight.end(), label) != cs->f10_flight.end();
					if (open && !cs->in_submit && cs->hold.empty()) {
						cs->open_ns = 1; // due now for the watchdog
						due         = true;
					}
					cs->mu.unlock();
					if (open) {
						w18.push_back(cs);
						c18[0]++;
					} else if (fl) fl18 = true; // F16's
					else c18[1]++;
					return true;
				});
				g_f10_reg_mu.unlock();
			}
			if (left.empty() || SoftCp::now_ns() - t1 >= 200'000ull) break;
			std::this_thread::yield();
		}
		for (ChainSlot* cs: left) {
			c18[2]++;
			w18.push_back(cs);
		}
		if (due) chainwd_wake();
		if (w18.empty()) f18_res = 4;
		uint64_t t_ph = 0;
		while (f18_res == 0) {
			if (!f10_pending(label, w18)) {
				f18_res = 1;
				break;
			}
			if (phase_gate(w18, t_ph, f18_ph)) {
				f18_res = 3;
				break;
			}
			if (SoftCp::now_ns() - t1 >= 50'000'000ull) {
				f18_res = 2;
				break;
			}
			std::this_thread::sleep_for(std::chrono::microseconds(20));
		}
		f18_t = SoftCp::now_ns() - t1;
		if ((f18_res == 1 || f18_res == 4) && !fl18) bound = false; // nothing of L pending any more
	}
#ifndef BC5_LEAN
	Store&          s = st();
	std::lock_guard lk(s.m);
	s.f10_calls++;
	if (!mine.empty()) s.f10_hit++;
	if (!mine.empty() && !bound && f16_res == 0 && f18_res == 0) s.f10_gone++;
	if (f16_res != 0 || f18_res != 0) s.f10_bound++;
	if (list_busy) s.f10_busy++;
	if (f16_res != 0) {
		s.f16_wait++;
		if (f16_res == 1) s.f16_ok++;
		else if (f16_res == 2) s.f16_bound++;
		else s.f16_stop[f16_ph]++;
		s.f16_ns += f16_t;
		if (f16_t > s.f16_max) s.f16_max = f16_t;
		if (s.f16_wait <= 64 || f16_res != 1)
			journal("ho430 F16: in-flight writer of 0x%" PRIx64 " %s after %.3f ms more (2 ms before)%s\n", label,
			        f16_res == 1 ? "returned" : f16_res == 2 ? "STILL IN SUBMIT at the 50 ms bound" : "not waited on", static_cast<double>(f16_t) / 1e6,
			        f16_res == 3 ? (f16_ph == 1 ? ": it is in back-pressure" : ": it drains the GPU") : "");
	}
	if (f18_res != 0) {
		s.f18_wait++;
		if (f18_res == 1) s.f18_ok++;
		else if (f18_res == 4) s.f18_none++;
		else if (f18_res == 2) s.f18_bound++;
		else s.f18_stop[f18_ph]++;
		for (int k = 0; k < 3; k++) s.f18_cls[k] += c18[k];
		s.f18_ns += f18_t;
		if (f18_t > s.f18_max) s.f18_max = f18_t;
		if (s.f18_wait <= 64 || bound)
			journal("ho430 F18: bound on 0x%" PRIx64 ": pending slots open writer/not a writer/still busy %u/%u/%u; %s after %.3f ms more%s\n", label, c18[0], c18[1], c18[2],
			        f18_res == 1 ? "the writers went" : f18_res == 4 ? "no writer of the label among them" : f18_res == 2 ? "A WRITER STILL PENDING at the 50 ms bound" : "a writer not waited on", static_cast<double>(f18_t) / 1e6,
			        f18_res == 3 ? (f18_ph == 1 ? ": it is in back-pressure" : ": it drains the GPU") : "");
	}
	if (bound) {
		s.stands++;
		journal("ho430: THE BOUND STANDS on 0x%" PRIx64 " after %.3f ms: the wait is decided as before (%" PRIu64 " so far)\n", label, static_cast<double>(SoftCp::now_ns() - t0) / 1e6, s.stands);
	}
	s.f10_ns += SoftCp::now_ns() - t0;
#else
	(void)f16_t;
	(void)f18_t;
	(void)f16_ph;
	(void)f18_ph;
#endif
}
// At a wait of a buffer about to be submitted (submit_split), before the host decides it.
inline void at_wait(const uint32_t* p, bool is64, uint64_t label, const char* kind, int ring, const uint32_t* ib, uint32_t num_dwords, uint32_t off) {
	(void)off;
	if (kind != nullptr && std::strncmp(kind, "acb", 3) == 0) f10_observe(label); // F10: the chains that write this label go first
	if (!wait_satisfied(p, is64)) return;
	std::vector<std::pair<int, uint64_t>> others; // (ring, seq) of pending writes to this label on another ring
	{
		std::lock_guard lk(g_plw_mutex);
		for (const auto& w: g_plw)
			if (w.label == label && w.ring != ring && std::find(others.begin(), others.end(), std::make_pair(w.ring, w.seq)) == others.end()) others.emplace_back(w.ring, w.seq);
	}
	if (others.empty()) return;
	// The cycle check: a writer job holding a kept GPU wait on a label this buffer writes cannot complete before this buffer runs.
	std::vector<uint64_t> writes;
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h = ib[q], len = pkt_len(h);
		if (q + len > num_dwords) break;
		const uint32_t op = (h >> 8u) & 0xffu;
		if ((h >> 30u) == 3 && ((op == 0x49 && len >= 6) || (op == 0x37 && len >= 4) || (op == 0x47 && len >= 4))) {
			const int lo = op == 0x49 ? 3 : 2;
			writes.push_back((static_cast<uint64_t>(ib[q + lo]) & ~3ull) | (static_cast<uint64_t>(ib[q + lo + 1] & 0xffffu) << 32u));
		}
		q += len;
	}
	Store&           s = st();
	std::unique_lock lk(s.m);
	for (const auto& o: others) {
		const auto it = s.job_waits.find(o);
		if (it == s.job_waits.end()) continue;
		for (const uint64_t l: it->second)
			if (std::find(writes.begin(), writes.end(), l) != writes.end()) {
#ifndef BC5_LEAN
				const uint64_t k = s.f2_cycle++;
				if (k < 64 || (k & 0xfffu) == 0)
					journal("ho430 F2: %s wait at %u on 0x%" PRIx64 " (satisfied) has a pending write from job %" PRIu64 " on ring %d, which waits on a label this buffer writes: a cycle, not ordered (%" PRIu64 " so far)\n", kind, off, label, o.second, o.first, k + 1);
#endif
				return;
			}
	}
#ifndef BC5_LEAN
	const uint64_t k = s.f4_fence++;
#endif
	lk.unlock();
	for (const auto& o: others) bc5::direct::Device::add_next_submit_dependency(o.first, o.second); // F4: the kernel orders it
#ifndef BC5_LEAN
	if (k < 64 || (k & 0x3fffu) == 0)
		journal("ho430 F4: %s wait at %u on 0x%" PRIx64 " was satisfied with a pending write from job %" PRIu64 " on ring %d (%zu such jobs): the submission depends on it (%" PRIu64 " so far)\n", kind, off, label,
		        others.front().second, others.front().first, others.size(), k + 1);
#endif
}
} // namespace ho430
