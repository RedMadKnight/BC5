// Laptop stand-in for the host's common/file.h: only DbgDump uses it, and the tests do not call DbgDump.
#pragma once
#include <string>
namespace Common {
class File {
public:
	static void CreateDirectories(const std::string&) {}
	void Create(const std::string&) {}
	template <typename... A>
	void Printf(const char*, A...) {}
	void Close() {}
};
} // namespace Common
