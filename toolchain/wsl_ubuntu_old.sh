#!/usr/bin/env bash
echo ===whoami/hosts===
ls /home 2>/dev/null; du -sh /root /home/* /opt /srv /var/cache 2>/dev/null | sort -h | tail -12