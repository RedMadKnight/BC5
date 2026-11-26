#!/usr/bin/env python3
"""BC5 experiment 0401 series e4 (exp 0402, Top 10 item 2): the AnyPS5 AudioOut2 fixes after 7ba97f4 that our host lacks,
in the box tree's src/libs/libAudio2.cpp (KytyPlus f266548 + patch 0001; md5 fb44443e6f19f5d62c739cb39a7c377c), behind
KYTY_BC5_AUDIO_FIXES (on when set, non-empty and not "0", F767's reading; read once; off is today's path exactly).
Ported from AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762 and rewritten
for the grain model of experiment 0188:
  set      c34ab0258  core/libs/prx/libSceAudioOut/src/AudioOut2Port.cpp     a grain takes the PCM copied at the last set
  silence  11f217b14  core/libs/prx/libSceAudioOut/src/AudioOut2Port.cpp     a port not set again plays silence unless
                                                                             it was given a buffer once
  room     42beeaa46  core/libs/prx/libSceAudioOut/src/AudioOut2Context.cpp  a blocking push returns once there is room
                                                                             (here only where no port plays on a device)
A value naming parts ("set,room") turns on only those. b87075aad and ccaac6602 are not ported (aud0401-notes.md).
Only libAudio2.cpp is written. src/libs/audio.cpp and src/bc5/pad_audio_route.hpp (experiment 0372's pad audio route) are
read only: both must be there, audio.cpp with its 'exp 0372' lines; their md5s go to stderr. Each anchor must occur exactly
once; a tree with the edit already is refused; the count of 'exp 0372' in the edited file must not change; every edit keeps
braces and parentheses balanced; the output stays ASCII. Prints "<md5>  <relpath>" for the written file.
usage: mkaud0401.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/libs/libAudio2.cpp"
RO = ("src/libs/audio.cpp", "src/bc5/pad_audio_route.hpp")  # read only (experiment 0372)
EXPECT_IN = "fb44443e6f19f5d62c739cb39a7c377c"
MARKS = (b"KYTY_BC5_AUDIO_FIXES", b"Bc5AudioFixes", b"experiment 0401 series e4")
EXP0372 = b"exp 0372"


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    out = text.replace("»", "\t").encode("ascii")
    return out


# ---- the helpers, before audioout2_context_has_queueable_device (after the find/update helpers they use) ---------------
BLOCK_ANCHOR = b"static bool audioout2_context_has_queueable_device(AudioOut2ContextHandle ctx) {\n"
BLOCK = T(r"""// ---- experiment 0401 series e4: AnyPS5's AudioOut2 fixes after 7ba97f4 (exp 0402, Top 10 item 2) ----
// Ported from AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only), read at 4f41f4c375f5abb487dbd184fbc150f31994d762, and
// rewritten for this file's grain model (experiment 0188). Behind KYTY_BC5_AUDIO_FIXES; off is today's path exactly.
// - "set", c34ab0258 (core/libs/prx/libSceAudioOut/src/AudioOut2Port.cpp, AudioOut2CaptureGrain): a grain takes the PCM a
//   port was given at its last set, copied at that set; Advance read the buffer when it ran. AnyPS5's case: a title whose
//   Wwise clears its buffers after setting them and before Advance played silence.
// - "silence", 11f217b14 (same file, sceAudioOut2PortSetAttributes): a port not set since its last grain repeats its
//   buffer, read when the grain is taken, only if it was given a buffer once since it was created or cleared with a null
//   buffer; any other such port plays silence (zeros, so that its device keeps its pace). AnyPS5's case: a title that gives
//   a port the same buffer every grain, then none for ~350 ms while that memory is reused, played a loud burst of noise.
// - "room", 42beeaa46 (core/libs/prx/libSceAudioOut/src/AudioOut2Context.cpp, sceAudioOut2ContextPush and WaitForRoom): a
//   blocking push also waits after it queued its grain, until the queue has room again, at most 200 ms. Here only on the
//   timer path (no port of the context plays on a device): with a device the push already waits for the device's queue
//   before it queues (audio.cpp QueueSdlAudio, experiment 0180), and the level counts that queue beyond a two-grain
//   cushion (experiment 0188).
// Not ported: b87075aad and ccaac6602, the reopen of a default output or a controller sound card that SDL stopped (the pad
// ports' route of experiment 0372 reopens the controller's streams; SDL's PipeWire backend never stops the default
// output; experiment 0401 aud0401-notes.md).
// KYTY_BC5_AUDIO_FIXES: unset, empty or "0" is off; any other value turns all three on, unless it names parts
// (comma-separated "set", "silence", "room"): then only those. Read once; one stderr line at the first context.
// AnyPS5's copyright remains with its authors; GPL-2.0-only as the rest of this file.
static constexpr uint32_t BC5_AUDIO_FIX_SET          = 1u;     // c34ab0258
static constexpr uint32_t BC5_AUDIO_FIX_SILENCE      = 2u;     // 11f217b14
static constexpr uint32_t BC5_AUDIO_FIX_ROOM         = 4u;     // 42beeaa46
static constexpr uint64_t BC5_AUDIO_FIX_ROOM_WAIT_US = 200000; // AnyPS5's FULL_WAIT_TIMEOUT
static constexpr uint32_t BC5_AUDIO_FIX_ROOM_STEP_US = 1000;   // AnyPS5's FULL_WAIT_STEP

