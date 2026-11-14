#!/usr/bin/env python3
r"""BC5 experiment 0419, phase 2, batch 3, round 1: the constant branches the built-in library ports left behind.
Candidate G made 23 switch functions return true (mklibs0419g.py). This folds their `if` statements:
    if (!Bc5XOn()) { stub }                 -> gone            (with `else { E }`: the block { E } stays)
    if (Bc5XOn()) { port } else { stub }    -> { port }
    if (Bc5XOn()) { port }                  -> { port }        (a plain block: the port's variables keep their scope)
  and, after `if (Bc5XOn()) { port ... return ...; }` that stands directly in a function's body:
    the rest of that function (the old stub path, unreachable now) is removed too
A file's level is a sum: 1 the positive folds, 2 the negated blocks removed, 4 the unreachable rest removed.
A site followed by `else if`, or one the reader cannot match, is left as it is and counted. Braces are matched by a
small reader that skips comments, strings, character literals and digit separators.
The level of each file is decided on the laptop (7, else 5, 3, 1, 0 = untouched: the first of them at which
the file still passes the laptop's -fsyntax-only -Wall -Wextra -Werror as it did before) and written to a levels file,
so that the box applies exactly what was checked:
    mkfold0419.py <tree root> <levels file>             apply the levels file (lines "<level> <path under src/>")
    mkfold0419.py <tree root> one <path> <level>        one file at one level (used to make the levels file)"""
import os, re, sys

NAMES = ("Bc5VoicePortsOn Bc5TcmOn Bc5HttpdOn Bc5CompanionUtilOn Bc5DiscMapOn Bc5GlsOn Bc5HmdOn Bc5InvdOn Bc5MoveOn "
         "Bc5TbpAuthOn Bc5TbpPartnerOn Bc5TbpPartyOn Bc5TbpFacebookOn Bc5NtuOn Bc5NtuRunOn Bc5ScreenShotOn Bc5ShpOn "
         "Bc5UlobjmgrOn Bc5UsbOn Bc5VoiceOn Bc5VoicePortsSwitch Bc5VrOn Bc5WbdOn").split()
SITE = re.compile(r"if \((!?)(?:%s)\(\)\) \{" % "|".join(NAMES))


def code_mask(s):
    """mask[i] is True where s[i] is code (not inside a comment, a string or a character literal)."""
    n = len(s)
    mask = [True] * n
    i = 0
    while i < n:
        c = s[i]
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            j = s.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                mask[k] = False
            i = j
        elif c == "/" and i + 1 < n and s[i + 1] == "*":
            j = s.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                mask[k] = False
            i = j
        elif c == '"':
            if i > 0 and s[i - 1] == "R":  # a raw string R"delim( ... )delim"
                p = s.find("(", i)
                end = ")" + s[i + 1:p] + '"'
                j = s.find(end, p)
                j = n if j < 0 else j + len(end)
            else:
                j = i + 1
                while j < n and s[j] != '"':
                    j += 2 if s[j] == "\\" else 1
                j += 1
            for k in range(i, min(j, n)):
                mask[k] = False
            i = j
        elif c == "'":
            if i > 0 and s[i - 1].isalnum() and i + 1 < n and s[i + 1].isalnum():  # 1'000: a digit separator
                i += 1
                continue
            j = i + 1
            while j < n and s[j] != "'":
                j += 2 if s[j] == "\\" else 1
            j += 1
            for k in range(i, min(j, n)):
                mask[k] = False
            i = j
        else:
            i += 1
    return mask


def match(s, mask, o):
    """the index of the brace that closes the one at o, or -1"""
    d = 0
    for i in range(o, len(s)):
        if not mask[i]:
            continue
        if s[i] == "{":
            d += 1
        elif s[i] == "}":
            d -= 1
            if d == 0:
                return i
    return -1


def opener(s, mask, pos):
    """the index of the brace that opens the block containing pos, or -1"""
    d = 0
    for i in range(pos - 1, -1, -1):
        if not mask[i]:
            continue
        if s[i] == "}":
            d += 1
        elif s[i] == "{":
            if d == 0:
                return i
            d -= 1
    return -1


def line_start(s, i):
    return s.rfind("\n", 0, i) + 1


