# BC5 exp 0439 (tag fz439): the audio catcher for the third title's SIGFPE (README item 42: the Scream audio engine's thread
# divides by a zero field). Private units from the shared tree's src/libs/ajm.cpp (md5 971b3d66) and src/libs/libAudio2.cpp
# (md5 1ed2731a). BC5_0439_AUDIO_CATCH=1 (off by default):
#   - every AJM and AudioOut2 entry point notes its name (and for some, its arguments and answers) into a ring of the
#     calling host thread's last 20 calls; bc5_fz439_dump() prints the calling thread's ring (gdb calls it at the SIGFPE,
#     k439/fpe439.gdb, on the faulting thread);
#   - an answer with a zero where a size or a rate belongs is also printed at once as a "ZERO" line (at most 400): AJM codec
#     info (any zero word), AJM format (channel count or sampling frequency 0), AjmDecAt9ParseConfigData (its result and the
#     info it leaves), AudioOut2 context and port parameters (grains, queue depth, sampling frequency 0), port state (0
#     channels).
# Off: no change. Not for lean.
#   python mkfz439.py <dir with ajm.cpp and libAudio2.cpp> <out dir>
import hashlib
import os
import sys

src, dst = sys.argv[1], sys.argv[2]


def load(name, md5):
    b = open(os.path.join(src, name), 'rb').read()
    assert hashlib.md5(b).hexdigest().startswith(md5), (name, hashlib.md5(b).hexdigest())
    t = b.decode('utf-8')
    assert '\r' not in t
    return t


def rep(t, a, b, n=1):
    assert t.count(a) == n, (a[:80], t.count(a))
    return t.replace(a, b)


DECL = 'extern "C" void bc5_fz439_note(int zero, const char* fmt, ...); // exp 0439 (tag fz439), defined in ajm.cpp\n'

RING = r'''
// ---- exp 0439 (tag fz439): BC5_0439_AUDIO_CATCH=1, the audio catcher (k439/mkfz439.py) ----
namespace {
struct Fz439Ring {
	char     line[20][240];
	unsigned n = 0;
};
thread_local Fz439Ring t_fz439;
bool fz439_on() {
	static const bool v = [] {
		const char* e  = std::getenv("BC5_0439_AUDIO_CATCH");
		const bool  on = e != nullptr && e[0] == '1' && e[1] == 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag fz439): BC5_0439_AUDIO_CATCH=%d\n", on ? 1 : 0);
		return on;
	}();
	return v;
}
double fz439_now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
} // namespace
extern "C" void bc5_fz439_note(int zero, const char* fmt, ...) {
	if (!fz439_on()) return;
	char    body[200];
	va_list ap;
	va_start(ap, fmt);
	std::vsnprintf(body, sizeof(body), fmt, ap);
	va_end(ap);
	char name[32] = "?";
	pthread_getname_np(pthread_self(), name, sizeof(name));
	const double t = fz439_now();
	auto&        r = t_fz439;
	std::snprintf(r.line[r.n % 20], sizeof(r.line[0]), "%.3f %s: %s", t, name, body);
	r.n++;
	if (zero != 0) {
		static std::atomic<int> k {0};
		if (k++ < 400) std::fprintf(stderr, "[bc5] exp 0439 (tag fz439): ZERO %.3f %s: %s\n", t, name, body);
	}
}
// gdb: call (void)bc5_fz439_dump() on the faulting thread (k439/fpe439.gdb)
extern "C" __attribute__((used, noinline)) void bc5_fz439_dump() {
	auto& r       = t_fz439;
	char  name[32] = "?";
	pthread_getname_np(pthread_self(), name, sizeof(name));
	std::fprintf(stderr, "[bc5] exp 0439 (tag fz439): now %.3f; the last %u AJM/AudioOut2 calls of thread %s (%u in all):\n", fz439_now(), r.n < 20 ? r.n : 20u, name, r.n);
	for (unsigned k = r.n > 20 ? r.n - 20 : 0; k < r.n; k++) std::fprintf(stderr, "[bc5] exp 0439 (tag fz439):   %s\n", r.line[k % 20]);
	std::fflush(stderr);
}
static void fz439_words(const char* what, const void* decoder, uint64_t flags, const void* p, size_t bytes) {
	if (!fz439_on() || p == nullptr) return;
	const auto* w = static_cast<const uint32_t*>(p);
	char        s[120];
	int         o    = 0;
	int         zero = 0;
	s[0]             = 0;
	for (size_t q = 0; q < bytes / 4 && q < 8 && o < 100; q++) {
		zero |= w[q] == 0 ? 1 : 0;
		o += std::snprintf(s + o, sizeof(s) - static_cast<size_t>(o), " %u", w[q]);
	}
	bc5_fz439_note(zero, "%s decoder %p flags 0x%llx codec-info words:%s", what, decoder, static_cast<unsigned long long>(flags), s);
}
static void fz439_format(const char* what, const void* decoder, uint64_t flags, const void* p) {
	if (!fz439_on() || p == nullptr) return;
	const auto* w = static_cast<const uint32_t*>(p); // channel_num, channel_mask, sampling_frequency, sample_encoding, bitrate
	bc5_fz439_note(w[0] == 0 || w[2] == 0 ? 1 : 0, "%s decoder %p flags 0x%llx format: channels %u mask 0x%x rate %u encoding %u bitrate %u", what, decoder,
	               static_cast<unsigned long long>(flags), w[0], w[1], w[2], w[3], w[4]);
}
'''


