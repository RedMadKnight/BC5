import sys
root = sys.argv[1]
p = root + "/src/libs/libAudio2.cpp"
b = open(p, "rb").read()


def rep(old, new):
    global b
    if b.count(new) == 1 and b.count(old) == 0:
        print("already:", old[:40]); return
    assert b.count(old) == 1, (old[:70], b.count(old))
    b = b.replace(old, new); print("ok:", old[:40])


rep(b"#include <cstring>\n#include <vector>\n", b"#include <cstring>\n#include <deque>\n#include <vector>\n")

rep(b"""	uint32_t               num_grains  = 512;
	uint64_t               last_update = 0;
};
""", b"""	uint32_t               num_grains  = 512;
	uint64_t               last_update = 0;
	// BC5 (experiment 0188): grains the title advanced (rendered) and has not pushed yet, each a copy of
	// its ports' PCM at the advance, oldest first; see Bc5Audio2Advanced().
	struct Bc5Captured {
		int                  audio_handle = 0;
		uint32_t             data_format  = 0;
		uint32_t             frames       = 0;
		std::vector<uint8_t> pcm;
	};
	bool                                  advanced_mode = false;
	std::deque<std::vector<Bc5Captured>>  advanced;
};

// BC5 (experiment 0188): the AudioOut2 grain model of AnyPS5 (github.com/boykopovar/AnyPS5 27c88a8,
// core/libs/prx/libSceAudioOut/src/AudioOut2Context.cpp sceAudioOut2ContextAdvance / Push /
// GetQueueLevel and src/AudioOut2Port.cpp AudioOut2CaptureGrain, GPL-2.0; rewritten here). Advance
// copies each port's PCM into a grain, Push plays the oldest copied grain, and the queue level counts
// the grains advanced and not yet pushed. The second title's Wwise sink renders as many grains as the
// level leaves free and pushes on another thread (AnyPS5 docs/dev/debt/libSceAudioOut.md); with the
// pushed grains alone counted, it advanced up to 2.65 grains for every grain played and its music and
// timeline ran that much fast (experiment 0188, run M2). KYTY_BC5_AUDIO2_ADVANCED=1.
static bool Bc5Audio2Advanced() {
	static const bool on = [] {
		const char* e = std::getenv("KYTY_BC5_AUDIO2_ADVANCED");
		return e != nullptr && std::atoi(e) != 0;
	}();
	return on;
}
static constexpr size_t BC5_AUDIO2_ADVANCED_MAX = 64; // grains kept at most (oldest dropped beyond)
""")

rep(b"""int KYTY_SYSV_ABI AudioOut2ContextAdvance(AudioOut2ContextHandle ctx) {
	Bc5Audio2Count(2); // experiment 0188
	g_audioout2_context_mutex.Lock();
	if (auto* state = audioout2_find_context_locked(ctx); state != nullptr) {
		audioout2_update_context_locked(state);
	}
	g_audioout2_context_mutex.Unlock();
""", b"""int KYTY_SYSV_ABI AudioOut2ContextAdvance(AudioOut2ContextHandle ctx) {
	Bc5Audio2Count(2); // experiment 0188
	std::vector<AudioOut2ContextState::Bc5Captured> grain;
	if (Bc5Audio2Advanced()) {
		g_audioout2_port_mutex.Lock();
		for (const auto& port: g_audioout2_ports) {
			if (!port.used || port.context != ctx || port.audio_handle <= 0 || port.pcm_data == nullptr) {
				continue;
			}
			const uint32_t channels    = audioout2_data_format_channels(port.data_format);
			const uint32_t sample_size = (port.data_format & 0x7fu) == 0 ? 4u : 2u;
			AudioOut2ContextState::Bc5Captured c;
			c.audio_handle = port.audio_handle;
			c.data_format  = port.data_format;
			c.frames       = port.samples_num;
			c.pcm.resize(static_cast<size_t>(port.samples_num) * channels * sample_size);
			std::memcpy(c.pcm.data(), port.pcm_data, c.pcm.size());
			grain.push_back(std::move(c));
		}
		g_audioout2_port_mutex.Unlock();
	}
	g_audioout2_context_mutex.Lock();
	if (auto* state = audioout2_find_context_locked(ctx); state != nullptr) {
		audioout2_update_context_locked(state);
		if (Bc5Audio2Advanced()) {
			state->advanced_mode = true;
			state->advanced.push_back(std::move(grain));
			while (state->advanced.size() > BC5_AUDIO2_ADVANCED_MAX) {
				state->advanced.pop_front();
			}
		}
	}
	g_audioout2_context_mutex.Unlock();
""")

