// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0356: the AMM ledger (ammLedger.h), built alone: clang++ -std=c++20 AmmLedgerTests.cpp.
#include "ammLedger.h"

#include <cassert>
#include <cinttypes>
#include <cstdio>

using Kyty::Libs::LibAmpr::AmmLedger;

int main() {
	AmmLedger l(4);
	AmmLedger::Entry a {};
	a.command_buffer = 0x1000;
	a.record_offset  = 0x20;
	a.va             = 0x8500000000ull;
	a.size           = 0x10000;
	a.kind           = AmmLedger::MapDirect;
	a.submission_id  = 7;
	a.queue          = 1;
	a.t_ns           = 1'000'000;
	l.Pend(a);
	AmmLedger::Entry u = a;
	u.record_offset    = 0x40;
	u.kind             = AmmLedger::Unmap;
	l.Pend(u);
	assert(l.PendingCount() == 2);
	// a pending map covers its range; an unmap never counts as cover; outside: none
	AmmLedger::Entry hit {};
	assert(l.PendingMapCovering(0x8500001930ull, &hit) && hit.record_offset == 0x20);
	assert(!l.PendingMapCovering(0x8500010000ull, nullptr));
	assert(l.IsPending(0x1000, 0x20));
	// executed: out of pending, into the ring with the result and the time
	l.Executed(0x1000, 0x20, 0, 2'000'000);
	assert(!l.IsPending(0x1000, 0x20));
	assert(l.PendingCount() == 1);
	assert(!l.PendingMapCovering(0x8500001930ull, nullptr)); // only the unmap is pending now
	// an unknown executed command still lands in the ring
	l.Executed(0x2000, 0x8, -1, 3'000'000);
	// the ring wraps at 4
	for (int k = 0; k < 6; k++) {
		AmmLedger::Entry e = a;
		e.command_buffer   = 0x3000 + static_cast<uint64_t>(k);
		e.va               = 0x8600000000ull + static_cast<uint64_t>(k) * 0x4000;
		l.Pend(e);
		l.Executed(e.command_buffer, e.record_offset, 0, 4'000'000 + static_cast<uint64_t>(k));
	}
	// a dropped submission leaves pending
	l.Dropped(0x1000);
	assert(l.PendingCount() == 0);
	// the dump runs (to stdout) without touching anything
	l.Dump(0x8600000000ull + 5 * 0x4000 + 0x10, stdout);
	std::printf("AmmLedgerTests: ok\n");
	return 0;
}
