#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
namespace bc5 { inline bool env_on(const char* e) { return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0); } }
#ifdef BC5_LEAN
#define BC5_DIAG_ENV(w) static_cast<const char*>(nullptr)
#else
#define BC5_DIAG_ENV(w) std::getenv(w)
#endif
// Exp 0421 (tag fs421e), BC5_DIRECT_FS_EAGER (default ON; "0" is build W's way, the heap imported by data): the
// title's heap "FileSystem" is imported whole when its view appears, as the heaps of BC5_DIRECT_EAGER_NAMES are. The
// title keeps GPU-written buffers there (F443, F468, F472) and the GPU read its CPU-written chunks (fault record
// 20261114-184017); on the console every page of it is the GPU's from the map call. Eager makes one import of the
// view instead of one per freshly written 2 MiB chunk during the loads.
static bool fs421_eager_on() {
	static const bool on = [] {
		const char* e = std::getenv("BC5_DIRECT_FS_EAGER");
		const bool  v = !(e != nullptr && e[0] == '0' && e[1] == 0);
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0421 (tag fs421e): \"FileSystem\" %s\n",
		             v ? "is eager (imported whole when its view appears); BC5_DIRECT_FS_EAGER=0 gives build W's way"
		               : "is imported by data (BC5_DIRECT_FS_EAGER=0, build W's way)");
#endif
		return v;
	}();
	return on;
}
static bool direct_lazy_name(const char* name) {
	static const std::vector<std::string> names = [] {
		std::vector<std::string> v;
		if (const char* e = std::getenv("BC5_DIRECT_LAZY_NAMES"); e != nullptr) {
			std::string cur;
			for (const char* c = e;; c++) {
				if (*c == ',' || *c == 0) {
					if (!cur.empty()) v.push_back(cur);
					cur.clear();
					if (*c == 0) break;
				} else {
					cur.push_back(*c);
				}
			}
		}
		// exp 0419 (build V) for exp 0412: "FileSystem" is never lazy (fault record 20261114-184017: a shader read two
		// of its written pages, which a lazy heap does not import). BC5_DIAG_LAZY_FILESYSTEM=1 keeps the old list.
		if (!bc5::env_on(BC5_DIAG_ENV("BC5_DIAG_LAZY_FILESYSTEM"))) {
			const auto it = std::find(v.begin(), v.end(), std::string("FileSystem"));
			if (it != v.end()) {
				v.erase(it);
				std::fprintf(stderr, "[bc5] exp 0419: FileSystem taken out of BC5_DIRECT_LAZY_NAMES (fault record 20261114-184017); "
				                     "BC5_DIAG_LAZY_FILESYSTEM=1 keeps the old list\n");
			}
		}
		return v;
	}();
	static const bool by_data = [] { // exp 0412 (tag kl412): BC5_GUARD_LAZY_BY_DATA=1, no view is lazy
		const char* e = BC5_DIAG_ENV("BC5_GUARD_LAZY_BY_DATA");
		const bool  v = e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
		if (v) std::fprintf(stderr, "[bc5] exp 0412 (tag kl412): BC5_GUARD_LAZY_BY_DATA on: BC5_DIRECT_LAZY_NAMES is ignored, every view of direct memory is imported where it holds data\n");
		return v;
	}();
	if (by_data) return false;
	if (name == nullptr || names.empty()) return false;
	return std::find(names.begin(), names.end(), name) != names.end();
}

// Experiment 0412 (tag bd412): bd0412.inc, BC5_GUARD_BYDATA_NAMES, option B's rule per heap.
namespace bd412 {
inline std::vector<std::string> parse(const char* e) {
	std::vector<std::string> v;
	if (e == nullptr) return v;
	std::string cur;
	for (const char* c = e;; c++) {
		if (*c == ',' || *c == 0) {
			if (!cur.empty() && std::find(v.begin(), v.end(), cur) == v.end()) v.push_back(cur);
			cur.clear();
			if (*c == 0) break;
		} else {
			cur.push_back(*c);
		}
	}
	return v;
}
inline bool has(const std::vector<std::string>& names, const char* name) {
	return name != nullptr && std::find(names.begin(), names.end(), name) != names.end();
}
} // namespace bd412
static const std::vector<std::string>& bd412_names() {
	static const std::vector<std::string> v = [] {
		auto n = bd412::parse(BC5_DIAG_ENV("BC5_GUARD_BYDATA_NAMES"));
		for (const auto& s: n) std::fprintf(stderr, "[bc5] exp 0412 (tag bd412): BC5_GUARD_BYDATA_NAMES: the heap \"%s\" is imported by data, not whole\n", s.c_str());
		return n;
	}();
	return v;
}
static bool bd412_name(const char* name) {
	const auto& n = bd412_names();
	return !n.empty() && bd412::has(n, name);
}
// BC5_DIRECT_EAGER_NAMES=name[,name...]: views with these names are imported in full as soon as
// they exist, data or not. The game's GPU heaps hold render targets and GPU-written textures no
// CPU ever touches; the first draw into one faulted, and a fault is a 14 s freeze (2 s fence
// timeout, 12 s for the kernel's reset; run 103: opening the pause menu). 17 of the 18 regions learned
// from faults so far lie in those two heaps.
static bool direct_eager_name(const char* name) {
	static const std::vector<std::string> names = [] {
		std::vector<std::string> v;
		if (const char* e = std::getenv("BC5_DIRECT_EAGER_NAMES"); e != nullptr) {
			std::string cur;
			for (const char* c = e;; c++) {
				if (*c == ',' || *c == 0) {
					if (!cur.empty()) v.push_back(cur);
					cur.clear();
					if (*c == 0) break;
				} else {
					cur.push_back(*c);
				}
			}
		}
		if (fs421_eager_on() && std::find(v.begin(), v.end(), std::string("FileSystem")) == v.end()) v.push_back("FileSystem"); // exp 0421 (tag fs421e)
		return v;
	}();
	if (bd412_name(name)) return false; // exp 0412 (tag bd412): this heap is imported by data
	if (name == nullptr || names.empty()) return false;
	return std::find(names.begin(), names.end(), name) != names.end();
}

// Experiment 0415 (ls415d), KYTY_BC5_NAMES_FAST (default off; "verify" asks the old function too): the lazy and eager
// class of a range's name remembered per name. Both lists are read once from the environment, so a name's class never
// changes. Used only from direct_views_build, which runs under direct_views' mutex. If this were wrong, a heap would
// be imported eagerly or lazily against its list: memory pinned that should not be, or a GPU fault on a heap that
// should have been imported whole.
int main() {
	std::printf("eager(FileSystem)=%d lazy(FileSystem)=%d eager(Other)=%d\n", direct_eager_name("FileSystem"), direct_lazy_name("FileSystem"), direct_eager_name("Other"));
	return 0;
}
