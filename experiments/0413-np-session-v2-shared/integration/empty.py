"""Exp 0413: the defaults table emptied; every row becomes a launcher word of the second title (as fast7/lean7 ran)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defaults as d  # noqa: E402

TREE, REPO, WORK = sys.argv[1], sys.argv[2], sys.argv[3]
d.TREE, d.REPO, d.WORK = TREE, REPO, WORK
d.PATCH = os.path.join(REPO, "backend", "kytyplus-patches", "0001-bc5-lle-agc.patch")
H = os.path.join(TREE, "src", "bc5", "switch_defaults.hpp")
s = open(H, "rb").read().decode()
a = s.index("inline constexpr Default kDefaults[] = {\n") + len("inline constexpr Default kDefaults[] = {\n")
b = s.index("    {nullptr, nullptr}};")
s = s[:a] + ("    // Empty since exp 0413's checks: ASTRO BOT's start crashed (eboot+0x48f) with these rows on by default, through\n"
             "    // setenv and through the re-exec alike, and passed with the table off at every environment size tried. The\n"
             "    // second title's launcher sets all of them (as the daily line fast7/lean7 ran them); a row comes back here\n"
             "    // only with an ASTRO BOT start that passes.\n") + s[b:]
open(H, "wb").write(s.encode())
d.commit("int(0413): the switch-defaults table emptied; all 35 rows become the second title's launcher words\n\n"
         "On the final private binary (d1b6f9cb) ASTRO BOT's start still crashed with the remaining 35 rows delivered by the\n"
         "re-exec (run f1astro), and passed with the table off at 10, 25 and 36 extra variables (g10, g25, g36): the crash\n"
         "follows the switches' combined effect, not the delivery. The second title with all 55 switches as launcher words and\n"
         "the table off passed (p4full, 25.8 flips/s). The cause in ASTRO BOT stays open; the mechanism stays, with no rows.")
print("committed")
