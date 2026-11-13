// ---- experiment 0417 (tag sdm417): the save data memory per slot, its parameters and icon, and a call log ----------
// Finding (exp 0417 README section 11): ASTRO BOT, started on an empty save directory and taken past its first screen
// by a key, stores a save data memory on which every later start ends by itself at 5 s, on every build. Three
// switches, all off by default (unset, empty or "0": the code below is the old path, one store and one file):
//  KYTY_BC5_SAVEDATA_MEMORY_SLOTS=1  candidate fix. Today the memory is ONE store for every slot_id
//      (sce_sdmemory/memory.dat), so a title that uses two slots writes one over the other at the same offsets. On:
//      slot 0 keeps today's store and file; slots 1-3 get their own store and their own file
//      (sce_sdmemory<n>/memory.dat, the directory names this file's "sync" event already reports, after KytyPS5
//      dfec14a libs/libSaveData.cpp:1151-1182); a slot of 4 or more is PARAMETER (KytyPS5 dfec14a :1154).
//  KYTY_BC5_SAVEDATA_MEMORY_PARAM=1  candidate fix. Today SetSaveDataMemory2 drops the parameters and the icon it is
//      given and GetSaveDataMemory2 answers zeroed parameters and an empty icon. On: both are kept per slot
//      (param.bin, icon.bin beside memory.dat), Setup's init_param / init_icon fill them when no file existed, and Get
//      returns them (the icon up to the caller's buffer). shadPS4 60c42b9 save_data/savedata.cpp:1470-1560 keeps both.
//  KYTY_BC5_SAVEDATA_MEMORY_LOG=1    catcher, changes nothing: one stderr line per Setup / Get / Set / Sync with the
//      slot, each piece's offset, size, count of non-zero bytes and FNV-1a, and what the call returns.
// The third candidate needs no new code: KYTY_BC5_SAVEDATA_MEMORY_FIXES=existed (exp 0401 series e5), without which
// Setup reports an existing memory on an empty directory and the title reads zeros as a save.
// Nothing here is measured on a console.
static bool bc5_sdm_switch(const char* name, const char* what) {
	const char* e = std::getenv(name);
	const bool  v = e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
	std::fprintf(stderr, "[bc5] exp 0417: savedata memory %s %s\n", what, v ? "on" : "off");
	return v;
}
static bool bc5_sdm_slots_on() {
	static const bool on = bc5_sdm_switch("KYTY_BC5_SAVEDATA_MEMORY_SLOTS", "per slot");
	return on;
}
static bool bc5_sdm_param_on() {
	static const bool on = bc5_sdm_switch("KYTY_BC5_SAVEDATA_MEMORY_PARAM", "parameters and icon kept");
	return on;
}
static bool bc5_sdm_log_on() {
	static const bool on = bc5_sdm_switch("KYTY_BC5_SAVEDATA_MEMORY_LOG", "call log");
	return on;
}

struct Bc5SdmMeta {
	SaveDataParam        param {};
	bool                 has_param = false;
	std::vector<uint8_t> icon;
};
static std::vector<uint8_t> g_bc5_sdm_slot_memory[BC5_SAVE_DATA_MEMORY_SLOTS - 1]; // slots 1-3; slot 0 is g_save_data_memory
static bool                 g_bc5_sdm_slot_loaded[BC5_SAVE_DATA_MEMORY_SLOTS - 1] = {};
static Bc5SdmMeta           g_bc5_sdm_meta[BC5_SAVE_DATA_MEMORY_SLOTS];
static bool                 g_bc5_sdm_meta_loaded[BC5_SAVE_DATA_MEMORY_SLOTS] = {};

// The store a slot_id uses: its own with the switch on, slot 0's without it. -1: the switch is on and the slot is not 0-3.
static int bc5_sdm_slot(uint32_t slot_id) {
	if (!bc5_sdm_slots_on()) {
		return 0;
	}
	return slot_id < BC5_SAVE_DATA_MEMORY_SLOTS ? static_cast<int>(slot_id) : -1;
}
static std::vector<uint8_t>& bc5_sdm_memory(int slot) {
	return slot == 0 ? g_save_data_memory : g_bc5_sdm_slot_memory[slot - 1];
}
static uint64_t bc5_sdm_fnv(const void* p, size_t n) {
	const auto* b = static_cast<const uint8_t*>(p);
	uint64_t    h = 1469598103934665603ull;
	for (size_t i = 0; i < n; i++) {
		h = (h ^ b[i]) * 1099511628211ull;
	}
	return h;
}
static size_t bc5_sdm_nonzero(const void* p, size_t n) {
	const auto* b = static_cast<const uint8_t*>(p);
	size_t      c = 0;
	for (size_t i = 0; i < n; i++) {
		c += (b[i] != 0 ? 1 : 0);
	}
	return c;
}

