#!/bin/bash
# autofader.sh <file> [ceiling 0-1] [ramp_s] [rate] — software fader on the Lenovo output (Taheed does not ride physical knobs).
# Starts at 0, unmutes, ramps linearly to ceiling while playing; ALWAYS re-mutes and releases the forced rate on exit.
f=$1; cap=${2:-0.25}; ramp=${3:-10}; rate=${4:-0}
restore(){ wpctl set-mute @DEFAULT_AUDIO_SINK@ 1; wpctl set-volume @DEFAULT_AUDIO_SINK@ 0; pw-metadata -n settings 0 clock.force-rate 0 >/dev/null; kill $pid 2>/dev/null; }
trap restore EXIT TERM INT
port=$(pactl list sinks | grep -oP 'Active Port: \K\S+'); [ "$port" = analog-output-headphones ] || { echo "ABORT: output is $port (cable in mic jack?)"; exit 1; }
[ "$rate" != 0 ] && { pw-metadata -n settings 0 clock.force-rate $rate >/dev/null; sleep 1; }
wpctl set-volume @DEFAULT_AUDIO_SINK@ 0; wpctl set-mute @DEFAULT_AUDIO_SINK@ 0
pw-play "$f" & pid=$!
n=$((ramp*4)); for i in $(seq 1 $n); do wpctl set-volume @DEFAULT_AUDIO_SINK@ $(awk "BEGIN{print $cap*$i/$n}"); sleep 0.25; kill -0 $pid 2>/dev/null || break; done
echo "$(date +%T) at ceiling $cap"; wait $pid
