#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tag a2): the backend's sorted mapping list as a chunked, immutable, incrementally edited index.
Usage: mka2be.py BACKEND_DIR OUT_DIR
  BACKEND_DIR: main's backend (src/direct.cpp eacf8d2a..., include/bc5/direct.hpp 9256f3b9..., the exp 0436 bake
  sources of the shared archive d6638808). Writes OUT_DIR/src/direct.cpp, OUT_DIR/include/bc5/direct.hpp and copies
  mapping_index.hpp (beside this script) to OUT_DIR/include/bc5/.
- Device::sorted_mappings() returns std::shared_ptr<const MappingIndex> (both arms: one type for the host).
- BC5_DIRECT_0438_A2 (off unless "1", read once): ON, the index is kept up to date at the four edits of the lists
  (map_userptr, unmap_userptr, map_shared, unmap_shared) by index_insert / index_erase, and sorted_mappings() only
  hands it out; free_shared (many maps of one BO at once) drops it and the next call rebuilds. OFF: today's full
  rebuild per list_gen, wrapped as one chunk.
- BC5_DIRECT_0438_A2_CHECK=1 (with A2 on; records only, never a repair): every 64th sorted_mappings() call also builds
  today's list and compares it with the index element by element; a mismatch prints one stderr line (the first 20).
