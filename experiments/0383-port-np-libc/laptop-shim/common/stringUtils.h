// Laptop stand-in for the host's common/stringUtils.h: the four helpers symbolDatabase.cpp uses.
#pragma once
#include <string>
namespace Common {
inline bool StartsWith(const std::string& s, const std::string& prefix) { return s.rfind(prefix, 0) == 0; }
inline bool EndsWith(const std::string& s, const std::string& suffix) {
	return s.size() >= suffix.size() && s.compare(s.size() - suffix.size(), suffix.size(), suffix) == 0;
}
inline std::string RemoveFirst(const std::string& s, std::size_t n) { return s.substr(n); }
inline std::string FixDirectorySlash(const std::string& s) { return s; }
} // namespace Common