def notes(t):
    # every entry point: its name into the thread's ring, after PRINT_NAME()
    return t.replace('\tPRINT_NAME();\n', '\tPRINT_NAME();\n\tbc5_fz439_note(0, "%s", __func__); // exp 0439 (tag fz439)\n')


# ---- ajm.cpp ----
a = load('ajm.cpp', '971b3d66')
a = rep(a, '#include <map>\n', '#include <map>\n#include <atomic>  // exp 0439 (tag fz439)\n#include <chrono>\n#include <cstdarg>\n#include <cstdio>\n#include <cstdlib>\n#include <pthread.h>\n' + DECL)
a = notes(a)
a = rep(a, 'static void AjmWriteResult(void* result, size_t size, const AjmDecodeResult& decode_result = {}) {', RING + '\nstatic void AjmWriteResult(void* result, size_t size, const AjmDecodeResult& decode_result = {}) {')
# AjmDecAt9ParseConfigData: the config bytes, the result and the info it leaves
a = rep(a, '''	if (info_result != 0 || codec_info.channels <= 0 || codec_info.samplingRate <= 0 ||
	    codec_info.frameSamples <= 0 || codec_info.framesInSuperframe <= 0 ||
	    codec_info.superframeSize <= 0) {
		return AJM_ERROR_INVALID_PARAMETER;
	}''', '''	if (info_result != 0 || codec_info.channels <= 0 || codec_info.samplingRate <= 0 ||
	    codec_info.frameSamples <= 0 || codec_info.framesInSuperframe <= 0 ||
	    codec_info.superframeSize <= 0) {
		bc5_fz439_note(1, "AjmDecAt9ParseConfigData config %02x %02x %02x %02x: INVALID_PARAMETER (init %d, info %d); the caller's info left as it was", config[0], config[1], config[2], config[3], init_result, info_result); // exp 0439 (tag fz439)
		return AJM_ERROR_INVALID_PARAMETER;
	}''')
a = rep(a, '''	config_info->superframe_size = static_cast<uint32_t>(codec_info.superframeSize);
	return OK;''', '''	config_info->superframe_size = static_cast<uint32_t>(codec_info.superframeSize);
	bc5_fz439_note(0, "AjmDecAt9ParseConfigData config %02x %02x %02x %02x: channels %u rate %u frame %u superframe samples %u size %u", config[0], config[1], config[2], config[3], config_info->channels, config_info->sample_rate,
	               config_info->frame_samples_per_channel, config_info->superframe_samples_per_channel, config_info->superframe_size); // exp 0439 (tag fz439)
	return OK;''')
# the sideband writer: codec info and format as written
a = rep(a, '''			decoder->WriteCodecInfo(static_cast<uint8_t*>(sideband_output) + offset,
			                        sideband_output_size - offset, decode_result);''', '''			decoder->WriteCodecInfo(static_cast<uint8_t*>(sideband_output) + offset,
			                        sideband_output_size - offset, decode_result);
			fz439_words("sideband", decoder, flags, static_cast<uint8_t*>(sideband_output) + offset, codec_info_size); // exp 0439 (tag fz439)''')
a = rep(a, '''		*format = decode_result.format;
		offset += AJM_SIDEBAND_FORMAT_SIZE;''', '''		*format = decode_result.format;
		fz439_format("sideband", decoder, flags, format); // exp 0439 (tag fz439)
		offset += AJM_SIDEBAND_FORMAT_SIZE;''')
