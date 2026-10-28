// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0356: a ledger of the title's AMM map and unmap commands, for the reserved-range fault
// handler. A command is pending from its submission (the APR engine is asynchronous, exp 0156: a worker
// per priority queue runs the buffers in order) until the worker has executed it; the last executed
// commands stay in a ring. The fault handler asks whether a pending map covers the page the title
// touched (then the page is about to appear and the access waits for it) and, when none does, what
// the page's history was (the last maps and unmaps overlapping it), before the host gives up.
// Header-only; no host dependency, so tests/AmmLedgerTests.cpp builds it alone.
#pragma once

#include <cinttypes>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <vector>

namespace Kyty::Libs::LibAmpr {

class AmmLedger {
public:
	enum Kind : uint8_t { MapAuto = 0, MapDirect = 1, Unmap = 2, Other = 3 };

	struct Entry {
		uint64_t command_buffer = 0; // with record_offset: the command's identity
		uint64_t record_offset  = 0;
		uint64_t va             = 0;
		uint64_t size           = 0;
		uint64_t t_ns           = 0; // when it was submitted (pending) or executed (ring)
		uint32_t submission_id  = 0;
		int32_t  result         = 0; // the executed command's result
		Kind     kind           = Other;
		uint8_t  queue          = 0;
	};

	explicit AmmLedger(size_t ring = 16384): ring_(ring) {}

	// A command of a submitted buffer, not executed yet.
	void Pend(const Entry& e) {
		std::scoped_lock lock(mutex_);
		pending_.push_back(e);
	}

	// The worker executed it: out of the pending list, into the ring with its result.
	void Executed(uint64_t command_buffer, uint64_t record_offset, int32_t result, uint64_t t_ns) {
		std::scoped_lock lock(mutex_);
		Entry e {};
		bool  found = false;
		for (size_t i = 0; i < pending_.size(); i++) {
			if (pending_[i].command_buffer == command_buffer && pending_[i].record_offset == record_offset) {
				e = pending_[i];
				pending_.erase(pending_.begin() + static_cast<std::ptrdiff_t>(i));
				found = true;
				break;
			}
		}
		if (!found) {
			e.command_buffer = command_buffer;
			e.record_offset  = record_offset;
		}
		e.result = result;
		e.t_ns   = t_ns;
		if (ring_.empty()) {
			return;
		}
		ring_[ring_next_ % ring_.size()] = e;
		ring_next_++;
	}

	// A submission the engine dropped (an earlier command failed, the buffer stopped): its commands leave
	// the pending list without executing.
	void Dropped(uint64_t command_buffer) {
		std::scoped_lock lock(mutex_);
		for (size_t i = 0; i < pending_.size();) {
			if (pending_[i].command_buffer == command_buffer) {
				pending_.erase(pending_.begin() + static_cast<std::ptrdiff_t>(i));
			} else {
				i++;
			}
		}
	}

	// The oldest pending map (not unmap) whose range holds `va`, if any.
	bool PendingMapCovering(uint64_t va, Entry* out) const {
		std::scoped_lock lock(mutex_);
		for (const Entry& e : pending_) {
			if (e.kind != Unmap && va >= e.va && va < e.va + e.size) {
				if (out != nullptr) *out = e;
				return true;
			}
		}
		return false;
	}

	bool IsPending(uint64_t command_buffer, uint64_t record_offset) const {
		std::scoped_lock lock(mutex_);
		for (const Entry& e : pending_) {
			if (e.command_buffer == command_buffer && e.record_offset == record_offset) return true;
		}
		return false;
	}

	size_t PendingCount() const {
		std::scoped_lock lock(mutex_);
		return pending_.size();
	}

	// The executed commands overlapping the page of `va`, oldest first (at most `max`), and the last
	// `last` executed commands overall; both written to `f`.
	void Dump(uint64_t va, std::FILE* f, size_t max = 16, size_t last = 16) const {
		std::scoped_lock lock(mutex_);
		const uint64_t page = va & ~uint64_t {0x3fff};
		const size_t   n    = ring_next_ < ring_.size() ? ring_next_ : ring_.size();
		std::vector<const Entry*> hits;
		for (size_t k = 0; k < n; k++) {
			const Entry& e = ring_[(ring_next_ - n + k) % ring_.size()];
			if (e.va < page + 0x4000 && e.va + e.size > page) hits.push_back(&e);
		}
		std::fprintf(f, "amm ledger: %zu executed commands kept, %zu pending; %zu touched the page 0x%016" PRIx64 "\n", n,
		             pending_.size(), hits.size(), page);
		const size_t from = hits.size() > max ? hits.size() - max : 0;
		for (size_t k = from; k < hits.size(); k++) Line(f, *hits[k], "  page history");
		const size_t lfrom = n > last ? n - last : 0;
		for (size_t k = lfrom; k < n; k++) Line(f, ring_[(ring_next_ - n + k) % ring_.size()], "  recent");
		for (const Entry& e : pending_) {
			if (e.va < page + 0x4000 && e.va + e.size > page) Line(f, e, "  pending on the page");
		}
	}

	static const char* KindName(Kind k) {
		switch (k) {
			case MapAuto: return "map-auto";
			case MapDirect: return "map-direct";
			case Unmap: return "unmap";
			default: return "other";
		}
	}

private:
	static void Line(std::FILE* f, const Entry& e, const char* tag) {
		std::fprintf(f, "%s: t %.3f s %s va 0x%016" PRIx64 " size 0x%" PRIx64 " cb 0x%016" PRIx64 " +0x%" PRIx64 " sub %u q%u result 0x%08x\n", tag,
		             static_cast<double>(e.t_ns) / 1e9, KindName(e.kind), e.va, e.size, e.command_buffer, e.record_offset, e.submission_id, e.queue,
		             static_cast<unsigned>(e.result));
	}

	mutable std::mutex mutex_;
	std::vector<Entry> pending_;
	std::vector<Entry> ring_;
	size_t             ring_next_ = 0;
};

} // namespace Kyty::Libs::LibAmpr
