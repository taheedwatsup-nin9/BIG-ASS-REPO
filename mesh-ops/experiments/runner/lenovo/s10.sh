#!/bin/bash
# s10.sh — S10 recorder control over USB (adb). Subcommands: start | stop | state | pull <out.wav> | tap "<ui text>"
# Recording state is judged by FILE GROWTH, never by tap count (taps toggle; counts drift).
A=${ADB:-~/Android/Sdk/platform-tools/adb}
F=${S10_REC_DIR:-/sdcard/Android/data/com.nll.asr/files/recordings}
REC_X=${S10_REC_X:-540}; REC_Y=${S10_REC_Y:-1972}   # ASR record button (1080x2280 screen)
sz(){ $A shell "ls -l $F" | awk '{s+=$5} END{print s+0}'; }
growing(){ local a=$(sz); sleep 2; [ "$(sz)" -gt "$a" ]; }
case $1 in
  state) growing && echo recording || echo idle ;;
  start) growing || { $A shell input tap $REC_X $REC_Y; sleep 2; }; growing && echo "recording LIVE" || { echo "FAILED to start"; exit 1; } ;;
  stop)  growing && { $A shell input tap $REC_X $REC_Y; sleep 2; }; growing && { echo "still recording"; exit 1; } || echo stopped ;;
  pull)  f=$($A shell "ls -t $F | head -1" | tr -d '\r'); $A pull "$F/$f" "${2:-s10_latest.wav}" >/dev/null && echo "pulled $f -> ${2:-s10_latest.wav}" ;;
  tap)   $A shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1
         b=$($A shell cat /sdcard/ui.xml | grep -oE "(text|content-desc)=\"$2\"[^>]*bounds=\"\[[0-9]+,[0-9]+\]\[[0-9]+,[0-9]+\]\"" | head -1 | grep -oE '\[[0-9]+,[0-9]+\]\[[0-9]+,[0-9]+\]')
         [ -z "$b" ] && { echo "not found: $2"; exit 1; }; read x1 y1 x2 y2 <<<"$(echo $b | tr -c '0-9' ' ')"; $A shell input tap $(((x1+x2)/2)) $(((y1+y2)/2)) ;;
  *) echo "usage: s10.sh start|stop|state|pull [out]|tap <text>"; exit 2 ;;
esac