static uint32_t Bc5AudioFixesParse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»uint32_t    parts = 0;
»const char* p     = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»if (n == 3 && std::strncmp(p, "set", n) == 0) {
»»»parts |= BC5_AUDIO_FIX_SET;
»»} else if (n == 7 && std::strncmp(p, "silence", n) == 0) {
»»»parts |= BC5_AUDIO_FIX_SILENCE;
»»} else if (n == 4 && std::strncmp(p, "room", n) == 0) {
»»»parts |= BC5_AUDIO_FIX_ROOM;
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return parts != 0 ? parts : (BC5_AUDIO_FIX_SET | BC5_AUDIO_FIX_SILENCE | BC5_AUDIO_FIX_ROOM);
}

// The parts of KYTY_BC5_AUDIO_FIXES that are on (0: off), read once.
static uint32_t Bc5AudioFixes() {
»static const uint32_t parts = [] {
»»const uint32_t p = Bc5AudioFixesParse(std::getenv("KYTY_BC5_AUDIO_FIXES"));
»»if (p == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0401: audio fixes off\n");
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0401: audio fixes on:%s%s%s\n", (p & BC5_AUDIO_FIX_SET) != 0 ? " set" : "",
»»»             (p & BC5_AUDIO_FIX_SILENCE) != 0 ? " silence" : "", (p & BC5_AUDIO_FIX_ROOM) != 0 ? " room" : "");
»»}
»»std::fflush(stderr);
»»return p;
»}();
»return parts;
}

// The bytes of one grain of the port, as AudioOut2ContextAdvance copies them.
static size_t Bc5AudioFixesGrainBytes(const AudioOut2PortStateEntry& port) {
»const uint32_t channels    = audioout2_data_format_channels(port.data_format);
»const uint32_t sample_size = (port.data_format & 0x7fu) == 0 ? 4u : 2u;
»return static_cast<size_t>(port.samples_num) * channels * sample_size;
}

// "silence" took a grain of the port: one stderr line at the port's first such grain (at most 32 lines in a run), so that a
// run shows which ports the rule touches (the second title's vibration port is an AudioOut2 port, experiment 0372's P1).
static void Bc5AudioFixesTellSilence(AudioOut2PortStateEntry& port, const char* where) {
»static std::atomic<uint32_t> told {0};
»if (port.bc5_silence_told) {
»»return;
»}
»port.bc5_silence_told = true;
»if (told.fetch_add(1, std::memory_order_relaxed) >= 32) {
»»return;
»}
»std::fprintf(stderr, "[bc5] exp 0401: AudioOut2 port 0x%" PRIx64 " (type 0x%x, format 0x%08x): silence at %s, no buffer set since its last grain (the port's first)\n",
»             static_cast<uint64_t>(port.handle), static_cast<unsigned>(port.port_type), static_cast<unsigned>(port.data_format), where);
»std::fflush(stderr);
}

