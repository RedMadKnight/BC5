// BC5 exp 0419, test build T: the main of test0419diag.cpp (KYTY_BC5_DIAG_UNFORCE). The file is test0419g.cpp's
// preamble (the setenv/getenv stand-ins and the include of switch_defaults.hpp) followed by this main:
//   awk '/^int main/{exit} {print}' test0419g.cpp > test0419diag.cpp; cat test0419diag.main.inc >> test0419diag.cpp
int main() {
	using namespace bc5::switch_defaults;
	// nothing listed: every row forced, the environment's own value overwritten
	g_env.clear();
	g_env["KYTY_BC5_TITLE_DEFAULTS"] = "0"; // Apply returns before it looks for a title
	g_env["KYTY_BC5_APR_POSIX"]      = "0";
	Apply();
	expect("forced without the diagnostic", g_env["KYTY_BC5_APR_POSIX"] == "direct");
	expect("another fix forced", g_env.count("KYTY_BC5_FS_FIXES") != 0 && g_env["KYTY_BC5_FS_FIXES"] == "1");
	const size_t all = g_env.size();
	// the arm: the row is not applied, the environment's 0 stands, every other row as before
	g_env.clear();
	g_env["KYTY_BC5_TITLE_DEFAULTS"] = "0";
	g_env["KYTY_BC5_APR_POSIX"]      = "0";
	g_env["KYTY_BC5_DIAG_UNFORCE"]   = "KYTY_BC5_APR_POSIX";
	Apply();
	expect("the listed row keeps the environment's value", g_env["KYTY_BC5_APR_POSIX"] == "0");
	expect("the others are forced as before", g_env["KYTY_BC5_FS_FIXES"] == "1" && g_env.size() == all + 1);
	// listed and unset: stays unset
	g_env.clear();
	g_env["KYTY_BC5_TITLE_DEFAULTS"] = "0";
	g_env["KYTY_BC5_DIAG_UNFORCE"]   = "KYTY_BC5_FW_AUDIO,KYTY_BC5_APR_POSIX";
	Apply();
	expect("two names, both unset stay unset", g_env.count("KYTY_BC5_APR_POSIX") == 0 && g_env.count("KYTY_BC5_FW_AUDIO") == 0);
	expect("a third is forced", g_env["KYTY_BC5_FW_NET"] == "1");
	// whole names only
	g_env.clear();
	g_env["KYTY_BC5_DIAG_UNFORCE"] = "KYTY_BC5_APR,KYTY_BC5_APR_POSIX_X,,";
	expect("a prefix does not match", !Unforced("KYTY_BC5_APR_POSIX"));
	g_env["KYTY_BC5_DIAG_UNFORCE"] = "";
	expect("empty: none", !Unforced("KYTY_BC5_APR_POSIX"));
	g_env.erase("KYTY_BC5_DIAG_UNFORCE");
	expect("unset: none", !Unforced("KYTY_BC5_APR_POSIX"));
	std::printf(g_fail == 0 ? "test0419diag: all ok\n" : "test0419diag: %d FAILED\n", g_fail);
	return g_fail == 0 ? 0 : 1;
}
