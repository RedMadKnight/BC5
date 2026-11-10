#!/usr/bin/env python3
"""BC5 experiment 0405 (series e6 of experiment 0401), tag "fwn": the maintainer's decision 1 of 2026-11-04 (values that
AnyPS5's authors took from firmware modules run natively or under an emulator, or from readings of modules, are accepted as
another person's description) for the Rtc, Rudp, Net, SystemService and NpCppWebApi units of the e6 input tree (e5's
sources), behind one switch that is off by default and read once (off is today's path exactly):
  KYTY_BC5_FW_NET  items  rtc       src/libs/libRtc.cpp            R1 #35: AnyPS5 4dd4ec5ff, far-year rule of FormatRFC3339
                          rudp      src/libs/libRudp.cpp           R1 #35: AnyPS5 11f42d025, SetEventHandler's checks
                          resolver  src/libs/network.cpp           R1 #35: AnyPS5 ce093095f, resolver timeout/retry checks
                          param400  src/libs/libSystemService.cpp  e5 lib0405 "Item 4": parameter 400 = the language
                          npwebapi  src/libs/libNpCppWebApi.cpp    R1 D1 row 08fa66176: finish of a never-started transaction
A value naming items ("rtc,param400") turns on only those; any other non-empty value but "0" turns on all of them.
libRtc.cpp prints the group's one stderr line at its registration; the other units read the switch silently.
Each unit's input md5 is pinned and asserted; a unit that has the edit already is refused; every anchor must occur exactly
once; every edit keeps braces, parentheses and brackets balanced; the inserted text is ASCII; line ends stay as they are
(all five units are LF). After editing, the script undoes its own edits on the output and asserts that this gives the
input back byte for byte. Only the five units are written, and only when all five are done. Prints "<relpath> <md5>" per
written file. Notes: fwn0405-notes.md; CPU test: fwn0405.cpp.
usage: mkfwn0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

MARKS = (b"KYTY_BC5_FW_NET", b"Bc5FwNet", b"Bc5RtcFormat", b"Bc5RudpSetEventHandler", b"Bc5NetResolver",
         b"Bc5SysParam400", b"Bc5NpFinish", b"BC5_FWN_")


def T(text, crlf=False):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    out = text.replace("»", "\t").encode("ascii")
    if crlf:
        assert b"\r" not in out
        out = out.replace(b"\n", b"\r\n")
    return out


ANYPS5 = "AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762"

# The switch's parser, the same in every unit (each unit gets its own copy under its own names: "@P@").
SWITCH = r"""static uint32_t Bc5FwNet@P@Parse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»static const char* const names[] = {"rtc", "rudp", "resolver", "param400", "npwebapi"}; // bit i is names[i]
»uint32_t                 parts   = 0;
»const char*              p       = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»for (uint32_t i = 0; i < 5; i++) {
»»»if (n == std::strlen(names[i]) && std::strncmp(p, names[i], n) == 0) {
»»»»parts |= 1u << i;
»»»}
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return parts != 0 ? parts : 31u; // every item
}

"""

ITEMS_SILENT = r"""// The items of KYTY_BC5_FW_NET that are on (0: off), read once (libRtc.cpp prints the group's line).
static uint32_t Bc5FwNet@P@Items() {
»static const uint32_t parts = Bc5FwNet@P@Parse(std::getenv("KYTY_BC5_FW_NET"));
»return parts;
}

"""

ITEMS_PRINT = r"""// The items of KYTY_BC5_FW_NET that are on (0: off), read once; the first call (this library's registration) prints the
// group's one stderr line, on or off.
static uint32_t Bc5FwNet@P@Items() {
»static const uint32_t parts = [] {
»»const uint32_t p = Bc5FwNet@P@Parse(std::getenv("KYTY_BC5_FW_NET"));
»»if (p == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: fw-net off\n");
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0405: fw-net on (items:%s%s%s%s%s)\n", (p & 1u) != 0 ? " rtc" : "",
»»»             (p & 2u) != 0 ? " rudp" : "", (p & 4u) != 0 ? " resolver" : "", (p & 8u) != 0 ? " param400" : "",
»»»             (p & 16u) != 0 ? " npwebapi" : "");
»»}
»»std::fflush(stderr);
»»return p;
»}();
»return parts;
}

