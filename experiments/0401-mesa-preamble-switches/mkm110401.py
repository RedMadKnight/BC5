#!/usr/bin/env python3
"""BC5 experiment 0401 series e11, tag m11: four switches from hang2242-0401.md section 4 (the 2026-11-09 22:42 hang), as one
edit of src/libs/bc5LleAgc.cpp (pinned input: MAIN_MD5, e8's main unit, the one exp 0409's binary was built from).
  BC5_DIRECT_RESET_REPLAY_ACB     fix. An acb head's GPU marks (AcbHead.marks) taken before a device reopen are dropped when
                                  the head is used again (the next head piece or the rest), so the soft CP replays the head's
                                  memory side effects (its label writes) on the CPU at the ring's post. Each AcbHead records
                                  the reopen count it was made at. Journaled (at most 200 lines).
  BC5_DIRECT_RESET_LABELS         fix. At a timed-out job the completion thread keeps exp 0055's pending label writes (every
                                  in-flight job's) before forget_label_writes clears them; at the reopen ("reopen: ok") the
                                  last write of each label is written to guest memory in order where memory does not hold its
                                  value already and the label lies in a guest range. Journaled (one count line).
  BC5_DIRECT_LEARN_GUEST_ONLY     fix. A fault whose learned window (learned_add's 96 MiB) holds no guest range is not learned
                                  or saved: one "e11: fault ... not learned" line instead.
  BC5_DIRECT_RESET_LABEL_JOURNAL  catcher. The kept writes are journaled at the reopen (at most 64, with what memory holds),
                                  and again 5 s and 30 s later from a thread of its own (address, value, held or not).
Not in this build: hang2242's switch 5 (STUCK_AFTER_REOPEN; the runner's external read-only stall0409.sh dump stands in) and
switch 6 (FAULT_PAGES; the runner already keeps every amdgpu fault line of dmesg in <tag>-dmesg-after.txt).
Each switch: unset, empty and "0" are off, any other value is on (bc5::env_on, F767); read once. With all four off the binary
does what e8's does, plus one reopen counter (an atomic add at each reopen) and one more AcbHead field.
The edit: every anchor occurs exactly once; every edit keeps braces, parentheses and brackets balanced outside comments and
literals; the inserted text is ASCII; LF line ends; a unit that has the edit already is refused, and so is an input that is
not the pinned one. After editing, the script undoes its edits and asserts that this gives the input back byte for byte.
Prints "<relpath> <md5>".
CPU test: m110401.cpp (on, off, unset).
usage: mkm110401.py <tree root in> <out dir>"""
import hashlib
import os
import sys

MAIN = "src/libs/bc5LleAgc.cpp"
MAIN_MD5 = "bd1811690b685369194602027b61a2d5"  # e8's main unit (exp 0409's binary)
MARKS = (b"BC5_DIRECT_RESET_REPLAY_ACB", b"BC5_DIRECT_RESET_LABELS", b"BC5_DIRECT_LEARN_GUEST_ONLY", b"BC5_DIRECT_RESET_LABEL_JOURNAL",
         b"bc5_m11_", b"tag m11", b"m11_", b"M11")