Every replacement must match exactly once.
"""
import hashlib
import os
import shutil
import sys

BE, OUT = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
cpp_p, hpp_p = os.path.join(BE, 'src', 'direct.cpp'), os.path.join(BE, 'include', 'bc5', 'direct.hpp')
cpp, hpp = open(cpp_p, 'rb').read(), open(hpp_p, 'rb').read()
assert hashlib.md5(cpp).hexdigest().startswith('eacf8d2a'), 'direct.cpp is not eacf8d2a'
assert hashlib.md5(hpp).hexdigest().startswith('9256f3b9'), 'direct.hpp is not 9256f3b9'
cpp, hpp = cpp.decode('utf-8'), hpp.decode('utf-8')
assert '\r' not in cpp and '\r' not in hpp


def rep(s, old, new):
    n = s.count(old)
    assert n == 1, (n, old[:90])
    return s.replace(old, new)


# --- direct.hpp
hpp = rep(hpp, '''    bool shared = false;   // a mapping of an imported memfd range (map_shared), not a userptr BO
};
''', '''    bool shared = false;   // a mapping of an imported memfd range (map_shared), not a userptr BO
};
} // namespace bc5::direct
#include "bc5/mapping_index.hpp" // exp 0438 (tag a2): needs Mapping complete
namespace bc5::direct {
''')
hpp = rep(hpp, '''    std::shared_ptr<const std::vector<Mapping>> sorted_mappings() const;''',
          '''    // Experiment 0438 (tag a2): an immutable chunked index (mapping_index.hpp), read like a const vector.
    std::shared_ptr<const MappingIndex> sorted_mappings() const;''')

# --- direct.cpp
cpp = rep(cpp, '''    std::shared_ptr<const std::vector<Mapping>> sorted;
    std::uint64_t sorted_gen = ~0ull;''', '''    std::shared_ptr<const MappingIndex> sorted;
    std::uint64_t sorted_gen = ~0ull;
    // exp 0438 (tag a2): BC5_DIRECT_0438_A2=1 keeps `sorted` up to date at each edit of the lists (no rebuild);
    // BC5_DIRECT_0438_A2_CHECK=1 compares it with a full rebuild every 64th call (records only)
    const bool a2 = [] { const char *e = std::getenv("BC5_DIRECT_0438_A2"); return e != nullptr && e[0] == '1' && e[1] == 0; }();
    const bool a2_check = [] { const char *e = std::getenv("BC5_DIRECT_0438_A2_CHECK"); return e != nullptr && e[0] == '1' && e[1] == 0; }();
    std::uint64_t a2_calls = 0, a2_mismatches = 0;
    void a2_insert(const Mapping &m) { if (a2 && sorted) sorted = index_insert(sorted, m); }
    void a2_erase(const Mapping &m) { if (a2 && sorted) sorted = index_erase(sorted, m); }''')
cpp = rep(cpp, '''std::shared_ptr<const std::vector<Mapping>> Device::sorted_mappings() const {
    std::lock_guard lock(impl_->mutex);
    if (impl_->sorted == nullptr || impl_->sorted_gen != impl_->list_gen) {''', '''std::shared_ptr<const MappingIndex> Device::sorted_mappings() const {
    std::lock_guard lock(impl_->mutex);
    if (impl_->a2 && impl_->sorted != nullptr) { // exp 0438 (tag a2): kept up to date at each edit
        if (impl_->a2_check && (impl_->a2_calls++ & 63u) == 0) {
            std::vector<Mapping> users;
            for (const auto &u : impl_->userptrs) users.push_back({u.va, u.size, u.readonly, false});
            std::sort(users.begin(), users.end(), [](const Mapping &x, const Mapping &y) { return x.va < y.va; });
            std::vector<Mapping> ref;
            auto u = users.begin();
            for (const auto &m : impl_->shared_maps) {
                while (u != users.end() && u->va < m.va) ref.push_back(*u++);
                ref.push_back({m.va, m.size, m.readonly, true});
            }
            ref.insert(ref.end(), u, users.end());
            bool same = ref.size() == impl_->sorted->size();
            std::size_t at = 0;
            for (const auto &m : *impl_->sorted) {
                if (!same) break;
                const Mapping &r = ref[at];
                if (r.va != m.va || r.size != m.size || r.readonly != m.readonly || r.shared != m.shared) same = false;
                else at++;
            }
            if (!same && impl_->a2_mismatches++ < 20)
                std::fprintf(stderr, "bc5-direct: exp 0438 (tag a2): MISMATCH of the index against a rebuild at element %zu (index %zu, rebuild %zu entries; %llu so far)\\n", at,
                             impl_->sorted->size(), ref.size(), static_cast<unsigned long long>(impl_->a2_mismatches));
        }
        return impl_->sorted;
    }
    if (impl_->sorted == nullptr || impl_->sorted_gen != impl_->list_gen) {''')
cpp = rep(cpp, '''        out->insert(out->end(), u, users.end());
        impl_->sorted = std::move(out);
        impl_->sorted_gen = impl_->list_gen;''', '''        out->insert(out->end(), u, users.end());
        impl_->sorted = std::make_shared<const MappingIndex>(std::move(*out)); // exp 0438 (tag a2): one chunk
        impl_->sorted_gen = impl_->list_gen;''')
cpp = rep(cpp, '''    impl_->userptrs.push_back(u);
    impl_->list_gen++;
    return true;''', '''    impl_->userptrs.push_back(u);
    impl_->a2_insert({u.va, u.size, u.readonly, false}); // exp 0438 (tag a2)
    impl_->list_gen++;
    return true;''')
cpp = rep(cpp, '''            amdgpu_bo_free(it->bo);
            impl_->userptrs.erase(it);''', '''            amdgpu_bo_free(it->bo);
            impl_->a2_erase({it->va, it->size, it->readonly, false}); // exp 0438 (tag a2)
            impl_->userptrs.erase(it);''')
cpp = rep(cpp, '''    impl_->shared_maps.insert(at, SharedMap{gpu_va, size, bo_offset, id, b->bo, readonly});''',
          '''    impl_->shared_maps.insert(at, SharedMap{gpu_va, size, bo_offset, id, b->bo, readonly});
    impl_->a2_insert({gpu_va, size, readonly, true}); // exp 0438 (tag a2)''')
cpp = rep(cpp, '''    if (SharedBo *b = impl_->shared_bo_locked(it->id); b != nullptr && b->maps != 0) b->maps--;
    impl_->shared_maps.erase(it);''', '''    if (SharedBo *b = impl_->shared_bo_locked(it->id); b != nullptr && b->maps != 0) b->maps--;
    impl_->a2_erase({it->va, it->size, it->readonly, true}); // exp 0438 (tag a2)
    impl_->shared_maps.erase(it);''')
cpp = rep(cpp, '''        impl_->shared_maps.resize(w);
        b->maps = 0;''', '''        impl_->shared_maps.resize(w);
        impl_->sorted = nullptr; // exp 0438 (tag a2): many maps went at once; the next call rebuilds
        b->maps = 0;''')
assert 'cstdlib' in cpp or 'std::getenv' in cpp
os.makedirs(os.path.join(OUT, 'src'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'include', 'bc5'), exist_ok=True)
for p, s in ((os.path.join(OUT, 'src', 'direct.cpp'), cpp), (os.path.join(OUT, 'include', 'bc5', 'direct.hpp'), hpp)):
    open(p, 'w', encoding='utf-8', newline='\n').write(s)
shutil.copyfile(os.path.join(HERE, 'mapping_index.hpp'), os.path.join(OUT, 'include', 'bc5', 'mapping_index.hpp'))
for f in ('src/direct.cpp', 'include/bc5/direct.hpp', 'include/bc5/mapping_index.hpp'):
    print(f, hashlib.md5(open(os.path.join(OUT, f), 'rb').read()).hexdigest())
