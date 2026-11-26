# BC5 exp 0381, re-reads: exp 0382's journal gate and route stages, as functions so that a stand-in can drive them.
# Needs CMD, K, RS, FASTN, PREV, LOADT, G, WHY, NOW, NT, FPS3, SLOW5, RR.
# "<newest flip t> <flips per s over its last 3 s> <the last 5 flips all slower than 55 ms>" from the journal.
gate() {
    tail -c 3000000 "$1" | grep -a "^frame profile: t" | tail -400 | sed -n 's/^frame profile: t \([0-9.]*\) s, \([0-9.]*\) ms since.*/\1 \2/p' |
        awk 'NF == 2 { n++; t[n] = $1; m[n] = $2 }
             END { if (n < 5) { print 0, 0, 0; exit }
                   c = 0; for (i = n; i >= 1 && t[i] >= t[n] - 3; i--) c++
                   s = 1; for (i = n - 4; i <= n; i++) if (m[i] <= 55) s = 0
                   printf "%s %.1f %d\n", t[n], c / 3, s }'
}
# One second of the route. 0 start screen, 1 save list, 2 Continue menu, 3 the load, 4 gameplay from G: then the walk.
route_step() {
    local fresh runs loading
    fresh=$(awk -v a="${NT:-0}" -v b="$PREV" 'BEGIN { print (a > b) ? 1 : 0 }'); PREV=${NT:-0}
    runs=15; [ "$RS" = 3 ] && runs=20
    if [ "$fresh" = 1 ] && awk -v f="${FPS3:-0}" -v r="$runs" 'BEGIN { exit !(f >= r) }'; then FASTN=$((FASTN + 1)); else FASTN=0; fi
    loading=0; { [ "${SLOW5:-0}" = 1 ] || [ "$fresh" = 0 ]; } && loading=1
    case "$RS" in
        0) if [ "$FASTN" -ge 2 ]; then printf 'press cross\n' >> "$CMD"; RS=1; K=$NOW
           elif [ "$NOW" -ge 160 ]; then WHY="ROUTE: the start screen did not run by 160 s"; fi ;;
        1) if [ "$NOW" -ge $((K + 6)) ] && [ "$FASTN" -ge 3 ]; then printf 'press down\nwait 400\npress down\nwait 400\npress down\nwait 800\npress cross\n' >> "$CMD"; RS=2; K=$NOW
           elif [ "$NOW" -ge $((K + 90)) ]; then WHY="ROUTE: the save list did not run within 90 s"; fi ;;
        2) if [ "$NOW" -ge $((K + 6)) ] && [ "$FASTN" -ge 2 ]; then printf 'press cross\n' >> "$CMD"; RS=3; K=$NOW
           elif [ "$NOW" -ge $((K + 60)) ]; then WHY="ROUTE: the Continue menu did not run within 60 s"; fi ;;
        3) [ -z "$LOADT" ] && [ "$loading" = 1 ] && LOADT=$NOW
           if [ -n "$LOADT" ] && [ "$NOW" -ge $((LOADT + 3)) ] && [ "$FASTN" -ge 3 ]; then G=$NOW; RS=4; cat "$RR/walk0381r.cmd" >> "$CMD"
           elif [ -z "$LOADT" ] && [ "$NOW" -ge $((K + 40)) ]; then WHY="ROUTE: no load within 40 s of Continue"
           elif [ -n "$LOADT" ] && [ "$NOW" -ge $((LOADT + 150)) ]; then WHY="ROUTE: no gameplay within 150 s of the load"; fi ;;
    esac
}