// AudioOut2PortSetAttributes gave the port `pcm` (under g_audioout2_port_mutex).
static void Bc5AudioFixesOnSet(AudioOut2PortStateEntry& port, const void* pcm) {
»const uint32_t parts = Bc5AudioFixes();
»if (parts == 0) {
»»return;
»}
»if (pcm == nullptr) { // cleared: the next buffer it is given counts as given once (11f217b14)
»»port.bc5_set_pending = false;
»»port.bc5_sets        = 0;
»»port.bc5_set_pcm.clear();
»»return;
»}
»port.bc5_set_pending = true;
»port.bc5_sets        = std::min<uint32_t>(port.bc5_sets + 1u, 2u); // only "once" and "more than once" matter
»if ((parts & BC5_AUDIO_FIX_SET) != 0 && port.audio_handle > 0) {
»»port.bc5_set_pcm.resize(Bc5AudioFixesGrainBytes(port));
»»std::memcpy(port.bc5_set_pcm.data(), pcm, port.bc5_set_pcm.size());
»}
}

// AudioOut2ContextAdvance takes the port's grain into `pcm`, sized for one grain (under g_audioout2_port_mutex). False:
// it reads the port's buffer now, as without the fixes.
static bool Bc5AudioFixesCaptureAtAdvance(AudioOut2PortStateEntry& port, std::vector<uint8_t>* pcm) {
»const uint32_t parts = Bc5AudioFixes();
»if (parts == 0) {
»»return false;
»}
»const bool pending   = port.bc5_set_pending;
»port.bc5_set_pending = false;
»if (pending) {
»»if ((parts & BC5_AUDIO_FIX_SET) != 0 && port.bc5_set_pcm.size() == pcm->size()) {
»»»std::memcpy(pcm->data(), port.bc5_set_pcm.data(), pcm->size());
»»»return true;
»»}
»»return false;
»}
»if ((parts & BC5_AUDIO_FIX_SILENCE) != 0 && port.bc5_sets != 1) {
»»std::memset(pcm->data(), 0, pcm->size());
»»Bc5AudioFixesTellSilence(port, "Advance");
»»return true;
»}
»return false;
}

// The push-time path (no advanced grain) takes the port's PCM: its buffer, read now (as AnyPS5 does outside its advanced
// mode), or silence (11f217b14). The port's buffer, pcm_data, when the fixes are off (under g_audioout2_port_mutex).
static const void* Bc5AudioFixesAtPush(AudioOut2PortStateEntry& port) {
»const uint32_t parts = Bc5AudioFixes();
»if (parts == 0) {
»»return port.pcm_data;
»}
»const bool pending   = port.bc5_set_pending;
»port.bc5_set_pending = false;
»if (!pending && (parts & BC5_AUDIO_FIX_SILENCE) != 0 && port.bc5_sets != 1) {
»»const size_t bytes = Bc5AudioFixesGrainBytes(port);
»»if (port.bc5_zero.size() != bytes) {
»»»port.bc5_zero.assign(bytes, uint8_t {0});
»»}
»»Bc5AudioFixesTellSilence(port, "Push");
»»return port.bc5_zero.data();
»}
»return port.pcm_data;
}

