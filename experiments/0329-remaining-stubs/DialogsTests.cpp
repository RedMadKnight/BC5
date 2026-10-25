// BC5 experiment 0329: tests of the three dialog units (libPlayGoDialog.cpp, libNpCommerceDialog.cpp,
// libPlayerInvitationDialog.cpp): the common-dialog state machine, the error codes of shadPS4's commondialog.h, the
// results an offline console gives (PlayGo: proceed; the store and the invitation dialogs: cancelled by the user).
#include "common/abi.h"

#include <cstdint>
#include <cstdio>
#include <cstring>

namespace Libs::PlayGoDialog {
struct PlayGoDialogParam;
struct PlayGoDialogResult {
	uint8_t unk1[0x4];
	int32_t result;
	uint8_t unk2[0x20];
};
int KYTY_SYSV_ABI PlayGoDialogInitialize();
int KYTY_SYSV_ABI PlayGoDialogTerminate();
int KYTY_SYSV_ABI PlayGoDialogOpen(const PlayGoDialogParam* param);
int KYTY_SYSV_ABI PlayGoDialogClose();
int KYTY_SYSV_ABI PlayGoDialogUpdateStatus();
int KYTY_SYSV_ABI PlayGoDialogGetStatus();
int KYTY_SYSV_ABI PlayGoDialogGetResult(PlayGoDialogResult* result);
} // namespace Libs::PlayGoDialog

namespace Libs::NpCommerceDialog {
struct NpCommerceDialogResult {
	int32_t result;
	bool    authorized;
	uint8_t reserved[32];
};
int KYTY_SYSV_ABI NpCommerceDialogInitialize();
int KYTY_SYSV_ABI NpCommerceDialogOpen(const void* param);
int KYTY_SYSV_ABI NpCommerceDialogUpdateStatus();
int KYTY_SYSV_ABI NpCommerceDialogGetStatus();
int KYTY_SYSV_ABI NpCommerceDialogClose();
int KYTY_SYSV_ABI NpCommerceDialogGetResult(NpCommerceDialogResult* result);
int KYTY_SYSV_ABI NpCommerceDialogTerminate();
} // namespace Libs::NpCommerceDialog

namespace Libs::PlayerInvitationDialog {
struct PlayerInvitationDialogResult {
	int32_t error_code;
	int32_t result;
	uint8_t reserved[32];
};
int KYTY_SYSV_ABI PlayerInvitationDialogInitialize();
int KYTY_SYSV_ABI PlayerInvitationDialogOpen(const void* param);
int KYTY_SYSV_ABI PlayerInvitationDialogUpdateStatus();
int KYTY_SYSV_ABI PlayerInvitationDialogGetStatus();
int KYTY_SYSV_ABI PlayerInvitationDialogClose();
int KYTY_SYSV_ABI PlayerInvitationDialogTerminate();
int KYTY_SYSV_ABI PlayerInvitationDialogGetResult(PlayerInvitationDialogResult* result);
} // namespace Libs::PlayerInvitationDialog

static int g_failed = 0;

static void Check(bool ok, const char* what) {
	if (!ok) {
		std::fprintf(stderr, "DialogsTests: FAILED: %s\n", what);
		g_failed++;
	}
}

constexpr int NOT_INITIALIZED     = static_cast<int>(0x80B80003u);
constexpr int ALREADY_INITIALIZED = static_cast<int>(0x80B80004u);
constexpr int NOT_FINISHED        = static_cast<int>(0x80B80005u);
constexpr int INVALID_STATE       = static_cast<int>(0x80B80006u);
constexpr int ARG_NULL            = static_cast<int>(0x80B8000Du);
constexpr int STATUS_NONE = 0, STATUS_INITIALIZED = 1, STATUS_RUNNING = 2, STATUS_FINISHED = 3;

static void TestPlayGo() {
	using namespace Libs::PlayGoDialog;
	alignas(8) uint8_t param[0x68] = {};
	PlayGoDialogResult result      = {};
	Check(PlayGoDialogGetStatus() == STATUS_NONE, "PlayGo: NONE at first");
	Check(PlayGoDialogGetResult(&result) == NOT_INITIALIZED, "PlayGo: GetResult before Initialize is NOT_INITIALIZED");
	Check(PlayGoDialogTerminate() == NOT_INITIALIZED, "PlayGo: Terminate before Initialize is NOT_INITIALIZED");
	Check(PlayGoDialogOpen(reinterpret_cast<PlayGoDialogParam*>(param)) == NOT_INITIALIZED,
	      "PlayGo: Open before Initialize is NOT_INITIALIZED");
	Check(PlayGoDialogInitialize() == 0, "PlayGo: Initialize");
	Check(PlayGoDialogInitialize() == ALREADY_INITIALIZED, "PlayGo: a second Initialize is ALREADY_INITIALIZED");
	Check(PlayGoDialogGetStatus() == STATUS_INITIALIZED, "PlayGo: INITIALIZED");
	Check(PlayGoDialogGetResult(&result) == NOT_FINISHED, "PlayGo: GetResult before Open is NOT_FINISHED");
	Check(PlayGoDialogOpen(nullptr) == ARG_NULL, "PlayGo: Open(null) is ARG_NULL");
	Check(PlayGoDialogOpen(reinterpret_cast<PlayGoDialogParam*>(param)) == 0, "PlayGo: Open");
	Check(PlayGoDialogUpdateStatus() == STATUS_FINISHED, "PlayGo: finished at once (nothing to download)");
	Check(PlayGoDialogGetResult(nullptr) == ARG_NULL, "PlayGo: GetResult(null) is ARG_NULL");
	std::memset(&result, 0x5a, sizeof(result));
	Check(PlayGoDialogGetResult(&result) == 0 && result.result == 3, "PlayGo: the result lets the title proceed (3)");
	Check(PlayGoDialogClose() == 0, "PlayGo: Close");
	Check(PlayGoDialogOpen(reinterpret_cast<PlayGoDialogParam*>(param)) == 0, "PlayGo: Open again after a finish");
	Check(PlayGoDialogTerminate() == 0, "PlayGo: Terminate");
	Check(PlayGoDialogGetStatus() == STATUS_NONE, "PlayGo: NONE after Terminate");
	Check(PlayGoDialogClose() == NOT_INITIALIZED, "PlayGo: Close after Terminate is NOT_INITIALIZED");
}

