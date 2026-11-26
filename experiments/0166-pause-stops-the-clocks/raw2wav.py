"""raw2wav.py <raw> <out.wav> <channels> <rate> <f32|s16> [downmix-to-stereo]
Converts a raw PCM dump of the host's audio port into a WAV. f32 input is converted to s16;
with the 6th argument the first two channels are kept (front left/right)."""
import sys, struct, wave, array
raw, out, ch, rate, fmt = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
stereo = len(sys.argv) > 6
data = open(raw, "rb").read()
if fmt == "f32":
    n = len(data) // 4
    f = array.array("f"); f.frombytes(data[: n * 4])
    s = array.array("h", (max(-32768, min(32767, int(v * 32767))) for v in f))
else:
    s = array.array("h"); s.frombytes(data[: (len(data) // 2) * 2])
frames = len(s) // ch
if stereo and ch > 2:
    o = array.array("h")
    for i in range(frames):
        o.append(s[i * ch]); o.append(s[i * ch + 1])
    s, ch = o, 2
w = wave.open(out, "wb"); w.setnchannels(ch); w.setsampwidth(2); w.setframerate(rate); w.writeframes(s.tobytes()); w.close()
print(out, "frames", frames, "seconds %.1f" % (frames / rate), "channels", ch)
