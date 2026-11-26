#!/usr/bin/env bash
# BC5 experiment 0362: the D bursts per frame in a pl0362.py poll log (events.txt or .gz): frames cut at a P change (a
# second P change within 1 ms joins the first), D changes grouped into bursts by gaps over 1 ms; the number of bursts
# per frame and the start and end of bursts 1-4 (ms after the frame's P change; 10th/50th/90th percentiles). Polling
# pauses during a snapshot read, so captured frames are counted too, with their gaps.
# usage: bt0362.sh <events.txt[.gz]>
f=$1; cat=cat; case "$f" in *.gz) cat=zcat;; esac
$cat "$f" | awk '
function flush(   i,nb,bs,be){ if(r==0) return; nb=0; for(i=1;i<=nd;i++){ if(i==1 || d[i]-d[i-1]>1.0){nb++; bs[nb]=d[i]} be[nb]=d[i] }
  hist[nb]++; for(i=1;i<=nb && i<=4;i++){ st[i]=st[i] " " bs[i]; en[i]=en[i] " " be[i]; cnt[i]++ } }
{ t=$1*1000 }
$3=="D1" && r { nd++; d[nd]=t-r }
$4=="P1" { if (r && t-r < 1.0) next; flush(); r=t; nd=0 }
END{ for(k in hist) printf "frames with %d bursts: %d\n", k, hist[k]; for(i=1;i<=4;i++){ if(!cnt[i]) continue; n=split(st[i],a," "); asort(a); m=split(en[i],b," "); asort(b); printf "burst %d (%d frames): start %.1f / %.1f / %.1f ms, end %.1f / %.1f / %.1f ms\n", i, cnt[i], a[int(n*.1)+1], a[int(n*.5)+1], a[int(n*.9)+1], b[int(m*.1)+1], b[int(m*.5)+1], b[int(m*.9)+1] } }'
