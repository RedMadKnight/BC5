// SPDX-License-Identifier: GPL-2.0-only
// F767: one reading of an on/off environment switch. Unset, empty and "0" are off; any other value
// is on, and a switch with parameters then reads them from the same value.
#pragma once

namespace bc5 {

inline bool env_on(const char *e) { return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0); }

} // namespace bc5