"""

TELL = r"""// A stderr line for each of the first 8 calls in this file whose answer KYTY_BC5_FW_NET changed (only when it is on).
static void Bc5FwNet@P@Tell(const char* what) {
»static std::atomic<uint32_t> told {0};
»if (told.fetch_add(1, std::memory_order_relaxed) < 8) {
»»std::fprintf(stderr, "[bc5] exp 0405: fw-net %s\n", what);
»»std::fflush(stderr);
»}
}

"""

SWITCH_DOC = """// KYTY_BC5_FW_NET (one switch for this group: libRtc.cpp, libRudp.cpp, network.cpp, libSystemService.cpp,
// libNpCppWebApi.cpp): unset, empty or "0" is off (today's path exactly); any other value turns every item on, unless it
// names items (comma-separated): rtc, rudp, resolver, param400, npwebapi. Each unit reads it once; libRtc.cpp prints the
// group's one stderr line at its registration.
"""


def switch(p, printer):
    return (SWITCH + (ITEMS_PRINT if printer else ITEMS_SILENT) + TELL).replace("@P@", p)


# =====================================================================================================================
# src/libs/libRtc.cpp ("rtc", R1 #35)
# =====================================================================================================================
RTC_BLOCK_ANCHOR = "static int KYTY_SYSV_ABI RtcFormatRFC3339(char* date_time, const RtcTick* utc,\n"
RTC_BLOCK = (r"""// ---- BC5 experiment 0405 (series e6 of experiment 0401): KYTY_BC5_FW_NET, item "rtc" ----
// exp 0405 R1 #35, cleared by the maintainer's decision 1 of 2026-11-04 (values from firmware modules run natively or
// under an emulator are accepted as another person's description). Ported in adapted form from """ + ANYPS5 + r""",
// core/libs/prx/libSceRtc/Export.cpp:578-599 (sceRtcFormatRFC3339), commit 4dd4ec5ff "check the 16-bit year when
// formatting far ticks" (BunnyFl). Its debt note docs/dev/debt/libSceRtc.md:12: the zone-shifted tick is converted to a
// date whose year is kept in 16 bits, as the date-time record stores it, and only that year is checked (1 to 9999), so
// past year 65535 it wraps: a tick in year 65536 returns RTC_ERROR_INVALID_YEAR (0x80B50008), one in year 65537 formats
// as year 0001; "from firmware 13.42's module run natively" (SDK versions 0x01000051, 0x03000000, 0x0A000000), "not
// measured on a console". From the same function: a zone outside -1439 to 1439 minutes returns RTC_ERROR_INVALID_VALUE
// (debt :14, native formatting), and so does a zone shift that overflows or underflows 64 bits (debt :11, measured on PS4
// 10.71 for SDK 0x03000000 on and on PS5 13.60, the rule a PS5 title always gets).
// Today: a tick past year 9999 returns INVALID_VALUE (0x80B50003, from RtcSetTick), a zone outside the limit is
// formatted, and an eastern zone that overflows 64 bits wraps to year 1. Here the date is computed with this file's own
// day arithmetic (RtcSetTick's) in 64 bits; only the year is then cut to 16 bits. The text is today's format.
""" + SWITCH_DOC + r"""// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file.
static constexpr uint32_t BC5_FWN_RTC = 1u;

