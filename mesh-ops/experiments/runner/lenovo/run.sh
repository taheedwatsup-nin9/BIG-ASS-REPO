#!/bin/bash
# run.sh <exp-label> <stimulus.wav> [ceiling] [rate] [ramp_s] — one logged run: phone LIVE first (rule 1), auto-fader ramp (rules 2-3), stop, pull.
H=$(cd "$(dirname "$0")" && pwd); lbl=$1; f=$2; cap=${3:-0.6}; rate=${4:-0}; ramp=${5:-10}
out=$H/../../results/raw; mkdir -p "$out"
# Agreed with MUZI (#14, 23:27): sha256 check before play, hard time limit, hard mute.
b=$(basename "$f"); d=$(dirname "$f")
sum=$(grep -h "  $b\$" "$d/SHA256SUMS.txt" "$H/LENOVO_SUMS.txt" 2>/dev/null | head -1 | cut -d' ' -f1)
[ -n "$sum" ] && [ "$(sha256sum "$f" | cut -d' ' -f1)" = "$sum" ] || { echo "ABORTED: sha256 mismatch or unlisted stimulus $b"; exit 1; }
limit=$(( $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" | cut -d. -f1) + ramp + 30 ))
$H/s10.sh start || exit 1
echo "$(date -Is),$lbl,$(basename $f),lenovo-hp->MonitorStation-AUX->BX5,$cap,$rate,$(sha256sum "$f" | cut -c1-12),${NOTE:-}" >> $H/../run_log_lenovo.csv
timeout $limit $H/autofader.sh "$f" $cap $ramp $rate || { wpctl set-mute @DEFAULT_AUDIO_SINK@ 1; pw-metadata -n settings 0 clock.force-rate 0 >/dev/null; $H/s10.sh stop; echo "ABORTED (exit or ${limit}s limit)"; exit 1; }; sleep 3
$H/s10.sh stop; o="$out/${lbl}_$(date +%Y%m%d_%H%M%S).wav"; $H/s10.sh pull "$o" && echo "RESULT_FILE=$o"
