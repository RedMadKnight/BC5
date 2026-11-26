// BC5 exp 0417 (tag sdm417): an own test of sdm0417.inc, the block mksdm0417.py puts into src/libs/libSaveData.cpp.
// The block is compiled as it is, between stand-ins for what the unit gives it. Each case is one process (the
// switches are read once); test0417sdm.sh runs them in a fresh directory each.
//   usage: test0417sdm <case>      (the switches come from the environment)
// On Windows std::rename does not replace an existing file; the stand-in below removes the target first (test only).
#include <algorithm>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <mutex>
#include <string>
#include <system_error>
#include <vector>

namespace std {
inline int bc5_test_rename(const char* a, const char* b) {
	std::remove(b);
	return std::rename(a, b);
}
} // namespace std
#define rename bc5_test_rename

#define KYTY_SYSV_ABI
#define PRINT_NAME()
#define LOGF(...)
static constexpr int  OK                        = 0;
static constexpr int  SAVE_DATA_ERROR_PARAMETER = static_cast<int>(0x809F0000);
static constexpr char SAVE_DATA_DIR[]           = "_SaveData";
static std::string    get_title_id() {
	return "TEST00000";
}
namespace sg412 {
static constexpr int kLib = 0;
struct Op {
	Op(int, bool) {}
};
} // namespace sg412

struct SaveDataParam {
	char     title[128];
	char     sub_title[128];
	char     detail[1024];
	uint32_t user_param;
	int      pad;
	int64_t  mtime;
	uint8_t  reserved[32];
};
struct SaveDataIcon {
	void*   buf;
	size_t  buf_size;
	size_t  data_size;
	uint8_t reserved[32];
};
struct SaveDataMemoryData {
	void*   buf;
	size_t  buf_size;
	int64_t offset;
	uint8_t reserved[40];
};
struct SaveDataMemoryGet2 {
	int32_t             user_id;
	uint8_t             padding[4];
	SaveDataMemoryData* data;
	SaveDataParam*      param;
	SaveDataIcon*       icon;
	uint32_t            slot_id;
	uint8_t             reserved[28];
};
struct SaveDataMemorySetup2 {
	uint32_t             option;
	int32_t              user_id;
	size_t               memory_size;
	size_t               icon_memory_size;
	const SaveDataParam* init_param;
	const SaveDataIcon*  init_icon;
	uint32_t             slot_id;
	uint8_t              reserved[20];
};
struct SaveDataMemorySetupResult {
	size_t  existed_memory_size;
	uint8_t reserved[16];
};
struct SaveDataMemorySet2 {
	int32_t                   user_id;
	uint8_t                   padding[4];
	const SaveDataMemoryData* data;
	const SaveDataParam*      param;
	const SaveDataIcon*       icon;
	uint32_t                  data_num;
	uint32_t                  slot_id;
	uint8_t                   reserved[24];
};
struct SaveDataTransferringMount;

static std::vector<uint8_t>     g_save_data_memory(0x10000);
static constexpr uint32_t       BC5_SDM_FIX_SYNC           = 1u;
static constexpr uint32_t       BC5_SDM_FIX_EXISTED        = 4u;
static constexpr uint32_t       BC5_SAVE_DATA_MEMORY_SLOTS = 4u;
static bool                     g_bc5_memory_set_up[BC5_SAVE_DATA_MEMORY_SLOTS] = {};
static bool bc5_savedata_memory_fix(uint32_t item) {
	const char* e = std::getenv("TEST_EXISTED");
	return item == BC5_SDM_FIX_EXISTED && e != nullptr && e[0] == '1';
}
static std::mutex g_save_data_memory_mutex;
static bool       g_save_data_memory_loaded = false;

#include "sdm0417.inc"

static int g_fail = 0;
static void expect(const char* what, bool ok) {
	if (!ok) {
		g_fail++;
		std::printf("FAIL %s\n", what);
	}
}
static int set(uint32_t slot, int64_t offset, const char* text, const SaveDataParam* param = nullptr, const SaveDataIcon* icon = nullptr) {
	SaveDataMemoryData d {};
	d.buf      = const_cast<char*>(text);
	d.buf_size = std::strlen(text);
	d.offset   = offset;
	SaveDataMemorySet2 s {};
	s.data     = &d;
	s.data_num = 1;
	s.slot_id  = slot;
	s.param    = param;
	s.icon     = icon;
	return SaveDataSetSaveDataMemory2(&s);
}
static std::string get(uint32_t slot, int64_t offset, size_t n, int* rc = nullptr, SaveDataParam* param = nullptr, SaveDataIcon* icon = nullptr) {
	std::string        out(n, '?');
	SaveDataMemoryData d {};
	d.buf      = out.data();
	d.buf_size = n;
	d.offset   = offset;
	SaveDataMemoryGet2 g {};
	g.data    = &d;
	g.slot_id = slot;
	g.param   = param;
	g.icon    = icon;
	const int r = SaveDataGetSaveDataMemory2(&g);
	if (rc != nullptr) {
		*rc = r;
	}
	return out;
}
static size_t setup(uint32_t slot, int* rc = nullptr, const SaveDataParam* init = nullptr) {
	SaveDataMemorySetup2 s {};
	s.memory_size = 2u << 20;
	s.slot_id     = slot;
	s.init_param  = init;
	SaveDataMemorySetupResult r {};
	const int                 c = SaveDataSetupSaveDataMemory2(&s, &r);
	if (rc != nullptr) {
		*rc = c;
	}
	return r.existed_memory_size;
}
static bool exists(const char* p) {
	return std::filesystem::exists(p);
}

