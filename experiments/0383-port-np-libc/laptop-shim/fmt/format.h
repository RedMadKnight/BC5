// Laptop stand-in for fmt: "{}" in order, which is all symbolDatabase.cpp asks of it. The submodule is empty here.
#pragma once
#include <sstream>
#include <string>
namespace fmt {
inline void format_to_stream(std::ostringstream& out, const char* f) { out << f; }
template <typename T, typename... A>
void format_to_stream(std::ostringstream& out, const char* f, const T& value, const A&... rest) {
	for (; *f != 0; f++) {
		if (f[0] == '{' && f[1] == '}') {
			out << value;
			format_to_stream(out, f + 2, rest...);
			return;
		}
		out << *f;
	}
}
template <typename... A>
std::string format(const char* f, const A&... args) {
	std::ostringstream out;
	format_to_stream(out, f, args...);
	return out.str();
}
} // namespace fmt
