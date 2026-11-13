"""BC5 experiment 0419, candidate G: the small editor the mkg0419_*.py steps use. Bytes in, bytes out; an edit's
text is written with LF and is matched in the file's own line ending; every edit must match exactly `n` times."""


class File:
    def __init__(self, path):
        self.path = path
        self.b = open(path, "rb").read()
        self.crlf = b"\r\n" in self.b
        self.n = 0

    def _c(self, s):
        b = s.encode("utf-8")
        assert b"\r" not in b
        return b.replace(b"\n", b"\r\n") if self.crlf else b

    def sub(self, old, new, n=1):
        o, w = self._c(old), self._c(new)
        got = self.b.count(o)
        assert got == n, "%s: %d matches, wanted %d, of: %r" % (self.path, got, n, old[:90])
        self.b = self.b.replace(o, w)
        self.n += n

    def cut(self, first, last, new=""):
        """remove from the one match of `first` through the next match of `last` (both included)"""
        f, l = self._c(first), self._c(last)
        assert self.b.count(f) == 1, "%s: %d matches of %r" % (self.path, self.b.count(f), first[:90])
        a = self.b.index(f)
        e = self.b.index(l, a + len(f)) + len(l)
        self.b = self.b[:a] + self._c(new) + self.b[e:]
        self.n += 1
        return e - a

    def gone(self, *words):
        for w in words:
            assert self.b.count(w.encode()) == 0, "%s still holds %s (%d)" % (self.path, w, self.b.count(w.encode()))

    def save(self):
        d = 0
        for ch in self.b:
            d += (ch == 0x7B) - (ch == 0x7D)
        open(self.path, "wb").write(self.b)
        print("%s: %d edits, brace balance %+d" % (self.path.replace("\\", "/").split("/src/")[-1], self.n, d))
