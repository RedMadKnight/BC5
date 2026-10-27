// BC5 experiment 0329: libScePlayGoDialog for the KytyPlus host. The structures, the PROCEED result and the NIDs are
// those of upstream KytyPlus's src/libs/libPlayGoDialog.cpp (Coder787/KytyPlus commit 3eee96a, GPL-2.0, after this
// tree's base f266548; its result value after shadPS4's scePlayGoDialogGetResult, playgo_dialog.cpp:26); the state
// machine is this tree's common-dialog one (src/libs/dialog.cpp: NONE / INITIALIZED / RUNNING / FINISHED), with the
// common dialog errors of shadPS4's commondialog.h. The title's package is wholly installed, so an opened dialog
// finishes at once — there is nothing to download — and its result lets the title proceed.
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

namespace Libs::PlayGoDialog {

LIB_VERSION("PlayGoDialog", 1, "PlayGoDialog", 1, 1);

constexpr int STATUS_NONE        = 0;
constexpr int STATUS_INITIALIZED = 1;
constexpr int STATUS_RUNNING     = 2;
constexpr int STATUS_FINISHED    = 3;

constexpr int RESULT_PROCEED = 3; // shadPS4 playgo_dialog.cpp:26: "Result value 3 allows games to proceed"

constexpr int COMMON_DIALOG_ERROR_NOT_INITIALIZED     = static_cast<int>(0x80B80003u);
constexpr int COMMON_DIALOG_ERROR_ALREADY_INITIALIZED = static_cast<int>(0x80B80004u);
constexpr int COMMON_DIALOG_ERROR_NOT_FINISHED        = static_cast<int>(0x80B80005u);
constexpr int COMMON_DIALOG_ERROR_INVALID_STATE       = static_cast<int>(0x80B80006u);
constexpr int COMMON_DIALOG_ERROR_ARG_NULL            = static_cast<int>(0x80B8000Du);

struct CommonDialogBaseParam {
	uint64_t size;
	uint8_t  reserved[36];
	uint32_t magic;
};
static_assert(sizeof(CommonDialogBaseParam) == 0x30);

struct PlayGoDialogParam {
	CommonDialogBaseParam base_param;
	int32_t               size;
	uint8_t               unk[0x30];
};
static_assert(sizeof(PlayGoDialogParam) == 0x68);

struct PlayGoDialogResult {
	uint8_t unk1[0x4];
	int32_t result;
	uint8_t unk2[0x20];
};
static_assert(sizeof(PlayGoDialogResult) == 0x28);

static std::mutex g_mutex;
static int        g_status = STATUS_NONE;

int KYTY_SYSV_ABI PlayGoDialogInitialize() {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	if (g_status != STATUS_NONE) {
		return COMMON_DIALOG_ERROR_ALREADY_INITIALIZED;
	}
	g_status = STATUS_INITIALIZED;
	return OK;
}

int KYTY_SYSV_ABI PlayGoDialogTerminate() {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	if (g_status == STATUS_NONE) {
		return COMMON_DIALOG_ERROR_NOT_INITIALIZED;
	}
	g_status = STATUS_NONE;
	return OK;
}

int KYTY_SYSV_ABI PlayGoDialogOpen(const PlayGoDialogParam* param) {
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

	LOGF("\t size = %" PRId32 " (the package is installed in full: the dialog finishes at once)\n", param->size);

	g_status = STATUS_FINISHED;
	return OK;
}

int KYTY_SYSV_ABI PlayGoDialogClose() {
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

int KYTY_SYSV_ABI PlayGoDialogUpdateStatus() {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	return g_status;
}

int KYTY_SYSV_ABI PlayGoDialogGetStatus() {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	return g_status;
}

int KYTY_SYSV_ABI PlayGoDialogGetResult(PlayGoDialogResult* result) {
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
	result->result = RESULT_PROCEED;
	return OK;
}

LIB_DEFINE(InitPlayGoDialog_1) {
	LIB_FUNC("fECamTJKpsM", PlayGoDialogInitialize);
	LIB_FUNC("okgIGdr5Iz0", PlayGoDialogTerminate);
	LIB_FUNC("kHd72ukqbxw", PlayGoDialogOpen);
	LIB_FUNC("fbigNQiZpm0", PlayGoDialogClose);
	LIB_FUNC("wx9TDplJKB4", PlayGoDialogGetResult);
	LIB_FUNC("NOAMxY2EGS0", PlayGoDialogGetStatus);
	LIB_FUNC("Yb60K7BST48", PlayGoDialogUpdateStatus);
}

} // namespace Libs::PlayGoDialog