""" + switch("Rtc", True) + r"""// "rtc": sceRtcFormatRFC3339 with the far-year rule; date_time is not null (the caller checked it, as today).
static int Bc5RtcFormatRFC3339(char* date_time, const RtcTick* utc, int time_zone_minutes) {
»RtcTick tick {};
»if (utc == nullptr) {
»»const auto ret = RtcGetCurrentTick(&tick);
»»if (ret != OK) {
»»»return ret;
»»}
»} else {
»»tick = *utc;
»}
»if (time_zone_minutes < -1439 || time_zone_minutes > 1439) {
»»Bc5FwNetRtcTell("rtc: FormatRFC3339 zone outside -1439..1439 minutes -> 0x80B50003 (formatted when off)");
»»return RTC_ERROR_INVALID_VALUE;
»}
»const int64_t shift = static_cast<int64_t>(time_zone_minutes) * 60000000ll;
»if (shift < 0 ? tick.tick < static_cast<uint64_t>(-shift)
»              : tick.tick > std::numeric_limits<uint64_t>::max() - static_cast<uint64_t>(shift)) {
»»if (shift > 0) {
»»»Bc5FwNetRtcTell("rtc: FormatRFC3339 zone shift overflows 64 bits -> 0x80B50003 (wraps when off)");
»»}
»»return RTC_ERROR_INVALID_VALUE;
»}
»const uint64_t local = tick.tick + static_cast<uint64_t>(shift); // modulo 2^64: a western zone subtracts

»// The date of `local`, with RtcSetTick's day arithmetic, the year in 64 bits.
»uint64_t days = local / 86400000000ull;
»uint64_t usec = local % 86400000000ull;
»days += 307;
»uint64_t j  = (days << 2) - 1;
»uint64_t ly = j / 146097;
»j -= 146097 * ly;
»uint64_t ld = j >> 2;
»j           = ((ld << 2) + 3) / 1461;
»ld          = (((ld << 2) + 7) - 1461 * j) >> 2;
»uint64_t lm = (5 * ld - 3) / 153;
»ld          = (5 * ld + 2 - 153 * lm) / 5;
»ly          = 100 * ly + j;
»if (lm < 10) {
»»lm += 3;
»} else {
»»lm -= 9;
»»ly++;
»}
»if (ly > 9999) {
»»Bc5FwNetRtcTell("rtc: FormatRFC3339 past year 9999: the 16-bit year rule (0x80B50003 when off)");
»}
»const auto year = static_cast<uint16_t>(ly); // kept in 16 bits, as the date-time record keeps it: wraps past 65535
»if (year == 0 || year > 9999) {
»»return RTC_ERROR_INVALID_YEAR;
»}

»const auto hour = static_cast<unsigned>(usec / 3600000000ull);
»usec %= 3600000000ull;
»const auto minute = static_cast<unsigned>(usec / 60000000ull);
»usec %= 60000000ull;
»const auto second = static_cast<unsigned>(usec / 1000000ull);
»usec %= 1000000ull;

»char zone[8] {};
»if (time_zone_minutes == 0) {
»»std::snprintf(zone, sizeof(zone), "Z");
»} else {
»»const auto sign    = (time_zone_minutes < 0 ? '-' : '+');
»»const auto minutes = (time_zone_minutes < 0 ? -time_zone_minutes : time_zone_minutes);
»»std::snprintf(zone, sizeof(zone), "%c%02d:%02d", sign, minutes / 60, minutes % 60);
»}

»std::snprintf(date_time, 32, "%04u-%02u-%02uT%02u:%02u:%02u.%02u%s", static_cast<unsigned>(year),
»              static_cast<unsigned>(lm), static_cast<unsigned>(ld), hour, minute, second,
»              static_cast<unsigned>(usec / 10000), zone);

»return OK;
}
// ---- end of experiment 0405's fw-net Rtc helpers ----

