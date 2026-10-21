import sys
root = sys.argv[1]
p = root + "/src/libs/libAudio2.cpp"
b = open(p, "rb").read()
old = b"""		const uint32_t unplayed = (state->advanced_mode && bc5_device > 0) ? (bc5_frames + grain - 1) / grain : state->queued;"""
new = b"""		// The first grains in the device are its own latency, not the queue (AnyPS5 counts the unplayed grains
		// beyond a 40-ms cushion): KYTY_BC5_AUDIO2_CUSHION grains, default 2. Counting all of them left the
		// device short 2.6 % of the time (run M4).
		static const uint32_t cushion = [] {
			const char* e = std::getenv("KYTY_BC5_AUDIO2_CUSHION");
			return e != nullptr ? static_cast<uint32_t>(std::atoi(e)) : 2u;
		}();
		const uint32_t device_grains = (bc5_frames + grain - 1) / grain;
		const uint32_t unplayed      = (state->advanced_mode && bc5_device > 0) ? (device_grains > cushion ? device_grains - cushion : 0u) : state->queued;"""
if b.count(new) == 0:
    assert b.count(old) == 1
    b = b.replace(old, new)
open(p, "wb").write(b)
print("ok")
