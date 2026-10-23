#!/bin/bash
# copilot_job.sh <job-name> "<prompt>" [extra --add-dir paths...]
# Copilot = task assistant (agreed Claude+MUZI 2026-10-23). Bounded, low-risk jobs only.
# Guard rails: runs in its own job dir; can only READ the dirs passed in, WRITE only the job dir;
# METADATA ONLY by default (names, sizes, dates): file CONTENTS never reach Copilot's model,
# because session logs and vault notes can hold secrets/private text. Content jobs need an explicit
# Claude+MUZI agreement and a dir with no secrets; no git, no network tools, no secrets dirs ever passed in.
# Claude or MUZI verifies the result (owner executes / other verifies).
set -u
H=$(cd "$(dirname "$0")" && pwd); name=$1; prompt=$2; shift 2
J="$H/jobs/$(date +%Y%m%d_%H%M)_$name"; mkdir -p "$J"; cd "$J"
adds=(); for d in "$@"; do adds+=(--add-dir "$d"); done
printf '%s\n' "$prompt" > PROMPT.txt
timeout 600 copilot -p "$prompt

RULES: report only; never modify, move or delete anything outside this folder; never read files named *.env, *key*, *secret*, *token*, rclone.conf, or anything under .ssh/.config/cr8mor/.gnupg; write your findings to REPORT.md in this folder." \
  --no-ask-user --no-auto-update -s "${adds[@]}" \
  --allow-tool 'shell(ls)' 'shell(find)' 'shell(stat)' 'shell(wc)' 'shell(du)' 'shell(date)' 'write' \
  --deny-tool 'shell(git)' 'shell(rm)' 'shell(mv)' 'shell(curl)' 'shell(wget)' 'shell(ssh)' 'shell(scp)' 'shell(rclone)' \
              'shell(cat)' 'shell(head)' 'shell(tail)' 'shell(grep)' 'shell(sort)' 'shell(less)' 'shell(strings)' \
              'shell(python3)' 'shell(python)' 'shell(node)' 'shell(sed)' 'shell(awk)' 'read' \
  > COPILOT_OUTPUT.txt 2>&1
echo "exit=$? job=$J"; ls "$J"