""")

RTC_EDITS = (
    ("includes",
     "#include <chrono>\n#include <cstdint>\n#include <cstdio>\n#include <ctime>\n#include <limits>\n",
     "#include <atomic>  // BC5 experiment 0405 (KYTY_BC5_FW_NET)\n#include <chrono>\n#include <cstdint>\n#include <cstdio>\n"
     "#include <cstdlib> // BC5 experiment 0405: std::getenv\n#include <cstring> // BC5 experiment 0405: std::strcmp\n"
     "#include <ctime>\n#include <limits>\n"),
    ("RtcFormatRFC3339: rtc",
     "»if (date_time == nullptr) {\n»»return RTC_ERROR_INVALID_POINTER;\n»}\n\n»RtcTick tick {};\n»if (utc == nullptr) {\n",
     "»if (date_time == nullptr) {\n»»return RTC_ERROR_INVALID_POINTER;\n»}\n"
     "»if ((Bc5FwNetRtcItems() & BC5_FWN_RTC) != 0) { // BC5 experiment 0405 (KYTY_BC5_FW_NET \"rtc\"); today's path when off\n"
     "»»return Bc5RtcFormatRFC3339(date_time, utc, time_zone_minutes);\n»}\n\n»RtcTick tick {};\n»if (utc == nullptr) {\n"),
    ("registration: the group's line",
     "LIB_DEFINE(InitRtc_1_Rtc) {\n",
     "LIB_DEFINE(InitRtc_1_Rtc) {\n"
     "»(void)Rtc::Bc5FwNetRtcItems(); // BC5 experiment 0405: reads KYTY_BC5_FW_NET once and prints the group's line\n"),
)
RTC_BEFORE = ("static int KYTY_SYSV_ABI RtcGetCurrentTick(RtcTick* tick) {\n", "struct RtcDateTime {\n",
              "constexpr int RTC_ERROR_INVALID_YEAR           = -2135621624; /* 0x80B50008 */\n")
RTC_AFTER = ("LIB_DEFINE(InitRtc_1_Rtc) {",)
RTC_USES = (("static uint32_t Bc5FwNetRtcItems()", 1), ("Bc5FwNetRtcItems()", 3), ("Bc5FwNetRtcParse(", 2),
            ("Bc5FwNetRtcTell(", 4), ("Bc5RtcFormatRFC3339(", 2), ("BC5_FWN_RTC", 2))

# =====================================================================================================================
# src/libs/libRudp.cpp ("rudp", R1 #35)
# =====================================================================================================================
RUDP_BLOCK_ANCHOR = "static KYTY_SYSV_ABI int RudpSetEventHandler(RudpEventHandler handler, void* arg) {\n"
RUDP_BLOCK = (r"""// ---- BC5 experiment 0405 (series e6 of experiment 0401): KYTY_BC5_FW_NET, item "rudp" ----
// exp 0405 R1 #35, cleared by the maintainer's decision 1 of 2026-11-04. Ported in adapted form from """ + ANYPS5 + r""",
// core/libs/prx/libSceRudp/Export.cpp:269-280 (sceRudpSetEventHandler), commit 11f42d025 "bind, listen and accept as a
// firmware 13.42 run shows" (zaryabzip). Its debt note docs/dev/debt/libSceRudp.md:23: sceRudpSetEventHandler returns
// RUDP_ERROR_NOT_INITIALIZED (0x80770001) before sceRudpInit and RUDP_ERROR_NO_EVENT_HANDLER (0x80770022) for a null
// handler, "as the 13.42 run under an emulator with imports stubbed shows; not measured on a console" (BunnyFl's run,
// AnyPS5 issue 13682). Neither error stores the handler. Today both store it and return 0.
// Not taken: sceRudpEnd clearing the handler, sceRudpBind, sceRudpListen and sceRudpAccept from the same commit: this file
// registers none of them (exp 0405 R1 #39 keeps Rudp's 31 missing exports for later).
""" + SWITCH_DOC + r"""// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file.
static constexpr uint32_t BC5_FWN_RUDP                    = 2u;
static constexpr int      BC5_RUDP_ERROR_NOT_INITIALIZED  = static_cast<int>(0x80770001u);
static constexpr int      BC5_RUDP_ERROR_NO_EVENT_HANDLER = static_cast<int>(0x80770022u);

""" + switch("Rudp", False) + r"""// "rudp": the checks sceRudpSetEventHandler makes before it stores the handler; OK (store it: today's path) when off.
static int Bc5RudpSetEventHandlerCheck(RudpEventHandler handler) {
»if ((Bc5FwNetRudpItems() & BC5_FWN_RUDP) == 0) {
»»return OK;
»}
»if (!g_initialized) {
»»Bc5FwNetRudpTell("rudp: SetEventHandler before sceRudpInit -> 0x80770001, not stored (stored and 0 when off)");
»»return BC5_RUDP_ERROR_NOT_INITIALIZED;
»}
»if (handler == nullptr) {
»»Bc5FwNetRudpTell("rudp: SetEventHandler(null) -> 0x80770022, not stored (stored and 0 when off)");
»»return BC5_RUDP_ERROR_NO_EVENT_HANDLER;
»}
»return OK;
}
// ---- end of experiment 0405's fw-net Rudp helpers ----

