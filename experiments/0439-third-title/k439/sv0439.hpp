// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 (tag sv439): KYTY_BC5_SYSTEM_SW_VERSION, the system software version the host reports to a title, as a
// diagnosis switch read once at start (the maintainer, 11-21: the firmware version is to be a switch, so
// that it can be changed for a test). Not in lean builds (the host answers its constant there) unless it is later baked as a
// per-title default.
//   unset            today's constant, 10.60
//   "param"          the title's own requiredSystemSoftwareVersion from param.json ("0x1160000000000000": the top byte is
//                    the major version as BCD-like hex digits, the next byte the minor as written, so 11.60)
//   "MAJOR.MINOR"    any explicit version, e.g. 9.00, 10.60, 11.60, 12.00 (major 1-99, minor 0-99)
// anything else is malformed and refused (the caller ends the run with a line; never a silent default).
// The forms the host hands out (the host's own constants for 10.60, bc5LleAgc.cpp GetProsperoSystemSwVersion and libNp.cpp
// sceNpGetSdkVersion: "10.60.000" and 0x0A600000):
//   word    (major << 24) | (minor as two decimal digits in hex << 16)        10.60 -> 0x0A600000, 11.60 -> 0x0B600000
//   string  "<major>.<minor two digits>.000"                                   10.60 -> "10.60.000"
// TODO(verify): that a console encodes other versions the same way (only 10.60's word is in the host, from AnyPS5 via exp 0405).
#pragma once

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

namespace bc5::sv439 {

struct Version {
    unsigned major = 10;
    unsigned minor = 60; // decimal, 0-99
    char str[16] = "10.60.000";
    std::uint32_t word = 0x0A600000u;
    const char *source = "unset: the host's constant";
};

inline void encode(Version &v) {
    std::snprintf(v.str, sizeof(v.str), "%u.%02u.000", v.major, v.minor);
    v.word = (static_cast<std::uint32_t>(v.major) << 24u) | (((v.minor / 10u) << 4u | (v.minor % 10u)) << 16u);
}

// "MAJOR.MINOR": digits only, a dot, two-digit minor ("10.6" is refused: it is ambiguous).
inline bool parse_explicit(const char *s, Version &v) {
    if (s == nullptr) return false;
    const char *dot = std::strchr(s, '.');
    if (dot == nullptr || dot == s || dot - s > 2 || std::strlen(dot + 1) != 2) return false;
    for (const char *p = s; *p != 0; ++p)
        if (p != dot && (*p < '0' || *p > '9')) return false;
    const unsigned a = static_cast<unsigned>(std::strtoul(s, nullptr, 10));
    const unsigned b = static_cast<unsigned>(std::strtoul(dot + 1, nullptr, 10));
    if (a < 1 || a > 99 || b > 99) return false;
    v.major = a;
    v.minor = b;
    encode(v);
    return true;
}

// param.json's text: "requiredSystemSoftwareVersion": "0x1160000000000000" -> 11.60.
inline bool parse_param(const std::string &json, Version &v) {
    const std::size_t at = json.find("\"requiredSystemSoftwareVersion\"");
    if (at == std::string::npos) return false;
    const std::size_t hx = json.find("0x", at);
    if (hx == std::string::npos || hx > at + 64) return false;
    const std::uint64_t raw = std::strtoull(json.c_str() + hx, nullptr, 16);
    const unsigned hi = static_cast<unsigned>(raw >> 56u), lo = static_cast<unsigned>(raw >> 48u) & 0xffu;
    if ((hi >> 4u) > 9u || (hi & 15u) > 9u || (lo >> 4u) > 9u || (lo & 15u) > 9u) return false;
    v.major = (hi >> 4u) * 10u + (hi & 15u);
    v.minor = (lo >> 4u) * 10u + (lo & 15u);
    if (v.major < 1) return false;
    encode(v);
    return true;
}

// The switch: env value (or nullptr) and param.json's text (empty when not read). False = malformed: refuse.
inline bool from_switch(const char *env, const std::string &param_json, Version &v, std::string &why) {
    v = Version{};
    if (env == nullptr || env[0] == 0) return true;
    if (std::strcmp(env, "param") == 0) {
        if (param_json.empty()) {
            why = "\"param\" but the title's param.json (BC5_PARAM_JSON) could not be read";
            return false;
        }
        if (!parse_param(param_json, v)) {
            why = "\"param\" but param.json has no readable requiredSystemSoftwareVersion";
            return false;
        }
        v.source = "the title's param.json";
        return true;
    }
    if (!parse_explicit(env, v)) {
        why = std::string("\"") + env + "\" is not MAJOR.MINOR (e.g. 11.60), \"param\", or unset";
        return false;
    }
    v.source = "the switch's explicit value";
    return true;
}

} // namespace bc5::sv439
