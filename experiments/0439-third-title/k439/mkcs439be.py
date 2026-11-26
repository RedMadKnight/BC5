#!/usr/bin/env python3
# BC5 exp 0439 (tag cs439, 11-24): puts cs0439.hpp's switches into the backend kit (all off by default).
#   mkcs439be.py <backend dir: has src/direct.cpp and src/state_stack.cpp> (state_stack.hpp unchanged: the class layout
#   other units see stays; state_stack.cpp reads BC5_0439_PUSH_NO_CLEAR through cs0439.hpp)
# Edits in place; every anchor must occur exactly once, else nothing is written (exit 1).
import sys, os

B = sys.argv[1]


def edit(rel, reps):
    p = os.path.join(B, rel)
    s = open(p, encoding="utf-8").read()
    for a, b in reps:
        n = s.count(a)
        if n != 1:
            print("mkcs439be: %s: anchor found %d times: %r" % (rel, n, a[:80]))
            sys.exit(1)
        s = s.replace(a, b)
    return p, s


out = []

# state_stack.cpp: at a push, NOP the packet and keep the context valid when the flag is on
out.append(edit("src/state_stack.cpp", [
    ('#include "bc5/policy.hpp"', '#include "bc5/policy.hpp"\n#include "bc5/cs0439.hpp" // exp 0439 (tag cs439)'),
    ("                if (conditional) {\n                    stats.conditional++;",
     "                if (conditional) {\n                    stats.conditional++;\n"
     "                    if (cmd == 2 && cs439::env().cond_pop_nop) // exp 0439 (tag cs439): no clear for a pop under COND_EXEC\n"
     "                        for (std::size_t k = 0; k < len; ++k) io[i + k] = policy::kNop;"),
    ("                    stats.pushes++;\n                    ctx_.valid.reset(); // the filter's cmd 0 runs: the kernel's clear state",
     "                    stats.pushes++;\n"
     "                    if (cs439::env().push_no_clear) { // exp 0439 (tag cs439): no clear at the push; `io` is read lazily below\n"
     "                        for (std::size_t k = 0; k < len; ++k) io[i + k] = policy::kNop;\n"
     "                    } else {\n"
     "                        ctx_.valid.reset(); // the filter's cmd 0 runs: the kernel's clear state\n"
     "                    }"),
]))