""")

RUDP_EDITS = (
    ("includes",
     "#include <cinttypes>\n#include <cstdint>\n",
     "#include <atomic>  // BC5 experiment 0405 (KYTY_BC5_FW_NET)\n#include <cinttypes>\n#include <cstdint>\n"
     "#include <cstdio>  // BC5 experiment 0405: std::fprintf\n#include <cstdlib> // BC5 experiment 0405: std::getenv\n"
     "#include <cstring> // BC5 experiment 0405: std::strcmp\n"),
    ("RudpSetEventHandler: rudp",
     "»g_event_handler = handler;\n»g_event_arg     = arg;\n",
     "»const int bc5_refused = Bc5RudpSetEventHandlerCheck(handler); // BC5 experiment 0405 (KYTY_BC5_FW_NET \"rudp\"); OK when off\n"
     "»if (bc5_refused != OK) {\n»»return bc5_refused;\n»}\n\n"
     "»g_event_handler = handler;\n»g_event_arg     = arg;\n"),
)
RUDP_BEFORE = ("static bool             g_initialized   = false;\n",
               "using RudpEventHandler = void (*)(int ctx_id, int event_id, int error_code, void* arg);\n")
RUDP_AFTER = ("LIB_DEFINE(InitRudp_1) {",)
RUDP_USES = (("Bc5FwNetRudpItems()", 2), ("Bc5FwNetRudpParse(", 2), ("Bc5FwNetRudpTell(", 3),
             ("Bc5RudpSetEventHandlerCheck(", 2), ("BC5_FWN_RUDP", 2))

# =====================================================================================================================
# src/libs/network.cpp ("resolver", R1 #35)
# =====================================================================================================================
NET_BLOCK_ANCHOR = "int KYTY_SYSV_ABI NetResolverStartNtoa(int rid, const char* hostname, void* addr, int timeout,\n"
NET_BLOCK = (r"""// ---- BC5 experiment 0405 (series e6 of experiment 0401): KYTY_BC5_FW_NET, item "resolver" ----
// exp 0405 R1 #35, cleared by the maintainer's decision 1 of 2026-11-04. Ported in adapted form from """ + ANYPS5 + r""",
// core/libs/prx/libSceNet/Export.cpp:2547-2552 (sceNetResolverStartNtoa), commit ce093095f "refuse resolver timeouts
// below one second as firmware 13.42 does" (zaryabzip). Its debt note docs/dev/debt/libSceNet.md:98: a negative timeout
// or retry count fails with NET_EINVAL before anything else is checked, as prosper's reading of the libSceNet module gives
// (github.com/mattias800/prosper @ 6c09a34a prosper/src/hle/net/hle_net.cpp:579-587), and a timeout from 1 to 999999
// also fails with NET_EINVAL before the resolver is looked up, 0 counting as 1000000, as "@BunnyFl's 13.42 run of the
// module shows" (AnyPS5 PR 9727). Today neither the timeout nor the retry count is looked at. Still not applied: the
// timeout and the retry count themselves (one synchronous host lookup, as today).
""" + SWITCH_DOC + r"""// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file.
static constexpr uint32_t BC5_FWN_RESOLVER = 4u;

""" + switch("Net", False) + r"""// "resolver": true when sceNetResolverStartNtoa refuses its timeout or retry count with NET_EINVAL; false when off.
static bool Bc5NetResolverArgsRefused(int timeout, int retry) {
»if ((Bc5FwNetNetItems() & BC5_FWN_RESOLVER) == 0) {
»»return false;
»}
»if (timeout < 0 || (timeout != 0 && timeout < 1000000) || retry < 0) {
»»Bc5FwNetNetTell("resolver: StartNtoa timeout under 1 s or a negative retry -> NET_ERROR_EINVAL (looked up when off)");
»»return true;
»}
»return false;
}
// ---- end of experiment 0405's fw-net resolver helpers ----

