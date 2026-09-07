#!/usr/bin/env bash
ps -eo pid,etime,cmd | grep wave2.py | grep -v grep
echo ===log tail===
tail -6 /root/wave2.log