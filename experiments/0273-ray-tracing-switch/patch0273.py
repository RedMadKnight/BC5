#!/usr/bin/env python3
# BC5 experiment 0273: a "Ray tracing" switch in the emulator window (Emulation menu), default on.
#   1. Generic detection: a compute program whose code holds a gfx10 ray-intersection MIMG instruction
#      (IMAGE_BVH_INTERSECT_RAY, opcode 0xe6; IMAGE_BVH64_INTERSECT_RAY, 0xe7 — LLVM
#      llvm/lib/Target/AMDGPU/MIMGInstructions.td, the GFX10 column of `mimgopc`; encoding MIMGe_gfx10:
#      Inst{31-26} = 0x3c, Inst{24-18} = op{6-0}, Inst{0} = op{7}) is marked the first time it is dispatched.
#      F103's instruction, encoded 0xF1989F01, decodes that way: top bits 0x3c, op (0x66 | 0x80) = 0xe6.
#   2. A per-title build list, KYTY_BC5_RT_BUILD_PGM=<hex list> (the launcher sets it), of programs
#      dropped with ray tracing off: for the second title the BVH compaction 0x909974400 and the
#      "Ray Tracing Update" chain 0x909939400, 0x909936c00, 0x909939700, 0x909939900 (F332, F234).
#   3. The switch: Libs::Bc5Gc::Direct::SetRayTracing(bool) sets a pending value, taken at the next flip
#      (a frame boundary); the filter reads the active one per buffer. KYTY_BC5_RT=0 starts it off; the
#      input configuration's RayTracing.<TITLE_ID>=on|off (per title, as RenderScale.<TITLE_ID>, F101)
#      overrides the environment; the menu item saves the choice into that file.
#   With ray tracing off, dispatches of marked or listed programs are dropped exactly as
#   BC5_DIRECT_SKIP_PGM drops them (opt.drop_offsets). Draws are not touched. Nothing else changes.
# Four files of the shared tree (KytyPlus f266548 + patch 0001 as integrated on the box); every anchor
# must occur exactly the number of times given. The inputs are only read.
# usage: patch0273.py <src root of the shared tree> <out dir>   (writes <out dir>/<file> and <out dir>/patch_0273.diff)
import difflib, os, sys

