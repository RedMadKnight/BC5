// SPDX-License-Identifier: GPL-2.0-only
// libSceAgcDriver re-creation: thin kernel-setting wrappers, system helpers, event-queue
// wrappers, and the many stubs (resource registration, capture, PA debug, wavefront debug,
// reset debug). Behaviour per the original module's behaviour (clean-room description, see
// src/reimpl/PROVENANCE.md).
#include "bc5/reimpl/agc_driver_internal.hpp"

#include <cstring>

namespace bc5::reimpl::agc_driver {

using namespace detail;

namespace {

std::int32_t simple_ioctl(std::uint64_t request, void *arg) {
    return gc_ioctl(request, arg) == 0 ? kOk : kErrGeneric;
}

std::int32_t refuse(const char *name) {
    drv_log("Warning - %s(): permission insufficient", name);
    return kErrNotPermitted;
}

constexpr std::int16_t kGpuEventFilter = -14;
constexpr std::uint16_t kEvAdd = 1;
constexpr std::uint16_t kEvDelete = 2;

std::int32_t change_event(void *eq, std::int32_t event_id, std::uint16_t flags, void *udata) {
    KernelEvent change{};
    change.ident = static_cast<std::uint64_t>(static_cast<std::int64_t>(event_id));
    change.filter = kGpuEventFilter;
    change.flags = flags;
    change.fflags = 0;
    change.data = event_id;
    change.udata = addr_of(udata);
    if (g_imports.kevent == nullptr) {
        return kErrGeneric;
    }
    if (g_imports.kevent(eq, &change, 1, nullptr, 0, nullptr) < 0) {
        const int err = g_imports.error_location != nullptr ? *g_imports.error_location() : 0;
        return g_imports.kernel_error != nullptr ? g_imports.kernel_error(err) : kErrGeneric;
    }
    return kOk;
}

// Internal stub used by the reset-mode selector (always refused, result ignored).
std::int32_t reset_halt_stub(std::uint32_t) { return kErrNotPermitted; }

} // namespace

// ---------------------------------------------------------------------------------------------
// Kernel settings.

std::int32_t sceAgcDriverSetTFRing(std::uint64_t gpu_addr, std::uint32_t size_bytes) {
    if (g_imports.get_main_soc_id != nullptr && g_imports.get_main_soc_id() == 0x840F00u &&
        size_bytes > 0x4000u) {
        size_bytes = 0x4000u;
    }
    if ((size_bytes % 4u) != 0 || (gpu_addr & 0xFFu) != 0) {
        return kErrGeneric;
    }
    TfRingArgs a{gpu_addr, size_bytes, 0};
    return simple_ioctl(kIoctlSetTfRing, &a);
}

std::int32_t sceAgcDriverGetTFRing(std::uint64_t *addr_out, std::uint32_t *size_out) {
    TfRingArgs a{};
    if (gc_ioctl(kIoctlGetTfRing, &a) != 0) {
        return kErrGeneric;
    }
    if (addr_out != nullptr) { // deviation: the original writes without null checks
        *addr_out = a.address;
    }
    if (size_out != nullptr) {
        *size_out = a.size;
    }
    return kOk;
}

std::int32_t sceAgcDriverSetHsOffchipParam(std::uint32_t value_a, std::uint32_t value_b) {
    std::uint16_t a[2] = {static_cast<std::uint16_t>(value_b), static_cast<std::uint16_t>(value_a)};
    return simple_ioctl(kIoctlSetHsOffchip, a);
}

std::int32_t sceAgcDriverGetHsOffchipParam(std::uint16_t *value_a_out, std::uint16_t *value_b_out) {
    std::uint32_t v = 0;
    if (gc_ioctl(kIoctlGetHsOffchip, &v) != 0) {
        return kErrGeneric;
    }
    if (value_a_out != nullptr) { // deviation: the original writes without null checks
        *value_a_out = static_cast<std::uint16_t>(v >> 16);
    }
    if (value_b_out != nullptr) {
        *value_b_out = static_cast<std::uint16_t>(v & 0xFFFFu);
    }
    return kOk;
}

std::int32_t sceAgcDriverDebugHardwareStatus(std::int32_t mode) {
    if (mode != 0) {
        return 0; // the original leaves the return value unset here
    }
    U32PairArgs a{0, 0};
    return gc_ioctl(kIoctlDebugHwStatus, &a) == 0 ? 1 : 0;
}

std::int32_t sceAgcDriverIsTraceInProgress() { return 0; }
std::int32_t sceAgcDriverGetShaderDebuggingStatus() { return 1; }
void *nid_NhnGMuunz0Y() { return at<void>(g_state.gpu_info); }
std::int32_t sceAgcDriverGetGpuRefClks() { return kErrNotPermitted; }
std::int32_t sceAgcDriverSetTargetRingForDiag() { return refuse("sceAgcDriverSetTargetRingForDiag"); }

std::int32_t nid_yuO_lNrj_Do(std::int32_t kind, std::uint64_t arg) {
    if (kind != 1) {
        return kErrInvalid;
    }
    const int r = g_imports.debug_raise_exception != nullptr
                      ? g_imports.debug_raise_exception(0xA002030Au, arg)
                      : -1;
    // The original has no success code: 0x8A6D0003 when the call returned 0, 0x8A6D0005 if not.
    return r == 0 ? kErrInvalid : kErrProcessOrMemory;
}

std::int32_t sceAgcDriverIsPaDebug() { return 0; }
std::int32_t sceAgcDriverGetGpuPrintfWorkArea() { return kErrNotPermitted; }
std::int32_t sceAgcDriverRegisterGpuResetCallbacks() { return kOk; }
std::int32_t sceAgcDriverUnregisterGpuResetCallbacks() { return kOk; }
std::int32_t sceAgcDriverGetTraceInitiator() { return 0; }

std::int32_t sceAgcDriverAllocateToolMemoryForGpuReset(std::uint64_t, std::uint64_t, std::uint64_t,
                                                       void *out) {
    if (out != nullptr) {
        std::memset(out, 0, 12);
    }
    return kErrNotPermitted;
}

std::int32_t sceAgcDriverGetAllocatedToolMemoryForGpuReset(std::uint64_t, void *out) {
    if (out != nullptr) {
        std::memset(out, 0, 12);
    }
    return kErrNotPermitted;
}

std::int32_t sceAgcDriverModuleRegistration(std::uint32_t, const void *interface_ptr) {
    if (interface_ptr == nullptr) {
        drv_log("module registration failed: invalid interface");
    } else {
        drv_log("module registration failed: invalid index");
    }
    return kErrInvalid;
}

std::int32_t nid_6v_D6CQHA4Y() { return kOk; }

// ---------------------------------------------------------------------------------------------
// System helpers.

std::int32_t sceAgcDriverSysGetClientNumber() {
    std::uint32_t n = 0;
    if (gc_ioctl(kIoctlSysClientNumber, &n) != 0) {
        drv_log("gnm client count error: %d", 0);
        return kErrGeneric;
    }
    return static_cast<std::int32_t>(n);
}

std::int32_t sceAgcDriverSysIsGameClosed() {
    std::uint32_t v = 0;
    // deviation: the original returns an uninitialised value when the ioctl fails.
    if (gc_ioctl(kIoctlSysIsGameClosed, &v) != 0) {
        return 0;
    }
    return static_cast<std::int32_t>(v);
}

std::int32_t sceAgcDriverSysEnableSubmitDone45Exception() {
    std::uint32_t v = 0;
    if (gc_ioctl(kIoctlSysSubmitDone45, &v) != 0) {
        drv_log("enabling the submit-done exception failed");
        return kErrGeneric;
    }
    return kOk;
}

std::uint32_t sceAgcDriverSysGetGfxAppGpuResetStatus() {
    std::uint32_t v = 0;
    return gc_ioctl(kIoctlSysGfxResetStatus, &v) == 0 ? v : 0u;
}

std::int32_t sceAgcDriverSysSubmitFlipHandleProxy() { return kOk; }

std::int32_t sceAgcDriverHp3dLockStart() {
    std::uint32_t v = 1;
    return simple_ioctl(kIoctlHp3dLock, &v);
}

std::int32_t sceAgcDriverHp3dLockEnd() {
    std::uint32_t v = 0;
    return simple_ioctl(kIoctlHp3dLock, &v);
}

std::int32_t nid_NQLvUnSDyBU(std::uint32_t a, std::uint32_t b) {
    U32PairArgs args{a, b};
    return simple_ioctl(kIoctlForwardPair, &args);
}

// ---------------------------------------------------------------------------------------------
// Event queue.

std::int32_t sceAgcDriverAddEqEvent(void *eq, std::int32_t event_id, void *udata) {
    return change_event(eq, event_id, kEvAdd, udata);
}

std::int32_t sceAgcDriverDeleteEqEvent(void *eq, std::int32_t event_id) {
    return change_event(eq, event_id, kEvDelete, nullptr);
}

std::uint64_t sceAgcDriverGetEqEventType(const void *ev) {
    return g_imports.get_event_data != nullptr ? g_imports.get_event_data(ev) : 0;
}

std::uint64_t sceAgcDriverGetEqContextId(const void *ev) {
    return g_imports.get_event_data != nullptr ? g_imports.get_event_data(ev) >> 16 : 0;
}

// ---------------------------------------------------------------------------------------------
// Resource registration: not available in this build.

std::int32_t sceAgcDriverQueryResourceRegistrationUserMemoryRequirements(std::uint64_t *size_out) {
    if (size_out != nullptr) {
        *size_out = 0;
    }
    return kErrResourceRegistration;
}
std::int32_t sceAgcDriverInitResourceRegistration() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverGetResourceRegistrationMaxNameLength() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverRegisterOwner() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverRegisterResource() { return kErrResourceRegistration; }
std::int32_t nid_JQc0956gCf0() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverRegisterGdsResource() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverUnregisterResource() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverUnregisterOwnerAndResources() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverUnregisterAllResourcesForOwner() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverRegisterDefaultOwner() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverGetDefaultOwner() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverFindResourcesPublic() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverGetResourceName() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverGetResourceType() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverGetResourceBaseAddressAndSizeInBytes() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverGetResourceUserData() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverSetResourceUserData() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverGetResourceShaderGuid() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverGetOwnerName() { return kErrResourceRegistration; }

// ---------------------------------------------------------------------------------------------
// Capture and submit validation: not available.

std::int32_t sceAgcDriverTriggerCapture() { return kErrCaptureUnavailable; }
std::int32_t sceAgcDriverRequestCaptureStart() { return kErrCaptureUnavailable; }
std::int32_t sceAgcDriverRequestCaptureStop() { return kErrCaptureUnavailable; }
std::int32_t sceAgcDriverIsCaptureInProgress() { return 0; }
std::int32_t sceAgcDriverIsSubmitValidationEnabled() { return 0; }
std::int32_t nid_jwKQ1B98Q0g() { return kErrCaptureUnavailable; }
std::int32_t nid_m9n9wJC2D_4() { return kErrCaptureUnavailable; }
std::int32_t nid__iAOE3jCnkk() { return kErrCaptureUnavailable; }
std::int32_t nid_WHIOMbb_iIU() { return kErrCaptureUnavailable; }
std::int32_t nid_chJWZcNSzjk() { return kErrCaptureUnavailable; }
std::int32_t nid_ICaGtkEIXTk() { return kErrCaptureUnavailable; }
std::int32_t sceAgcDriverSetValidationErrorOutputFrequency() { return kErrCaptureUnavailable; }

// ---------------------------------------------------------------------------------------------
// libSceAgcDriverPaDebug: stubs only.

std::int32_t sceAgcDriverGetPaDebugInterfaceVersion() {
    return refuse("sceAgcDriverGetPaDebugInterfaceVersion");
}
std::int32_t nid__MqhSEVvAPw() { return kOk; }
std::int32_t nid_Jkypw0U_HYo() { return kErrNotPermitted; }
std::int32_t sceAgcDriverSubmitMultiCommandBuffersDirect() {
    return refuse("sceAgcDriverSubmitMultiCommandBuffersDirect");
}
std::int32_t sceAgcDriverSuspendPointSubmitDirect() {
    return refuse("sceAgcDriverSuspendPointSubmitDirect");
}
std::int32_t sceAgcDriverAcquireRazorACQ() { return refuse("sceAgcDriverAcquireRazorACQ"); }
std::int32_t sceAgcDriverReleaseRazorACQ() { return refuse("sceAgcDriverReleaseRazorACQ"); }
std::int32_t sceAgcDriverSubmitToRazorACQ() { return refuse("sceAgcDriverSubmitToRazorACQ"); }
std::int32_t sceAgcDriverIsSuspendPointInFlightDirect() {
    return refuse("sceAgcDriverIsSuspendPointInFlightDirect");
}
std::int32_t nid_o2gvlIFMF1o() { return kOk; }
std::int32_t nid_tD2ECNSuTQQ() { return kOk; }
std::int32_t nid_9rDcI6cJb_8(std::uint32_t) { return kErrNotPermitted; }
void nid_O144kUYDSBo() {}
void nid_NmE3PfE211o() {}
std::int32_t nid_wxdcyVqXJEY() { return kOk; }
std::int32_t nid_1l15IdtXNWw() { return kOk; }
std::int32_t nid_8CXPPlNmvIc() { return kOk; }
std::int32_t nid_V_rBNI2HzGA() { return kErrNotPermitted; }
std::int32_t nid_kFiKcGagv5k() { return kErrNotPermitted; }
std::int32_t nid_EqwPDQyh_Ec(std::uint32_t *out) {
    if (out == nullptr) {
        return kErrInvalid;
    }
    *out = 0;
    return kOk;
}
std::int32_t nid__JFkLpCDeHM() { return kOk; }
std::int32_t nid_gpF0LZ3_19c() { return kErrNotPermitted; }
std::int32_t nid_J6S2TMmGWgA() { return kErrNotPermitted; }
std::int32_t nid_8j6_e3dPf4c() { return kErrNotPermitted; }
std::int32_t nid_nhzPF9s5WF0() { return kErrNotPermitted; }
std::int32_t nid_Cia3HgY0WiY() { return kErrNotPermitted; }
std::uint8_t nid__NIAY3DWpOw() {
    if (g_state.gpu_info == 0) {
        return 0;
    }
    std::uint32_t v = 0;
    std::memcpy(&v, at<void>(g_state.gpu_info), 4);
    return v != 0 ? 1 : 0;
}
std::uint64_t nid_LgctzJSGy7s() {
    if (g_state.gpu_info == 0) {
        return 0;
    }
    std::uint64_t v = 0;
    std::memcpy(&v, at<void>(g_state.gpu_info + 0xC8), 8);
    return v;
}
std::int32_t nid_6WO4CscVnfM() { return kOk; }
std::int32_t nid_pto0YBGGOJo(std::uint32_t *out) {
    if (out == nullptr) {
        return kErrInvalid;
    }
    *out = 0;
    return kOk;
}
std::int32_t sceAgcDriverSetTFRingDirect() { return refuse("sceAgcDriverSetTFRingDirect"); }
std::int32_t sceAgcDriverSetHsOffchipParamDirect() {
    return refuse("sceAgcDriverSetHsOffchipParamDirect");
}
std::int32_t nid_VerAUWCtrX0() { return kErrResourceRegistration; }
std::int32_t nid_IGYqP_WKCgc() { return kErrResourceRegistration; }
std::int32_t nid__CSrlr1yY_o() { return kErrResourceRegistration; }
std::int32_t nid_mxyUaQfPgb8() { return kErrResourceRegistration; }
std::int32_t nid_DGN_IaHNR8o() { return kErrResourceRegistration; }
std::int32_t nid_38aK8XQj6Cg() { return kErrResourceRegistration; }
std::int32_t nid_nTwzz_6W9Jg() { return kErrResourceRegistration; }
std::int32_t sceAgcDriverSdmaCopyLinearBlocking() {
    return refuse("sceAgcDriverSdmaCopyLinearBlocking");
}
std::int32_t sceAgcDriverRegisterCaptureInterface() {
    return refuse("sceAgcDriverRegisterCaptureInterface");
}
std::int32_t sceAgcDriverDeregisterCaptureInterface() {
    return refuse("sceAgcDriverDeregisterCaptureInterface");
}
std::int32_t nid_sW7yp7NVlrk() { return kErrCaptureUnavailable; }
std::int32_t nid_1QTqF_hYqQE() { return kErrCaptureUnavailable; }

// ---------------------------------------------------------------------------------------------
// libSceAgcDriverDebugWavefronts_nosubmission: stubs.

std::int32_t nid_JvVqPfac9vE(std::uint32_t *out) {
    if (out == nullptr) {
        return kErrWfNull;
    }
    *out = 0;
    return kErrFeatureUnavailable;
}

std::int32_t nid_CkL1hUyKZyo(std::uint32_t *buffer, std::uint32_t *count_out, std::uint64_t,
                             std::uint32_t buffer_dwords) {
    if (buffer == nullptr || count_out == nullptr) {
        return kErrWfNull;
    }
    std::memset(buffer, 0xFF, std::size_t{buffer_dwords} * 4u);
    *count_out = 0;
    return kErrFeatureUnavailable;
}

namespace {
std::int32_t zero_u64_stub(std::uint64_t *out) {
    if (out == nullptr) {
        return kErrWfNull;
    }
    *out = 0;
    return kErrFeatureUnavailable;
}
std::int32_t zero_buffer_stub(void *buffer, std::size_t bytes) {
    if (buffer == nullptr) {
        return kErrWfNull;
    }
    if (bytes == 0) {
        return kErrWfSizeZero;
    }
    std::memset(buffer, 0, bytes);
    return kErrFeatureUnavailable;
}
} // namespace

std::int32_t nid_6fugJiMPLGQ(std::uint64_t *out) { return zero_u64_stub(out); }
std::int32_t nid_cRjqDvsrGkg(std::uint64_t *out) { return zero_u64_stub(out); }
std::int32_t nid_dN1zf573IKU(std::uint64_t *out) { return zero_u64_stub(out); }
std::int32_t nid_IfCY5tDfgK8(void *buffer, std::size_t bytes) {
    return zero_buffer_stub(buffer, bytes);
}
std::int32_t nid_RXqABdLqFFA(void *buffer, std::size_t bytes) {
    return zero_buffer_stub(buffer, bytes);
}

// ---------------------------------------------------------------------------------------------
// libSceAgcDriverDebugReset_nosubmission.

std::int32_t nid_Dg_D0_2_m8g() { return kErrFeatureUnavailable; }

std::int32_t nid_4JOwdjYqMpU(std::uint32_t reset_mode_bits) {
    if ((reset_mode_bits & ~g_state.reset_allowed_mask) != 0) {
        return kErrResetMode;
    }
    g_state.reset_mode = reset_mode_bits;
    (void)reset_halt_stub(reset_mode_bits & 1u);
    (void)nid_9rDcI6cJb_8((reset_mode_bits >> 1) & 1u);
    return kOk;
}

std::uint32_t nid_KKrEe_LWNG8() { return g_state.reset_mode; }
std::uint32_t nid_qDjJ_CgiMzs() { return g_state.reset_allowed_mask; }

} // namespace bc5::reimpl::agc_driver
