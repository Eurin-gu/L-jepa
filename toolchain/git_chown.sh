#!/usr/bin/env bash
# 修正 .git 属主，使其与仓库其余文件一致（避免 dubious ownership）
set -u
R=/mnt/d/lagrangian-jepa-cn
o=$(stat -c '%u:%g' "$R/planning")
echo "repo owner      = $o"
echo ".git owner (前) = $(stat -c '%u:%g' "$R/.git")"
chown -R "$o" "$R/.git" && echo "chown 完成"
echo ".git owner (后) = $(stat -c '%u:%g' "$R/.git")"
echo
echo "属主对应的账号:"
getent passwd "${o%%:*}" || echo "  (passwd 中无此 uid)"
echo
echo "该账号能否写入 .git:"
sudo -u "#${o%%:*}" test -w "$R/.git" 2>/dev/null && echo "  ✅ 可写" || echo "  (无法用 sudo -u 验证，稍后以该用户实跑确认)"