def tabs(text):
    """C++ written with 4-space indents; the unit indents with tabs."""
    out = []
    for line in text.split("\n"):
        body = line.lstrip(" ")
        k = len(line) - len(body)
        out.append("\t" * (k // 4) + " " * (k % 4) + body)
    return "\n".join(out).encode("ascii")


E = []  # (name, old, new) in file order


def edit(name, old, new):
    E.append((name, old, new))


# ---- block A, before learned_add: the switches, the guest test, the learned decision, the reopen count, the head check ----
BLOCK_A = tabs(r"""// Experiment 0401 series e11 (tag m11, mkm110401.py; hang2242-0401.md section 4, the 2026-11-09 22:42 hang): four
// switches, default off; unset, empty and "0" are off (bc5::env_on, F767), each read once.
//   BC5_DIRECT_RESET_REPLAY_ACB     an acb head's GPU marks taken before a device reopen are dropped when the head is used
//                                   again, so the soft CP replays the head's memory side effects (its label writes).
//   BC5_DIRECT_RESET_LABELS         at the reopen, the lost jobs' label writes (exp 0055's list at the timeout) go to guest
//                                   memory: the last write of each label, where memory does not hold it already.
//   BC5_DIRECT_LEARN_GUEST_ONLY     a fault whose learned window holds no guest range is not learned or saved.
//   BC5_DIRECT_RESET_LABEL_JOURNAL  the lost label writes are journaled at the reopen, and 5 s and 30 s later.
// hang2242's switch 5 (STUCK_AFTER_REOPEN) is not in this build (the runner's external stall0409.sh dump stands in), nor
// switch 6 (FAULT_PAGES: the runner keeps every amdgpu fault line of dmesg).
static const char* const kM11Names[4] = {"BC5_DIRECT_RESET_REPLAY_ACB", "BC5_DIRECT_RESET_LABELS", "BC5_DIRECT_LEARN_GUEST_ONLY", "BC5_DIRECT_RESET_LABEL_JOURNAL"};
static bool m11_on(int k) {
    static const bool v[4] = {bc5::env_on(std::getenv(kM11Names[0])), bc5::env_on(std::getenv(kM11Names[1])), bc5::env_on(std::getenv(kM11Names[2])),
                              bc5::env_on(std::getenv(kM11Names[3]))};
    return k >= 0 && k < 4 && v[k];
}
static void m11_switch_line() {
    static std::atomic<bool> done {false};
    if (done.exchange(true)) return;
    journal("e11: switches: %s %s, %s %s, %s %s, %s %s (exp 0401 e11, tag m11)\n", kM11Names[0], m11_on(0) ? "on" : "off", kM11Names[1], m11_on(1) ? "on" : "off", kM11Names[2],
            m11_on(2) ? "on" : "off", kM11Names[3], m11_on(3) ? "on" : "off");
}
static bool m11_guest_in_real(uint64_t lo, uint64_t hi) {
    std::vector<std::pair<uint64_t, uint64_t>> guest;
    Libs::LibKernel::Memory::Bc5GuestRangesIn(lo, hi, &guest);
    return !guest.empty();
}
static bool (*g_m11_guest_in)(uint64_t lo, uint64_t hi) = m11_guest_in_real; // true when [lo, hi) meets a guest range; the CPU test puts its own here
static std::atomic<uint64_t> g_m11_reopens {0};                                // device reopens so far (m11_after_reopen, every reopen)
// BC5_DIRECT_LEARN_GUEST_ONLY: true when the window [lo, lo + n) that learned_add would save for fault_addr holds no guest range.
static bool m11_learn_refused(uint64_t fault_addr, uint64_t lo, uint64_t n) {
    if (!m11_on(2)) return false;
    m11_switch_line();
    if (g_m11_guest_in(lo, lo + n)) return false;
    journal("e11: fault 0x%" PRIx64 ": no guest range in its window 0x%" PRIx64 "+0x%" PRIx64 ", not learned\n", fault_addr, lo, n);
    return true;
}
// BC5_DIRECT_RESET_REPLAY_ACB: an acb head's marks taken before the last device reopen are dropped, so the soft CP replays them.
static void m11_head_check(std::vector<SoftCp::GpuDone>& marks, uint64_t& reopens, const char* where) {
    if (!m11_on(0)) return;
    const uint64_t now = g_m11_reopens.load();
    if (reopens == now) return;
    m11_switch_line();
    static std::atomic<uint32_t> lines {0};
    if (lines++ < 200) journal("e11: acb head (%s): %zu GPU marks from before reopen %" PRIu64 " dropped, the soft CP replays that part\n", where, marks.size(), now);
    marks.clear();
    reopens = now;
}
""")
A_ANCHOR = b"static void learned_add(uint64_t fault_addr) {\n"
edit("block A", A_ANCHOR, BLOCK_A + A_ANCHOR)

# ---- learned_add: the guest-only test -------------------------------------------------------------------------------------
L_ANCHOR = b"\tconst uint64_t n  = 0x6000000ull; // 96 MiB\n"
edit("learned_add's test", L_ANCHOR, L_ANCHOR + b"\tif (m11_learn_refused(fault_addr, lo, n)) return; // exp 0401 e11 (tag m11): BC5_DIRECT_LEARN_GUEST_ONLY\n")

# ---- AcbHead: the reopen count it was made at ---------------------------------------------------------------------------
H_ANCHOR = b"\tstd::vector<SoftCp::GpuDone> marks; // what the GPU executed of them, for the soft CP\n};\n"
edit("AcbHead's field", H_ANCHOR, H_ANCHOR[:-3] + b"\n\tuint64_t                     reopens; // exp 0401 e11 (tag m11): g_m11_reopens when made (BC5_DIRECT_RESET_REPLAY_ACB)\n};\n")

# ---- the head: made with the count; an older head's marks checked before more are added ------------------------------------
N_ANCHOR = (b"\t\t\t\t\t\t\tg_acb_heads.push_back({ib, num_dwords, 0, {}});\n\t\t\t\t\t\t\te = &g_acb_heads.back();\n\t\t\t\t\t\t}\n"
            b"\t\t\t\t\t\te->done = i;\n")
edit("the head", N_ANCHOR, b"\t\t\t\t\t\t\tg_acb_heads.push_back({ib, num_dwords, 0, {}, g_m11_reopens.load()}); // exp 0401 e11: + the reopen count\n"
     b"\t\t\t\t\t\t\te = &g_acb_heads.back();\n\t\t\t\t\t\t}\n"
     b"\t\t\t\t\t\tm11_head_check(e->marks, e->reopens, \"head\"); // exp 0401 e11 (tag m11): BC5_DIRECT_RESET_REPLAY_ACB\n"
     b"\t\t\t\t\t\te->done = i;\n")

# ---- block B, after forget_label_writes: the lost writes, the reopen's step, the CPU test's seams ---------------------------
BLOCK_B = tabs(r"""// Experiment 0401 series e11 (tag m11): the label writes the jobs in flight had pending at a timeout (exp 0055's list, kept by
// m11_keep_lost just before forget_label_writes clears it) and what the reopen does with them (BC5_DIRECT_RESET_LABELS,
// BC5_DIRECT_RESET_LABEL_JOURNAL; the switches are in m11's block above learned_add).
static std::vector<PendingLabelWrite> g_m11_lost;         // under g_plw_mutex
static uint64_t                       g_m11_lost_for = 0; // the reopen they belong to (g_m11_reopens + 1 when kept)
static void m11_keep_lost() {
    if (!m11_on(1) && !m11_on(3)) return;
    std::lock_guard lk(g_plw_mutex);
    g_m11_lost     = g_plw;
    g_m11_lost_for = g_m11_reopens.load() + 1;
}
static uint64_t m11_read(uint64_t a, bool is64) {
    return is64 ? *reinterpret_cast<const volatile uint64_t*>(a) : *reinterpret_cast<const volatile uint32_t*>(a);
}
static void m11_after_reopen(bool ok) {
    const uint64_t reopen = g_m11_reopens.fetch_add(1) + 1;
    const bool     labels = m11_on(1), lj = m11_on(3);
    if (!labels && !lj) return;
    m11_switch_line();
    std::vector<PendingLabelWrite> lost;
    uint64_t                       kept_for = 0;
    {
        std::lock_guard lk(g_plw_mutex);
        lost.swap(g_m11_lost);
        kept_for = g_m11_lost_for;
    }
    if (kept_for != reopen) {
        journal("e11: reopen %" PRIu64 ": no lost label writes kept for it (%zu kept for reopen %" PRIu64 ", dropped)\n", reopen, lost.size(), kept_for);
        return;
    }
    std::vector<char> last(lost.size(), 0); // the last write of its label in the list
    {
        std::set<uint64_t> seen;
        for (size_t i = lost.size(); i-- > 0;) last[i] = seen.insert(lost[i].label).second ? 1 : 0;
    }
    size_t held = 0, outside = 0, superseded = 0, written = 0;
    for (size_t i = 0; i < lost.size(); i++) {
        const PendingLabelWrite& w   = lost[i];
        const bool               in  = g_m11_guest_in(w.label, w.label + (w.is64 ? 8u : 4u));
        const uint64_t           was = in ? m11_read(w.label, w.is64) : 0;
        if (lj && i < 64) {
            journal("e11: lost write %zu: label 0x%" PRIx64 " value 0x%" PRIx64 " (%s), seq %" PRIu64 " ring %d%s; %s 0x%" PRIx64 "\n", i, w.label, w.value, w.is64 ? "64-bit" : "32-bit",
                    w.seq, w.ring, last[i] != 0 ? "" : ", superseded", in ? "memory holds" : "not in guest memory, read", was);
        }
        if (!in) {
            outside++;
        } else if (was == w.value) {
            held++;
        } else if (last[i] == 0) {
            superseded++;
        } else if (labels && ok) {
            if (w.is64) {
                *reinterpret_cast<volatile uint64_t*>(w.label) = w.value;
            } else {
                *reinterpret_cast<volatile uint32_t*>(w.label) = static_cast<uint32_t>(w.value);
            }
            written++;
        }
    }
    journal("e11: reopen %" PRIu64 " (%s): %zu label writes of the lost jobs: %zu held already, %zu not in guest memory, %zu superseded, %zu written (BC5_DIRECT_RESET_LABELS %s)\n",
            reopen, ok ? "ok" : "FAILED", lost.size(), held, outside, superseded, written, labels ? "on" : "off");
    if (!lj || lost.empty()) return;
    if (lost.size() > 64) lost.resize(64);
    std::thread([lost = std::move(lost), reopen] {
        for (const int s: {5, 30}) {
            std::this_thread::sleep_for(std::chrono::seconds(s == 5 ? 5 : 25));
            size_t holds = 0;
            for (const PendingLabelWrite& w: lost) {
                const bool     in  = g_m11_guest_in(w.label, w.label + (w.is64 ? 8u : 4u));
                const uint64_t now = in ? m11_read(w.label, w.is64) : 0;
                if (in && now == w.value) holds++;
                journal("e11: %d s after reopen %" PRIu64 ": label 0x%" PRIx64 " %s 0x%" PRIx64 " (the lost value 0x%" PRIx64 ")\n", s, reopen, w.label, in ? "holds" : "not in guest memory, read",
                        now, w.value);
            }
            journal("e11: %d s after reopen %" PRIu64 ": %zu of %zu lost label writes held\n", s, reopen, holds, lost.size());
        }
    }).detach();
}
// The CPU test's seams (m110401.cpp); nothing in the emulator calls them.
extern "C" int bc5_m11_0401_switch(int k) {
    return k >= 0 && k < 4 ? (m11_on(k) ? 1 : 0) : -1;
}
static uint64_t g_m11_test_lo = 0, g_m11_test_hi = 0;
static bool m11_guest_in_test(uint64_t lo, uint64_t hi) {
    return lo < hi && lo < g_m11_test_hi && hi > g_m11_test_lo;
}
extern "C" void bc5_m11_0401_guest(uint64_t lo, uint64_t hi) { // [lo, hi) is the only guest memory from now on; hi 0: the real test again
    g_m11_test_lo  = lo;
    g_m11_test_hi  = hi;
    g_m11_guest_in = hi != 0 ? m11_guest_in_test : m11_guest_in_real;
}
extern "C" int bc5_m11_0401_learn_refused(uint64_t fault_addr) {
    const uint64_t lo = (fault_addr & ~0x3ffffffull) > 0x2000000ull ? (fault_addr & ~0x3ffffffull) - 0x2000000ull : 0; // learned_add's window
    return m11_learn_refused(fault_addr, lo, 0x6000000ull) ? 1 : 0;
}
extern "C" void bc5_m11_0401_plw_add(uint64_t label, uint64_t value, int is64, uint64_t seq) {
    std::lock_guard   lk(g_plw_mutex);
    PendingLabelWrite w {label, value, seq, is64 != 0, bc5::direct::kGfxRing, 0};
    w.order = g_plw.size() + 1;
    g_plw.push_back(w);
}
extern "C" uint64_t bc5_m11_0401_timeout(uint64_t seq) { // the completion thread's two calls for a timed-out job; the writes left
    m11_keep_lost();
    forget_label_writes(seq, bc5::direct::kGfxRing, true);
    std::lock_guard lk(g_plw_mutex);
    return g_plw.size();
}
extern "C" void bc5_m11_0401_reopen(int ok) {
    m11_after_reopen(ok != 0);
}
extern "C" uint64_t bc5_m11_0401_reopens() {
    return g_m11_reopens.load();
}
extern "C" uint64_t bc5_m11_0401_head(uint64_t head_reopens) { // the marks left of two after m11_head_check
    std::vector<SoftCp::GpuDone> marks(2);
    m11_head_check(marks, head_reopens, "m110401");
    return marks.size();
}
""")
B_ANCHOR = (b"\tg_plw.erase(std::remove_if(g_plw.begin(), g_plw.end(), [seq, ring](const PendingLabelWrite& w) { return w.seq == seq && w.ring == ring; }), "
            b"g_plw.end());\n}\n")
edit("block B", B_ANCHOR, B_ANCHOR + b"\n" + BLOCK_B)

# ---- the rest: the head's marks checked before they go to the soft CP ------------------------------------------------------
R_ANCHOR = b"\t\t\t\t\t\t\tskip = g_acb_heads[k].done;\n\t\t\t\t\t\t\tfor (auto& g: g_acb_heads[k].marks) SoftCp::t_gpu_done.push_back(std::move(g));\n"
edit("the rest", R_ANCHOR, b"\t\t\t\t\t\t\tskip = g_acb_heads[k].done;\n"
     b"\t\t\t\t\t\t\tm11_head_check(g_acb_heads[k].marks, g_acb_heads[k].reopens, \"rest\"); // exp 0401 e11 (tag m11): BC5_DIRECT_RESET_REPLAY_ACB\n"
     b"\t\t\t\t\t\t\tfor (auto& g: g_acb_heads[k].marks) SoftCp::t_gpu_done.push_back(std::move(g));\n")

# ---- the reopen: the kept writes ------------------------------------------------------------------------------------------
O_ANCHOR = b"\t\tjournal(\"reopen: %s\\n\", g_dev ? \"ok\" : \"FAILED\");\n"
edit("the reopen", O_ANCHOR, O_ANCHOR + b"\t\tm11_after_reopen(static_cast<bool>(g_dev)); // exp 0401 e11 (tag m11): BC5_DIRECT_RESET_LABELS, BC5_DIRECT_RESET_LABEL_JOURNAL\n")

# ---- the completion thread: keep the writes before a timed-out job's forget_label_writes clears them ----------------------
C_ANCHOR = b"\t\t\tforget_label_writes(j.seq, r.ring, r.timed_out || r.rc == -125); // experiment 0055\n"
edit("the completion thread", C_ANCHOR, b"\t\t\tif (r.timed_out) m11_keep_lost(); // exp 0401 e11 (tag m11): the lost jobs' label writes, before they are forgotten\n" + C_ANCHOR)


def strip_code(b):
    """The text with comments and string/char literals removed (for the balance counts)."""
    out = bytearray()
    i, n = 0, len(b)
    while i < n:
        c = b[i:i + 1]
        if b[i:i + 2] == b"//":
            j = b.find(b"\n", i)
            i = n if j < 0 else j
        elif b[i:i + 2] == b"/*":
            j = b.find(b"*/", i + 2)
            i = n if j < 0 else j + 2
        elif c in (b'"', b"'") and not (c == b"'" and i > 0 and b[i - 1:i].isalnum()):  # 500'000'000ull: a digit separator, not a literal
            j = i + 1
            while j < n and b[j:j + 1] != c:
                j += 2 if b[j:j + 1] == b"\\" else 1
            i = j + 1
        else:
            out += c
            i += 1
    return bytes(out)


def balance(b):
    s = strip_code(b)
    return (s.count(b"{") - s.count(b"}"), s.count(b"(") - s.count(b")"), s.count(b"[") - s.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def apply(s, edits, rel):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", rel, m)
    assert b"\r" not in s, ("a CR in the LF unit", rel)
    done = []
    out = s
    at = -1
    for name, old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", rel, name, out.count(old))
        assert balance(old) == balance(new), ("the edit changes the balance", rel, name, balance(old), balance(new))
        new.decode("ascii")
        assert b"\r" not in new, ("a CR in the inserted text", rel, name)
        pos = out.index(old)
        assert pos > at, ("the edits are not in file order", rel, name)
        at = pos
        out = out.replace(old, new)
        done.append((old, new, name))
    assert balance(out) == balance(s), ("the unit's balance changed", rel, balance(s), balance(out))
    back = out
    for old, new, name in reversed(done):
        assert back.count(new) == 1, ("undo", rel, name)
        back = back.replace(new, old)
    assert back == s, ("undoing the edits does not give the input back", rel)
    assert out.startswith(b"\xef\xbb\xbf") == s.startswith(b"\xef\xbb\xbf"), ("the BOM changed", rel)
    return out


def edit_main(s):
    out = apply(s, E, MAIN)
    counts = {h: out.count(h.encode() + b"(") for h in ("m11_on", "m11_switch_line", "m11_learn_refused", "m11_head_check", "m11_keep_lost", "m11_after_reopen", "m11_read",
                                                         "g_m11_guest_in", "m11_guest_in_real", "m11_guest_in_test")}
    want = {"m11_on": 12, "m11_switch_line": 4, "m11_learn_refused": 3, "m11_head_check": 4, "m11_keep_lost": 3, "m11_after_reopen": 3, "m11_read": 3,
            "g_m11_guest_in": 3, "m11_guest_in_real": 1, "m11_guest_in_test": 1}
    assert counts == want, ("the functions' uses", counts)
    # The AcbHead initialisers: the one in the unit has the count now, and no other initialiser is left without it.
    assert out.count(b"g_acb_heads.push_back({ib, num_dwords, 0, {}, g_m11_reopens.load()});") == 1 and out.count(b"g_acb_heads.push_back(") == 1, "AcbHead's initialiser"
    # Block A comes before learned_add, block B after forget_label_writes and before recover_after_timeout and the completion thread.
    pos = [out.index(x) for x in (b"static bool m11_on(int k)", b"static void learned_add(", b"static void forget_label_writes(", b"static void m11_keep_lost()",
                                  b"static void recover_after_timeout(", b"\t\t\tif (r.timed_out) m11_keep_lost();")]
    assert pos == sorted(pos), ("the blocks' places", pos)
    # Both blocks sit inside the direct build's #if (it opens before the first and closes after the last).
    assert out.rfind(b"\n#if defined(KYTY_BC5_DIRECT)\n", 0, pos[0]) > 0, "block A's #if"
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    with open(os.path.join(root, MAIN), "rb") as f:
        s = f.read()
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", MAIN, m.decode())
    assert md5(s) == MAIN_MD5, ("refused: not the pinned input", MAIN, md5(s), MAIN_MD5)
    out = edit_main(s)
    print(f"# in:  {MAIN} {md5(s)}  ({len(s)} bytes, LF)", file=sys.stderr)
    dst = os.path.join(outdir, MAIN)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
    print(f"{MAIN} {md5(out)}")


if __name__ == "__main__":
    main()
