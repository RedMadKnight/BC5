// BC5 experiment 0329: libScePlayerInvitationDialog for the KytyPlus host — the invitation dialog of a console
// without a PSN sign-in: every open finishes cancelled by the user. Ported from boykopovar/AnyPS5 (GPL-2.0, commit
// 27c88a8) core/libs/prx/libScePlayerInvitationDialog/ (the state machine, the 40-byte result: int32 errorCode,
// int32 result, reserved), on this tree's common-dialog states and shadPS4's commondialog.h error values.
// SPDX-License-Identifier: GPL-2.0-only
#include "common/abi.h"
#include "common/assert.h"
#include "common/common.h"
#include "common/logging/log.h"
#include "libs/errno.h"
#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <cinttypes>
#include <cstdint>
#include <cstring>
#include <mutex>

namespace Libs::PlayerInvitationDialog {

LIB_VERSION("PlayerInvitationDialog", 1, "PlayerInvitationDialog", 1, 1);

constexpr int STATUS_NONE        = 0;
constexpr int STATUS_INITIALIZED = 1;
constexpr int STATUS_RUNNING     = 2;
constexpr int STATUS_FINISHED    = 3;

constexpr int RESULT_USER_CANCELED = 1;

constexpr int COMMON_DIALOG_ERROR_NOT_INITIALIZED     = static_cast<int>(0x80B80003u);
constexpr int COMMON_DIALOG_ERROR_ALREADY_INITIALIZED = static_cast<int>(0x80B80004u);
constexpr int COMMON_DIALOG_ERROR_NOT_FINISHED        = static_cast<int>(0x80B80005u);
constexpr int COMMON_DIALOG_ERROR_INVALID_STATE       = static_cast<int>(0x80B80006u);
constexpr int COMMON_DIALOG_ERROR_ARG_NULL            = static_cast<int>(0x80B8000Du);

struct PlayerInvitationDialogResult {
	int32_t error_code;
	int32_t result;
	uint8_t reserved[32];
};
static_assert(sizeof(PlayerInvitationDialogResult) == 40);

static std::mutex g_mutex;
static int        g_status = STATUS_NONE;

int KYTY_SYSV_ABI PlayerInvitationDialogInitialize() {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	if (g_status != STATUS_NONE) {
		return COMMON_DIALOG_ERROR_ALREADY_INITIALIZED;
	}
	g_status = STATUS_INITIALIZED;
	return OK;
}

int KYTY_SYSV_ABI PlayerInvitationDialogOpen(const void* param) {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	if (g_status == STATUS_NONE) {
		return COMMON_DIALOG_ERROR_NOT_INITIALIZED;
	}
	if (param == nullptr) {
		return COMMON_DIALOG_ERROR_ARG_NULL;
	}
	if (g_status != STATUS_INITIALIZED && g_status != STATUS_FINISHED) {
		return COMMON_DIALOG_ERROR_INVALID_STATE;
	}

	LOGF("\t param = 0x%016" PRIx64 " (no sign-in on this console: the dialog is cancelled at once)\n",
	     reinterpret_cast<uint64_t>(param));

	g_status = STATUS_RUNNING;
	return OK;
}

int KYTY_SYSV_ABI PlayerInvitationDialogUpdateStatus() {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	if (g_status == STATUS_RUNNING) {
		g_status = STATUS_FINISHED;
	}
	return g_status;
}

int KYTY_SYSV_ABI PlayerInvitationDialogGetStatus() {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	return g_status;
}

int KYTY_SYSV_ABI PlayerInvitationDialogClose() {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	if (g_status == STATUS_NONE) {
		return COMMON_DIALOG_ERROR_NOT_INITIALIZED;
	}
	if (g_status == STATUS_RUNNING) {
		g_status = STATUS_FINISHED;
	}
	return OK;
}

int KYTY_SYSV_ABI PlayerInvitationDialogTerminate() {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	if (g_status == STATUS_NONE) {
		return COMMON_DIALOG_ERROR_NOT_INITIALIZED;
	}
	g_status = STATUS_NONE;
	return OK;
}

int KYTY_SYSV_ABI PlayerInvitationDialogGetResult(PlayerInvitationDialogResult* result) {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	if (g_status == STATUS_NONE) {
		return COMMON_DIALOG_ERROR_NOT_INITIALIZED;
	}
	if (result == nullptr) {
		return COMMON_DIALOG_ERROR_ARG_NULL;
	}
	if (g_status != STATUS_FINISHED) {
		return COMMON_DIALOG_ERROR_NOT_FINISHED;
	}
	std::memset(result, 0, sizeof(*result));
	result->error_code = 0;
	result->result     = RESULT_USER_CANCELED;
	return OK;
}

LIB_DEFINE(InitPlayerInvitationDialog_1) {
	LIB_FUNC("gDm5a6GSE94", PlayerInvitationDialogTerminate);
	LIB_FUNC("kFhuwHrIUqs", PlayerInvitationDialogUpdateStatus);
	LIB_FUNC("AhqlQ8cngrk", PlayerInvitationDialogGetResult);
}

} // namespace Libs::PlayerInvitationDialog
