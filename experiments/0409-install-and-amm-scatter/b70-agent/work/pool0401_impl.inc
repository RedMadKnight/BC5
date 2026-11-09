// pool0401_impl.inc — shared pure helpers for pool scatter (experiment 0401).
// Included by both libAmpr.cpp (via mkpool0401.py) and pool0401.cpp.
// In libAmpr.cpp the g_* globals and AmmAutoRecordVa/ReleaseVa are the real ones.
// In pool0401.cpp they are simulated.
//
// Hooks (defined by the includer before this file):
//   Bc5PoolMapDirect(addr, size, mem_type, prot, flags, dmem, page_size) → void*
//   Bc5PoolUnmapDirect(addr, size) → int
//   Bc5PoolAllocDirect(search_start, search_end, size, align, type, allocated) → int
//   Bc5PoolSetName(addr, size, name) → int
//   Bc5PoolTraceStamp() → void
//   Bc5PoolWatchSurface(va) → void
//   Bc5PoolGetDirectMemorySize() → int64_t
//
// Globals assumed present: g_amm_auto_free, g_amm_auto_maps, g_amm_auto_pool_mutex
// Constants assumed present: PROT_CPU_READ, PROT_CPU_WRITE, OK, KERNEL_ERROR_EAGAIN,
//   AMM_MAP_FIXED, AMM_PAGE_SIZE
// Functions assumed present: NormalizeAmmProtection, AmmAutoRecordVa, AmmAutoReleaseVa

// ---- Mode reader ----
// Reads KYTY_BC5_AMM_SCATTER env var each call.
// unset / empty / "0" / unknown → 0 (off)
// "journal" → 1, "rescue" → 2, "first" → 3
static int Bc5AmmScatterMode() {
	const char* e = std::getenv("KYTY_BC5_AMM_SCATTER");
	if (e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0) {
		if (std::strcmp(e, "journal") == 0)      return 1;
		if (std::strcmp(e, "rescue") == 0)       return 2;
		if (std::strcmp(e, "first") == 0)        return 3;
	}
	return 0;
}

// ---- Pure helpers (no host state) ----

// Sum free bytes and count holes (g_amm_auto_free must be held).
static void Bc5PoolFreeStats(uint64_t* total, uint64_t* holes, uint64_t* largest) {
	uint64_t t = 0, h = 0, l = 0;
	for (const auto& r: g_amm_auto_free) {
		t += r.second;
		h++;
		if (r.second > l) l = r.second;
	}
	if (total) *total = t;
	if (holes) *holes = h;
	if (largest) *largest = l;
}

// Gather free ranges largest-first into [out_dmem, out_size] pairs, total >= want.
// Returns the number of pieces gathered (0 if not enough).
// FIX (review point 3): removes gathered pieces from the free list.
// FIX: trims the last piece to fit exactly within 'want'.
static size_t Bc5PoolGatherLocked(uint64_t want, std::vector<std::pair<uint64_t, uint64_t>>* out) {
	out->clear();
	if (want == 0) return 0;
	// Copy free list into a vector and sort largest first.
	std::vector<std::pair<uint64_t, uint64_t>> pieces;
	pieces.reserve(g_amm_auto_free.size());
	for (const auto& r: g_amm_auto_free) {
		pieces.push_back({r.first, r.second});
	}
	std::sort(pieces.begin(), pieces.end(),
	          [](const auto& a, const auto& b) { return a.second > b.second; });
	uint64_t have = 0;
	std::vector<uint64_t> erased_addrs;
	for (auto& p: pieces) {
		uint64_t take = p.second;
		if (have + take > want) {
			// Trim to fit within want.
			take = want - have;
		}
		out->push_back({p.first, take});
		have += take;
		erased_addrs.push_back(p.first);
		if (have >= want) {
			// Put remainder of last piece back into free list.
			if (take < p.second) {
				g_amm_auto_free[p.first + take] = p.second - take;
			}
			// Remove all gathered pieces from the free list.
			for (auto addr: erased_addrs) {
				auto it = g_amm_auto_free.find(addr);
				if (it != g_amm_auto_free.end()) {
					g_amm_auto_free.erase(it);
				}
			}
			return out->size();
		}
	}
	out->clear();
	return 0;
}

