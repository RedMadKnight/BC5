// BC5 experiment 0329: libSceNpCommerce's dialog for the KytyPlus host — the PlayStation Store dialog of a console
// without a store: every open finishes at once, cancelled by the user, nothing authorized. Ported from
// boykopovar/AnyPS5 (GPL-2.0, commit 27c88a8) core/libs/prx/libSceNpCommerce/Export.cpp (the state machine, the
// result layout: int32 result, bool authorized, reserved bytes), with the common dialog error values of shadPS4's
// commondialog.h (AnyPS5's file carries NOT_FINISHED as 0x80B80006 and ARG_NULL as 0x80B80009, which are
// INVALID_STATE and OUT_OF_MEMORY there) and this tree's RUNNING state between Open and the first UpdateStatus.
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

namespace Libs::NpCommerceDialog {

LIB_VERSION("NpCommerce", 1, "NpCommerce", 1, 1);

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

struct NpCommerceDialogResult {
	int32_t result;
	bool    authorized;
	uint8_t reserved[32];
};

static std::mutex g_mutex;
static int        g_status = STATUS_NONE;

int KYTY_SYSV_ABI NpCommerceDialogInitialize() {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	if (g_status != STATUS_NONE) {
		return COMMON_DIALOG_ERROR_ALREADY_INITIALIZED;
	}
	g_status = STATUS_INITIALIZED;
	return OK;
}

int KYTY_SYSV_ABI NpCommerceDialogOpen(const void* param) {
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

	LOGF("\t param = 0x%016" PRIx64 " (no store on this console: the dialog is cancelled at once)\n",
	     reinterpret_cast<uint64_t>(param));

	g_status = STATUS_RUNNING;
	return OK;
}

int KYTY_SYSV_ABI NpCommerceDialogUpdateStatus() {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	if (g_status == STATUS_RUNNING) {
		g_status = STATUS_FINISHED;
	}
	return g_status;
}

int KYTY_SYSV_ABI NpCommerceDialogGetStatus() {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	return g_status;
}

int KYTY_SYSV_ABI NpCommerceDialogClose() {
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

int KYTY_SYSV_ABI NpCommerceDialogGetResult(NpCommerceDialogResult* result) {
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
	result->result     = RESULT_USER_CANCELED;
	result->authorized = false;
	return OK;
}

int KYTY_SYSV_ABI NpCommerceDialogTerminate() {
	PRINT_NAME();

	std::lock_guard lock(g_mutex);
	if (g_status == STATUS_NONE) {
		return COMMON_DIALOG_ERROR_NOT_INITIALIZED;
	}
	g_status = STATUS_NONE;
	return OK;
}

LIB_DEFINE(InitNpCommerceDialog_1) {
	LIB_FUNC("0aR2aWmQal4", NpCommerceDialogInitialize);
	LIB_FUNC("DfSCDRA3EjY", NpCommerceDialogOpen);
	LIB_FUNC("LR5cwFMMCVE", NpCommerceDialogUpdateStatus);
	LIB_FUNC("r42bWcQbtZY", NpCommerceDialogGetResult);
	LIB_FUNC("m-I92Ab50W8", NpCommerceDialogTerminate);
}

} // namespace Libs::NpCommerceDialog