// A blocking push on the timer path (`timer_blocking`) waits after it queued its grain until the context's queue has
// room again, at most BC5_AUDIO_FIX_ROOM_WAIT_US (42beeaa46). It returns at once when "room" is off.
static void Bc5AudioFixesWaitForRoom(AudioOut2ContextHandle ctx, bool timer_blocking) {
»if (!timer_blocking || (Bc5AudioFixes() & BC5_AUDIO_FIX_ROOM) == 0) {
»»return;
»}
»const uint64_t start = LibKernel::KernelGetProcessTime();
»for (;;) {
»»bool room = true;
»»g_audioout2_context_mutex.Lock();
»»if (auto* state = audioout2_find_context_locked(ctx); state != nullptr) {
»»»audioout2_update_context_locked(state);
»»»room = state->queued < state->queue_depth;
»»}
»»g_audioout2_context_mutex.Unlock();
»»if (room || LibKernel::KernelGetProcessTime() - start > BC5_AUDIO_FIX_ROOM_WAIT_US) {
»»»return;
»»}
»»Common::Thread::SleepMicro(BC5_AUDIO_FIX_ROOM_STEP_US);
»}
}

// For the CPU test aud0401.cpp of experiment 0401 only; the emulator never calls it. Copies what the advanced grain
// `index` (0: the oldest not yet pushed) of context `ctx` holds for the port `port` into `out`, at most `size` bytes.
// Returns the grain's bytes for that port; -1: no such context or grain; -2: the grain holds nothing of the port.
int64_t Bc5AudioFixesPeekGrain(AudioOut2ContextHandle ctx, size_t index, AudioOut2PortHandle port, void* out, size_t size);
int64_t Bc5AudioFixesPeekGrain(AudioOut2ContextHandle ctx, size_t index, AudioOut2PortHandle port, void* out, size_t size) {
»int audio_handle = 0;
»g_audioout2_port_mutex.Lock();
»if (const auto* p = audioout2_find_port_locked(port); p != nullptr) {
»»audio_handle = p->audio_handle;
»}
»g_audioout2_port_mutex.Unlock();
»int64_t result = -1;
»g_audioout2_context_mutex.Lock();
»if (const auto* state = audioout2_find_context_locked(ctx); state != nullptr && index < state->advanced.size()) {
»»result = -2;
»»for (const auto& c: state->advanced[index]) {
»»»if (audio_handle > 0 && c.audio_handle == audio_handle) {
»»»»if (out != nullptr && size != 0) {
»»»»»std::memcpy(out, c.pcm.data(), std::min(size, c.pcm.size()));
»»»»}
»»»»result = static_cast<int64_t>(c.pcm.size());
»»»»break;
»»»}
»»}
»}
»g_audioout2_context_mutex.Unlock();
»return result;
}
// ---- end of experiment 0401 series e4's helpers ----

