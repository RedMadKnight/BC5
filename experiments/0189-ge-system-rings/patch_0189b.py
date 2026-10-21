import sys
# BC5 experiment 0189, second step: the title's own libSceAgcDriver hands /dev/gc its tessellation-factor ring
# (ioctl 0x80108128: u64 base, u32 size, u32 0) and one more dword right after it (ioctl 0x8004812a, 0x1ff in the
# second title) before its first submission (run R0, BC5_GC_IOCTL_TRACE=1). The host answered both as unhandled.
# Now they are recorded (no other change), and two behaviour switches, off by default, use them in the prefix:
#   BC5_DIRECT_GC_TF_RING=1     VGT_TF_RING_SIZE / VGT_TF_MEMORY_BASE(_HI) from 0x80108128
#   BC5_DIRECT_GC_HS_OFFCHIP=1  VGT_HS_OFFCHIP_PARAM from 0x8004812a (TODO(verify): that it is this register's value)
root = sys.argv[1]


def patch(path, pairs):
    b = open(path, "rb").read()
    for old, new in pairs:
        done = False
        for nl in (b"\n", b"\r\n"):
            o = old.replace(b"\n", nl); n = new.replace(b"\n", nl)
            if b.count(n) == 1 and b.count(o) == 0:
                print("already:", old[:60]); done = True; break
            if b.count(o) == 1:
                b = b.replace(o, n); print("ok:", old[:60]); done = True; break
        assert done, ("not found", old[:80])
    open(path, "wb").write(b)


