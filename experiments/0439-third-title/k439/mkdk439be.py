# BC5 exp 0439 (tag dk439 arm): the backend half of BC5_0439_DCC_UNCOMPRESSED (dk0439.hpp says what and why).
# Run after pw439patch.py in prep439d.sh:   python3 -I mkdk439be.py <direct.cpp>   (in place)
# In Device::submit_impl, after the job copy is filtered (main IB, prologue and every nested piece in `dst`) and before
# the INDIRECT_BUFFER packets are re-pointed: on the GFX ring only, each piece's copy is walked (dk0439.hpp strip), DCC_ENABLE
# cleared in every CB_COLORn_INFO value, and the keys of each stripped target whose size and DCC_BASE are known (from this
# job or earlier GFX jobs: the GPU's context persists) are set to 0xff, where FilterOptions::mapped covers them. The title's
# own IBs are not written; only the job copy and the keys. A counter line every 4096 GFX jobs that strip.
import sys

p = sys.argv[1]
s = open(p, encoding='utf-8', newline='').read()


def rep(tag, a, b):
    global s
    assert s.count(a) == 1, (tag, s.count(a))
    s = s.replace(a, b)


rep('include', '#include "bc5/ds0439.hpp" // exp 0439 (tag ds439)\n', '''#include "bc5/ds0439.hpp" // exp 0439 (tag ds439)
#include "bc5/dk0439.hpp" // exp 0439 (tag dk439 arm): BC5_0439_DCC_UNCOMPRESSED
''')

rep('strip', '''    if (pieces.size() > 1) {
        r.prep_nested_ms += now_ms() - t_phase;
''', '''    { // exp 0439 (tag dk439 arm): BC5_0439_DCC_UNCOMPRESSED=1, the GFX job copy without colour DCC, its targets' keys 0xff
        static const bool dk439 = [] {
            const char *e = std::getenv("BC5_0439_DCC_UNCOMPRESSED");
            const bool v = e != nullptr && e[0] == '1' && e[1] == 0;
            std::fprintf(stderr, "[bc5] exp 0439 (tag dk439): BC5_0439_DCC_UNCOMPRESSED=%d (1: colour targets written without DCC, their keys set to uncompressed)\\n", v ? 1 : 0);
            return v;
        }();
        static bc5::dk439::Target dk_t[8]; // the GFX ring's colour targets as last set (one GFX ring; submits are serialised)
        static std::atomic<std::uint64_t> dk_jobs{0}, dk_info{0}, dk_keys{0}, dk_keys_bytes{0}, dk_unknown{0};
        if (dk439 && !comp) {
            for (auto &x : dk_t) x.stripped = false;
            std::uint32_t changed = bc5::dk439::strip(std::span<std::uint32_t>(dst, pro), dk_t);
            for (std::size_t k = 0; k < pieces.size(); ++k)
                changed += bc5::dk439::strip(std::span<std::uint32_t>(dst + pieces[k].off, k == 0 ? main_n : pieces[k].n), dk_t);
            if (changed != 0) {
                dk_info += changed;
                for (auto &x : dk_t) {
                    if (!x.stripped) continue;
                    const std::uint64_t kb = bc5::dk439::key_bytes(x), ka = bc5::dk439::dcc_base(x);
                    if (kb == 0 || ka == 0 || !opt.mapped || !opt.mapped(ka, kb)) {
                        dk_unknown++;
                        continue;
                    }
                    std::memset(reinterpret_cast<void *>(ka), 0xff, static_cast<std::size_t>(kb));
                    dk_keys++;
                    dk_keys_bytes += kb;
                }
                if ((dk_jobs++ & 0xfffu) == 0)
                    std::fprintf(stderr, "[bc5] exp 0439 (tag dk439): %llu GFX jobs stripped: %llu CB_COLORn_INFO values without DCC_ENABLE, %llu key ranges set to 0xff (%.1f MB), %llu with size or DCC_BASE unknown or unmapped\\n",
                                 static_cast<unsigned long long>(dk_jobs.load()), static_cast<unsigned long long>(dk_info.load()), static_cast<unsigned long long>(dk_keys.load()),
                                 static_cast<double>(dk_keys_bytes.load()) / 1e6, static_cast<unsigned long long>(dk_unknown.load()));
            }
        }
    }
    if (pieces.size() > 1) {
        r.prep_nested_ms += now_ms() - t_phase;
''')
open(p, 'w', encoding='utf-8', newline='').write(s)
print('mkdk439be: patched', p)