def line_end(s, i):
    j = s.find("\n", i)
    return len(s) if j < 0 else j + 1


FUNC_HEAD = re.compile(r"^[A-Za-z_].*\)\s*(const\s*)?(noexcept\s*)?\{[^\n]*$")
ELSE_IF = re.compile(r"\s*else\s+if\b")
ELSE = re.compile(r"\s*else\s*\{")
LABEL = re.compile(r"^\s*(case\b.*|default|[A-Za-z_]\w*)\s*:\s*(//.*)?$", re.M)


def fold(s, level):
    done = {"neg": 0, "pos": 0, "else": 0, "tail": 0, "left": 0}
    while True:
        mask = code_mask(s)
        sites = [m for m in SITE.finditer(s) if mask[m.start()]]
        sites = [m for m in sites if not s.startswith("/*folded*/", m.end())]
        if not sites:
            break
        m = sites[-1]  # the last one first: an edit never moves a site not yet handled
        o = m.end() - 1
        c = match(s, mask, o)
        after = s[c + 1:c + 200] if c >= 0 else ""
        if c < 0 or ELSE_IF.match(after):
            s = s[:m.end()] + "/*folded*/" + s[m.end():]  # marked so the loop does not see it again; taken out at the end
            done["left"] += 1
            continue
        e = ELSE.match(after)
        eo = c + 1 + e.end() - 1 if e else -1
        ec = match(s, mask, eo) if e else -1
        if e and ec < 0:
            s = s[:m.end()] + "/*folded*/" + s[m.end():]
            done["left"] += 1
            continue
        a = line_start(s, m.start())
        if s[a:m.start()].strip() != "":  # `} else if (...)` or something before it on the line: not ours
            s = s[:m.end()] + "/*folded*/" + s[m.end():]
            done["left"] += 1
            continue
        if m.group(1) == "!":
            if not level & 2:
                s = s[:m.end()] + "/*folded*/" + s[m.end():]
                done["left"] += 1
                continue
            if e:  # the else block stays as a plain block
                s = s[:m.start()] + s[eo:]
                done["else"] += 1
            else:
                s = s[:a] + s[line_end(s, c):]
            done["neg"] += 1
            continue
        # positive: the condition goes, the block stays; an else block goes
        if not level & 1:
            s = s[:m.end()] + "/*folded*/" + s[m.end():]
            done["left"] += 1
            continue
        tail_cut = None
        if e:
            done["else"] += 1
            s = s[:c + 1] + s[ec + 1:]
        elif level & 4:
            body = s[o + 1:c].rstrip()
            last = body[body.rfind("\n") + 1:].strip() if "\n" in body else body.strip()
            po = opener(s, mask, m.start())
            if last.startswith("return") and last.endswith(";") and po >= 0:
                pl = s[line_start(s, po):line_end(s, po)].rstrip("\n")
                pc = match(s, mask, po)
                tail = s[line_end(s, c):line_start(s, pc)] if pc > c else None
                if FUNC_HEAD.match(pl) and tail is not None and tail.strip() != "" and not LABEL.search(tail):
                    tail_cut = (line_end(s, c), line_start(s, pc))
        if tail_cut:
            s = s[:tail_cut[0]] + s[tail_cut[1]:]
            done["tail"] += 1
        s = s[:m.start()] + "{/*folded*/" + s[m.end():]
        done["pos"] += 1
    return s.replace("{/*folded*/", "{").replace("/*folded*/", ""), done


def one(root, rel, level):
    p = os.path.join(root, "src", rel)
    s = open(p, encoding="utf-8", newline="").read()
    assert "\r" not in s
    if level == 0:
        return {}
    t, done = fold(s, level)
    assert t.count("{") - t.count("}") == s.count("{") - s.count("}"), rel
    open(p, "w", encoding="utf-8", newline="").write(t)
    return done


if __name__ == "__main__":
    root = sys.argv[1]
    if sys.argv[2] == "one":
        print(sys.argv[3], sys.argv[4], one(root, sys.argv[3], int(sys.argv[4])))
    else:
        for line in open(sys.argv[2], encoding="utf-8"):
            if line.strip() and not line.startswith("#"):
                lv, rel = line.split()
                print(rel, lv, one(root, rel, int(lv)))