// Map a scattered automatic map: walk pieces, map each with the hook,
// record each with AmmAutoRecordVa. On failure of piece k, unmap 0..k-1.
// FIX (point 1): each piece is mapped at va + offset_of_piece, not at va.
// FIX (point 2): the last piece is trimmed to fit exactly 'size' bytes.
// FIX (point 5): each piece gets its own AmmAutoRecordVa(va_i, dmem_i, size_i).
static int Bc5MapAutoScattered(uint64_t va, uint64_t size, int memory_type, int32_t prot) {
	const int host_prot = NormalizeAmmProtection(prot);
	int host = host_prot | PROT_CPU_READ | PROT_CPU_WRITE;

	std::vector<std::pair<uint64_t, uint64_t>> pieces;
	{
		std::scoped_lock lock(g_amm_auto_pool_mutex);
		const int mode = Bc5AmmScatterMode();
		if (mode == 0) {
			// Off: first-fit — find one contiguous range >= size.
			for (auto it = g_amm_auto_free.begin(); it != g_amm_auto_free.end(); ++it) {
				if (it->second >= size) {
					pieces.push_back({it->first, size});
					const uint64_t rest_start = it->first + size;
					const uint64_t rest_size = it->second - size;
					g_amm_auto_free.erase(it);
					if (rest_size != 0) g_amm_auto_free[rest_start] = rest_size;
					break;
				}
			}
		} else {
			Bc5PoolGatherLocked(size, &pieces);
		}
	}
	if (pieces.empty()) return KERNEL_ERROR_EAGAIN;

	// Trim the last piece if the sum exceeds 'size'.
	uint64_t sum_before_last = 0;
	if (pieces.size() > 1) {
		for (size_t i = 0; i < pieces.size() - 1; i++) {
			sum_before_last += pieces[i].second;
		}
		uint64_t last_trim = size - sum_before_last;
		if (last_trim < pieces.back().second) {
			pieces.back().second = last_trim;
			// Put the remainder back into the free list.
			{ std::scoped_lock lock(g_amm_auto_pool_mutex);
				g_amm_auto_free[pieces.back().first + last_trim] = pieces.back().second - last_trim;
			}
		}
	}

	// Map each piece.
	std::vector<void*> mapped(pieces.size(), nullptr);
	for (size_t i = 0; i < pieces.size(); i++) {
		// FIX (point 1): each piece at its own VA offset.
		uint64_t piece_va = va;
		for (size_t j = 0; j < i; j++) piece_va += pieces[j].second;
		void* addr = reinterpret_cast<void*>(piece_va);
		void* result = Bc5PoolMapDirect(&addr, pieces[i].second, memory_type, host,
		                                 AMM_MAP_FIXED,
		                                 static_cast<int64_t>(pieces[i].first), AMM_PAGE_SIZE);
		if (result == nullptr) {
			// Rollback: unmap pieces 0..i-1.
			for (size_t j = 0; j < i; j++) {
				Bc5PoolUnmapDirect(mapped[j], pieces[j].second);
			}
			return KERNEL_ERROR_EAGAIN;
		}
		mapped[i] = addr;
	}

	// All pieces mapped: record each in g_amm_auto_maps.
	// AmmAutoRecordVa acquires its own mutex internally.
	{
		uint64_t cur_va = va;
		for (size_t i = 0; i < pieces.size(); i++) {
			// FIX (point 5): each piece gets its own record.
			AmmAutoRecordVa(cur_va, pieces[i].first, pieces[i].second);
			cur_va += pieces[i].second;
		}
	}

	// Name the full range.
	(void)Bc5PoolSetName(reinterpret_cast<void*>(
		reinterpret_cast<uint64_t>(mapped[0])), size, "AMM");

	// Watch for the surface size.
	if (size == 0x1fe0000ull) {
		Bc5PoolWatchSurface(reinterpret_cast<uint64_t>(mapped[0]));
	}

	return static_cast<int>(pieces.size());
}
