// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0412 (tag ps412, mksort0412.py; README section 18): PhysicalMemory's mapping table kept sorted by guest
// address, so a block is found by binary search. Used only with KYTY_BC5_PHYSMAP_SORTED set and only while no two blocks
// overlap (insert() refuses an overlapping block; the caller then goes back to the old code for the rest of the run).
// Under that condition the old code's "first block, in insertion order, that matches" is "the block that contains the
// address", which is what containing() returns. V is a std::vector of blocks with map_vaddr, map_size, start_addr, size,
// host_vaddr, host_size and gpu_mode. No system call, no global: physmap0412.cpp runs this text against the old code.
namespace pm412 {

// The block whose [map_vaddr, map_vaddr + map_size) holds addr; end() when none does.
template <class V> auto containing(V& v, uint64_t addr) {
	auto it = std::upper_bound(v.begin(), v.end(), addr, [](uint64_t a, const auto& b) { return a < b.map_vaddr; });
	if (it == v.begin()) return v.end();
	--it;
	return addr - it->map_vaddr < it->map_size ? it : v.end();
}

// A place to start a walk over every block that can overlap [addr, ...): one block before the first that starts after addr.
template <class V> auto walk_from(V& v, uint64_t addr) {
	auto it = std::upper_bound(v.begin(), v.end(), addr, [](uint64_t a, const auto& b) { return a < b.map_vaddr; });
	if (it != v.begin()) --it;
	return it;
}

// Puts b in its place. False, and nothing changed, when b is empty, wraps, or overlaps a neighbour.
template <class V, class B> bool insert(V& v, const B& b) {
	if (b.map_size == 0 || UINT64_MAX - b.map_vaddr < b.map_size) return false;
	auto it = std::lower_bound(v.begin(), v.end(), b.map_vaddr, [](const auto& x, uint64_t a) { return x.map_vaddr < a; });
	if (it != v.end() && it->map_vaddr - b.map_vaddr < b.map_size) return false;
	if (it != v.begin()) {
		const auto& p = *std::prev(it);
		if (b.map_vaddr - p.map_vaddr < p.map_size) return false;
	}
	v.insert(it, b);
	return true;
}

enum Hit { None = 0, Whole = 1, Middle = 2, Head = 3, Tail = 4 };

// Which of Unmap's four cases the block at `it` matches for [vaddr, vaddr + size), in the old code's order.
template <class It> Hit match(It it, uint64_t vaddr, uint64_t size) {
	const auto& b = *it;
	if (b.map_vaddr == vaddr && b.map_size == size) return Whole;
	if (vaddr > b.map_vaddr && vaddr + size < b.map_vaddr + b.map_size) return Middle;
	if (vaddr == b.map_vaddr && size < b.map_size) return Head;
	if (vaddr > b.map_vaddr && vaddr + size == b.map_vaddr + b.map_size) return Tail;
	return None;
}

// The block Unmap acts on, or end(): the one that contains vaddr, when it matches a case.
template <class V> auto candidate(V& v, uint64_t vaddr, uint64_t size) {
	auto it = containing(v, vaddr);
	return it != v.end() && match(it, vaddr, size) != None ? it : v.end();
}

// The old search, for the verify mode and the CPU test: the first block in vector order that matches a case.
template <class V> auto linear_first(V& v, uint64_t vaddr, uint64_t size) {
	for (auto it = v.begin(); it != v.end(); ++it) {
		if (match(it, vaddr, size) != None) return it;
	}
	return v.end();
}

// Unmap's edit on the sorted table, the old code's statements. For Whole, *host_vaddr and *host_size are the removed
// block's host mapping (the caller asks host_still_mapped). The table stays sorted and without overlaps.
template <class V, class G> Hit unmap(V& v, uint64_t vaddr, uint64_t size, G* gpu_mode, uint64_t* host_vaddr, uint64_t* host_size) {
	auto it = candidate(v, vaddr, size);
	if (it == v.end()) return None;
	const Hit h = match(it, vaddr, size);
	auto&     b = *it;
	*gpu_mode   = b.gpu_mode;
	if (h == Whole) {
		*host_vaddr = b.host_vaddr;
		*host_size  = b.host_size;
		v.erase(it);
	} else if (h == Middle) {
		auto right = b;
		right.start_addr += (vaddr + size) - b.map_vaddr;
		right.size      = b.map_vaddr + b.map_size - (vaddr + size);
		right.map_size  = right.size;
		right.map_vaddr = vaddr + size;
		b.size          = vaddr - b.map_vaddr;
		b.map_size      = b.size;
		v.insert(std::next(it), right); // right after its left half: still sorted
	} else if (h == Head) {
		b.start_addr += size;
		b.size -= size;
		b.map_vaddr += size;
		b.map_size -= size;
	} else {
		b.size     = vaddr - b.map_vaddr;
		b.map_size = b.size;
	}
	return h;
}

// Whether a block with this host mapping is left. Every block is a piece of the Map() call that made its host mapping
// (Map sets host_vaddr = vaddr, host_size = len; the splits copy them), so it lies inside the host range.
template <class V> bool host_still_mapped(V& v, uint64_t host_vaddr, uint64_t host_size) {
	for (auto it = walk_from(v, host_vaddr); it != v.end(); ++it) {
		if (it->map_vaddr >= host_vaddr && it->map_vaddr - host_vaddr >= host_size) break; // past the host range
		if (it->host_vaddr == host_vaddr && it->host_size == host_size) return true;
	}
	return false;
}

// Whether every block lies inside its host range (what host_still_mapped relies on) and the table is sorted without overlaps.
template <class V> bool sound(const V& v) {
	for (size_t i = 0; i < v.size(); i++) {
		const auto& b = v[i];
		if (b.map_size == 0 || b.map_vaddr < b.host_vaddr || b.map_vaddr - b.host_vaddr > b.host_size || b.map_size > b.host_size - (b.map_vaddr - b.host_vaddr)) return false;
		if (i != 0 && b.map_vaddr - v[i - 1].map_vaddr < v[i - 1].map_size) return false;
		if (i != 0 && b.map_vaddr < v[i - 1].map_vaddr) return false;
	}
	return true;
}

} // namespace pm412
