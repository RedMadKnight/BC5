# BC5 exp 0439 (tag dm439): ATRAC9 DMC configurations (bc5/dm0439.hpp, README item 44). Private units:
#   - src/libs/ajm/atrac9_decoder.h (md5 c2f248cb): InitializeConfig takes a DMC config (sync 0x30) through vgmstream
#     (atrac9_init + atrac9_get_info; LibAtrac9 not called), decoding on the vgmstream frame path the haptic layouts
#     already use; the S32 conversion buffer of that path is sized by the stream (it was 512 samples: 2 x 256);
#   - src/libs/ajm.cpp, over mkfz439.py's output (the catcher stays): sceAjmDecAt9ParseConfigData answers a DMC config
#     from vgmstream's description (dm0439.hpp dmc_info).
# No switch: a refusal of a valid config is corrected (the top session, 11-21 ~23:20); the fz439 catcher line stays.
#   python mkdm439.py <dir with atrac9_decoder.h> <dir with mkfz439's ajm.cpp> <out dir>
import hashlib
import os
import sys

hdir, adir, dst = sys.argv[1], sys.argv[2], sys.argv[3]


def load(path, md5=None):
    b = open(path, 'rb').read()
    if md5:
        assert hashlib.md5(b).hexdigest().startswith(md5), (path, hashlib.md5(b).hexdigest())
    t = b.decode('utf-8')
    assert '\r' not in t
    return t


def rep(t, a, b):
    assert t.count(a) == 1, (a[:80], t.count(a))
    return t.replace(a, b)


h = load(os.path.join(hdir, 'atrac9_decoder.h'), 'c2f248cb')
h = rep(h, '#include "atrac9_dec.h"\n}\n', '#include "atrac9_dec.h"\n}\n#include "bc5/dm0439.hpp" // exp 0439 (tag dm439): ATRAC9 DMC configurations\n')
h = rep(h, r'''		std::memcpy(m_config_data, config_data, ATRAC9_CONFIG_DATA_SIZE);
		m_has_config = true;
''', r'''		std::memcpy(m_config_data, config_data, ATRAC9_CONFIG_DATA_SIZE);
		m_has_config = true;

		if (m_config_data[0] == bc5::dm439::kDmcSync) { // exp 0439 (tag dm439): a DMC config, vgmstream only
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
			static std::atomic<int> noted {0};
			if (noted++ < 8)
				std::fprintf(stderr, "bc5 ajm: ATRAC9 DMC config %02x %02x %02x %02x: %d ch, %d Hz, frame %d samples, superframe %d bytes/%d frames (vgmstream)\n",
				             m_config_data[0], m_config_data[1], m_config_data[2], m_config_data[3], m_codec_info.channels, m_codec_info.samplingRate,
				             m_codec_info.frameSamples, m_codec_info.superframeSize, m_codec_info.framesInSuperframe);
			return true;
		}
''')
h = rep(h, r'''				float tmp[ATRAC9_MAX_FRAME_SAMPLES * 2];
				samples = atrac9_decode_float(m_vib, input, src_size, tmp, bytes_used);''', r'''				// exp 0439 (tag dm439): sized by the stream (a DMC stream has up to 64 channels; this was 2 x 256)
				m_dm439_tmp.resize(static_cast<size_t>(ATRAC9_MAX_FRAME_SAMPLES) * static_cast<size_t>(std::max(2, m_codec_info.channels)));
				float* tmp = m_dm439_tmp.data();
				samples = atrac9_decode_float(m_vib, input, src_size, tmp, bytes_used);''')
h = rep(h, '	std::vector<uint8_t> m_pcm_buffer;\n', '	std::vector<uint8_t> m_pcm_buffer;\n	std::vector<float>   m_dm439_tmp; // exp 0439 (tag dm439)\n')

a = load(os.path.join(adir, 'ajm.cpp'))
assert 'tag fz439' in a, 'ajm.cpp must be mkfz439.py output'
a = rep(a, r'''	auto* handle = Atrac9GetHandle();
	if (handle == nullptr) {
		return AJM_ERROR_INVALID_PARAMETER;
	}

	uint8_t config[ATRAC9_CONFIG_DATA_SIZE] {};''', r'''	if (atrac9_info_t dmc {}; static_cast<const uint8_t*>(config_data)[0] == bc5::dm439::kDmcSync) { // exp 0439 (tag dm439)
		if (!bc5::dm439::dmc_info(config_data, &dmc)) {
			bc5_fz439_note(1, "AjmDecAt9ParseConfigData DMC config refused by vgmstream too"); // exp 0439 (tag fz439)
			return AJM_ERROR_INVALID_PARAMETER;
		}
		config_info->channels                       = static_cast<uint32_t>(dmc.channels);
		config_info->sample_rate                    = static_cast<uint32_t>(dmc.sample_rate);
		config_info->frame_samples_per_channel      = static_cast<uint32_t>(dmc.frame_samples);
		config_info->superframe_samples_per_channel = static_cast<uint32_t>(dmc.frame_samples) * static_cast<uint32_t>(dmc.frames_per_superframe);
		config_info->superframe_size                = static_cast<uint32_t>(dmc.superframe_size);
		bc5_fz439_note(0, "AjmDecAt9ParseConfigData DMC config: channels %u rate %u frame %u superframe samples %u size %u (vgmstream)", config_info->channels, config_info->sample_rate,
		               config_info->frame_samples_per_channel, config_info->superframe_samples_per_channel, config_info->superframe_size); // exp 0439 (tag fz439)
		static std::atomic<int> noted {0};
		if (noted++ < 8)
			std::fprintf(stderr, "bc5 ajm: ParseConfigData ATRAC9 DMC config: %u ch, %u Hz, frame %u, superframe %u bytes (vgmstream)\n", config_info->channels,
			             config_info->sample_rate, config_info->frame_samples_per_channel, config_info->superframe_size);
		return OK;
	}

	auto* handle = Atrac9GetHandle();
	if (handle == nullptr) {
		return AJM_ERROR_INVALID_PARAMETER;
	}

	uint8_t config[ATRAC9_CONFIG_DATA_SIZE] {};''')

for name, t in (('atrac9_decoder.h', h), ('ajm.cpp', a)):
    for k, line in enumerate(t.split('\n')):
        if ('dm439' in line or 'fz439' in line or 'DMC' in line) and line.count('"') % 2 != 0 and not line.rstrip().endswith('\\'):
            raise SystemExit('%s:%d: odd quotes' % (name, k + 1))
    os.makedirs(dst, exist_ok=True)
    open(os.path.join(dst, name), 'wb').write(t.encode('utf-8'))
print('dm439: atrac9_decoder.h and ajm.cpp written')