static std::string save_data_memory_dir(int slot = 0) {
	const char* root = std::getenv("KYTY_BC5_SAVEDATA_DIR");
	return std::string(root != nullptr && root[0] != 0 ? root : SAVE_DATA_DIR) + "/" + get_title_id() + "/sce_sdmemory" +
	       (slot == 0 ? std::string() : std::to_string(slot));
}

static bool bc5_sdm_read_file(const std::string& path, std::vector<uint8_t>* data) {
	std::FILE* f = std::fopen(path.c_str(), "rb");
	if (f == nullptr) {
		return false;
	}
	uint8_t buf[65536];
	size_t  n = 0;
	while ((n = std::fread(buf, 1, sizeof(buf), f)) > 0) {
		data->insert(data->end(), buf, buf + n);
	}
	std::fclose(f);
	return true;
}

static bool bc5_sdm_write_file(const std::string& path, const void* p, size_t n) {
	const std::string tmp = path + ".tmp";
	std::FILE*        f   = std::fopen(tmp.c_str(), "wb");
	if (f == nullptr) {
		return false;
	}
	const size_t written = std::fwrite(p, 1, n, f);
	const bool   ok      = (std::fclose(f) == 0 && written == n);
	if (!ok || std::rename(tmp.c_str(), path.c_str()) != 0) {
		std::remove(tmp.c_str());
		return false;
	}
	return true;
}

static void save_data_memory_load(int slot = 0) {
	bool& loaded = (slot == 0 ? g_save_data_memory_loaded : g_bc5_sdm_slot_loaded[slot - 1]);
	if (loaded) {
		return;
	}
	loaded     = true;
	auto& mem  = bc5_sdm_memory(slot);
	if (mem.size() < 0x10000) {
		mem.resize(0x10000); // slot 0's store begins with this size
	}
	const std::string    path = save_data_memory_dir(slot) + "/memory.dat";
	std::vector<uint8_t> data;
	if (!bc5_sdm_read_file(path, &data)) {
		LOGF("\t save data memory: no file at %s\n", path.c_str());
		return;
	}
	if (data.size() > mem.size()) {
		mem.resize(data.size());
	}
	if (!data.empty()) {
		std::memcpy(mem.data(), data.data(), data.size());
	}
	LOGF("\t save data memory: %zu bytes read from %s\n", data.size(), path.c_str());
}

static bool save_data_memory_store(int slot = 0) { // experiment 0401 series e5: true when written ("sync"'s status)
	const std::string dir = save_data_memory_dir(slot);
	std::error_code   ec;
	std::filesystem::create_directories(dir, ec);
	const std::string path = dir + "/memory.dat";
	const auto&       mem  = bc5_sdm_memory(slot);
	if (!bc5_sdm_write_file(path, mem.data(), mem.size())) {
		LOGF("\t save data memory: writing %s failed\n", path.c_str());
		return false; // experiment 0401 series e5
	}
	LOGF("\t save data memory: %zu bytes written to %s\n", mem.size(), path.c_str());
	return true; // experiment 0401 series e5
}

// experiment 0401 series e5 (KYTY_BC5_SAVEDATA_MEMORY_FIXES "existed", R2 KS09 + SS02): the size of the stored memory
// file, 0 when there is none (KytyPS5 dfec14a load_memory, libs/libSaveData.cpp:457-483; sharpemu 514d766, added in
// 488b285, SaveDataExports.cs:1525-1526, the backing file's length before the call).
static size_t bc5_save_data_memory_file_size(int slot = 0) {
	std::error_code ec;
	const auto      size = std::filesystem::file_size(save_data_memory_dir(slot) + "/memory.dat", ec);
	return ec ? 0 : static_cast<size_t>(size);
}