EDITS = {
    'src/libs/bc5LleAgc.cpp': [
        # 1. The switch's state and its three functions, at file scope in Libs::Bc5Gc::Direct, before the filter.
        ('''static void submit(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header);
''', 1, '''static void submit(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header);
// Experiment 0273: the window's Emulation > Ray tracing switch. The pending value is taken at the next
// flip (a frame boundary, ApplyPendingRayTracing in the VideoOut path); the filter reads the active one
// per buffer. KYTY_BC5_RT=0 starts it off; the input configuration's RayTracing.<TITLE_ID>=on|off
// overrides that at load (hostInput.cpp). With it off, dispatches of programs that carry a gfx10
// IMAGE_BVH(64)_INTERSECT_RAY and of the per-title build list (KYTY_BC5_RT_BUILD_PGM) are dropped as
// BC5_DIRECT_SKIP_PGM drops them.
static std::atomic<bool>     g_rt_on {[] { const char* e = std::getenv("KYTY_BC5_RT"); return !(e != nullptr && e[0] == '0' && e[1] == 0); }()};
static std::atomic<int>      g_rt_pending {-1};
static std::atomic<uint64_t> g_rt_dropped {0};
void SetRayTracing(bool on) {
	g_rt_pending.store(on ? 1 : 0, std::memory_order_relaxed);
}
bool GetRayTracing() {
	const int p = g_rt_pending.load(std::memory_order_relaxed);
	return p < 0 ? g_rt_on.load(std::memory_order_relaxed) : p != 0;
}
void ApplyPendingRayTracing() {
	const int p = g_rt_pending.exchange(-1, std::memory_order_relaxed);
	if (p < 0) return;
	const bool on = p != 0;
	if (g_rt_on.exchange(on, std::memory_order_relaxed) != on) {
		std::fprintf(stderr, "bc5-direct: ray tracing %s at the flip (%" PRIu64 " dispatches dropped so far)\\n", on ? "on" : "off", g_rt_dropped.load());
	}
}
'''),
        # 2. The drop, right after the BC5_DIRECT_SKIP_PGM block of the filter.
        ('''				static const std::set<uint64_t> any_skip = pgm_list("BC5_DIRECT_SKIP_PGM");
				if (!any_skip.empty() && type == 3 && (op == 0x15 || op == 0x16) && any_skip.count(pgm) != 0) {
					static std::atomic<uint64_t> n_skipped {0};
					if ((n_skipped++ & 0xfffu) == 0) journal("  skip pgm 0x%" PRIx64 ": %s dispatch op %02x at %u dropped (%" PRIu64 " so far)\\n", pgm, kind, op, q, n_skipped.load());
					opt.drop_offsets.push_back(q);
					q += len;
					continue;
				}
			}
''', 1, '''				static const std::set<uint64_t> any_skip = pgm_list("BC5_DIRECT_SKIP_PGM");
				if (!any_skip.empty() && type == 3 && (op == 0x15 || op == 0x16) && any_skip.count(pgm) != 0) {
					static std::atomic<uint64_t> n_skipped {0};
					if ((n_skipped++ & 0xfffu) == 0) journal("  skip pgm 0x%" PRIx64 ": %s dispatch op %02x at %u dropped (%" PRIu64 " so far)\\n", pgm, kind, op, q, n_skipped.load());
					opt.drop_offsets.push_back(q);
					q += len;
					continue;
				}
			}
			// Experiment 0273: with the window's ray-tracing switch off, a dispatch of a program that
			// carries a gfx10 IMAGE_BVH_INTERSECT_RAY / IMAGE_BVH64_INTERSECT_RAY (MIMG opcodes 0xe6 /
			// 0xe7: LLVM MIMGInstructions.td, GFX10 column; encoding MIMGe_gfx10: Inst{31-26} 0x3c,
			// Inst{24-18} op{6-0}, Inst{0} op{7}) or of the title's BVH build list
			// (KYTY_BC5_RT_BUILD_PGM) is dropped. A program is scanned once, up to its s_code_end or
			// an s_endpgm followed by four zero dwords, within the 64 KiB that is mapped; a literal in
			// the code that happens to look like the instruction marks a program wrongly (accepted:
			// the mark only drops its dispatches while ray tracing is off, and the journal names it).
			{
				static const std::set<uint64_t> rt_build = pgm_list("KYTY_BC5_RT_BUILD_PGM");
				if (!g_rt_on.load(std::memory_order_relaxed) && type == 3 && (op == 0x15 || op == 0x16) && pgm != 0) {
					static const auto rt_program = [](uint64_t p, const std::vector<bc5::direct::Mapping>& maps) -> bool {
						static std::mutex                m;
						static std::map<uint64_t, bool>  known;
						{
							std::lock_guard<std::mutex> lk(m);
							if (auto it = known.find(p); it != known.end()) return it->second;
						}
						uint32_t n = 0x10000 / 4; // as far as the 64 KiB window is mapped (shader_dump's window)
						while (n >= 0x400 && !covered_sorted(maps, p, static_cast<uint64_t>(n) * 4)) n -= 0x400;
						bool     hit = false;
						uint32_t which = 0;
						if (n >= 0x400) {
							const auto* w = reinterpret_cast<const volatile uint32_t*>(p);
							for (uint32_t k = 0; k < n; k++) {
								const uint32_t d = w[k];
								if (d == 0xbf9f0000u) break; // s_code_end
								if (d == 0xbf810000u && k + 4 < n && w[k + 1] == 0 && w[k + 2] == 0 && w[k + 3] == 0 && w[k + 4] == 0) break; // s_endpgm + padding
								if ((d & 0xfc000000u) != 0xf0000000u) continue;
								const uint32_t o = ((d >> 18u) & 0x7fu) | ((d & 1u) << 7u);
								if (o == 0xe6u || o == 0xe7u) {
									hit   = true;
									which = o;
									break;
								}
							}
						}
						std::lock_guard<std::mutex> lk(m);
						known.emplace(p, hit);
						journal("  ray tracing: program 0x%" PRIx64 " %s (%u dwords scanned)\\n", p, hit ? (which == 0xe6u ? "uses image_bvh_intersect_ray" : "uses image_bvh64_intersect_ray") : "has no ray-intersection instruction", n);
						return hit;
					};
					const bool build = rt_build.count(pgm) != 0;
					if (build || rt_program(pgm, *maps_p)) {
						const uint64_t n_rt = g_rt_dropped.fetch_add(1);
						if ((n_rt & 0xfffu) == 0) journal("  ray tracing off: %s dispatch op %02x at %u of 0x%" PRIx64 " dropped (%s; %" PRIu64 " so far)\\n", kind, op, q, pgm, build ? "build list" : "ray-intersection program", n_rt + 1);
						opt.drop_offsets.push_back(q);
						q += len;
						continue;
					}
				}
			}
'''),
        # 3. The frame boundary: the pending value is taken just before the flip is submitted.
        ('''	const double flip_t0 = Bc5Gc::Direct::timing_now();
	const int rc = VideoOut::VideoOutSubmitFlip(handle, index, flip_mode, flip_arg);
''', 1, '''	Bc5Gc::Direct::ApplyPendingRayTracing(); // experiment 0273: the switch takes effect at a frame boundary
	const double flip_t0 = Bc5Gc::Direct::timing_now();
	const int rc = VideoOut::VideoOutSubmitFlip(handle, index, flip_mode, flip_arg);
'''),
    ],
    'src/graphics/presentation/hostMenu.cpp': [
        # 4. The switch's functions, declared before the file's namespace (hostMenu.cpp has no such block yet).
        ('''#include <vector>

namespace Libs::Graphics {

namespace {

constexpr int EXIT_CODE_RESTART = 75; // experiment 0047: the launcher starts the same game again
''', 1, '''#include <vector>

#include "graphics/presentation/window/hostInput.h" // experiment 0273: the switch is saved with the input configuration

namespace Libs::Bc5Gc::Direct {
void SetRayTracing(bool on); // bc5LleAgc.cpp, experiment 0273: the Emulation menu's switch
bool GetRayTracing();
} // namespace Libs::Bc5Gc::Direct

namespace Libs::Graphics {

namespace {

constexpr int EXIT_CODE_RESTART = 75; // experiment 0047: the launcher starts the same game again
'''),
        # 5. Emulation > Ray tracing, after the logging item.
        ('''				Log::Bc5SetLogging(!logging);
				std::fprintf(stderr, "host menu: logging %s\\n", logging ? "off" : "on");
			}
''', 1, '''				Log::Bc5SetLogging(!logging);
				std::fprintf(stderr, "host menu: logging %s\\n", logging ? "off" : "on");
			}
			// Experiment 0273: the ray-tracing switch (default on; KYTY_BC5_RT=0 or the title's
			// RayTracing.<TITLE_ID>=off starts it off). It takes effect at the next flip and is saved per
			// title into the input configuration, as the Video tab saves RenderScale.<TITLE_ID>.
			{
				bool rt = Libs::Bc5Gc::Direct::GetRayTracing();
				if (ImGui::MenuItem("Ray tracing", nullptr, rt, !launcher)) {
					rt = !rt;
					Libs::Bc5Gc::Direct::SetRayTracing(rt);
					const std::string        key   = "RayTracing." + HostInputTitleId();
					std::vector<std::string> lines = HostInputStatements();
					lines.erase(std::remove_if(lines.begin(), lines.end(),
					                           [&](const std::string& l) { return l.size() > key.size() && l.compare(0, key.size(), key) == 0 && l[key.size()] == '='; }),
					            lines.end());
					lines.insert(lines.begin(), key + (rt ? "=on" : "=off"));
					const std::string path = HostInputConfigPath();
					std::string       error;
					if (path.empty() || !HostInputSave(path, lines, &error)) {
						std::fprintf(stderr, "host menu: ray tracing %s (not saved: %s)\\n", rt ? "on" : "off", path.empty() ? "no input configuration file" : error.c_str());
					} else {
						std::fprintf(stderr, "host menu: ray tracing %s (saved to %s)\\n", rt ? "on" : "off", path.c_str());
					}
				}
			}
'''),
    ],
    'src/graphics/presentation/window/hostInput.cpp': [
        # 6. The declaration, next to the timestamp scale's.
        ('''bool   GetMainPass(uint32_t* w, uint32_t* h);
} // namespace Libs::Bc5Gc::Direct
''', 1, '''bool   GetMainPass(uint32_t* w, uint32_t* h);
void   SetRayTracing(bool on); // bc5LleAgc.cpp, experiment 0273
} // namespace Libs::Bc5Gc::Direct
'''),
        # 7. The statement RayTracing.<TITLE_ID>=on|off, parsed like RenderScale.<TITLE_ID>.
        ('''		if (EqualNoCase(left, "DefaultKeys")) {
''', 1, '''		if (left.size() > 11 && EqualNoCase(left.substr(0, 11), "RayTracing.")) { // experiment 0273, per title
			int v = -1;
			if (EqualNoCase(right, "on") || EqualNoCase(right, "true") || right == "1") {
				v = 1;
			} else if (EqualNoCase(right, "off") || EqualNoCase(right, "false") || right == "0") {
				v = 0;
			} else {
				return Fail(error, where + ": RayTracing takes on or off, got: " + std::string(right));
			}
			const std::string id(left.substr(11));
			if (EqualNoCase(id, HostInputTitleId())) {
				m_ray_tracing = v;
			} else {
				m_other_title_scales.emplace_back("RayTracing." + id + (v == 1 ? "=on" : "=off")); // another title's line, kept
			}
			return true;
		}

		if (EqualNoCase(left, "DefaultKeys")) {
'''),
        # 8. Written back with the other statements.
        ('''		for (const auto& other: m_other_title_scales) out.push_back(other);
''', 1, '''		for (const auto& other: m_other_title_scales) out.push_back(other);
		if (m_ray_tracing >= 0) out.emplace_back("RayTracing." + HostInputTitleId() + (m_ray_tracing == 1 ? "=on" : "=off")); // experiment 0273
'''),
        # 9. The accessor and the member.
        ('''	[[nodiscard]] double RenderScale() const { return m_render_scale; }
''', 1, '''	[[nodiscard]] double RenderScale() const { return m_render_scale; }
	[[nodiscard]] int    RayTracing() const { return m_ray_tracing; } // experiment 0273: -1 not set, 0 off, 1 on
'''),
        ('''	double               m_render_scale     = 0.0; // 0: not set (timestamps untouched)
''', 1, '''	double               m_render_scale     = 0.0; // 0: not set (timestamps untouched)
	int                  m_ray_tracing      = -1;  // experiment 0273: -1 not set (the environment decides), 0 off, 1 on
'''),
        # 10. Applied where the render scale is applied: at the first load and on Apply from the overlay.
        ('''	if (map->RenderScale() > 0.0) Libs::Bc5Gc::Direct::SetTimestampScale(map->RenderScale());
''', 2, '''	if (map->RenderScale() > 0.0) Libs::Bc5Gc::Direct::SetTimestampScale(map->RenderScale());
	if (map->RayTracing() >= 0) Libs::Bc5Gc::Direct::SetRayTracing(map->RayTracing() == 1); // experiment 0273
'''),
    ],
}


def main():
    if len(sys.argv) != 3:
        print(__doc__ or 'usage: patch0273.py <src root> <out dir>')
        sys.exit(2)
    root, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    diff = []
    for rel, edits in EDITS.items():
        path = os.path.join(root, rel)
        src = open(path, encoding='utf-8').read()
        dst = src
        for old, n, new in edits:
            c = dst.count(old)
            if c != n:
                print(f'{rel}: anchor found {c} times, expected {n}:\n{old}')
                sys.exit(1)
            dst = dst.replace(old, new)
        target = os.path.join(out, os.path.basename(rel))
        open(target, 'w', encoding='utf-8', newline='\n').write(dst)
        diff += difflib.unified_diff(src.splitlines(True), dst.splitlines(True), 'a/' + rel, 'b/' + rel)
        print(f'{rel}: {len(edits)} edits -> {target}')
    open(os.path.join(out, 'patch_0273.diff'), 'w', encoding='utf-8', newline='\n').write(''.join(diff))
    print(f'patch_0273.diff: {sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))} added lines')


if __name__ == '__main__':
    main()