a = rep(a, '''	AjmWriteFormat(result, AJM_SIDEBAND_RESULT_SIZE + AJM_SIDEBAND_FORMAT_SIZE, format,
	               decode_result);
''', '''	AjmWriteFormat(result, AJM_SIDEBAND_RESULT_SIZE + AJM_SIDEBAND_FORMAT_SIZE, format,
	               decode_result);
	if (result != nullptr) fz439_format("get-info", nullptr, instance, static_cast<uint8_t*>(result) + AJM_SIDEBAND_RESULT_SIZE); // exp 0439 (tag fz439): "flags" = the instance
''')
a = rep(a, '''	AjmWriteCodecInfo(decoder, result, result_size, decode_result);
''', '''	AjmWriteCodecInfo(decoder, result, result_size, decode_result);
	if (decoder != nullptr && result != nullptr && result_size > AJM_SIDEBAND_RESULT_SIZE) // exp 0439 (tag fz439): "flags" = the instance
		fz439_words("get-codec-info", decoder, instance, static_cast<uint8_t*>(result) + AJM_SIDEBAND_RESULT_SIZE, decoder->CodecInfoSize());
''')

# ---- libAudio2.cpp ----
u = load('libAudio2.cpp', '1ed2731a')
u = rep(u, '#include <vector>\n', '#include <vector>\n' + DECL)
u = notes(u)
u = rep(u, '''	EXIT_NOT_IMPLEMENTED(ctx == nullptr);

	*ctx = g_audioout2_next_context.fetch_add(1, std::memory_order_relaxed);''', '''	EXIT_NOT_IMPLEMENTED(ctx == nullptr);
	bc5_fz439_note(params->num_grains == 0 || params->queue_depth == 0 ? 1 : 0, "AudioOut2ContextCreate max_ports %u object %u queue_depth %u num_grains %u flags 0x%x buffer_size %zu", params->max_ports, params->max_object_ports, params->queue_depth,
	               params->num_grains, params->flags, buffer_size); // exp 0439 (tag fz439)

	*ctx = g_audioout2_next_context.fetch_add(1, std::memory_order_relaxed);''')
u = rep(u, '''	EXIT_NOT_IMPLEMENTED(params == nullptr);
	EXIT_NOT_IMPLEMENTED(port == nullptr);

	const auto next_port    = g_audioout2_next_port.fetch_add(1, std::memory_order_relaxed);''', '''	EXIT_NOT_IMPLEMENTED(params == nullptr);
	EXIT_NOT_IMPLEMENTED(port == nullptr);
	bc5_fz439_note(params->sampling_freq == 0 ? 1 : 0, "AudioOut2PortCreate ctx %llu type %u data_format 0x%x sampling_freq %u flags 0x%x", static_cast<unsigned long long>(ctx), params->port_type, params->data_format, params->sampling_freq,
	               params->flags); // exp 0439 (tag fz439)

	const auto next_port    = g_audioout2_next_port.fetch_add(1, std::memory_order_relaxed);''')
u = rep(u, '''	// LOGF("\\t port = 0x%016" PRIx64 "\\n", port);
	// LOGF("\\t num_channels = %" PRIu8 "\\n", state->num_channels);
''', '''	bc5_fz439_note(state->num_channels == 0 ? 1 : 0, "AudioOut2PortGetState port %llu: output %u channels %u volume %d", static_cast<unsigned long long>(port), state->output, state->num_channels, state->volume); // exp 0439 (tag fz439)
''')
u = rep(u, '''int KYTY_SYSV_ABI AudioOut2GetSpeakerInfo(AudioOut2SpeakerInfo* info, uint32_t flags) {
	EXIT_NOT_IMPLEMENTED(info == nullptr);''', '''int KYTY_SYSV_ABI AudioOut2GetSpeakerInfo(AudioOut2SpeakerInfo* info, uint32_t flags) {
	bc5_fz439_note(0, "AudioOut2GetSpeakerInfo flags 0x%x: type 0, available_bits 0x3", flags); // exp 0439 (tag fz439)
	EXIT_NOT_IMPLEMENTED(info == nullptr);''')
u = rep(u, '''int KYTY_SYSV_ABI AudioOut2PortCreate(AudioOut2ContextHandle ctx, const AudioOut2PortParam* params,
                                      AudioOut2PortHandle* port) {
''', '''int KYTY_SYSV_ABI AudioOut2PortCreate(AudioOut2ContextHandle ctx, const AudioOut2PortParam* params,
                                      AudioOut2PortHandle* port) {
	bc5_fz439_note(0, "%s", __func__); // exp 0439 (tag fz439): no PRINT_NAME here
''')

for name, t in (('ajm.cpp', a), ('libAudio2.cpp', u)):
    for k, line in enumerate(t.split('\n')):
        if 'fz439' in line and line.count('"') % 2 != 0 and not line.rstrip().endswith('\\'):
            raise SystemExit('%s:%d: odd quotes in a fz439 line' % (name, k + 1))
    os.makedirs(dst, exist_ok=True)
    open(os.path.join(dst, name), 'wb').write(t.encode('utf-8'))
print('fz439: ajm.cpp %d notes, libAudio2.cpp %d notes' % (a.count('bc5_fz439_note('), u.count('bc5_fz439_note(')))
