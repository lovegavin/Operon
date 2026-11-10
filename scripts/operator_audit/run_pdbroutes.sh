#!/bin/bash
cd /home/gavin/Operon || exit 1
PY=/home/gavin/bp-numpy21/bin/python
ok=0
fail=0
skip=0
: > /tmp/pdbroutes_run.txt
for d in /tmp/pdbroutes/*; do
  name=${d##*/}
  timeout 90 "$PY" scripts/run.py "$d" > /tmp/pdb_last.log 2>&1
  rc=$?
  if [ "$rc" -eq 0 ]; then
    ok=$((ok + 1))
    echo "PASS $name" >> /tmp/pdbroutes_run.txt
  else
    fail=$((fail + 1))
    echo "FAIL $name rc=$rc :: $(tail -2 /tmp/pdb_last.log | tr '\n' ' ')" >> /tmp/pdbroutes_run.txt
  fi
done
echo "OK=$ok FAIL=$fail" >> /tmp/pdbroutes_run.txt
cat /tmp/pdbroutes_run.txt
