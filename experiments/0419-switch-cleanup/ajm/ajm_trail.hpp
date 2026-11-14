// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0419 (the title's CPU fault at eboot+0x1b349f): the pure part of three AJM switches, all off by
// default, tested on the laptop by test0419ajm.cpp. No project header is used here.
//   KYTY_BC5_AUDIO_TRAIL=1   catcher: a ring of the last AJM calls, printed with a wider dump when the guest faults
//   KYTY_BC5_AJM_DEFER=1     fix candidate: a batch's jobs run at sceAjmBatchStart, as on the console, not when added
//   KYTY_BC5_AJM_LIVE_IDS=1  fix candidate: an instance id that is still alive is not given out again (the 14-bit
//                            slot counter wraps after 16,384 creates and today overwrites a live instance)
#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <mutex>
#include <unordered_map>
#include <utility>
#include <vector>

namespace bc5::ajm_trail {

struct Rec {
	uint64_t    seq      = 0;
	uint64_t    t_us     = 0;
	const char* kind     = ""; // a string literal
	uint64_t    in       = 0, in_size = 0, out = 0, out_size = 0;
	uint32_t    instance = 0;
	int32_t     tid      = 0;
	int32_t     result   = 0, internal = 0;
	uint32_t    consumed = 0, produced = 0, frames = 0;
};

constexpr uint32_t kRing = 256;

// Writers come from several guest threads: the sequence number is taken atomically and each writer fills its own
// slot; two writers meet in one slot only when 256 calls overlap. The reader is the fault handler: no lock, no
// allocation.
struct Trail {
	Rec                   ring[kRing] {};
	std::atomic<uint64_t> n {0};

	void add(Rec r) {
		const uint64_t i = n.fetch_add(1, std::memory_order_relaxed);
		r.seq            = i;
		ring[i % kRing]  = r;
	}
	[[nodiscard]] uint64_t first() const {
		const uint64_t e = n.load(std::memory_order_relaxed);
		return e > kRing ? e - kRing : 0;
	}
	[[nodiscard]] uint64_t end() const { return n.load(std::memory_order_relaxed); }
	[[nodiscard]] const Rec& at(uint64_t seq) const { return ring[seq % kRing]; }

	// The newest record one of whose buffers holds address v. *is_out: its output buffer; *off: v's offset in it.
	bool where(uint64_t v, Rec* r, bool* is_out, uint64_t* off) const {
		const uint64_t b = first();
		for (uint64_t i = end(); i > b; i--) {
			const Rec& x = at(i - 1);
			if (x.out != 0 && x.out_size != 0 && v >= x.out && v - x.out < x.out_size) {
				*r      = x;
				*is_out = true;
				*off    = v - x.out;
				return true;
			}
			if (x.in != 0 && x.in_size != 0 && v >= x.in && v - x.in < x.in_size) {
				*r      = x;
				*is_out = false;
				*off    = v - x.in;
				return true;
			}
		}
		return false;
	}
};

constexpr uint32_t kSlots = 0x4000;

// The next instance id of a codec: (codec << 14) | slot, the slot from a counter. With skip_live, ids for which
// live(id) is true are passed over (*skipped counts them); when all 16,384 are alive the last one tried is returned,
// as today. Without skip_live this is today's rule and *skipped says whether the id given out is alive (0 or 1).
template <class Live>
uint32_t next_id(std::atomic_uint32_t& counter, uint32_t codec, bool skip_live, Live live, uint32_t* skipped) {
	*skipped    = 0;
	uint32_t id = 0;
	for (uint32_t k = 0; k < kSlots; k++) {
		id = (codec << 14u) | (counter.fetch_add(1, std::memory_order_relaxed) & (kSlots - 1u));
		if (!live(id)) {
			return id;
		}
		(*skipped)++;
		if (!skip_live) {
			return id;
		}
	}
	return id;
}

// KYTY_BC5_AJM_DEFER: the jobs added to a batch buffer, in order, until the batch is started.
struct Pending {
	std::mutex                                                          mu;
	std::unordered_map<const void*, std::vector<std::function<void()>>> q;

	// sceAjmBatchInitialize: jobs of this buffer that were never started are dropped; their number is returned
	size_t reset(const void* buffer) {
		std::scoped_lock lock(mu);
		const auto       it = q.find(buffer);
		if (it == q.end()) {
			return 0;
		}
		const size_t n = it->second.size();
		q.erase(it);
		return n;
	}
	void push(const void* buffer, std::function<void()> f) {
		std::scoped_lock lock(mu);
		q[buffer].push_back(std::move(f));
	}
	// sceAjmBatchStart: the buffer's jobs run in the order they were added, outside the lock; their number
	size_t run(const void* buffer) {
		std::vector<std::function<void()>> jobs;
		{
			std::scoped_lock lock(mu);
			const auto       it = q.find(buffer);
			if (it == q.end()) {
				return 0;
			}
			jobs = std::move(it->second);
			q.erase(it);
		}
		for (auto& f: jobs) {
			f();
		}
		return jobs.size();
	}
};

} // namespace bc5::ajm_trail
