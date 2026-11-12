"""Run an edit script as on the box (Linux python3): text-mode writes get LF line ends (newline="\n") instead of Windows'
CRLF translation. Run with -X utf8 so text mode reads and writes UTF-8 as on the box.
usage: python -X utf8 -I runner.py <script> [args...]"""
import builtins
import io
import runpy
import sys

_open = builtins.open
TEXT_WRITES = []


def lf_open(file, mode="r", buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
    if "b" not in mode and newline is None and any(c in mode for c in "wax+"):
        newline = "\n"
        TEXT_WRITES.append(str(file))
    return _open(file, mode, buffering, encoding, errors, newline, closefd, opener)


builtins.open = lf_open
io.open = lf_open
script = sys.argv[1]
sys.argv = sys.argv[1:]
try:
    runpy.run_path(script, run_name="__main__")
finally:
    if TEXT_WRITES:
        sys.stderr.write("runner: text-mode writes forced to LF: %s\n" % ", ".join(TEXT_WRITES))
