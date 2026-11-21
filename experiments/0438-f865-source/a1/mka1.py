# SPDX-License-Identifier: GPL-2.0-only
# BC5 exp 0438 A1 (tag a1438): VirtualRanges' table in an ordered map (std::map keyed by start) instead of a sorted
# vector, behind KYTY_BC5_0438_A1 ("1" = map; anything else or unset = the old vector code, unchanged).
#   python -I mka1.py IN_memory.cpp OUT_memory.cpp
#       applies the change by exact replacements (each must match once; the input md5 is pinned).
#   python -I mka1.py --extract OUT_memory.cpp HEADER.h [MUTANT]
#       pulls the real range code (constants, helpers, VirtualRangesVec, VirtualRangesMap, VirtualRanges) out of a
#       generated memory.cpp into a standalone header for test_a1438.cpp; MUTANT (m1..m4) plants one bug in the map
#       class only, so the test can show it catches it.
import hashlib
import sys

IN_MD5 = "aa7d7f5b3fdbbe8d57bd440e7aa80922"

OLD_HEAD = b"class VirtualRanges {\npublic:\n\t// BC5 (experiment 0037): changes with every edit of the ranges"
NEW_HEAD = (b"// BC5 exp 0438 A1 (tag a1438): the old class, renamed only; VirtualRanges below picks it or VirtualRangesMap.\n"
            b"class VirtualRangesVec {\npublic:\n\t// BC5 (experiment 0037): changes with every edit of the ranges")

OLD_TAIL = (b"\tstd::vector<Range> m_ranges;\n\tstd::atomic<uint64_t> m_gen {1};\n\tCommon::Mutex      m_mutex;\n};\n\n"
            b"#if defined(KYTY_VIRTUAL_MEMORY_ALLOCATION_TESTS)\nstatic uint32_t g_test_physical_memory_unmaps_before_failure")