static void TestNpCommerce() {
	using namespace Libs::NpCommerceDialog;
	int                    param  = 0;
	NpCommerceDialogResult result = {};
	Check(NpCommerceDialogUpdateStatus() == STATUS_NONE, "Commerce: NONE at first");
	Check(NpCommerceDialogOpen(&param) == NOT_INITIALIZED, "Commerce: Open before Initialize is NOT_INITIALIZED");
	Check(NpCommerceDialogGetResult(&result) == NOT_INITIALIZED, "Commerce: GetResult before Initialize");
	Check(NpCommerceDialogTerminate() == NOT_INITIALIZED, "Commerce: Terminate before Initialize");
	Check(NpCommerceDialogInitialize() == 0, "Commerce: Initialize");
	Check(NpCommerceDialogInitialize() == ALREADY_INITIALIZED, "Commerce: a second Initialize");
	Check(NpCommerceDialogOpen(nullptr) == ARG_NULL, "Commerce: Open(null) is ARG_NULL");
	Check(NpCommerceDialogOpen(&param) == 0, "Commerce: Open");
	Check(NpCommerceDialogGetStatus() == STATUS_RUNNING, "Commerce: RUNNING after Open");
	Check(NpCommerceDialogOpen(&param) == INVALID_STATE, "Commerce: Open while running is INVALID_STATE");
	Check(NpCommerceDialogGetResult(&result) == NOT_FINISHED, "Commerce: GetResult while running is NOT_FINISHED");
	Check(NpCommerceDialogUpdateStatus() == STATUS_FINISHED, "Commerce: the first UpdateStatus finishes it");
	Check(NpCommerceDialogGetResult(nullptr) == ARG_NULL, "Commerce: GetResult(null) is ARG_NULL");
	std::memset(&result, 0x5a, sizeof(result));
	Check(NpCommerceDialogGetResult(&result) == 0 && result.result == 1 && !result.authorized,
	      "Commerce: cancelled by the user, not authorized");
	Check(NpCommerceDialogClose() == 0, "Commerce: Close");
	Check(NpCommerceDialogTerminate() == 0, "Commerce: Terminate");
	Check(NpCommerceDialogUpdateStatus() == STATUS_NONE, "Commerce: NONE after Terminate");
}

static void TestPlayerInvitation() {
	using namespace Libs::PlayerInvitationDialog;
	int                          param  = 0;
	PlayerInvitationDialogResult result = {};
	Check(PlayerInvitationDialogUpdateStatus() == STATUS_NONE, "Invitation: NONE at first");
	Check(PlayerInvitationDialogGetResult(&result) == NOT_INITIALIZED, "Invitation: GetResult before Initialize");
	Check(PlayerInvitationDialogTerminate() == NOT_INITIALIZED, "Invitation: Terminate before Initialize");
	Check(PlayerInvitationDialogInitialize() == 0, "Invitation: Initialize");
	Check(PlayerInvitationDialogGetResult(&result) == NOT_FINISHED, "Invitation: GetResult before Open is NOT_FINISHED");
	Check(PlayerInvitationDialogOpen(nullptr) == ARG_NULL, "Invitation: Open(null) is ARG_NULL");
	Check(PlayerInvitationDialogOpen(&param) == 0, "Invitation: Open");
	Check(PlayerInvitationDialogGetStatus() == STATUS_RUNNING, "Invitation: RUNNING after Open");
	Check(PlayerInvitationDialogUpdateStatus() == STATUS_FINISHED, "Invitation: the first UpdateStatus finishes it");
	Check(PlayerInvitationDialogGetResult(nullptr) == ARG_NULL, "Invitation: GetResult(null) is ARG_NULL");
	std::memset(&result, 0x5a, sizeof(result));
	Check(PlayerInvitationDialogGetResult(&result) == 0 && result.result == 1 && result.error_code == 0,
	      "Invitation: cancelled by the user, no error");
	Check(PlayerInvitationDialogClose() == 0, "Invitation: Close");
	Check(PlayerInvitationDialogTerminate() == 0, "Invitation: Terminate");
	Check(PlayerInvitationDialogUpdateStatus() == STATUS_NONE, "Invitation: NONE after Terminate");
}

int main() {
	TestPlayGo();
	TestNpCommerce();
	TestPlayerInvitation();
	if (g_failed != 0) {
		std::fprintf(stderr, "DialogsTests: %d check(s) FAILED\n", g_failed);
		return 1;
	}
	std::fprintf(stderr, "DialogsTests: all checks passed\n");
	return 0;
}