# direct.cpp
out.append(edit("src/direct.cpp", [
    ('#include "bc5/ib_chain.hpp" // exp 0439 (tag ib439)',
     '#include "bc5/ib_chain.hpp" // exp 0439 (tag ib439)\n#include "bc5/cs0439.hpp" // exp 0439 (tag cs439)'),
    ("    int depth = 0;\n};",
     "    int depth = 0;\n    std::size_t out_n = 0; // exp 0439 (tag cs439): the size after the piece's state stack grew it (0: n)\n};"),
    ("    policy::FilterOptions fopt = opt;",
     "    policy::FilterOptions fopt = opt;\n"
     "    if (cs439::env().pass_cc) fopt.safe_context_control = false; // exp 0439 (tag cs439): the guest's CONTEXT_CONTROL passes\n"
     "    else if (cs439::env().cc_guarded && !comp && opt.mapped) // exp 0439 (tag cs439 ccg): passes when its LOAD addresses are mapped\n"
     "        fopt.safe_context_control = !cs439::cc_loads_ok(ib.data(), ib.size(), opt.mapped);"),
    # exp 0439 (tag cs439 ml): the imported direct-memory ranges mlocked through a host mapping of their own
    ("    std::uint32_t maps = 0; // experiment 0170: how many shared mappings lie on this BO",
     "    std::uint32_t maps = 0; // experiment 0170: how many shared mappings lie on this BO\n"
     "    void *cs_lock_p = nullptr; // exp 0439 (tag cs439 ml): the host's mlocked mapping of this import (BC5_0439_MLOCK_IMPORTS)\n"
     "    std::uint64_t cs_lock_n = 0;"),
    ("    impl_->shared.push_back(b);",
     "    if (cs439::env().mlock_imports) cs439::lock_import(memfd, offset, size, b.cs_lock_p, b.cs_lock_n); // exp 0439 (tag cs439 ml)\n"
     "    impl_->shared.push_back(b);"),
    ("        if (b->id != id) continue;",
     "        if (b->id != id) continue;\n"
     "        cs439::unlock_import(b->cs_lock_p, b->cs_lock_n); // exp 0439 (tag cs439 ml); the BO still holds its pages until freed below"),
    ("        impl_->tracker.apply_in_place(ib, main_out, opt.mapped, r.state_stack);",
     "        impl_->tracker.apply_in_place(ib, main_out, opt.mapped, r.state_stack);\n"
     "        cs439::g_root_push += r.state_stack.pushes; cs439::g_root_pop += r.state_stack.pops;\n"
     "        cs439::g_root_unmatched += r.state_stack.unmatched_pops; cs439::g_root_cond += r.state_stack.conditional;"),
    ("    const Piece &last = pieces.back();\n    const std::size_t flag_off",
     "    // exp 0439 (tag cs439): counts over the guest's IBs; room for the pieces' restores (PIECE_STATE_STACK)\n"
     "    const bool cs_stack = cs439::env().piece_stack && state_stack_ && opt.mapped && !comp;\n"
     "    if (!comp && cs439::env().count) {\n"
     "        for (std::size_t k = 0; k < pieces.size(); ++k)\n"
     "            cs439::count_ib(pieces[k].src, pieces[k].n, k == 0 ? 0 : 1 + std::min(pieces[k].depth, 3));\n"
     "        cs439::report();\n"
     "    }\n"
     "    if (cs_stack) {\n"
     "        for (std::size_t k = 1; k < pieces.size(); ++k) {\n"
     "            const std::size_t room = cs439::pops_in(pieces[k].src, pieces[k].n) * 2048;\n"
     "            pieces[k].off = pieces[k - 1].off + pieces[k - 1].padded;\n"
     "            pieces[k].padded = (pieces[k].n + room + 7) & ~std::size_t{7};\n"
     "        }\n"
     "    }\n"
     "    if (!comp) {\n"
     "        std::vector<cs439::DumpPiece> dp;\n"
     "        if (!cs439::env().dump.empty() || cs439::env().cc_census) for (const Piece &q : pieces) dp.push_back({q.src, q.n});\n"
     "        cs439::maybe_dump(dp, opt.mapped);\n"
     "        if (cs439::env().cc_census) cs439::cc_census(dp, opt.mapped);\n"
     "    }\n"
     "    const Piece &last = pieces.back();\n    const std::size_t flag_off"),
    # the piece filter; the kit has pw439's block between the filter call and the padding, so two anchors
    ("        policy::filter(policy::Policy::builtin(), std::span<const std::uint32_t>(pc.src, pc.n),\n"
     "                       std::span<std::uint32_t>(dst + pc.off, pc.n), nested_opt, st);",
     "        std::vector<std::uint32_t> cs_io; // exp 0439 (tag cs439): the piece's filtered copy when its state stack runs\n"
     "        if (cs_stack) {\n"
     "            cs_io.resize(pc.n);\n"
     "            policy::filter(policy::Policy::builtin(), std::span<const std::uint32_t>(pc.src, pc.n), std::span<std::uint32_t>(cs_io), nested_opt, st);\n"
     "        } else {\n"
     "        policy::filter(policy::Policy::builtin(), std::span<const std::uint32_t>(pc.src, pc.n),\n"
     "                       std::span<std::uint32_t>(dst + pc.off, pc.n), nested_opt, st);\n"
     "        if (!comp && cs439::env().push_no_clear) cs439::push_nops(pc.src, dst + pc.off, pc.n, policy::kNop); // exp 0439 (tag cs439)\n"
     "        }"),
    ("        for (std::size_t i = pc.n; i < pc.padded; ++i) dst[pc.off + i] = policy::kNop;\n"
     "        std::vector<std::uint32_t> ex;\n"
     "        executed_offsets_of(std::span<const std::uint32_t>(pc.src, pc.n), dst + pc.off, ex);",
     "        std::vector<std::uint32_t> ex;\n"
     "        if (cs_stack) { // exp 0439 (tag cs439): the tracker over the piece; its restores fill the room reserved above\n"
     "            executed_offsets_of(std::span<const std::uint32_t>(pc.src, pc.n), cs_io.data(), ex); // in the guest's offsets\n"
     "            state_stack::Stats ss;\n"
     "            impl_->tracker.apply_in_place(std::span<const std::uint32_t>(pc.src, pc.n), cs_io, opt.mapped, ss);\n"
     "            cs439::g_piece_push += ss.pushes; cs439::g_piece_pop += ss.pops; cs439::g_piece_unmatched += ss.unmatched_pops;\n"
     "            cs439::g_piece_restored += ss.restored_regs;\n"
     "            if (cs_io.size() > pc.padded) { // cannot happen with 2048 per pop; never write past the room\n"
     "                std::fprintf(stderr, \"bc5-direct: exp 0439 (tag cs439): piece %zu grew to %zu over its room %zu: restores dropped\\n\", k, cs_io.size(), pc.padded);\n"
     "                cs_io.resize(pc.n);\n"
     "                policy::filter(policy::Policy::builtin(), std::span<const std::uint32_t>(pc.src, pc.n), std::span<std::uint32_t>(cs_io), nested_opt, st);\n"
     "            }\n"
     "            for (std::size_t i = 0; i < cs_io.size(); ++i) dst[pc.off + i] = cs_io[i];\n"
     "            for (std::size_t i = cs_io.size(); i < pc.padded; ++i) dst[pc.off + i] = policy::kNop;\n"
     "            if (cs_io.size() != pc.n) { pieces[k].out_n = cs_io.size(); cs439::g_grown++; }\n"
     "        } else {\n"
     "        for (std::size_t i = pc.n; i < pc.padded; ++i) dst[pc.off + i] = policy::kNop;\n"
     "        executed_offsets_of(std::span<const std::uint32_t>(pc.src, pc.n), dst + pc.off, ex);\n"
     "        }"),
    ("                        d[i + 2] = static_cast<std::uint32_t>((va >> 32) & 0xffffu);",
     "                        d[i + 2] = static_cast<std::uint32_t>((va >> 32) & 0xffffu);\n"
     "                        if (q.out_n != 0) d[i + 3] = (d[i + 3] & ~0xfffffu) | static_cast<std::uint32_t>(q.out_n); // exp 0439 (tag cs439)"),
]))

for p, s in out:
    open(p, "w", encoding="utf-8", newline="\n").write(s)
print("mkcs439be: ok (%d files)" % len(out))