rep(b"""int KYTY_SYSV_ABI AudioOut2ContextPush(AudioOut2ContextHandle ctx, uint32_t blocking) {
	Bc5Audio2Count(3); // experiment 0188
	uint32_t sleep_micros = audioout2_grain_micros(512);

	for (;;) {""", b"""// BC5 (experiment 0188): one advanced grain to the device, the copies made at the advance.
static void audioout2_output_grain(const std::vector<AudioOut2ContextState::Bc5Captured>& grain, bool blocking) {
	std::vector<AudioInternal::OutputParam> params;
	std::vector<std::vector<float>>         downmix(grain.size());
	for (size_t i = 0; i < grain.size() && params.size() < AudioInternal::OUT_PORTS_MAX; i++) {
		const auto& c    = grain[i];
		const void* data = c.pcm.data();
		if (audioout2_is_float12(c.data_format)) {
			data = audioout2_downmix_12_to_8(downmix[i], c.pcm.data(), c.frames);
		}
		params.push_back(AudioInternal::OutputParam {c.audio_handle, data});
	}
	if (!params.empty()) {
		(void)AudioInternal::AudioOutOutputs(params.data(), static_cast<uint32_t>(params.size()), blocking);
	}
}

int KYTY_SYSV_ABI AudioOut2ContextPush(AudioOut2ContextHandle ctx, uint32_t blocking) {
	Bc5Audio2Count(3); // experiment 0188
	uint32_t sleep_micros = audioout2_grain_micros(512);

	// BC5 (experiment 0188): in the advanced model a blocking push waits (up to 200 ms) for a grain the
	// title advanced, as AnyPS5 does; after that it plays the ports' current PCM as before.
	if (Bc5Audio2Advanced() && blocking != 0) {
		for (int waited = 0; waited < 400; waited++) {
			bool ready = true;
			g_audioout2_context_mutex.Lock();
			if (auto* state = audioout2_find_context_locked(ctx); state != nullptr) {
				ready = !state->advanced_mode || !state->advanced.empty();
			}
			g_audioout2_context_mutex.Unlock();
			if (ready) {
				break;
			}
			Common::Thread::SleepMicro(500);
		}
	}

	for (;;) {""")

rep(b"""				if (state->queued < state->queue_depth) {
					state->queued++;
				}
				g_audioout2_context_mutex.Unlock();
				audioout2_queue_context_audio(ctx, blocking != 0);
				return OK;""", b"""				if (state->queued < state->queue_depth) {
					state->queued++;
				}
				if (state->advanced_mode && !state->advanced.empty()) { // experiment 0188
					auto grain = std::move(state->advanced.front());
					state->advanced.pop_front();
					g_audioout2_context_mutex.Unlock();
					audioout2_output_grain(grain, blocking != 0);
					return OK;
				}
				g_audioout2_context_mutex.Unlock();
				audioout2_queue_context_audio(ctx, blocking != 0);
				return OK;""")

rep(b"""		if (queue_level != nullptr) {
			*queue_level = state->queued;
			g_bc5_a2_level_sum += state->queued; // experiment 0188
			for (uint32_t m = g_bc5_a2_level_max.load(); state->queued > m && !g_bc5_a2_level_max.compare_exchange_weak(m, state->queued);) {
			}
		}
		if (available_queues != nullptr) {
			*available_queues =
			    (state->queued < state->queue_depth ? state->queue_depth - state->queued : 0);
		}""", b"""		// BC5 (experiment 0188): the advanced and not yet pushed grains count as queued (advanced model).
		const uint32_t level = std::min<uint32_t>(
		    state->queue_depth, state->queued + static_cast<uint32_t>(state->advanced_mode ? state->advanced.size() : 0));
		if (queue_level != nullptr) {
			*queue_level = level;
			g_bc5_a2_level_sum += level; // experiment 0188
			for (uint32_t m = g_bc5_a2_level_max.load(); level > m && !g_bc5_a2_level_max.compare_exchange_weak(m, level);) {
			}
		}
		if (available_queues != nullptr) {
			*available_queues = state->queue_depth - level;
		}""")
open(p, "wb").write(b)
print("done")
