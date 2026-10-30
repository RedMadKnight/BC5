// Laptop stand-in for the host's common/magicEnum.h: the SymbolType names.
#pragma once
#include <string>
namespace Common {
template <typename E>
std::string EnumName(E e) {
	static const char* const names[] = {"Unknown", "Func", "Object", "TlsModule", "NoType"};
	return names[static_cast<int>(e)];
}
} // namespace Common
