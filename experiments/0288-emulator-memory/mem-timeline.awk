# exp 0288: the memory timeline of a direct-path GPU journal (direct.log), read-only.
# Per 60 s of journal time: pinned MiB of the direct and private memfds (the last "<label>: N views; +N BOs (N, X MiB pinned)"
# line of the minute), BOs, GPU mappings, AMM-style maps/unmaps, hint and learned window imports (MiB asked), frames and fps.
# Also prints every "by name" breakdown block (BC5_DIRECT_BREAKDOWN=1 or an -ENOMEM) and the memfd/eager-name header lines.
# Usage: gawk -f mem-timeline.awk direct.log
function num(s) { gsub(/[^0-9.]/, "", s); return s + 0 }
/^timing: t [0-9.]+ s/ { t = $3 + 0; next }
/^frame profile: t / { t = $4 + 0; b = int(t / 60); fr[b]++; if (b > maxb) maxb = b; next }
/^(direct|private) memory: memfd/ { print "HEADER " $0; next }
/^direct memory: eager names/ { print "HEADER " $0; next }
/^(direct|private): [0-9]+ views; / {
  lab = $1; sub(/:/, "", lab); b = int(t / 60); if (b > maxb) maxb = b
  match($0, /\(([0-9]+), ([0-9.]+) MiB pinned\); maps \+([0-9]+) -([0-9]+) \(([0-9]+)\)/, m)
  pin[lab, b] = m[2]; bos[lab, b] = m[1]; mp[lab, b] += m[3]; mu[lab, b] += m[4]; maps[lab, b] = m[5]; views[lab, b] = $2
  if (m[2] + 0 > pmax[lab]) { pmax[lab] = m[2] + 0; pmaxt[lab] = t }
  next
}
/^hint [A-Z_0-9]+ 0x/ { match($0, /direct memory \+([0-9.]+) MiB/, m); b = int(t / 60); hn[b]++; hm[b] += m[1]; next }
/^learned 0x/ { match($0, /direct memory \+([0-9.]+) MiB/, m); b = int(t / 60); ln[b]++; lm[b] += m[1]; next }
/^learned apply:/ { b = int(t / 60); la[b]++; next }
/ by name \(/ { inbd = 1; print "BREAKDOWN t=" t " " $0; next }
inbd && /^  [A-Za-z]/ { print "   " $0; next }
inbd { inbd = 0 }
/^(direct|private) merge:/ { b = int(t / 60); mg[b]++; next }
/SOME MAPS FAILED|ENOMEM|EAGAIN|refused/ { print "EVENT t=" t " " substr($0, 1, 160); next }
END {
  printf "\n%-5s %5s %5s | %8s %4s %5s %6s %6s | %8s %4s %5s | %5s %7s %5s %6s %5s\n", "min", "frames", "fps", "direct", "BOs", "maps", "map+", "map-", "private", "BOs", "maps", "hints", "MiB", "learn", "MiB", "merge"
  for (b = 0; b <= maxb; b++) {
    if (pin["direct", b] == "") pin["direct", b] = lastd; else lastd = pin["direct", b]
    if (pin["private", b] == "") pin["private", b] = lastp; else lastp = pin["private", b]
    printf "%-5d %5d %5.1f | %8.0f %4d %5d %6d %6d | %8.0f %4d %5d | %5d %7.1f %5d %6.1f %5d\n", b, fr[b], fr[b] / 60.0, pin["direct", b], bos["direct", b], maps["direct", b], mp["direct", b], mu["direct", b], pin["private", b], bos["private", b], maps["private", b], hn[b], hm[b], ln[b] + la[b], lm[b], mg[b]
  }
  printf "\npeak pinned: direct %.0f MiB at t %.0f s; private %.0f MiB at t %.0f s\n", pmax["direct"], pmaxt["direct"], pmax["private"], pmaxt["private"]
}
