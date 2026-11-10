#!/bin/bash
cd /home/gavin/Operon || exit 1
PY=/home/gavin/bp-numpy21/bin/python
ok=0
fail=0
: > /tmp/mlroutes_run.txt
for d in /tmp/mlroutes/*; do
  name=${d##*/}
  timeout 180 "$PY" scripts/run.py "$d" > /tmp/ml_last.log 2>&1
  rc=$?
  if [ "$rc" -eq 0 ]; then
    ok=$((ok + 1))
    echo "PASS $name" >> /tmp/mlroutes_run.txt
  else
    fail=$((fail + 1))
    echo "FAIL $name rc=$rc :: $(tail -2 /tmp/ml_last.log | tr '\n' ' ')" >> /tmp/mlroutes_run.txt
  fi
done
echo "OK=$ok FAIL=$fail" >> /tmp/mlroutes_run.txt
cat /tmp/mlroutes_run.txt