""")

NET_EDITS = (
    ("NetResolverStartNtoa: resolver",
     "»(void)timeout;\n»(void)retry;\n\n»if (hostname == nullptr || addr == nullptr || (flags & ~0x00010000) != 0) {\n",
     "»(void)timeout;\n»(void)retry;\n"
     "»if (Bc5NetResolverArgsRefused(timeout, retry)) { // BC5 experiment 0405 (KYTY_BC5_FW_NET \"resolver\"); false when off\n"
     "»»return NET_ERROR_EINVAL;\n»}\n\n"
     "»if (hostname == nullptr || addr == nullptr || (flags & ~0x00010000) != 0) {\n"),
)
NET_BEFORE = ("#include <atomic>\n#include <chrono>\n#include <condition_variable>\n#include <cstdlib>\n#include <cstdio>\n"
              "#include <cstring>\n", "namespace Net {\n")
NET_AFTER = ("int KYTY_SYSV_ABI NetInetPton(int af, const char* src, void* dst) {",)
NET_USES = (("Bc5FwNetNetItems()", 2), ("Bc5FwNetNetParse(", 2), ("Bc5FwNetNetTell(", 2),
            ("Bc5NetResolverArgsRefused(", 2), ("BC5_FWN_RESOLVER", 2))

# =====================================================================================================================
# src/libs/libSystemService.cpp ("param400", e5 lib0405 "Item 4")
# =====================================================================================================================
SYS_BLOCK_ANCHOR = "static int KYTY_SYSV_ABI SystemServiceParamGetInt(int param_id, int* value) {\n"
SYS_BLOCK = (r"""// ---- BC5 experiment 0405 (series e6 of experiment 0401): KYTY_BC5_FW_NET, item "param400" ----
// The value e5 held (lib0405-notes.md "Item 4"; exp 0405 R1 #4), cleared by the maintainer's decision 1 of 2026-11-04
// (readings of firmware modules are accepted as another person's description). After """ + ANYPS5 + r""",
// core/libs/prx/libSceSystemService/Export.cpp:549-566 (sceSystemServiceParamGetInt; :555, parameter 400 answers as
// parameter 1) and its debt note docs/dev/debt/libSceSystemService.md:70: "in the PS5 10.01 and 12.60 libSceSystemService
// modules parameter 400 reads the same registry value as parameter 1", without parameter 1's mapping of newer language
// numbers by SDK version (this file has no such mapping for parameter 1 either), and the 4.03 module has no parameter
// 400; the 0x80A10003 those modules return when an unidentified imported check returns 1 is not modelled (as in AnyPS5).
// A 13.40 console answered parameter 400 (debt :74, measured). Its name is not known. Today parameter 400 answers 0.
// With "param400" it answers what parameter 1 answers here (the input configuration's SystemLanguage, else
// --console-language). Independent of KYTY_BC5_SYSTEMSERVICE_VALUES (e5), which already lets parameter 400 answer.
""" + SWITCH_DOC + r"""// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file.
static constexpr uint32_t BC5_FWN_PARAM400 = 8u;

""" + switch("Sys", False) + r"""// "param400": ParamGetInt(400) answers the language into *v (true); false (today's "unsupported, 0") when off or another
// parameter.
static bool Bc5SysParam400(int param_id, int* v) {
»if (param_id != 400 || (Bc5FwNetSysItems() & BC5_FWN_PARAM400) == 0) {
»»return false;
»}
»const int system_language = Graphics::HostInputSystemLanguage();
»*v                        = system_language >= 0 ? system_language : static_cast<int>(Config::GetConsoleLanguage());
»Bc5FwNetSysTell("param400: ParamGetInt(400) answers the language (0 when off)");
»return true;
}
// ---- end of experiment 0405's fw-net SystemService helpers ----

""")

SYS_EDITS = (
    ("include <atomic>",
     "#include <cstdlib> // BC5 experiment 0405: std::getenv\n#include <cstring>\n",
     "#include <atomic>  // BC5 experiment 0405 (KYTY_BC5_FW_NET)\n"
     "#include <cstdlib> // BC5 experiment 0405: std::getenv\n#include <cstring>\n"),
    ("ParamGetInt: param400",
     "»»default:\n»»»LOGF_COLOR(Log::Color::Yellow, \" unsupported param_id %d, using 0\\n\", param_id);\n»»»break;\n",
     "»»default:\n"
     "»»»if (Bc5SysParam400(param_id, &v)) { // BC5 experiment 0405 (KYTY_BC5_FW_NET \"param400\"); false when off\n"
     "»»»»break;\n»»»}\n"
     "»»»LOGF_COLOR(Log::Color::Yellow, \" unsupported param_id %d, using 0\\n\", param_id);\n»»»break;\n"),
)
SYS_BEFORE = ("#include \"graphics/presentation/window/hostInput.h\" // experiment 0337\n",
              "#include \"common/emulatorConfig.h\"\n", "#include <cstdio>\n")
SYS_AFTER = ("LIB_DEFINE(InitSystemService_1) {",)
SYS_USES = (("Bc5FwNetSysItems()", 2), ("Bc5FwNetSysParse(", 2), ("Bc5FwNetSysTell(", 2), ("Bc5SysParam400(", 2),
            ("BC5_FWN_PARAM400", 2))

# =====================================================================================================================
# src/libs/libNpCppWebApi.cpp ("npwebapi", R1 D1 row 08fa66176)
# =====================================================================================================================
NP_BLOCK_ANCHOR = "extern \"C\" {\n\nstruct IntrusivePtr {\n"
NP_BLOCK = (r"""// ---- BC5 experiment 0405 (series e6 of experiment 0401): KYTY_BC5_FW_NET, item "npwebapi" ----
// exp 0405 R1 verdict row D1 libSceNpCppWebApi 08fa66176 (class excluded-provenance: "finish returns 0x80553508 per the
// bundled PPSA21564 module"), cleared by the maintainer's decision 1 of 2026-11-04 (a reading of a module's behaviour).
// Ported in adapted form from """ + ANYPS5 + r""", core/libs/prx/libSceNpCppWebApi/Export.cpp:11
// (TransactionNotStarted) and its finish overrides, commit 08fa66176 "answer finish, abort and getId for never-started
// transactions as the module does" (Alexandre Figueiredo): finish of a transaction that never started returns 0x80553508,
// as the libSceNpCppWebApi module bundled with PPSA21564 does. Here every request fails before its transaction starts
// (SCE_NP_WEBAPI_ERROR_NOT_SIGNED_IN), so every finish this file registers answers 0x80553508 with the item on; today they
// return 0. Not taken: abort and getId (this file registers neither) and the commit's constructor changes.
""" + SWITCH_DOC + r"""// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file.
static constexpr uint32_t BC5_FWN_NPWEBAPI               = 16u;
static constexpr int      BC5_NP_TRANSACTION_NOT_STARTED = static_cast<int>(0x80553508u);

