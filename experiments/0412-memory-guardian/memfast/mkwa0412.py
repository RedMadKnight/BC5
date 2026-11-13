#!/usr/bin/env python3
"""BC5 experiment 0412, tag wa412 (README section 67): the WATCHED ADDRESS, a catcher.
BC5_GUARD_WATCH=<hex guest address>[,<hex>...] (at most 4; default unset: nothing is done). For each address the
journal gets a line whenever its state changes, and every 10 s:
  under which view (name, eager / lazy / by data, the address's offset into it), or under none;
  whether the CPU has written the address's 2 MiB chunk of the direct file (SEEK_DATA finds data in it);
  whether that chunk is imported (pinned);
  what the GPU has at the address: no mapping, the title's memory, or a read-only zero cover (K1r).
The state is read on the submitting thread at the start of the per-submission sync (the state the previous
submission ran with), from the unit's own lists. It changes nothing.
Why: the fault of 2026-11-13 08:59 was a shader's read at 0x1100000000 with the chunk never written, not imported
and not mapped. The cutscene arm did not fault with K1r off (section 66); this says whether the page is in that
state in our runs at all, and when it leaves it.
Input: the main unit after mkk1r0412.py (k1r412_is_cover is used). One anchor for the glue, one for the call.
usage: mkwa0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import sys

T = b" // exp 0412 (tag wa412)\n"

GLUE = rb'''// Experiment 0412 (tag wa412): BC5_GUARD_WATCH, the state of up to four guest addresses in the journal. A catcher.
namespace wa412 {
inline const std::vector<uint64_t>& list() {
	static const std::vector<uint64_t> v = [] {
		std::vector<uint64_t> o;
		const char*           e = std::getenv("BC5_GUARD_WATCH");
		while (e != nullptr && *e != 0 && o.size() < 4) {
			char*              end = nullptr;
			const uint64_t     a   = std::strtoull(e, &end, 16);
			if (end == e) break;
			o.push_back(a);
			e = (*end == ',') ? end + 1 : end;
			if (*end != ',') break;
		}
		return o;
	}();
	return v;
}
} // namespace wa412
// The state of one address in words (also used by the read probe of mkpr0412.py).
static void wa412_text(const DState& S, const std::vector<DView>& views, int fd, uint64_t addr, char* text, size_t cap) {
	{
		const uint64_t page = addr & ~0xfffull;
		const DView*   v    = nullptr;
		for (const auto& x: views) {
			if (page >= x.va && page < x.va + x.size) {
				v = &x;
				break;
			}
		}
		int n = 0;
		if (v == nullptr) {
			n = std::snprintf(text, cap, "under NO view");
		} else {
			const uint64_t choff    = (v->off + (page - v->va)) & ~(kDChunk - 1);
			const off_t    d        = lseek(fd, static_cast<off_t>(choff), SEEK_DATA);
			const bool     written  = d >= 0 && static_cast<uint64_t>(d) < choff + kDChunk;
			const bool     imported = direct_covered_end(S, choff) != 0;
			n = std::snprintf(text, cap, "under \"%s\" (%s; view 0x%" PRIx64 "+0x%" PRIx64 ", 0x%" PRIx64 " into it; file chunk 0x%" PRIx64 "): the chunk %s by the CPU, %s", v->name.c_str(),
			                  v->eager ? "eager" : (v->lazy ? "lazy" : "by data"), v->va, v->size, page - v->va, choff, written ? "WRITTEN" : "never written", imported ? "IMPORTED" : "not imported");
		}
		auto it = std::upper_bound(S.maps.begin(), S.maps.end(), page, [](uint64_t p, const DMap& m) { return p < m.va; });
		const DMap* m = nullptr;
		if (it != S.maps.begin()) {
			--it;
			if (page < it->va + it->size) m = &*it;
		}
		if (n > 0 && static_cast<size_t>(n) < cap) {
			std::snprintf(text + n, cap - static_cast<size_t>(n), "; GPU: %s", m == nullptr ? "NO MAPPING (a read here faults)" : (k1r412_is_cover(m->id) ? "a read-only zero cover (K1r)" : "the title's memory"));
		}
	}
}
static void wa412_look(const DState& S, const std::vector<DView>& views, int fd) {
	const auto& a = wa412::list();
	if (a.empty() || S.kind != 0) return;
	static uint64_t    last_ns = 0;
	static std::string last[4];
	const uint64_t     now  = SoftCp::now_ns();
	const bool         tick = now - last_ns >= 10'000'000'000ull;
	for (size_t i = 0; i < a.size(); i++) {
		char text[640];
		wa412_text(S, views, fd, a[i], text, sizeof(text));
		const bool changed = last[i] != text;
		if (changed || tick) journal("watch (exp 0412, tag wa412): t %.1f s: 0x%" PRIx64 ": %s%s\n", timing_now(), a[i], text, changed ? "  <-- changed" : "");
		last[i] = text;
	}
	if (tick) last_ns = now;
}
'''


def once(s, old, new):
    assert s.count(old) == 1, ("an anchor does not occur exactly once", old[:70], s.count(old))
    return s.replace(old, new)


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s and b"tag k1r412" in s and b"tag wa412" not in s, "refused: not the unit after mkk1r0412.py, or already edited"
    GLUE.decode("ascii")
    a = b"static void direct_sync_one(DState& S, bool force) {\n"
    s = once(s, a, GLUE + a)
    i = s.index(a)
    b = b"\tconst auto               views_p = direct_views(S);\n\tconst std::vector<DView>& views  = views_p->v;\n"
    j = s.index(b, i)
    assert j - i < 3000, "the views are not read at the start of direct_sync_one"
    j += len(b)
    s = s[:j] + b"\twa412_look(S, views, fd);" + T + s[j:]
    g = s.index(b"static void wa412_look(")
    for need in (b"static bool k1r412_is_cover(uint32_t id)", b"static uint64_t direct_covered_end(const DState& S, uint64_t off) {", b"static double timing_now() {"):
        assert s.index(need) < g, ("must be defined before the glue", need[:40])
    open(sys.argv[2], "wb").write(s)
    print(f"bc5LleAgc.cpp {hashlib.md5(s).hexdigest()}")


if __name__ == "__main__":
    main()