BLOCK = r'''
// ---- BC5 exp 0438 A1 (tag a1438, mka1.py) ---------------------------------------------------------------------------
// VirtualRangesMap: VirtualRangesVec's public interface and results, the table in a std::map keyed by start. Every
// method follows the vector code step by step (same window, same pieces, same merge pairs, same generation bumps);
// a split rewrites the node in place (its key stays the piece's start) and emplaces the other pieces with a hint, a
// merge grows the left node and erases the right one. Snapshot/SnapshotWithDirty build the sorted vector from the
// map once per generation and copy the cached one after. test_a1438.cpp runs this text against VirtualRangesVec.
// A multimap, not a map: the vector code accepts a second range with the same start when that start is UINT64_MAX
// (End saturates, so VirtualRangesOverlap sees no overlap) and inserts it before the first; emplace_hint at
// lower_bound(start) puts it at the same place, and every lookup uses lower_bound/upper_bound as the vector code does.
class VirtualRangesMap {
public:
	using Range = VirtualRangesVec::Range;

	[[nodiscard]] uint64_t Generation() const { return m_gen.load(std::memory_order_acquire); }

	void Overlapping(uint64_t lo, uint64_t hi, std::vector<std::pair<uint64_t, uint64_t>>* out) {
		Common::LockGuard lock(m_mutex);
		out->clear();
		auto it = m_ranges.upper_bound(lo);
		if (it != m_ranges.begin()) --it;
		for (; it != m_ranges.end() && it->second.start < hi; ++it) {
			const Range& r = it->second;
			if (r.start + r.size > lo) out->emplace_back(r.start, r.start + r.size);
		}
	}

	bool Add(uint64_t start, uint64_t size, uint64_t offset, int protection, int memory_type, VirtualRangeType type,
	         const char* name, bool disallow_merge = false) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel);
		NoteDirtyUnlocked(start, size);

		if (start == 0 || size == 0) {
			return false;
		}
		auto position = m_ranges.lower_bound(start);
		if ((position != m_ranges.end() && VirtualRangesOverlap(start, size, position->second.start, position->second.size)) ||
		    (position != m_ranges.begin() &&
		     VirtualRangesOverlap(start, size, std::prev(position)->second.start, std::prev(position)->second.size))) {
			return false;
		}

		Range r {};
		r.start          = start;
		r.size           = size;
		r.offset         = offset;
		r.protection     = protection;
		r.memory_type    = memory_type;
		r.type           = type;
		r.disallow_merge = disallow_merge;
		CopyVirtualRangeName(r.name, name);
		MergeAroundUnlocked(m_ranges.emplace_hint(position, start, r));
		return true;
	}

	bool Remove(uint64_t start, uint64_t size) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel);
		NoteDirtyUnlocked(start, size);

		auto position = m_ranges.lower_bound(start); // the first range with this start, as LowerBound
		if (position != m_ranges.end() && position->second.start == start && position->second.size == size) {
			m_ranges.erase(position);
			return true;
		}
		return RemoveUnlocked(start, size);
	}

	bool HasOverlap(uint64_t start, uint64_t size) {
		Common::LockGuard lock(m_mutex);
		return FindOverlap(start, size) != nullptr;
	}

	bool QueryOverlap(uint64_t start, uint64_t size, Range* out) {
		EXIT_IF(out == nullptr);
		Common::LockGuard lock(m_mutex);
		const auto* overlap = FindOverlap(start, size);
		if (overlap == nullptr) {
			return false;
		}
		*out = *overlap;
		return true;
	}

	bool ReleaseReserved(uint64_t start, uint64_t size) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel);
		NoteDirtyUnlocked(start, size);

		// the vector code erases the first range with this start, size and a reserved type
		for (auto [it, e] = m_ranges.equal_range(start); it != e; ++it) {
			if (it->second.size == size && IsReservedRangeType(it->second.type)) {
				m_ranges.erase(it);
				break;
			}
		}
		return true;
	}

	bool ConsumeReserved(uint64_t start, uint64_t size, VirtualRangeType type = VirtualRangeType::Reserved) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel);
		NoteDirtyUnlocked(start, size);

		auto end = End(start, size);
		if (const Range* r = ContainingUnlocked(start); r != nullptr && r->type == type && end <= End(r->start, r->size)) {
			RemoveUnlocked(start, size);
			return true;
		}
		return false;
	}

	bool ConsumeReservedSpan(uint64_t start, uint64_t size, Range* first_range = nullptr,
	                         VirtualRangeType type = VirtualRangeType::Reserved) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel);
		NoteDirtyUnlocked(start, size);

		if (size == 0) {
			return false;
		}
		auto current = start;
		auto end     = End(start, size);
		while (current < end) {
			const Range* candidate = ContainingUnlocked(current);
			if (candidate == nullptr || candidate->type != type) {
				return false;
			}
			if (current == start && first_range != nullptr) {
				*first_range = *candidate;
			}
			current = std::min(end, End(candidate->start, candidate->size));
		}
		RemoveUnlocked(start, size);
		return true;
	}

	void Rename(uint64_t start, uint64_t size, const char* name) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel);
		NoteDirtyUnlocked(start, size);

		auto position = m_ranges.lower_bound(start); // the first range with this start, as LowerBound
		if (position != m_ranges.end() && position->second.start == start && position->second.size == size) {
			CopyVirtualRangeName(position->second.name, name);
			MergeAroundUnlocked(position);
			return;
		}
		EditUnlocked(start, size, [name](Range* r) { CopyVirtualRangeName(r->name, name); });
	}

	void Protect(uint64_t start, uint64_t size, int protection) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel);
		NoteDirtyUnlocked(start, size);
		EditUnlocked(start, size, [protection](Range* r) { r->protection = protection; });
	}

	void SetMemoryType(uint64_t start, uint64_t size, int memory_type) {
		Common::LockGuard lock(m_mutex);
		m_gen.fetch_add(1, std::memory_order_acq_rel);
		NoteDirtyUnlocked(start, size);
		EditUnlocked(start, size, [memory_type](Range* r) { r->memory_type = memory_type; });
	}

	bool Query(uint64_t addr, int flags, Range* out) {
		EXIT_IF(out == nullptr);
		Common::LockGuard lock(m_mutex);

		auto next = m_ranges.upper_bound(addr);
		if (next != m_ranges.begin()) {
			auto current = std::prev(next);
			if (addr < End(current->second.start, current->second.size)) {
				*out = current->second;
				return true;
			}
		}
		if (flags != 1 || next == m_ranges.end()) {
			return false;
		}
		*out = next->second;
		return true;
	}

	void Snapshot(std::vector<Range>* out) {
		EXIT_IF(out == nullptr);
		Common::LockGuard lock(m_mutex);
		*out = SortedUnlocked();
	}

	void SnapshotWithDirty(std::vector<Range>* out, uint64_t* gen, std::vector<std::pair<uint64_t, uint64_t>>* spans, bool* complete) {
		EXIT_IF(out == nullptr || gen == nullptr || spans == nullptr || complete == nullptr);
		Common::LockGuard lock(m_mutex);
		*out      = SortedUnlocked();
		*gen      = m_gen.load(std::memory_order_acquire);
		*complete = m_dirty_on && !m_dirty_overflow;
		spans->clear();
		spans->swap(m_dirty);
		m_dirty_on       = true;
		m_dirty_overflow = false;
	}

	bool QuerySpan(uint64_t start, uint64_t size, std::vector<Range>* out) {
		EXIT_IF(out == nullptr);
		Common::LockGuard lock(m_mutex);
		out->clear();
		if (start == 0 || size == 0 || size > UINT64_MAX - start) {
			return false;
		}

		const auto end     = start + size;
		auto       current = start;
		// exp 0412's switch and journal line as in VirtualRangesVec::QuerySpan (both walks give the same result)
		static const bool fast412 = [] {
			const char* e  = BC5_FIXED_ENV("KYTY_BC5_RANGES_FAST", "1");
			const bool  on = e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
			std::fprintf(stderr, "[bc5] exp 0412 ranges fast: %s (tag mf412)\n", on ? "on" : "off");
			return on;
		}();
		auto first412 = m_ranges.begin();
		if (fast412) {
			first412 = m_ranges.upper_bound(start);
			if (first412 != m_ranges.begin()) --first412;
		}
		for (auto it412 = first412; it412 != m_ranges.end(); ++it412) {
			const auto& range     = it412->second;
			const auto  range_end = End(range.start, range.size);
			if (range_end <= current) {
				continue;
			}
			if (range.start > current) {
				break;
			}
			Range part = range;
			part.start = current;
			part.size  = std::min(end, range_end) - current;
			if (part.type == VirtualRangeType::Direct) {
				part.offset += current - range.start;
			}
			out->push_back(part);
			current += part.size;
			if (current == end) {
				return true;
			}
		}
		out->clear();
		return false;
	}

	uint64_t ClampRangeSize(uint64_t virtual_addr, uint64_t size) {
		Common::LockGuard lock(m_mutex);
		if (virtual_addr == 0 || size == 0 || size > UINT64_MAX - virtual_addr) {
			return 0;
		}
		auto vma = m_ranges.upper_bound(virtual_addr);
		if (vma == m_ranges.begin()) {
			return 0;
		}
		--vma;
		const auto vma_end = End(vma->second.start, vma->second.size);
		if (virtual_addr < vma->second.start || virtual_addr >= vma_end || !IsCommittedRangeType(vma->second.type)) {
			return 0;
		}
		uint64_t clamped_size = std::min(size, vma_end - virtual_addr);
		uint64_t expected     = virtual_addr + clamped_size;
		++vma;
		while (vma != m_ranges.end() && vma->second.start == expected && IsCommittedRangeType(vma->second.type) &&
		       clamped_size < size) {
			const auto chunk = std::min(size - clamped_size, vma->second.size);
			clamped_size += chunk;
			expected += chunk;
			++vma;
		}
		return clamped_size;
	}

	uint64_t CountPageTableEntries(bool gpu) {
		Common::LockGuard lock(m_mutex);
		uint64_t used = 0;
		for (const auto& [key, r]: m_ranges) {
			if (!IsCommittedRangeType(r.type) || r.size == 0) {
				continue;
			}
			const bool has_cpu_access = (r.protection & (PROT_CPU_READ | PROT_CPU_WRITE | PROT_CPU_EXEC)) != 0;
			const bool has_gpu_access = (r.protection & (PROT_GPU_READ | PROT_GPU_WRITE)) != 0;
			if (gpu ? !has_gpu_access : !has_cpu_access) {
				continue;
			}
			const auto end         = End(r.start, r.size);
			const auto first_entry = r.start / PAGE_TABLE_GRANULARITY;
			const auto last_entry  = (end - 1) / PAGE_TABLE_GRANULARITY;
			used += last_entry - first_entry + 1;
		}
		return used;
	}

	// As VirtualRangesVec::DirtyWithTouching; bc5::map_records::touching's index pair becomes an iterator pair.
	void DirtyWithTouching(uint64_t* gen, std::vector<std::pair<uint64_t, uint64_t>>* spans, std::vector<std::vector<Range>>* touching, bool* complete) {
		EXIT_IF(gen == nullptr || spans == nullptr || touching == nullptr || complete == nullptr);
		Common::LockGuard lock(m_mutex);
		*gen      = m_gen.load(std::memory_order_acquire);
		*complete = m_dirty_on && !m_dirty_overflow;
		spans->clear();
		spans->swap(m_dirty);
		m_dirty_on       = true;
		m_dirty_overflow = false;
		touching->clear();
		if (!*complete) return;
		touching->reserve(spans->size());
		for (const auto& [start, size]: *spans) {
			const auto [a, b] = TouchingUnlocked(start, End(start, size));
			auto& v           = touching->emplace_back();
			for (auto it = a; it != b; ++it) v.push_back(it->second);
		}
	}

private:
	using Map = std::multimap<uint64_t, Range>; // a multimap: see the note at the class head
	using It  = Map::iterator;

	static uint64_t End(uint64_t start, uint64_t size) { return (UINT64_MAX - start < size ? UINT64_MAX : start + size); }

	static bool SameMergeKey(const Range& left, const Range& right) {
		if (left.disallow_merge || right.disallow_merge || left.type == VirtualRangeType::Direct ||
		    right.type == VirtualRangeType::Direct) {
			return false;
		}
		return left.type == right.type && left.protection == right.protection && left.memory_type == right.memory_type &&
		       std::strncmp(left.name, right.name, KERNEL_MAXIMUM_NAME_LENGTH) == 0;
	}

	void NoteDirtyUnlocked(uint64_t start, uint64_t size) {
		if (!m_dirty_on) return;
		if (m_dirty.size() >= 65536) {
			m_dirty_overflow = true;
			return;
		}
		m_dirty.emplace_back(start, size);
	}

	// The sorted vector the old code kept, built at most once per generation.
	const std::vector<Range>& SortedUnlocked() {
		const uint64_t gen = m_gen.load(std::memory_order_acquire);
		if (m_sorted_gen != gen) {
			m_sorted.clear();
			m_sorted.reserve(m_ranges.size());
			for (const auto& kv: m_ranges) m_sorted.push_back(kv.second);
			m_sorted_gen = gen;
		}
		return m_sorted;
	}

	// bc5::map_records::touching on the map: [first, last) of the ranges that overlap [lo, hi) or touch it.
	std::pair<It, It> TouchingUnlocked(uint64_t lo, uint64_t hi) {
		auto first = m_ranges.upper_bound(lo); // every range starting after lo ends after lo
		while (first != m_ranges.begin()) {
			auto p = std::prev(first);
			if (End(p->second.start, p->second.size) < lo) break;
			first = p;
		}
		if (hi < lo) return {first, first};
		auto last = m_ranges.upper_bound(hi);
		return {first, last};
	}

	// A piece [start, end) of `source`, as VirtualRangesVec::AddPiece; false when empty.
	static bool MakePiece(const Range& source, uint64_t start, uint64_t end, Range* piece) {
		if (end <= start) {
			return false;
		}
		*piece       = source;
		piece->start = start;
		piece->size  = end - start;
		if (piece->type == VirtualRangeType::Direct) {
			piece->offset += start - source.start;
		}
		return true;
	}

	// VirtualRangesVec::MergeAroundUnlocked(index) with the iterator of that index.
	void MergeAroundUnlocked(It it) {
		if (it == m_ranges.end()) {
			return;
		}
		if (it != m_ranges.begin()) {
			auto previous = std::prev(it);
			if (End(previous->second.start, previous->second.size) == it->second.start && SameMergeKey(previous->second, it->second)) {
				previous->second.size += it->second.size;
				m_ranges.erase(it);
				it = previous;
			}
		}
		for (;;) {
			auto next = std::next(it);
			if (next == m_ranges.end() || End(it->second.start, it->second.size) != next->second.start ||
			    !SameMergeKey(it->second, next->second)) {
				break;
			}
			it->second.size += next->second.size;
			m_ranges.erase(next);
		}
	}

	std::pair<It, It> OverlapWindowUnlocked(uint64_t start, uint64_t size) {
		const auto end   = End(start, size);
		auto       first = m_ranges.lower_bound(start);
		if (first != m_ranges.begin()) {
			auto prev = std::prev(first);
			if (VirtualRangesOverlap(start, size, prev->second.start, prev->second.size)) {
				first = prev;
			}
		}
		auto last = first;
		while (last != m_ranges.end() && last->second.start < end) {
			++last;
		}
		return {first, last};
	}

	const Range* ContainingUnlocked(uint64_t address) {
		auto it = m_ranges.lower_bound(address);
		if (it != m_ranges.end() && it->second.start == address) {
			return &it->second;
		}
		if (it == m_ranges.begin()) {
			return nullptr;
		}
		--it;
		return address >= it->second.start && address < End(it->second.start, it->second.size) ? &it->second : nullptr;
	}

	// VirtualRangesVec::EditUnlocked: each overlapping range becomes [left] mid [right]; the node keeps the first piece
	// (its key is that piece's start), the others are emplaced after it. Then the merge pass of MergeWindowUnlocked
	// over the same nodes: the left neighbour, the pieces, the right neighbour.
	template <typename EditFunc>
	void EditUnlocked(uint64_t start, uint64_t size, EditFunc edit) {
		if (size == 0) {
			return;
		}
		const auto edit_end = End(start, size);
		auto [first, last]  = OverlapWindowUnlocked(start, size);
		const bool has_prev = first != m_ranges.begin();
		const It   before   = has_prev ? std::prev(first) : m_ranges.end();
		It         first_piece = m_ranges.end();
		for (auto it = first; it != last;) {
			const Range r       = it->second;
			const auto  r_end   = End(r.start, r.size);
			const auto  mid_start = std::max(start, r.start);
			const auto  mid_end   = std::min(edit_end, r_end);
			Range       left {};
			Range       right {};
			const bool  has_left  = MakePiece(r, r.start, mid_start, &left);
			const bool  has_right = MakePiece(r, mid_end, r_end, &right);
			Range       mid = r;
			mid.start       = mid_start;
			mid.size        = mid_end - mid_start;
			if (mid.type == VirtualRangeType::Direct) {
				mid.offset += mid_start - r.start;
			}
			edit(&mid);
			const auto next_it = std::next(it);
			if (has_left) {
				it->second = left; // the node shrinks to the left piece
				m_ranges.emplace_hint(next_it, mid.start, mid);
			} else {
				it->second = mid; // mid starts at r.start
			}
			if (has_right) m_ranges.emplace_hint(next_it, right.start, right); // a1438-m1
			if (first_piece == m_ranges.end()) first_piece = it;
			it = next_it;
		}
		// MergeWindowUnlocked(index, count): pairs from index - 1 (or index) up to the node after `last`, exclusive
		It cur = has_prev ? before : (first_piece != m_ranges.end() ? first_piece : last);
		if (cur == m_ranges.end()) {
			return;
		}
		const It stop = last == m_ranges.end() ? m_ranges.end() : std::next(last);
		for (;;) {
			auto next = std::next(cur);
			if (next == m_ranges.end() || next == stop) {
				break;
			}
			if (End(cur->second.start, cur->second.size) == next->second.start && SameMergeKey(cur->second, next->second)) {
				cur->second.size += next->second.size;
				m_ranges.erase(next);
			} else {
				cur = next;
			}
		}
	}

	// VirtualRangesVec::RemoveUnlocked: each overlapping range keeps its pieces left and right of the span, no merge.
	bool RemoveUnlocked(uint64_t start, uint64_t size) {
		if (size == 0) {
			return false;
		}
		const auto rem_end = End(start, size);
		auto [first, last] = OverlapWindowUnlocked(start, size);
		if (first == last) {
			return false;
		}
		for (auto it = first; it != last;) {
			const Range r     = it->second;
			const auto  r_end = End(r.start, r.size);
			Range       left {};
			Range       right {};
			const bool  has_left  = MakePiece(r, r.start, std::max(start, r.start), &left);
			const bool  has_right = MakePiece(r, std::min(rem_end, r_end), r_end, &right);
			const auto  next_it   = std::next(it);
			if (has_left) {
				it->second = left;
			} else {
				m_ranges.erase(it);
			}
			if (has_right) m_ranges.emplace_hint(next_it, right.start, right);
			it = next_it;
		}
		return true;
	}

	Range* FindOverlap(uint64_t start, uint64_t size) {
		auto position = m_ranges.lower_bound(start);
		if (position != m_ranges.end() && VirtualRangesOverlap(start, size, position->second.start, position->second.size)) {
			return &position->second;
		}
		if (position != m_ranges.begin()) {
			auto previous = std::prev(position);
			if (VirtualRangesOverlap(start, size, previous->second.start, previous->second.size)) {
				return &previous->second;
			}
		}
		return nullptr;
	}

	Map                                        m_ranges;
	std::vector<Range>                         m_sorted;         // SortedUnlocked's cache
	uint64_t                                   m_sorted_gen = 0; // its generation (m_gen starts at 1)
	std::vector<std::pair<uint64_t, uint64_t>> m_dirty;
	bool                                       m_dirty_on       = false;
	bool                                       m_dirty_overflow = false;
	std::atomic<uint64_t>                      m_gen {1};
	Common::Mutex                              m_mutex;
};

// The class the rest of memory.cpp uses: one of the two, chosen once per process from KYTY_BC5_0438_A1 ("1" = map).
class VirtualRanges {
public:
	using Range = VirtualRangesVec::Range;

	VirtualRanges(): m_a1(A1On()) {
		if (m_a1) {
			m_map = std::make_unique<VirtualRangesMap>();
		} else {
			m_vec = std::make_unique<VirtualRangesVec>();
		}
	}

	static bool A1On() {
		static const bool on = [] {
			const char* e  = std::getenv("KYTY_BC5_0438_A1");
			const bool  v  = e != nullptr && std::strcmp(e, "1") == 0;
			std::fprintf(stderr, "[bc5] exp 0438 A1 ranges map: %s (tag a1438)\n", v ? "on" : "off");
			return v;
		}();
		return on;
	}

	[[nodiscard]] uint64_t Generation() const { return m_a1 ? m_map->Generation() : m_vec->Generation(); }
	void Overlapping(uint64_t lo, uint64_t hi, std::vector<std::pair<uint64_t, uint64_t>>* out) {
		m_a1 ? m_map->Overlapping(lo, hi, out) : m_vec->Overlapping(lo, hi, out);
	}
	bool Add(uint64_t start, uint64_t size, uint64_t offset, int protection, int memory_type, VirtualRangeType type,
	         const char* name, bool disallow_merge = false) {
		return m_a1 ? m_map->Add(start, size, offset, protection, memory_type, type, name, disallow_merge)
		            : m_vec->Add(start, size, offset, protection, memory_type, type, name, disallow_merge);
	}
	bool Remove(uint64_t start, uint64_t size) { return m_a1 ? m_map->Remove(start, size) : m_vec->Remove(start, size); }
	bool HasOverlap(uint64_t start, uint64_t size) { return m_a1 ? m_map->HasOverlap(start, size) : m_vec->HasOverlap(start, size); }
	bool QueryOverlap(uint64_t start, uint64_t size, Range* out) {
		return m_a1 ? m_map->QueryOverlap(start, size, out) : m_vec->QueryOverlap(start, size, out);
	}
	bool ReleaseReserved(uint64_t start, uint64_t size) {
		return m_a1 ? m_map->ReleaseReserved(start, size) : m_vec->ReleaseReserved(start, size);
	}
	bool ConsumeReserved(uint64_t start, uint64_t size, VirtualRangeType type = VirtualRangeType::Reserved) {
		return m_a1 ? m_map->ConsumeReserved(start, size, type) : m_vec->ConsumeReserved(start, size, type);
	}
	bool ConsumeReservedSpan(uint64_t start, uint64_t size, Range* first_range = nullptr,
	                         VirtualRangeType type = VirtualRangeType::Reserved) {
		return m_a1 ? m_map->ConsumeReservedSpan(start, size, first_range, type)
		            : m_vec->ConsumeReservedSpan(start, size, first_range, type);
	}
	void Rename(uint64_t start, uint64_t size, const char* name) {
		m_a1 ? m_map->Rename(start, size, name) : m_vec->Rename(start, size, name);
	}
	void Protect(uint64_t start, uint64_t size, int protection) {
		m_a1 ? m_map->Protect(start, size, protection) : m_vec->Protect(start, size, protection);
	}
	void SetMemoryType(uint64_t start, uint64_t size, int memory_type) {
		m_a1 ? m_map->SetMemoryType(start, size, memory_type) : m_vec->SetMemoryType(start, size, memory_type);
	}
	bool Query(uint64_t addr, int flags, Range* out) { return m_a1 ? m_map->Query(addr, flags, out) : m_vec->Query(addr, flags, out); }
	void Snapshot(std::vector<Range>* out) { m_a1 ? m_map->Snapshot(out) : m_vec->Snapshot(out); }
	void SnapshotWithDirty(std::vector<Range>* out, uint64_t* gen, std::vector<std::pair<uint64_t, uint64_t>>* spans, bool* complete) {
		m_a1 ? m_map->SnapshotWithDirty(out, gen, spans, complete) : m_vec->SnapshotWithDirty(out, gen, spans, complete);
	}
	bool QuerySpan(uint64_t start, uint64_t size, std::vector<Range>* out) {
		return m_a1 ? m_map->QuerySpan(start, size, out) : m_vec->QuerySpan(start, size, out);
	}
	uint64_t ClampRangeSize(uint64_t virtual_addr, uint64_t size) {
		return m_a1 ? m_map->ClampRangeSize(virtual_addr, size) : m_vec->ClampRangeSize(virtual_addr, size);
	}
	uint64_t CountPageTableEntries(bool gpu) { return m_a1 ? m_map->CountPageTableEntries(gpu) : m_vec->CountPageTableEntries(gpu); }
	void DirtyWithTouching(uint64_t* gen, std::vector<std::pair<uint64_t, uint64_t>>* spans, std::vector<std::vector<Range>>* touching, bool* complete) {
		m_a1 ? m_map->DirtyWithTouching(gen, spans, touching, complete) : m_vec->DirtyWithTouching(gen, spans, touching, complete);
	}

private:
	const bool                        m_a1;
	std::unique_ptr<VirtualRangesVec> m_vec;
	std::unique_ptr<VirtualRangesMap> m_map;
};
// ---- end BC5 exp 0438 A1 (tag a1438) ----
'''.lstrip("\n").encode()