int main(int argc, char** argv) {
	const std::string c = argc > 1 ? argv[1] : "";
	int               rc = 0;
	if (c == "write") { // two slots written at the same offset
		setup(0);
		setup(1);
		expect("set slot 0", set(0, 0, "AAAA") == OK);
		expect("set slot 1", set(1, 0, "BBBB") == OK);
		expect("set slot 0 at 100", set(0, 100, "tail") == OK);
	} else if (c == "read-old") { // all switches off: one store, slot 1's bytes lie over slot 0's (today's behaviour)
		expect("existed is the store's size", setup(0) == (2u << 20));
		expect("slot 0 reads slot 1's bytes", get(0, 0, 4) == "BBBB");
		expect("slot 1 the same", get(1, 0, 4) == "BBBB");
		expect("the tail", get(0, 100, 4) == "tail");
		expect("one file", exists("_SaveData/TEST00000/sce_sdmemory/memory.dat") && !exists("_SaveData/TEST00000/sce_sdmemory1"));
		expect("slot 9 is slot 0's store", get(9, 0, 4, &rc) == "BBBB" && rc == OK);
		expect("no param file", !exists("_SaveData/TEST00000/sce_sdmemory/param.bin"));
	} else if (c == "read-slots") { // KYTY_BC5_SAVEDATA_MEMORY_SLOTS=1
		setup(0);
		expect("slot 0 keeps its bytes", get(0, 0, 4) == "AAAA");
		expect("slot 1 keeps its bytes", get(1, 0, 4) == "BBBB");
		expect("slot 1 has no tail", get(1, 100, 4) == std::string(4, '\0'));
		expect("slot 2 is empty", get(2, 0, 4) == std::string(4, '\0'));
		expect("two files", exists("_SaveData/TEST00000/sce_sdmemory/memory.dat") && exists("_SaveData/TEST00000/sce_sdmemory1/memory.dat") &&
		                        !exists("_SaveData/TEST00000/sce_sdmemory2"));
		get(4, 0, 4, &rc);
		expect("slot 4 get is PARAMETER", rc == SAVE_DATA_ERROR_PARAMETER);
		expect("slot 4 set is PARAMETER", set(4, 0, "x") == SAVE_DATA_ERROR_PARAMETER);
		setup(4, &rc);
		expect("slot 4 setup is PARAMETER", rc == SAVE_DATA_ERROR_PARAMETER);
	} else if (c == "existed") { // TEST_EXISTED=1 with the slots on: per slot, 0 before a file
		expect("slot 0 has a file", setup(0) == (2u << 20));
		expect("slot 2 has none", setup(2) == 0);
	} else if (c == "param-write") { // KYTY_BC5_SAVEDATA_MEMORY_PARAM=1
		SaveDataParam init {};
		std::snprintf(init.title, sizeof(init.title), "init");
		setup(0, nullptr, &init);
		SaveDataParam p {};
		expect("the init param is answered", (get(0, 0, 4, nullptr, &p), std::strcmp(p.title, "init") == 0));
		std::snprintf(p.title, sizeof(p.title), "second");
		p.user_param = 7;
		char         png[5] = {1, 2, 3, 4, 5};
		SaveDataIcon icon {};
		icon.buf       = png;
		icon.buf_size  = 5;
		icon.data_size = 5;
		expect("set with param and icon", set(0, 0, "DATA", &p, &icon) == OK);
	} else if (c == "param-read") {
		SaveDataParam init {};
		std::snprintf(init.title, sizeof(init.title), "init");
		setup(0, nullptr, &init); // a file exists: the init param must not replace the stored one
		SaveDataParam p {};
		char          buf[3] = {};
		SaveDataIcon  icon {};
		icon.buf      = buf;
		icon.buf_size = 3;
		expect("data", get(0, 0, 4, nullptr, &p, &icon) == "DATA");
		expect("param", std::strcmp(p.title, "second") == 0 && p.user_param == 7);
		expect("icon cut to the buffer", icon.data_size == 3 && buf[0] == 1 && buf[2] == 3);
	} else if (c == "param-off") { // the same files, the switch off: zeroed param, empty icon (today's behaviour)
		SaveDataParam p {};
		std::memset(&p, 0x55, sizeof(p));
		char         buf[3] = {9, 9, 9};
		SaveDataIcon icon {};
		icon.buf       = buf;
		icon.buf_size  = 3;
		icon.data_size = 99;
		expect("data", get(0, 0, 4, nullptr, &p, &icon) == "DATA");
		expect("param zeroed", p.title[0] == 0 && p.user_param == 0);
		expect("icon empty", icon.data_size == 0 && buf[0] == 9);
	} else {
		std::printf("unknown case\n");
		return 2;
	}
	std::printf("%s: %s\n", c.c_str(), g_fail == 0 ? "ok" : "FAILED");
	return g_fail == 0 ? 0 : 1;
}
