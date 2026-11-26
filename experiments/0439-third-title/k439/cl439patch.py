# BC5 exp 0439 (tag cl439): patch the private backend copy new/be/direct.cpp (run on the box, in k439/). With
# BC5_0439_COPY_LAYOUT=1, every job of 30 or more pieces prints its copy's layout to stderr: the slot, the slot's GPU VA
# (kScratchVa + slot << 32), the prologue's padded size, and per piece the guest source address, the dword offset in
# the copy and the dword count. With it the hang dump's CP_IB1/IB2 base (a copy address) maps to a piece and dword.
import sys

p = sys.argv[1] if len(sys.argv) > 1 else 'new/be/direct.cpp'
s = open(p, encoding='utf-8', newline='').read()
a = '''    if (pieces.size() > 1) {
        r.prep_nested_ms += now_ms() - t_phase;'''
b = '''    { // exp 0439 (tag cl439)
        static const bool cl439 = [] {
            const char *e = std::getenv("BC5_0439_COPY_LAYOUT");
            return e != nullptr && e[0] == '1' && e[1] == 0;
        }();
        if (cl439 && pieces.size() >= 30) {
            std::string l;
            char b[96];
            std::snprintf(b, sizeof(b), "[bc5] exp 0439 (tag cl439): slot %d va 0x%llx prologue %zu, %zu pieces:", cur,
                          static_cast<unsigned long long>(impl_->slots[cur].va), pro_padded, pieces.size());
            l = b;
            for (std::size_t k = 0; k < pieces.size(); ++k) {
                std::snprintf(b, sizeof(b), " %zu:0x%llx@%zu+%zu", k, static_cast<unsigned long long>(reinterpret_cast<std::uint64_t>(pieces[k].src)),
                              pieces[k].off, pieces[k].n);
                l += b;
            }
            std::fprintf(stderr, "%s\\n", l.c_str());
        }
    }
''' + a
assert s.count(a) == 1, s.count(a)
s = s.replace(a, b)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('cl439: patched', p)