// exp 0417 (KYTY_BC5_SAVEDATA_MEMORY_PARAM): the slot's parameters and icon, read once and written when they change.
static Bc5SdmMeta& bc5_sdm_meta(int slot) {
	Bc5SdmMeta& m = g_bc5_sdm_meta[slot];
	if (!g_bc5_sdm_meta_loaded[slot]) {
		g_bc5_sdm_meta_loaded[slot] = true;
		std::vector<uint8_t> data;
		if (bc5_sdm_read_file(save_data_memory_dir(slot) + "/param.bin", &data) && data.size() == sizeof(SaveDataParam)) {
			std::memcpy(&m.param, data.data(), sizeof(SaveDataParam));
			m.has_param = true;
		}
		bc5_sdm_read_file(save_data_memory_dir(slot) + "/icon.bin", &m.icon);
	}
	return m;
}
static void bc5_sdm_meta_set(int slot, const SaveDataParam* param, const SaveDataIcon* icon) {
	Bc5SdmMeta&     m = bc5_sdm_meta(slot);
	std::error_code ec;
	std::filesystem::create_directories(save_data_memory_dir(slot), ec);
	if (param != nullptr) {
		m.param     = *param;
		m.has_param = true;
		bc5_sdm_write_file(save_data_memory_dir(slot) + "/param.bin", &m.param, sizeof(m.param));
	}
	if (icon != nullptr && icon->buf != nullptr && icon->data_size != 0 && icon->data_size <= icon->buf_size) {
		const auto* b = static_cast<const uint8_t*>(icon->buf);
		m.icon.assign(b, b + icon->data_size);
		bc5_sdm_write_file(save_data_memory_dir(slot) + "/icon.bin", m.icon.data(), m.icon.size());
	}
}

int KYTY_SYSV_ABI SaveDataSetupSaveDataMemory2(const SaveDataMemorySetup2* setup_param,
                                               SaveDataMemorySetupResult*  result) {
	PRINT_NAME();

	if (setup_param == nullptr) {
		return SAVE_DATA_ERROR_PARAMETER;
	}

	LOGF("\t option           = 0x%08" PRIx32 "\n"
	     "\t user_id          = %" PRId32 "\n"
	     "\t memory_size      = %" PRIu64 "\n"
	     "\t icon_memory_size = %" PRIu64 "\n"
	     "\t slot_id          = %" PRIu32 "\n",
	     setup_param->option, setup_param->user_id, static_cast<uint64_t>(setup_param->memory_size),
	     static_cast<uint64_t>(setup_param->icon_memory_size), setup_param->slot_id);

	std::lock_guard lock(g_save_data_memory_mutex);
	const int       slot = bc5_sdm_slot(setup_param->slot_id); // exp 0417
	if (slot < 0) {
		if (bc5_sdm_log_on()) {
			std::fprintf(stderr, "[bc5] sdm417 setup: slot %" PRIu32 " -> PARAMETER\n", setup_param->slot_id);
		}
		return SAVE_DATA_ERROR_PARAMETER;
	}
	const size_t bc5_file = bc5_save_data_memory_file_size(slot); // exp 0417: for the log and for init_param
	// experiment 0401 series e5 ("existed"): the stored file's size before this call; off: not read
	const size_t bc5_existed = bc5_savedata_memory_fix(BC5_SDM_FIX_EXISTED) ? bc5_file : 0;
	save_data_memory_load(slot);
	auto& mem = bc5_sdm_memory(slot);
	if (setup_param->memory_size > mem.size()) {
		mem.resize(setup_param->memory_size);
	}
	if (bc5_savedata_memory_fix(BC5_SDM_FIX_SYNC) && setup_param->slot_id < BC5_SAVE_DATA_MEMORY_SLOTS) {
		g_bc5_memory_set_up[setup_param->slot_id] = true; // experiment 0401 series e5 ("sync"): this slot is ready
	}
	if (bc5_sdm_param_on() && bc5_file == 0 && !bc5_sdm_meta(slot).has_param) { // exp 0417: a new memory takes the init values
		bc5_sdm_meta_set(slot, setup_param->init_param, setup_param->init_icon);
	}

	size_t bc5_answer = mem.size();
	if (bc5_savedata_memory_fix(BC5_SDM_FIX_EXISTED)) { // experiment 0401 series e5 (KytyPS5 dfec14a :823, sharpemu 488b285)
		bc5_answer = bc5_existed;
	}
	if (result != nullptr) {
		*result                     = {};
		result->existed_memory_size = bc5_answer;
	}
	if (bc5_sdm_log_on()) {
		std::fprintf(stderr,
		             "[bc5] sdm417 setup: slot %" PRIu32 " (store %d) option 0x%" PRIx32 " memory_size %zu icon_memory_size %zu "
		             "init_param %d init_icon %d; file before %zu bytes; existed_memory_size answered %zu%s\n",
		             setup_param->slot_id, slot, setup_param->option, static_cast<size_t>(setup_param->memory_size),
		             static_cast<size_t>(setup_param->icon_memory_size), setup_param->init_param != nullptr ? 1 : 0,
		             setup_param->init_icon != nullptr ? 1 : 0, bc5_file, bc5_answer, result != nullptr ? "" : " (no result pointer)");
	}

	return OK;
}

