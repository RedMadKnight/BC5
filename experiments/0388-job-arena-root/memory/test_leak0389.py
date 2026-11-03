#!/usr/bin/env python3
"""BC5 exp 0388, memory: leak0389.py's sums. A part not read (-1) leaves the sum unknown; read parts add up.
usage: test_leak0389.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import leak0389  # noqa: E402

bad = 0


def check(what, got, want):
    global bad
    ok = got == want
    bad += 0 if ok else 1
    print(("ok   " if ok else "FAIL ") + f"{what}: {got}, want {want}")


path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "t-leak.rec")
open(path, "w").write(
    "t=600 e_rss=-1 e_swap=128 m_pss=-1 m_rss=-1 m_swap=64\n"
    "t=620 e_rss=1000 e_swap=-1 m_pss=-1 m_rss=300 m_swap=-1\n"
    "t=640 e_rss=1000 e_swap=128 m_pss=290 m_rss=300 m_swap=64\n"
    "t=660 e_rss=1000 e_swap=128 m_pss=-1 m_rss=300 m_swap=64\n")
r = leak0389.rows(path)
os.remove(path)
check("e_rss unread", r[0]["e_rss+e_swap"], -1)
check("m_pss and m_rss unread", r[0]["m_pss+m_swap"], -1)
check("e_swap unread", r[1]["e_rss+e_swap"], -1)
check("m_swap unread", r[1]["m_pss+m_swap"], -1)
check("both read, PSS", (r[2]["e_rss+e_swap"], r[2]["m_pss+m_swap"]), (1128, 354))
check("PSS unread, RSS read", r[3]["m_pss+m_swap"], 364)
print(f"== {6 - bad} passed, {bad} failed")
sys.exit(1 if bad else 0)
