import sys
root = sys.argv[1]


def patch(path, pairs):
    b = open(path, "rb").read()
    for old, new in pairs:
        if b.count(new) == 1 and b.count(old) == 0:
            print("already:", old[:50]); continue
        assert b.count(old) == 1, (path, old[:70], b.count(old))
        b = b.replace(old, new); print("ok:", old[:50])
    open(path, "wb").write(b)


patch(root + "/src/libs/audio.cpp", [
(b"""	bool     AudioOutHasDevice(Id handle);
""", b"""	bool     AudioOutHasDevice(Id handle);
	uint32_t AudioOutQueuedFrames(Id handle); // BC5 (experiment 0188)
"""),
(b"""bool Audio::AudioOutHasDevice(Id handle) {
	Common::LockGuard lock(m_mutex);

	return (handle.GetId() >= 0 && handle.GetId() < OUT_PORTS_MAX &&
	        m_out_ports[handle.GetId()].used && m_out_ports[handle.GetId()].audio_device != 0);
}
""", b"""bool Audio::AudioOutHasDevice(Id handle) {
	Common::LockGuard lock(m_mutex);

	return (handle.GetId() >= 0 && handle.GetId() < OUT_PORTS_MAX &&
	        m_out_ports[handle.GetId()].used && m_out_ports[handle.GetId()].audio_device != 0);
}

// BC5 (experiment 0188): the frames handed to the port's SDL device and not yet played (0 without one).
uint32_t Audio::AudioOutQueuedFrames(Id handle) {
	Common::LockGuard lock(m_mutex);

	if (handle.GetId() < 0 || handle.GetId() >= OUT_PORTS_MAX || !m_out_ports[handle.GetId()].used ||
	    m_out_ports[handle.GetId()].audio_device == 0) {
		return 0;
	}
	const auto&    port        = m_out_ports[handle.GetId()];
	const uint32_t frame_bytes = static_cast<uint32_t>(port.audio_spec.channels) * (SDL_AUDIO_BITSIZE(port.audio_spec.format) / 8u);
	return frame_bytes != 0 ? SDL_GetQueuedAudioSize(port.audio_device) / frame_bytes : 0;
}
"""),
(b"""bool AudioOutHasDevice(int handle) {
	return g_audio != nullptr && handle > 0 && g_audio->AudioOutHasDevice(Audio::Id(handle));
}
""", b"""bool AudioOutHasDevice(int handle) {
	return g_audio != nullptr && handle > 0 && g_audio->AudioOutHasDevice(Audio::Id(handle));
}

uint32_t AudioOutQueuedFrames(int handle) { // BC5 (experiment 0188)
	return g_audio != nullptr && handle > 0 ? g_audio->AudioOutQueuedFrames(Audio::Id(handle)) : 0;
}
"""),
])
patch(root + "/src/libs/audio_internal.h", [
(b"""bool     AudioOutHasDevice(int handle);
""", b"""bool     AudioOutHasDevice(int handle);
uint32_t AudioOutQueuedFrames(int handle); // BC5 (experiment 0188)
"""),
])
patch(root + "/src/libs/libAudio2.cpp", [
(b"""int KYTY_SYSV_ABI AudioOut2ContextGetQueueLevel(AudioOut2ContextHandle ctx, uint32_t* queue_level,
                                                uint32_t* available_queues) {
	Bc5Audio2Count(4); // experiment 0188
""", b"""// BC5 (experiment 0188): the audio handle of a context's port that has an SDL device (0 if none).
static int audioout2_context_device_handle(AudioOut2ContextHandle ctx) {
	int handle = 0;
	g_audioout2_port_mutex.Lock();
	for (const auto& port: g_audioout2_ports) {
		if (port.used && port.context == ctx && port.audio_handle > 0 && AudioInternal::AudioOutHasDevice(port.audio_handle)) {
			handle = port.audio_handle;
			break;
		}
	}
	g_audioout2_port_mutex.Unlock();
	return handle;
}

int KYTY_SYSV_ABI AudioOut2ContextGetQueueLevel(AudioOut2ContextHandle ctx, uint32_t* queue_level,
                                                uint32_t* available_queues) {
	Bc5Audio2Count(4); // experiment 0188
	// BC5 (experiment 0188): in the advanced model, a context that plays on a device counts the grains
	// its device has not played yet (SDL's queue, rounded up), not a timer, so the title renders exactly
	// as fast as the device plays (the timer lost time whenever the queue ran empty: 75-93 grains a
	// second instead of 93.75 in run M3).
	const int      bc5_device = Bc5Audio2Advanced() ? audioout2_context_device_handle(ctx) : 0;
	const uint32_t bc5_frames = bc5_device > 0 ? AudioInternal::AudioOutQueuedFrames(bc5_device) : 0;
"""),
(b"""		const uint32_t level = std::min<uint32_t>(
		    state->queue_depth, state->queued + static_cast<uint32_t>(state->advanced_mode ? state->advanced.size() : 0));""",
 b"""		const uint32_t grain  = state->num_grains == 0 ? 512u : state->num_grains;
		const uint32_t unplayed = (state->advanced_mode && bc5_device > 0) ? (bc5_frames + grain - 1) / grain : state->queued;
		const uint32_t level  = std::min<uint32_t>(
		    state->queue_depth, unplayed + static_cast<uint32_t>(state->advanced_mode ? state->advanced.size() : 0));"""),
])
print("done")