int KYTY_SYSV_ABI SaveDataGetSaveDataMemory2(SaveDataMemoryGet2* get_param) {
	PRINT_NAME();

	if (get_param == nullptr) {
		return SAVE_DATA_ERROR_PARAMETER;
	}

	LOGF("\t user_id  = %" PRId32 "\n"
	     "\t data     = 0x%016" PRIx64 "\n"
	     "\t param    = 0x%016" PRIx64 "\n"
	     "\t icon     = 0x%016" PRIx64 "\n"
	     "\t slot_id  = %" PRIu32 "\n",
	     get_param->user_id, reinterpret_cast<uint64_t>(get_param->data),
	     reinterpret_cast<uint64_t>(get_param->param), reinterpret_cast<uint64_t>(get_param->icon),
	     get_param->slot_id);

	std::lock_guard lock(g_save_data_memory_mutex);
	const int       slot = bc5_sdm_slot(get_param->slot_id); // exp 0417
	if (slot < 0) {
		if (bc5_sdm_log_on()) {
			std::fprintf(stderr, "[bc5] sdm417 get: slot %" PRIu32 " -> PARAMETER\n", get_param->slot_id);
		}
		return SAVE_DATA_ERROR_PARAMETER;
	}
	save_data_memory_load(slot);
	auto& mem = bc5_sdm_memory(slot);
	if (get_param->data != nullptr) {
		auto* data = get_param->data;
		if (data->buf == nullptr || data->offset < 0) {
			if (bc5_sdm_log_on()) {
				std::fprintf(stderr, "[bc5] sdm417 get: slot %" PRIu32 " buf %d offset %" PRId64 " -> PARAMETER\n", get_param->slot_id,
				             data->buf != nullptr ? 1 : 0, data->offset);
			}
			return SAVE_DATA_ERROR_PARAMETER;
		}

		const auto offset = static_cast<size_t>(data->offset);
		if (offset + data->buf_size > mem.size()) {
			mem.resize(offset + data->buf_size);
		}
		std::memcpy(data->buf, mem.data() + offset, data->buf_size);
	}
	size_t bc5_icon = 0;
	if (get_param->param != nullptr) {
		std::memset(get_param->param, 0, sizeof(*get_param->param));
		if (bc5_sdm_param_on() && bc5_sdm_meta(slot).has_param) { // exp 0417
			*get_param->param = bc5_sdm_meta(slot).param;
		}
	}
	if (get_param->icon != nullptr) {
		get_param->icon->data_size = 0;
		if (bc5_sdm_param_on() && get_param->icon->buf != nullptr) { // exp 0417: the kept icon, up to the caller's buffer
			const auto& icon = bc5_sdm_meta(slot).icon;
			bc5_icon         = std::min(icon.size(), get_param->icon->buf_size);
			if (bc5_icon != 0) {
				std::memcpy(get_param->icon->buf, icon.data(), bc5_icon);
			}
			get_param->icon->data_size = bc5_icon;
		}
	}
	if (bc5_sdm_log_on()) {
		if (get_param->data != nullptr) {
			const auto* d = get_param->data;
			std::fprintf(stderr,
			             "[bc5] sdm417 get: slot %" PRIu32 " (store %d) offset %" PRId64 " size %zu non-zero %zu fnv %016" PRIx64
			             "; param %d icon %d (icon bytes answered %zu); store %zu bytes\n",
			             get_param->slot_id, slot, d->offset, d->buf_size, bc5_sdm_nonzero(d->buf, d->buf_size),
			             bc5_sdm_fnv(d->buf, d->buf_size), get_param->param != nullptr ? 1 : 0, get_param->icon != nullptr ? 1 : 0,
			             bc5_icon, mem.size());
		} else {
			std::fprintf(stderr, "[bc5] sdm417 get: slot %" PRIu32 " (store %d) no data; param %d icon %d (icon bytes answered %zu)\n",
			             get_param->slot_id, slot, get_param->param != nullptr ? 1 : 0, get_param->icon != nullptr ? 1 : 0, bc5_icon);
		}
	}

	return OK;
}

