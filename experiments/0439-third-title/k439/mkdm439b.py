#!/usr/bin/env python3
# BC5 exp 0439 bake 2 (tag dm439, F892): ATRAC9 DMC configurations for every title, on the SHARED tree's units (not on
# mkfz439.py's private ajm.cpp: no catcher), with the off-word KYTY_BC5_AT9_DMC (on only when "1"; switch_defaults.hpp
# kSoft sets it, "=0" gives the old refusal). Writes atrac9_decoder.h, ajm.cpp and dm0439.hpp (with dm439::on()).
#   python mkdm439b.py <dir with the tree's src/libs/ajm/atrac9_decoder.h (c2f248cb) and src/libs/ajm.cpp (971b3d66)> <out dir>
# Det test: test_dm0439.cpp (dmc_info; the plant BC5_DM439_PLANT) and test_dm0439b.sh (the off-word gate, text check).
import hashlib
import os
import sys

src, dst = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))


def load(path, md5):
    b = open(path, 'rb').read()
    assert hashlib.md5(b).hexdigest().startswith(md5), (path, hashlib.md5(b).hexdigest())
    t = b.decode('utf-8')
    assert '\r' not in t
    return t


def rep(t, a, b):
    assert t.count(a) == 1, (a[:80], t.count(a))
    return t.replace(a, b)


# the header with the gate
d = open(os.path.join(HERE, 'dm0439.hpp'), 'rb').read().decode('utf-8')
d = rep(d, 'inline constexpr std::uint8_t kDmcSync = 0x30;\n', '''inline constexpr std::uint8_t kDmcSync = 0x30;

// KYTY_BC5_AT9_DMC: "1" (switch_defaults.hpp kSoft) takes DMC configs through vgmstream; anything else keeps the refusal.
inline bool on() {
    static const bool v = [] {
        const char *e = std::getenv("KYTY_BC5_AT9_DMC");
        return e != nullptr && e[0] == '1' && e[1] == 0;
    }();
    return v;
}
''')
if '#include <cstdlib>' not in d:
    d = rep(d, 'namespace bc5::dm439 {', '#include <cstdlib>\n\nnamespace bc5::dm439 {')

h = load(os.path.join(src, 'atrac9_decoder.h'), 'c2f248cb')
h = rep(h, '#include "atrac9_dec.h"\n}\n', '#include "atrac9_dec.h"\n}\n#include "bc5/dm0439.hpp" // exp 0439 (tag dm439): ATRAC9 DMC configurations\n')
h = rep(h, r'''		std::memcpy(m_config_data, config_data, ATRAC9_CONFIG_DATA_SIZE);
		m_has_config = true;
''', r'''		std::memcpy(m_config_data, config_data, ATRAC9_CONFIG_DATA_SIZE);
		m_has_config = true;

		if (m_config_data[0] == bc5::dm439::kDmcSync && bc5::dm439::on()) { // exp 0439 (tag dm439, F892): a DMC config, vgmstream only
			atrac9_info_t dmc {};
			if (m_vib != nullptr) {
				atrac9_free(m_vib);
				m_vib = nullptr;
			}
			m_vibration = false;
			if (bc5::dm439::dmc_info(m_config_data, &dmc)) m_vib = atrac9_init(m_config_data);
			if (m_vib == nullptr) {
				std::fprintf(stderr, "bc5 ajm: ATRAC9 DMC config %02x %02x %02x %02x rejected\n", m_config_data[0], m_config_data[1],
				             m_config_data[2], m_config_data[3]);
				m_is_initialized        = false;
				result->result          = AJM_RESULT_CODEC_ERROR | AJM_RESULT_INVALID_DATA;
				result->internal_result = -1;
				return false;
			}
			m_vibration                     = true; // the vgmstream frame path (DecodeFrame -> DecodeVibrationFrame)
			m_codec_info                    = {};
			m_codec_info.channels           = dmc.channels;
			m_codec_info.samplingRate       = dmc.sample_rate;
			m_codec_info.superframeSize     = dmc.superframe_size;
			m_codec_info.framesInSuperframe = dmc.frames_per_superframe;
			m_codec_info.frameSamples       = dmc.frame_samples;
			m_is_initialized                = true;
			m_num_frames                    = 0;
			m_total_decoded_samples         = 0;
			m_superframe_bytes_remain       = static_cast<uint32_t>(m_codec_info.superframeSize);
			SetFormat(static_cast<uint32_t>(m_codec_info.channels), static_cast<uint32_t>(m_codec_info.samplingRate), m_sample_encoding);
			m_pcm_buffer.assign(FrameOutputBytes(), 0);
			return true;
		}
''')
h = rep(h, r'''				float tmp[ATRAC9_MAX_FRAME_SAMPLES * 2];
				samples = atrac9_decode_float(m_vib, input, src_size, tmp, bytes_used);''', r'''				// exp 0439 (tag dm439): sized by the stream (a DMC stream has up to 64 channels; this was 2 x 256)
				m_dm439_tmp.resize(static_cast<size_t>(ATRAC9_MAX_FRAME_SAMPLES) * static_cast<size_t>(std::max(2, m_codec_info.channels)));
				float* tmp = m_dm439_tmp.data();
				samples = atrac9_decode_float(m_vib, input, src_size, tmp, bytes_used);''')
h = rep(h, '	std::vector<uint8_t> m_pcm_buffer;\n', '	std::vector<uint8_t> m_pcm_buffer;\n	std::vector<float>   m_dm439_tmp; // exp 0439 (tag dm439)\n')

a = load(os.path.join(src, 'ajm.cpp'), '971b3d66')
a = rep(a, r'''	auto* handle = Atrac9GetHandle();
	if (handle == nullptr) {
		return AJM_ERROR_INVALID_PARAMETER;
	}

	uint8_t config[ATRAC9_CONFIG_DATA_SIZE] {};''', r'''	if (atrac9_info_t dmc {}; static_cast<const uint8_t*>(config_data)[0] == bc5::dm439::kDmcSync && bc5::dm439::on()) { // exp 0439 (tag dm439, F892)
		if (!bc5::dm439::dmc_info(config_data, &dmc)) return AJM_ERROR_INVALID_PARAMETER;
		config_info->channels                       = static_cast<uint32_t>(dmc.channels);
		config_info->sample_rate                    = static_cast<uint32_t>(dmc.sample_rate);
		config_info->frame_samples_per_channel      = static_cast<uint32_t>(dmc.frame_samples);
		config_info->superframe_samples_per_channel = static_cast<uint32_t>(dmc.frame_samples) * static_cast<uint32_t>(dmc.frames_per_superframe);
		config_info->superframe_size                = static_cast<uint32_t>(dmc.superframe_size);
		return OK;
	}

	auto* handle = Atrac9GetHandle();
	if (handle == nullptr) {
		return AJM_ERROR_INVALID_PARAMETER;
	}

	uint8_t config[ATRAC9_CONFIG_DATA_SIZE] {};''')

os.makedirs(dst, exist_ok=True)
for name, t in (('atrac9_decoder.h', h), ('ajm.cpp', a), ('dm0439.hpp', d)):
    for k, line in enumerate(t.split('\n')):
        if ('dm439' in line or 'DMC' in line) and line.count('"') % 2 != 0 and not line.rstrip().endswith('\\'):
            raise SystemExit('%s:%d: odd quotes' % (name, k + 1))
    open(os.path.join(dst, name), 'wb').write(t.encode('utf-8'))
    print('dm439b: %s %s' % (name, hashlib.md5(t.encode('utf-8')).hexdigest()[:8]))