NEW_TAIL = (b"\tstd::vector<Range> m_ranges;\n\tstd::atomic<uint64_t> m_gen {1};\n\tCommon::Mutex      m_mutex;\n};\n\n" + BLOCK +
            b"\n#if defined(KYTY_VIRTUAL_MEMORY_ALLOCATION_TESTS)\nstatic uint32_t g_test_physical_memory_unmaps_before_failure")

# Planted bugs for the test (map class only).
MUTANTS = {
    "m1": (b"\t\t\tif (has_right) m_ranges.emplace_hint(next_it, right.start, right); // a1438-m1\n", b"\t\t\t(void)has_right;\n"),  # drop a split's right piece
    "m2": (b"\t\tif (left.disallow_merge || right.disallow_merge || left.type == VirtualRangeType::Direct ||\n"
           b"\t\t    right.type == VirtualRangeType::Direct) {\n\t\t\treturn false;\n\t\t}\n"
           b"\t\treturn left.type == right.type && left.protection",
           b"\t\tif (left.type == VirtualRangeType::Direct ||\n"
           b"\t\t    right.type == VirtualRangeType::Direct) {\n\t\t\treturn false;\n\t\t}\n"
           b"\t\treturn left.type == right.type && left.protection"),  # ignore disallow_merge
    "m3": (b"\t\tif (m_sorted_gen != gen) {\n", b"\t\tif (m_sorted_gen == 0) {\n"),  # stale snapshot cache
    "m4": (b"\t\t\tif (End(p->second.start, p->second.size) < lo) break;\n",
           b"\t\t\tif (End(p->second.start, p->second.size) <= lo) break;\n"),  # touching misses a range ending at lo
}


