// Laptop stand-in for the host's common/hostException.h: RawLog goes to stderr.
#pragma once
#include <cstdio>
namespace Common::HostException {
class RawLog {
public:
	void Append(const char* text) { std::fputs(text, stderr); }
	void Flush() { std::fflush(stderr); }
};
} // namespace Common::HostException