""")

# ---- the small edits: (what, old, new); each old must occur exactly once ------------------------------------------------
EDITS = (
    ("include <cstdlib>",
     T("#include <cstdio>\n#include <cstring>\n"),
     T("#include <cstdio>\n#include <cstdlib> // experiment 0401 series e4: std::getenv\n#include <cstring>\n")),
    ("the port's state",
     T("»std::vector<float>     downmix;      // BC5: 12-channel float ports, mixed down to 8 channels\n};\n"),
     T("»std::vector<float>     downmix;      // BC5: 12-channel float ports, mixed down to 8 channels\n"
       "»// experiment 0401 series e4 (KYTY_BC5_AUDIO_FIXES; used only when it is on)\n"
       "»bool                   bc5_set_pending = false; // given a buffer since its last grain\n"
       "»uint32_t               bc5_sets        = 0;     // buffers given since created or cleared (a null set), at most 2\n"
       "»std::vector<uint8_t>   bc5_set_pcm;             // the grain copied at the last set (\"set\")\n"
       "»std::vector<uint8_t>   bc5_zero;                // one grain of silence for the push-time path (\"silence\")\n"
       "»bool                   bc5_silence_told = false; // its first silenced grain was reported\n"
       "};\n")),
    ("the push-time path (audioout2_queue_context_audio)",
     T("»»»const void* data = state.pcm_data;\n"
       "»»»if (audioout2_is_float12(state.data_format)) {\n"
       "»»»»data = audioout2_downmix_12_to_8(state.downmix, state.pcm_data, state.samples_num);\n"
       "»»»}\n"),
     T("»»»// experiment 0401 series e4: state.pcm_data when KYTY_BC5_AUDIO_FIXES is off; else that or silence\n"
       "»»»const void* data = Bc5AudioFixesAtPush(state);\n"
       "»»»if (audioout2_is_float12(state.data_format)) {\n"
       "»»»»data = audioout2_downmix_12_to_8(state.downmix, data, state.samples_num); // experiment 0401 series e4: data (was state.pcm_data)\n"
       "»»»}\n")),
    ("AudioOut2ContextCreate: the switch's line",
     T("                                         size_t buffer_size, AudioOut2ContextHandle* ctx) {\n"
       "»PRINT_NAME();\n"),
     T("                                         size_t buffer_size, AudioOut2ContextHandle* ctx) {\n"
       "»PRINT_NAME();\n"
       "»(void)Bc5AudioFixes(); // experiment 0401 series e4: reads KYTY_BC5_AUDIO_FIXES once and prints its line, on or off\n")),
    ("AudioOut2ContextAdvance: the loop",
     T("»g_audioout2_port_mutex.Lock();\n"
       "»for (const auto& port: g_audioout2_ports) {\n"
       "»»if (!port.used || port.context != ctx || port.audio_handle <= 0 || port.pcm_data == nullptr) {\n"),
     T("»g_audioout2_port_mutex.Lock();\n"
       "»for (auto& port: g_audioout2_ports) { // experiment 0401 series e4: not const (the fixes mark the port's grain as taken)\n"
       "»»if (!port.used || port.context != ctx || port.audio_handle <= 0 || port.pcm_data == nullptr) {\n")),
    ("AudioOut2ContextAdvance: the copy",
     T("»»std::memcpy(c.pcm.data(), port.pcm_data, c.pcm.size());\n"
       "»»grain.push_back(std::move(c));\n"),
     T("»»if (!Bc5AudioFixesCaptureAtAdvance(port, &c.pcm)) { // experiment 0401 series e4: false when KYTY_BC5_AUDIO_FIXES is off\n"
       "»»»std::memcpy(c.pcm.data(), port.pcm_data, c.pcm.size());\n"
       "»»}\n"
       "»»grain.push_back(std::move(c));\n")),
    ("AudioOut2ContextPush: an advanced grain",
     T("»»»»»audioout2_output_grain(grain, blocking != 0);\n"
       "»»»»»return OK;\n"),
     T("»»»»»audioout2_output_grain(grain, blocking != 0);\n"
       "»»»»»Bc5AudioFixesWaitForRoom(ctx, blocking != 0 && !use_device_clock); // experiment 0401 series e4 (42beeaa46); at once when off\n"
       "»»»»»return OK;\n")),
    ("AudioOut2ContextPush: the ports' PCM",
     T("»»»»audioout2_queue_context_audio(ctx, blocking != 0);\n"
       "»»»»return OK;\n"),
     T("»»»»audioout2_queue_context_audio(ctx, blocking != 0);\n"
       "»»»»Bc5AudioFixesWaitForRoom(ctx, blocking != 0 && !use_device_clock); // experiment 0401 series e4 (42beeaa46); at once when off\n"
       "»»»»return OK;\n")),
    ("AudioOut2PortSetAttributes",
     T("»»»state->pcm_data = pcm_data;\n"),
     T("»»»state->pcm_data = pcm_data;\n"
       "»»»Bc5AudioFixesOnSet(*state, pcm_data); // experiment 0401 series e4: nothing when KYTY_BC5_AUDIO_FIXES is off\n")),
)

# Definitions the helpers use must come before the block; the functions that call the helpers come after it.
BEFORE_BLOCK = (b"static uint8_t audioout2_data_format_channels(uint32_t data_format) {\n",
                b"static void audioout2_update_context_locked(AudioOut2ContextState* state) {\n",
                b"static AudioOut2PortStateEntry* audioout2_find_port_locked(AudioOut2PortHandle port) {\n",
                b"static AudioOut2ContextState* audioout2_find_context_locked(AudioOut2ContextHandle ctx) {\n",
                b"static Common::Mutex                              g_audioout2_context_mutex;\n")
AFTER_BLOCK = (b"static void audioout2_queue_context_audio(AudioOut2ContextHandle ctx, bool blocking) {\n",
               b"int KYTY_SYSV_ABI AudioOut2ContextCreate(",
               b"int KYTY_SYSV_ABI AudioOut2ContextAdvance(",
               b"int KYTY_SYSV_ABI AudioOut2ContextPush(",
               b"int KYTY_SYSV_ABI AudioOut2PortSetAttributes(")


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def once(s, old, new, what):
    assert s.count(old) == 1, (what, old[:80], s.count(old))
    assert balance(old) == balance(new), ("the edit changes the balance", what, balance(old), balance(new))
    return s.replace(old, new)


def edit(s):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", m)
    s.decode("ascii")  # the box's unit is ASCII; so must the output be
    assert balance(BLOCK) == (0, 0, 0), ("the block is not balanced", balance(BLOCK))
    assert s.count(BLOCK_ANCHOR) == 1, ("the block's anchor", s.count(BLOCK_ANCHOR))
    at = s.index(BLOCK_ANCHOR)
    for b in BEFORE_BLOCK:
        assert s.count(b) == 1 and s.index(b) < at, ("must be defined before the block, once", b[:70], s.count(b))
    for b in AFTER_BLOCK:
        assert s.count(b) == 1 and s.index(b) > at, ("must come after the block, once", b[:70], s.count(b))
    n0372 = s.count(EXP0372)
    out = s.replace(BLOCK_ANCHOR, BLOCK + BLOCK_ANCHOR)
    for what, old, new in EDITS:
        out = once(out, old, new, what)
    assert out.count(EXP0372) == n0372, ("the count of 'exp 0372' changed", n0372, out.count(EXP0372))
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    out.decode("ascii")
    # Every helper is defined once and used where the edits put it.
    for name, uses in ((b"static uint32_t Bc5AudioFixes()", 1), (b"Bc5AudioFixesOnSet(", 2), (b"Bc5AudioFixesCaptureAtAdvance(", 2),
                       (b"Bc5AudioFixesAtPush(", 2), (b"Bc5AudioFixesWaitForRoom(", 3), (b"Bc5AudioFixesPeekGrain(", 2),
                       (b"Bc5AudioFixesTellSilence(", 3)):
        assert out.count(name) == uses, (name, out.count(name), uses)
    return out, n0372


def md5(b):
    return hashlib.md5(b).hexdigest()


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    src = os.path.join(root, REL)
    with open(src, "rb") as f:
        s = f.read()
    print(f"# in:  {md5(s)}  {REL}{'' if md5(s) == EXPECT_IN else '  (not the expected ' + EXPECT_IN + ')'}", file=sys.stderr)
    for rel in RO:
        p = os.path.join(root, rel)
        assert os.path.isfile(p), ("experiment 0372's file is missing from the tree", rel)
        with open(p, "rb") as f:
            b = f.read()
        if rel.endswith("audio.cpp"):
            assert b.count(EXP0372) > 0, "audio.cpp has no 'exp 0372' lines: not the tree with experiment 0372's route"
        print(f"# read only: {md5(b)}  {rel}  ('exp 0372' x{b.count(EXP0372)}; not written)", file=sys.stderr)
    out, n0372 = edit(s)
    dst = os.path.join(outdir, REL)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
    print(f"# 'exp 0372' in {REL}: {n0372} before and after", file=sys.stderr)
    print(f"{md5(out)}  {REL}")


if __name__ == "__main__":
    main()
