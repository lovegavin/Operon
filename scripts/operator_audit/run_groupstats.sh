#!/bin/bash
cd /home/gavin/Operon || exit 1
PY=/home/gavin/bp-numpy21/bin/python
ok=0
fail=0
: > /tmp/groupstats_run.txt
for d in /tmp/groupstats/*; do
  name=${d##*/}
  timeout 180 "$PY" scripts/run.py "$d" > /tmp/gs_last.log 2>&1
  rc=$?
  if [ "$rc" -eq 0 ]; then
    ok=$((ok + 1))
    echo "PASS $name" >> /tmp/groupstats_run.txt
  else
    fail=$((fail + 1))
    echo "FAIL $name rc=$rc :: $(tail -2 /tmp/gs_last.log | tr '\n' ' ')" >> /tmp/groupstats_run.txt
  fi
done
echo "OK=$ok FAIL=$fail" >> /tmp/groupstats_run.txt
cat /tmp/groupstats_run.txt
