#!/usr/bin/env python3
"""BC5 experiment 0412, tag k1r412 (README sections 62, 63): BC5_GUARD_K1R=1, the read-only zero cover (k1r0412.inc).
Two parts, both needed:
  backend: Device::map_shared gets an overload with `bool readonly` (AMDGPU_VM_PAGE_READABLE alone). The archive
           changes: the test build uses a private copy of the backend source and its own build directory.
  unit:    the main unit after mknl0412.py --keep-guards (and, if wanted, mkrl0412.py): the cover's pieces join the
           mapping rebuild's want list; they are mapped read-only; a rebuild that replaces covers drains the GPU first;
           the fault path names a write into a cover as its own kind; the zero buffer is checked for staying zero.
Each anchor occurs exactly once.
usage: mkk1r0412.py unit <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>
       mkk1r0412.py backend <backend dir in> <backend dir out>      (writes include/bc5/direct.hpp and src/direct.cpp)"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
T = b" // exp 0412 (tag k1r412)\n"

GLUE = b'''// Experiment 0412 (tag k1r412): BC5_GUARD_K1R, the host's part of the read-only zero cover (k1r0412.inc).
static int            g_k1r_fd  = -1;
static uint32_t       g_k1r_id  = 0;       // the zero buffer's import on the open device (0 after a reopen)
static const uint8_t* g_k1r_cpu = nullptr; // a read-only CPU view of it, for the "still zero" check
static uint32_t k1r412_bo() {
	if (g_k1r_id != 0 || !g_dev) return g_k1r_id;
	if (g_k1r_fd < 0) {
		g_k1r_fd = memfd_create("bc5-k1r-zero", MFD_CLOEXEC | MFD_ALLOW_SEALING);
		if (g_k1r_fd < 0) return 0;
		if (ftruncate(g_k1r_fd, static_cast<off_t>(kDChunk)) != 0 || fcntl(g_k1r_fd, F_ADD_SEALS, F_SEAL_SHRINK) != 0) {
			close(g_k1r_fd);
			g_k1r_fd = -1;
			return 0;
		}
		void* p = mmap(nullptr, kDChunk, PROT_READ, MAP_SHARED, g_k1r_fd, 0);
		g_k1r_cpu = p == MAP_FAILED ? nullptr : static_cast<const uint8_t*>(p);
	}
	g_k1r_id = g_dev->import_memfd(g_k1r_fd, 0, kDChunk);
	return g_k1r_id;
}
static bool k1r412_is_cover(uint32_t id) { return g_k1r_id != 0 && id == g_k1r_id; }
// The add pass: one wanted mapping; a cover is mapped READ-ONLY. (The map-over form, BC5_GUARD_K1R_REPLACE with
// AMDGPU_VA_OP_REPLACE, was removed on 2026-11-13: it ran once, run k1rg, and was never shown faster; README section 77.)
static bool k1r412_map(const DMap& w) {
	return k1r412_is_cover(w.id) ? g_dev->map_shared(w.id, w.bo_off, w.size, w.va, true) : g_dev->map_shared(w.id, w.bo_off, w.size, w.va);
}
// The mapping rebuild's hook: every part of a view of direct memory that no imported buffer covers is one or more
// read-only mappings of the zero buffer. Not with the zero skip or the pin cap (they put their own buffer there).
static void k1r412_want(const DState& S, const std::vector<DView>& views, std::vector<DMap>& want) {
	if (!k1r412::on() || S.kind != 0) return;
	static const bool refused = [] {
		const bool r = std::getenv("BC5_DIRECT_ZERO_SKIP") != nullptr || std::getenv("BC5_GUARD_PIN_CAP") != nullptr;
		journal("k1r (exp 0412, tag k1r412): BC5_GUARD_K1R on%s: never-written parts of the views of direct memory are GPU-mapped read-only onto one zero buffer; nothing is pinned for them\\n",
		        r ? ", but REFUSED because BC5_DIRECT_ZERO_SKIP or BC5_GUARD_PIN_CAP is set (they map their own buffer there)" : "");
		return r;
	}();
	if (refused) return;
	const uint32_t id = k1r412_bo();
	if (id == 0) {
		static bool said = false;
		if (!said) {
			said = true;
			journal("k1r (exp 0412, tag k1r412): no zero buffer: no cover\\n");
		}
		return;
	}
	static std::vector<k1r412::Bo>    bos;
	static std::vector<k1r412::Piece> pieces;
	bos.clear();
	for (const auto& b: S.bos) bos.push_back({b.off, b.size});
	uint64_t n = 0, bytes = 0;
	for (const auto& v: views) {
		pieces.clear();
		k1r412::cover(v.va, v.off, v.size, bos, kDChunk, pieces);
		for (const auto& p: pieces) {
			want.push_back({p.va, p.size, 0, id});
			n++;
			bytes += p.size;
		}
	}
	static uint64_t last_n = ~0ull, last_ns = 0, rebuilds = 0;
	rebuilds++;
	const uint64_t now = SoftCp::now_ns();
	if (n != last_n && now - last_ns >= 10'000'000'000ull) {
		last_n  = n;
		last_ns = now;
		uint64_t nonzero = 0;
		if (g_k1r_cpu != nullptr) {
			for (uint64_t i = 0; i < kDChunk; i += 8) nonzero += *reinterpret_cast<const uint64_t*>(g_k1r_cpu + i) != 0 ? 1u : 0u;
		}
		journal("k1r (exp 0412, tag k1r412): t %.0f s: %" PRIu64 " read-only zero pieces cover %.1f MiB of never-written memory under %zu views (rebuild %" PRIu64 "); the zero buffer holds %" PRIu64 " non-zero words%s\\n",
		        timing_now(), n, static_cast<double>(bytes) / 1048576.0, views.size(), rebuilds, nonzero, nonzero != 0 ? " <-- IT MUST BE ZERO" : "");
	}
}
// At a GPU fault: was it under the cover, and was it a write?
static void k1r412_fault(uint64_t fault, uint32_t status, bool under_view, bool chunk_imported) {
	if (!k1r412::on() || !under_view || chunk_imported) return;
	journal("k1r (exp 0412, tag k1r412): fault 0x%" PRIx64 " status 0x%08x under the read-only zero cover: %s\\n", fault, status,
	        k1r412::status_write(status) ? "a GPU WRITE (kind K1w): the job is lost; the cure is the import of this write target when the title binds it"
	                                     : "a READ although the cover serves reads: a defect (was the cover mapped at that moment?)");
}
'''


def md5(b):
    return hashlib.md5(b).hexdigest()


def once(s, old, new):
    assert s.count(old) == 1, ("an anchor does not occur exactly once", old[:70], s.count(old))
    return s.replace(old, new)


def unit(src, dst):
    s = open(src, "rb").read()
    inc = open(os.path.join(HERE, "k1r0412.inc"), "rb").read()
    assert b"\r" not in s and b"\r" not in inc and b"tag nl412" in s and b"tag k1r412" not in s, "refused: not the unit after mknl0412.py, or already edited"
    inc.decode("ascii")
    GLUE.decode("ascii")
    a = b"static void direct_sync_one(DState& S, bool force) {\n"
    s = once(s, a, inc + GLUE + a)
    a = b"\t\tguard0412_want(S, views, want); // exp 0412 (tag g412b): the zero buffer under the views of put-off chunks\n"
    s = once(s, a, a + b"\t\tk1r412_want(S, views, want);" + T)
    s = once(s, b"\t\t\t\tif (g_dev->map_shared(w.id, w.bo_off, w.size, w.va)) {\n",
             b"\t\t\t\tif (k1r412_map(w)) { // exp 0412 (tag k1r412): a cover is mapped READ-ONLY\n")
    # A rebuild that changes the set of buffers replaces covers by real mappings: an unmap and then a map, and no job
    # may run across it: the GPU is drained first.
    s = once(s, b"\tif (!retired.empty() || sig != S.views_sig || guard0412_cap_changed(S)) { // exp 0412 (tag g412b)\n",
             b"\tif (!retired.empty() || sig != S.views_sig || guard0412_cap_changed(S) || (k1r412::on() && S.kind == 0 && S.bos.size() != S.bos_mapped)) { // exp 0412 (tag g412b; k1r412: covers are about to be unmapped and replaced)\n")
    s = once(s, b"\t\tg_scratch.clear();\n\t\tg_scratch_id = 0;\n", b"\t\tg_scratch.clear();\n\t\tg_scratch_id = 0;\n\t\tg_k1r_id     = 0;" + T)
    a = b"\tjournal(\"would learn (exp 0412, tag mr412): t %.3f s: fault 0x%\" PRIx64"
    assert s.count(a) == 1
    s = s.replace(a, b"\tk1r412_fault(fault, status, under, imported);" + T + a)
    g = s.index(b"static void k1r412_want(")
    for need in (b"struct DMap {", b"struct DView {", b"static std::unique_ptr<bc5::direct::Device> g_dev;", b"static void journal(const char* fmt, ...) {", b"constexpr uint64_t kDChunk"):
        assert s.index(need) < g, ("must be defined before the glue", need[:40])
    assert g < s.index(b"\t\tk1r412_want(S, views, want);") and g < s.index(b"\tk1r412_fault(fault, status, under, imported);")
    open(dst, "wb").write(s)
    print(f"bc5LleAgc.cpp {md5(s)}")


def backend(src, dst):
    for rel, edits in (
        ("include/bc5/direct.hpp", [
            (b"    bool map_shared(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va);\n",
             b"    bool map_shared(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va);\n"
             b"    // exp 0412 (tag k1r412): readonly = the GPU may read these pages and not write them (AMDGPU_VM_PAGE_READABLE\n"
             b"    // alone): a GPU write is a page fault with the address (exp 0412 E1, case 4). For the read-only zero cover.\n"
             b"    bool map_shared(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va, bool readonly);\n"),
        ]),
        ("src/direct.cpp", [
            (b"bool Device::map_shared(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va) {\n"
             b"    std::lock_guard lock(impl_->mutex);\n",
             b"bool Device::map_shared(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va) {\n"
             b"    return map_shared(id, bo_offset, size, gpu_va, false); // exp 0412 (tag k1r412)\n"
             b"}\n\n"
             b"bool Device::map_shared(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va, bool readonly) {\n"
             b"    std::lock_guard lock(impl_->mutex);\n"),
            (b"    const int rc = impl_->va_map(b->bo, bo_offset, size, gpu_va,\n"
             b"                                 AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE | AMDGPU_VM_PAGE_EXECUTABLE);\n"
             b"    if (rc != 0) {\n"
             b"        std::fprintf(stderr, \"bc5-direct: shared map at 0x%llx+0x%llx: %d\\n\",\n",
             b"    const int rc = impl_->va_map(b->bo, bo_offset, size, gpu_va,\n"
             b"                                 readonly ? AMDGPU_VM_PAGE_READABLE // exp 0412 (tag k1r412)\n"
             b"                                          : AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE | AMDGPU_VM_PAGE_EXECUTABLE);\n"
             b"    if (rc != 0) {\n"
             b"        std::fprintf(stderr, \"bc5-direct: shared map at 0x%llx+0x%llx: %d\\n\",\n"),
        ]),
    ):
        s = open(os.path.join(src, rel), "rb").read()
        assert b"tag k1r412" not in s, "refused: already edited"
        crlf = b"\r\n" in s
        if crlf:
            s = s.replace(b"\r\n", b"\n")
        for old, new in edits:
            s = once(s, old, new)
        if crlf:
            s = s.replace(b"\n", b"\r\n")
        os.makedirs(os.path.dirname(os.path.join(dst, rel)), exist_ok=True)
        open(os.path.join(dst, rel), "wb").write(s)
        print(f"{rel} {md5(s)}")


def main():
    assert len(sys.argv) == 4 and sys.argv[1] in ("unit", "backend") and sys.argv[2] != sys.argv[3], __doc__
    (unit if sys.argv[1] == "unit" else backend)(sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()