def md5(b):
    return hashlib.md5(b).hexdigest()


def once(data, old, new, what):
    n = data.count(old)
    assert n == 1, f"{what}: {n} matches, want 1"
    return data.replace(old, new)


def cut(data, begin, end, what, include_end=False):
    i = data.find(begin)
    assert i >= 0 and data.count(begin) == 1, f"extract {what}: begin"
    j = data.find(end, i)
    assert j >= 0 and data.count(end) == 1, f"extract {what}: end"
    return data[i:j + (len(end) if include_end else 0)]


def apply(src, dst):
    data = open(src, "rb").read()
    assert md5(data) == IN_MD5, f"input md5 {md5(data)}, pinned {IN_MD5}"
    assert b"\r\n" not in data
    data = once(data, OLD_HEAD, NEW_HEAD, "class head")
    data = once(data, OLD_TAIL, NEW_TAIL, "class tail")
    open(dst, "wb").write(data)
    print(f"in  md5 {IN_MD5}\nout md5 {md5(data)}")


def extract(src, dst, mutant=None):
    data = open(src, "rb").read()
    consts = cut(data, b"constexpr int PROT_CPU_READ", b"constexpr uint64_t DEFAULT_FLEXIBLE_MEMORY_SIZE", "constants")
    helpers = cut(data, b"static void CopyVirtualRangeName", b"#if defined(KYTY_VIRTUAL_MEMORY_ALLOCATION_TESTS)\nstatic uint32_t g_test_backing_store", "helpers")
    classes = cut(data, b"enum class VirtualRangeType {", b"// ---- end BC5 exp 0438 A1 (tag a1438) ----\n", "classes", True)
    if mutant:
        old, new = MUTANTS[mutant]
        k = classes.find(b"class VirtualRangesMap {")
        head, tail = classes[:k], classes[k:]
        tail = once(tail, old, new, f"mutant {mutant}")
        classes = head + tail
    out = (b"// generated by mka1.py --extract from " + md5(data).encode() + (b" mutant " + mutant.encode() if mutant else b"") +
           b"\n#pragma once\n#include \"stub_a1.h\"\nnamespace Libs::LibKernel::Memory {\n" + consts + helpers + classes +
           b"} // namespace Libs::LibKernel::Memory\n")
    open(dst, "wb").write(out)
    print(f"extract {dst} from {md5(data)}{' mutant ' + mutant if mutant else ''}: md5 {md5(out)}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--extract":
        assert len(a) in (3, 4), "usage: mka1.py --extract OUT_memory.cpp HEADER.h [m1|m2|m3|m4]"
        extract(a[1], a[2], a[3] if len(a) == 4 else None)
    else:
        assert len(a) == 2, "usage: mka1.py IN_memory.cpp OUT_memory.cpp"
        apply(a[0], a[1])