lle = root + "/src/libs/bc5LleAgc.cpp"
patch(lle, [
(b"""// For the HLE GraphicsDriverGetTFRing (agc.cpp): the host's default ring, 0 when BC5_DIRECT_TF_DEFAULT is off.
""", b"""// Experiment 0189: what the title's own libSceAgcDriver (LLE) sends /dev/gc for the rings the console's kernel
// programs (BC5_GC_IOCTL_TRACE=1, run R0 of the second title, once each before its first submission):
//   0x80108128 (16 bytes in): u64 base, u32 size, u32 0 = its tessellation-factor ring (0x1120000000, 0x3fff8),
//                             the arguments of sceAgcDriverSetTFRing by their shape;
//   0x8004812a (4 bytes in):  one dword, 0x1ff, sent right after it: by its place the HS offchip parameter
//                             (sceAgcDriverSetHsOffchipParam). TODO(verify): which register value it is.
// Before, both were answered as unhandled (nothing written back, nothing programmed). They are recorded here;
// Direct::tf_ring_prefix uses them only with BC5_DIRECT_GC_TF_RING=1 / BC5_DIRECT_GC_HS_OFFCHIP=1.
static std::atomic<uint64_t> g_gc_tf_base {0};
static std::atomic<uint32_t> g_gc_tf_size {0};
static std::atomic<uint64_t> g_gc_hs_offchip {0}; // bit 32 = received
static bool gc_tf_ring_on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_DIRECT_GC_TF_RING");
		return e != nullptr && *e != 0 && std::strcmp(e, "0") != 0;
	}();
	return v;
}
static bool gc_hs_offchip_on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_DIRECT_GC_HS_OFFCHIP");
		return e != nullptr && *e != 0 && std::strcmp(e, "0") != 0;
	}();
	return v;
}
// For the HLE GraphicsDriverGetTFRing (agc.cpp): the host's default ring, 0 when BC5_DIRECT_TF_DEFAULT is off.
"""),
(b"""		case 0xc00c8110: { // set gs ring sizes
""", b"""		case 0x80108128: { // experiment 0189: the title's tessellation-factor ring {u64 base, u32 size, u32 0}
			const auto* a = static_cast<const uint32_t*>(argp);
			g_gc_tf_base  = static_cast<uint64_t>(a[0]) | (static_cast<uint64_t>(a[1]) << 32u);
			g_gc_tf_size  = a[2];
			std::fprintf(stderr, "bc5-direct: /dev/gc TF ring 0x%" PRIx64 " size 0x%x%s\\n", g_gc_tf_base.load(), a[2], gc_tf_ring_on() ? " (programmed, BC5_DIRECT_GC_TF_RING=1)" : "");
			return 0;
		}
		case 0x8004812a: { // experiment 0189: one dword after the TF ring, by its place the HS offchip parameter
			const uint32_t v  = *static_cast<const uint32_t*>(argp);
			g_gc_hs_offchip   = 0x100000000ull | v;
			std::fprintf(stderr, "bc5-direct: /dev/gc HS offchip 0x%x%s\\n", v, gc_hs_offchip_on() ? " (programmed, BC5_DIRECT_GC_HS_OFFCHIP=1)" : "");
			return 0;
		}
		case 0xc00c8110: { // set gs ring sizes
"""),
(b"""	bool       write_off    = true;
	bool       host_default = false;
	if ((base == 0 || size == 0) && tf_default_on()) { // experiment 0189
""", b"""	bool       write_off    = true;
	bool       host_default = false, gc_ring = false;
	if ((base == 0 || size == 0) && gc_tf_ring_on()) { // experiment 0189: the ring the title's driver sent /dev/gc
		const uint64_t       b = g_gc_tf_base.load();
		const uint32_t       s = g_gc_tf_size.load();
		static std::atomic<bool> told {false};
		const auto           pm = b != 0 && s != 0 && g_dev ? g_dev->sorted_mappings() : nullptr;
		if (pm != nullptr && covered_sorted(*pm, b, s)) {
			base      = b;
			size      = s;
			gc_ring   = true;
			write_off = false;
		} else if (!told.exchange(true)) {
			journal("tf ring (exp 0189): /dev/gc ring 0x%" PRIx64 " size 0x%x not mapped (yet), not programmed\\n", b, s);
		}
	}
	if (gc_hs_offchip_on() && (g_gc_hs_offchip.load() >> 32u) != 0 && (gc_ring || base == 0 || size == 0)) {
		off_v     = static_cast<uint32_t>(g_gc_hs_offchip.load());
		write_off = true;
	}
	if ((base == 0 || size == 0) && tf_default_on()) { // experiment 0189
"""),
(b"""			write_off    = hs_offchip_force(&off_v);
""", b"""			if (!(gc_hs_offchip_on() && (g_gc_hs_offchip.load() >> 32u) != 0)) write_off = hs_offchip_force(&off_v);
"""),
(b"""	if (base == 0 || size == 0) return;
	static std::atomic<uint64_t> n {0};
	if ((n++ & 0xffffu) == 0) journal("tf ring: base 0x%" PRIx64 " size 0x%x offchip 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 " -> VGT_HS_OFFCHIP_PARAM %s0x%x%s (%" PRIu64 " prefixes)\\n", base, size, o0, o1, o2, write_off ? "" : "untouched, not ", off_v, host_default ? ", host default ring" : "", n.load());
""", b"""	if (base == 0 || size == 0) {
		// Experiment 0189: BC5_DIRECT_GC_HS_OFFCHIP=1 without a ring to program: the parameter alone.
		if (write_off && gc_hs_offchip_on() && (g_gc_hs_offchip.load() >> 32u) != 0) p.insert(p.end(), {0xC0017900u, 0x24fu, off_v});
		return;
	}
	static std::atomic<uint64_t> n {0};
	if ((n++ & 0xffffu) == 0) journal("tf ring: base 0x%" PRIx64 " size 0x%x offchip 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 " -> VGT_HS_OFFCHIP_PARAM %s0x%x%s (%" PRIu64 " prefixes)\\n", base, size, o0, o1, o2, write_off ? "" : "untouched, not ", off_v, host_default ? ", host default ring" : gc_ring ? ", the title's /dev/gc ring" : "", n.load());
"""),
(b"""	if (host_default) {
		static std::atomic<bool> flushed {false};
""", b"""	if (host_default || gc_ring) {
		static std::atomic<bool> flushed {false};
"""),
])
print("done")