""" + switch("Np", False) + r"""// "npwebapi": true when finish answers BC5_NP_TRANSACTION_NOT_STARTED (no transaction here ever starts); false when off.
static bool Bc5NpFinishNotStarted() {
»if ((Bc5FwNetNpItems() & BC5_FWN_NPWEBAPI) == 0) {
»»return false;
»}
»Bc5FwNetNpTell("npwebapi: finish of a never-started transaction -> 0x80553508 (0 when off)");
»return true;
}
// ---- end of experiment 0405's fw-net NpCppWebApi helpers ----

""")

NP_FINISH = (
    ("_ZN3sce2Np9CppWebApi6Common21DownStreamTransactionINS2_12IntrusivePtrINS1_17TitleCloudStorage2V17DataApi27DownloadDataResponseHeadersEEEE6finishEv", " "),
    ("_ZN3sce2Np9CppWebApi6Common15TransactionBaseINS2_12IntrusivePtrINS1_14SessionManager2V130PostPlayerSessionsResponseBodyEEENS4_INS2_18ResponseHeaderBaseEEEE6finishEv", "    "),
    ("_ZN3sce2Np9CppWebApi6Common15TransactionBaseINS2_12IntrusivePtrINS1_14SessionManager2V152PostPlayerSessionsSessionIdMemberPlayersResponseBodyEEENS4_INS2_18ResponseHeaderBaseEEEE6finishEv", "    "),
    ("_ZN3sce2Np9CppWebApi6Common15TransactionBaseINS2_15DefaultResponseENS2_12IntrusivePtrINS2_18ResponseHeaderBaseEEEE6finishEv", "    "),
    ("_ZN3sce2Np9CppWebApi6Common15TransactionBaseINS2_12IntrusivePtrINS1_14SessionManager2V154GetUsersAccountIdPlayerSessionsInvitationsResponseBodyEEENS4_INS2_18ResponseHeaderBaseEEEE6finishEv", "    "),
)
NP_EDITS = tuple(
    [("include <cstdio>",
      "#include <cstdint>\n#include <cstdlib>\n",
      "#include <cstdint>\n#include <cstdio> // BC5 experiment 0405: std::fprintf\n#include <cstdlib>\n")]
    + [("finish: npwebapi %d" % i,
        "int KYTY_SYSV_ABI %s() {\n%sreturn 0;\n}\n" % (name, ind),
        "int KYTY_SYSV_ABI %s() {\n" % name
        + "%sif (Bc5NpFinishNotStarted()) { // BC5 experiment 0405 (KYTY_BC5_FW_NET \"npwebapi\"); false when off\n" % ind
        + "%s%sreturn BC5_NP_TRANSACTION_NOT_STARTED;\n%s}\n" % (ind, ind, ind)
        + "%sreturn 0;\n}\n" % ind)
       for i, (name, ind) in enumerate(NP_FINISH)])
NP_BEFORE = ("namespace Libs::NpCppWebApi {\n", "#include <atomic>\n", "#include <cstring>\n")
NP_AFTER = ("} // extern \"C\"\n",)
NP_USES = (("Bc5FwNetNpItems()", 2), ("Bc5FwNetNpParse(", 2), ("Bc5FwNetNpTell(", 2), ("Bc5NpFinishNotStarted()", 6),
           ("BC5_NP_TRANSACTION_NOT_STARTED", 7), ("BC5_FWN_NPWEBAPI", 2))

UNITS = (
    # rel, pinned input md5, crlf, block anchor, block, edits, defined-before, used-after, helper uses
    ("src/libs/libRtc.cpp", "e1689ac69353d76f206bd7bb7736d3b8", False, RTC_BLOCK_ANCHOR, RTC_BLOCK, RTC_EDITS, RTC_BEFORE,
     RTC_AFTER, RTC_USES),
    ("src/libs/libRudp.cpp", "9fbe2847b2aa61564c9eea80ceb4617a", False, RUDP_BLOCK_ANCHOR, RUDP_BLOCK, RUDP_EDITS,
     RUDP_BEFORE, RUDP_AFTER, RUDP_USES),
    ("src/libs/network.cpp", "98d501f4e09322ab8727dd65ff0ea45c", False, NET_BLOCK_ANCHOR, NET_BLOCK, NET_EDITS, NET_BEFORE,
     NET_AFTER, NET_USES),
    ("src/libs/libSystemService.cpp", "4aa00c539657776620a49e222f3f8fa2", False, SYS_BLOCK_ANCHOR, SYS_BLOCK, SYS_EDITS,
     SYS_BEFORE, SYS_AFTER, SYS_USES),
    ("src/libs/libNpCppWebApi.cpp", "935fcc7e4ab1108f3d2d8b33eaf65bf6", False, NP_BLOCK_ANCHOR, NP_BLOCK, NP_EDITS,
     NP_BEFORE, NP_AFTER, NP_USES),
)


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def edit_unit(rel, s, crlf, anchor, block, edits, before, after, uses):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", rel, m)
    assert (b"\r\n" in s) == crlf, ("line ends are not the expected ones", rel)
    if not crlf:
        assert b"\r" not in s, ("a CR in an LF unit", rel)
    A = T(anchor, crlf)
    B = T(block, crlf)
    assert balance(B) == (0, 0, 0), ("the block is not balanced", rel, balance(B))
    assert s.count(A) == 1, ("the block's anchor", rel, s.count(A))
    at = s.index(A)
    for b in before:
        bb = T(b, crlf)
        assert s.count(bb) == 1 and s.index(bb) < at, ("must be defined before the block, once", rel, b[:70], s.count(bb))
    for b in after:
        bb = T(b, crlf)
        assert s.count(bb) == 1 and s.index(bb) > at, ("must come after the block, once", rel, b[:70], s.count(bb))
    out = s.replace(A, B + A)
    done = []
    for what, old, new in edits:
        o, n = T(old, crlf), T(new, crlf)
        assert out.count(o) == 1, ("anchor", rel, what, out.count(o))
        assert balance(o) == balance(n), ("the edit changes the balance", rel, what, balance(o), balance(n))
        out = out.replace(o, n)
        done.append((o, n))
    assert balance(out) == balance(s), ("the unit's balance changed", rel, balance(s), balance(out))
    for name, n in uses:
        c = out.count(name.encode("ascii"))
        assert c == n, ("helper uses", rel, name, c, n)
    # Undo the edits on the output (last first) and the block: the input must come back byte for byte.
    back = out
    for o, n in reversed(done):
        assert back.count(n) == 1, ("undo", rel, n[:60])
        back = back.replace(n, o)
    assert back.count(B) == 1
    back = back.replace(B, b"")
    assert back == s, ("undoing the edits does not give the input back", rel)
    # The inserted text is ASCII.
    B.decode("ascii")
    for o, n in done:
        n.decode("ascii")
    if crlf:
        assert out.count(b"\n") == out.count(b"\r\n"), ("a bare LF in the CRLF unit", rel)
    else:
        assert b"\r" not in out, ("a CR in the LF unit", rel)
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    outs = []
    for rel, expect, crlf, anchor, block, edits, before, after, uses in UNITS:
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        for m in MARKS:
            assert m not in s, ("refused: the unit has the edit already", rel, m.decode())
        assert md5(s) == expect, ("refused: not the pinned input", rel, md5(s), expect)
        out = edit_unit(rel, s, crlf, anchor, block, edits, before, after, uses)
        print(f"# in:  {rel} {md5(s)}  ({len(s)} bytes, {'CRLF' if crlf else 'LF'})", file=sys.stderr)
        outs.append((rel, out))
    for rel, out in outs:  # written only when all five are done
        dst = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(out)
        print(f"{rel} {md5(out)}")


if __name__ == "__main__":
    main()