int KYTY_SYSV_ABI SaveDataSetSaveDataMemory2(const SaveDataMemorySet2* set_param) {
	PRINT_NAME();
	sg412::Op sg_op(sg412::kLib, true); // exp 0412 (tag sg412)

	if (set_param == nullptr) {
		return SAVE_DATA_ERROR_PARAMETER;
	}

	LOGF("\t user_id  = %" PRId32 "\n"
	     "\t data     = 0x%016" PRIx64 "\n"
	     "\t param    = 0x%016" PRIx64 "\n"
	     "\t icon     = 0x%016" PRIx64 "\n"
	     "\t data_num = %" PRIu32 "\n"
	     "\t slot_id  = %" PRIu32 "\n",
	     set_param->user_id, reinterpret_cast<uint64_t>(set_param->data),
	     reinterpret_cast<uint64_t>(set_param->param), reinterpret_cast<uint64_t>(set_param->icon),
	     set_param->data_num, set_param->slot_id);

	std::lock_guard lock(g_save_data_memory_mutex);
	const int       slot = bc5_sdm_slot(set_param->slot_id); // exp 0417
	if (slot < 0) {
		if (bc5_sdm_log_on()) {
			std::fprintf(stderr, "[bc5] sdm417 set: slot %" PRIu32 " -> PARAMETER\n", set_param->slot_id);
		}
		return SAVE_DATA_ERROR_PARAMETER;
	}
	save_data_memory_load(slot);
	auto&          mem      = bc5_sdm_memory(slot);
	const uint32_t data_num = (set_param->data_num == 0 ? 1 : set_param->data_num);
	if (set_param->data != nullptr) {
		for (uint32_t i = 0; i < data_num; i++) {
			const auto& data = set_param->data[i];
			if (data.buf == nullptr || data.offset < 0) {
				if (bc5_sdm_log_on()) {
					std::fprintf(stderr, "[bc5] sdm417 set: slot %" PRIu32 " piece %" PRIu32 " of %" PRIu32 " buf %d offset %" PRId64
					                     " -> PARAMETER (earlier pieces are in the store, nothing written to the file)\n",
					             set_param->slot_id, i, data_num, data.buf != nullptr ? 1 : 0, data.offset);
				}
				return SAVE_DATA_ERROR_PARAMETER;
			}

			const auto offset = static_cast<size_t>(data.offset);
			if (offset + data.buf_size > mem.size()) {
				mem.resize(offset + data.buf_size);
			}
			std::memcpy(mem.data() + offset, data.buf, data.buf_size);
			if (bc5_sdm_log_on()) {
				std::fprintf(stderr,
				             "[bc5] sdm417 set: slot %" PRIu32 " (store %d) piece %" PRIu32 " of %" PRIu32 " (data_num %" PRIu32
				             ") offset %" PRId64 " size %zu non-zero %zu fnv %016" PRIx64 "\n",
				             set_param->slot_id, slot, i, data_num, set_param->data_num, data.offset, data.buf_size,
				             bc5_sdm_nonzero(data.buf, data.buf_size), bc5_sdm_fnv(data.buf, data.buf_size));
			}
		}
		const bool bc5_written = save_data_memory_store(slot);
		if (bc5_sdm_log_on()) {
			std::fprintf(stderr, "[bc5] sdm417 set: slot %" PRIu32 " (store %d) file %s, %zu bytes, non-zero %zu; param %d icon %d\n",
			             set_param->slot_id, slot, bc5_written ? "written" : "NOT WRITTEN", mem.size(),
			             bc5_sdm_nonzero(mem.data(), mem.size()), set_param->param != nullptr ? 1 : 0,
			             set_param->icon != nullptr ? 1 : 0);
		}
	} else if (bc5_sdm_log_on()) {
		std::fprintf(stderr, "[bc5] sdm417 set: slot %" PRIu32 " (store %d) no data; param %d icon %d\n", set_param->slot_id, slot,
		             set_param->param != nullptr ? 1 : 0, set_param->icon != nullptr ? 1 : 0);
	}
	if (bc5_sdm_param_on()) { // exp 0417: the parameters and the icon are kept
		bc5_sdm_meta_set(slot, set_param->param, set_param->icon);
	}

	return OK;
}
