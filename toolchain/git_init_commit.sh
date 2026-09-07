#!/usr/bin/env bash
# 暂存 + 核验 + 提交（修正版）
#
# 相对上一版的三处修正：
#   1) dubious ownership -> 用 -c safe.directory 单次授权，不写全局配置
#   2) git diff --cached 在空仓库退化为 --no-index 而报错刷屏 -> 改用 git ls-files
#   3) 新增硬性体积闸门：暂存总量 >100MB 或出现 >2MB 单文件即中止，不提交
set -u
R=/mnt/d/lagrangian-jepa-cn
cd "$R" || exit 1

G="git -c safe.directory=$R"
MAX_TOTAL_MB=100
MAX_FILE_MB=2

# 上一版核验用 git diff --cached，此处统一封装为 ls-files
staged() { $G ls-files --cached; }

echo '===== 0. 前置：data/ 与 toolchain/ 子目录体积（确认大目录都被排除） ====='
for base in data toolchain; do
  for d in "$R/$base"/*/; do
    [ -d "$d" ] || continue
    printf '  %-46s %8.1f MB\n' "${d#$R/}" "$(du -sm "$d" 2>/dev/null | cut -f1)"
  done
done

echo
echo '===== 1. 修正 .git 属主（上一版由 root 创建，需与仓库一致） ====='
owner=$(stat -c '%u:%g' "$R/planning" 2>/dev/null)
echo "  仓库文件属主 = $owner"
if [ -d .git ]; then
  cur=$(stat -c '%u:%g' .git)
  echo "  .git 当前属主 = $cur"
  if [ "$cur" != "$owner" ]; then
    chown -R "$owner" .git && echo "  已改为 $owner"
  fi
fi

echo
echo '===== 2. 设置仓库级身份（仅本仓库，不动全局） ====='
$G config user.name  "Yuying Gu"
$G config user.email "2534171146@qq.com"
$G config core.fileMode false
$G config core.quotepath false          # 中文名不转义为 \351\241\271 形式
printf '  user.name  = %s\n' "$($G config user.name)"
printf '  user.email = %s\n' "$($G config user.email)"
printf '  fileMode   = %s\n' "$($G config core.fileMode)"
printf '  quotepath  = %s\n' "$($G config core.quotepath)"

echo
echo '===== 3. 清空旧索引并按新 .gitignore 重建 ====='
# 上一版用 `git rm -r --cached .` 失败（.gitignore/.gitattributes 等文件
# 暂存内容与工作区、HEAD 三者互不相同，git 拒绝移除），导致 9 个大 meta.json
# 残留在索引中，体积仍为 89 MB。
# 空仓库 HEAD 不存在（unborn branch main），索引可由工作区完全再生，
# 故直接删除索引文件后重建。此处只删 .git/index，不触碰任何工作区文件。
if $G rev-parse --verify HEAD >/dev/null 2>&1; then
  echo '  ⚠️ HEAD 已存在，中止：本脚本只允许在空仓库上重建索引'
  exit 1
fi
if [ -f .git/index ]; then
  rm -f .git/index && echo '  旧索引已删除（可由工作区再生）'
fi
time $G add -A
echo "  add rc=$?"

echo
echo '===== 4. 暂存规模 ====='
staged > /tmp/staged_list.txt
n=$(wc -l < /tmp/staged_list.txt)
echo "  暂存文件数: $n"
awk -F/ '{print $1}' /tmp/staged_list.txt | sort | uniq -c | sort -rn | sed 's/^/    /'

echo
echo '===== 5. 暂存总体积 ====='
total=$(tr '\n' '\0' < /tmp/staged_list.txt | xargs -0 du -cb 2>/dev/null | tail -1 | cut -f1)
total_mb=$(awk -v b="$total" 'BEGIN{printf "%.2f", b/1048576}')
echo "  合计 ${total_mb} MB"

echo
echo '===== 6. 🔴 凭据文件是否被误暂存 ====='
sec=0
for f in mirror/server_backup_20260830/footnet_jepa/agent.md toolchain/wsl_rc.sh toolchain/wsl_cdsapi2.sh; do
  if grep -qxF "$f" /tmp/staged_list.txt; then echo "  ❌ STAGED: $f"; sec=1; else echo "  ✅ 未入库: $f"; fi
done

echo
echo '===== 7. 暂存内容密钥形态扫描 ====='
# 两条纪律（均为首版踩过的坑）：
#   a) 不写密钥明文，只做形态匹配（UUID 结构 / 阿里云 AK 前缀），
#      否则本脚本自身成为泄漏源。
#   b) 跳过二进制文件。Note-arw2arl.pdf 为 zip deflate 编码，压缩流中
#      巧合出现 UUID 形态字节，经与已知凭据逐一比对确认不一致（误报）。
khit=0; kbin=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  enc=$(file -b --mime-encoding "$f" 2>/dev/null)
  if [ "$enc" = "binary" ]; then
    kbin=$((kbin+1)); continue
  fi
  if grep -qE 'LTAI[A-Za-z0-9]{12,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' "$f" 2>/dev/null; then
    echo "  ❌ 疑似密钥: $f"; khit=1
  fi
done < /tmp/staged_list.txt
echo "  （跳过二进制文件 $kbin 个）"
[ "$khit" -eq 0 ] && echo '  ✅ 无命中'

echo
echo '===== 7b. 暂存区二进制文件清单（应仅剩图标类） ====='
while IFS= read -r f; do
  [ -f "$f" ] || continue
  [ "$(file -b --mime-encoding "$f" 2>/dev/null)" = "binary" ] && echo "    $f"
done < /tmp/staged_list.txt

echo
echo '===== 8. 大文件（>2MB） ====='
big=$(tr '\n' '\0' < /tmp/staged_list.txt | xargs -0 du -b 2>/dev/null \
  | awk -v m=$((MAX_FILE_MB*1048576)) '$1>m {printf "  %8.2f MB  %s\n", $1/1048576, $2}')
if [ -n "$big" ]; then echo "$big" | sort -rn; else echo '  ✅ 无'; fi

echo
echo '===== 9. 数据目录/数据扩展名是否混入 ====='
dbad=0
for pat in '^data/datasets/' '^data/genghg/' '^met_cache/' '^reuse_stilt/' '^py311/' '^downloads/' \
           '\.npy$' '\.pt$' '\.nc$' '\.nc4$' '\.rds$' '\.GRIB$' '\.grib2$' '\.npz$' '\.whl$' '\.part[0-9]'; do
  c=$(grep -cE "$pat" /tmp/staged_list.txt)
  [ "$c" -ne 0 ] && { printf '  ❌ %-22s %s 个\n' "$pat" "$c"; dbad=1; }
done
[ "$dbad" -eq 0 ] && echo '  ✅ 全部为 0'

echo
echo '===== 10. 关键文件确认入库 ====='
for f in .gitignore .gitattributes planning/HANDOFF.md planning/PLAN_GLOBAL.md \
         planning/PRE_REGISTRATION_v1.json planning/HRRR_SAME_CYCLE_WAIVER_v1.md \
         planning/INCIDENT_arl_truncation_20150520.md planning/RUNBOOK.md \
         data/build/assemble.py data/build/feature_sources.py data/build/make_receipts.py \
         data/build/ARM_BUILD_REPORT.md data/receptors_v2/so_cal_LA_basin/receptors_20160807_n120_maximin.csv \
         toolchain/wsl_era5_post.sh toolchain/era5_progress.sh \
         mirror/server_backup_20260830/footnet_jepa/models.py \
         mirror/server_backup_20260830/footnet_jepa/train_stilt_strict.py \
         mirror/server_backup_20260830/footnet_jepa/stilt_pipeline/run_batch.py \
         mirror/server_backup_20260830/footnet_jepa/results/formal_v5_mass1.json; do
  grep -qxF "$f" /tmp/staged_list.txt && echo "  ✅ $f" || echo "  ⚠️  缺: $f"
done

echo
echo '===== 11. 各扩展名计数 ====='
sed -n 's/.*\.\([A-Za-z0-9_]\{1,10\}\)$/\1/p' /tmp/staged_list.txt \
  | tr 'A-Z' 'a-z' | sort | uniq -c | sort -rn | head -14 | sed 's/^/  /'

echo
echo '===== 12. 闸门判定 ====='
over=$(awk -v b="$total" -v m=$((MAX_TOTAL_MB*1048576)) 'BEGIN{print (b>m)?1:0}')
if [ "$sec" -eq 1 ] || [ "$khit" -eq 1 ] || [ "$dbad" -eq 1 ] || [ "$over" -eq 1 ] || [ -n "$big" ]; then
  echo "  ❌ 中止提交（sec=$sec khit=$khit dbad=$dbad over=$over big=$([ -n "$big" ] && echo 1 || echo 0)）"
  echo '  已暂存内容保留在索引中，未产生提交。请检查上方 ❌ 项。'
  exit 1
fi
echo "  ✅ 全部通过（${total_mb} MB ≤ ${MAX_TOTAL_MB} MB，无凭据，无数据混入）"

echo
echo '===== 13. 提交 ====='
$G commit -q -F - <<'MSG'
chore: 初始化仓库，纳入代码与决策文档，排除数据产物

跟踪范围（798 文件，约 11 MB）：
- planning/           39 份决策与轮次文档，含预注册、同源铁律豁免论证、
                      ARL 截断事故处置记录
- data/build/         本地建集器（assemble.py / feature_sources.py /
                      make_receipts.py 等）与逐日期 manifests、构建日志
- data/receptors_v2/  6 区 × 45 张 OCO-2 maximin 受体表（含 provenance）
- toolchain/          STILT 与 hysplit_data2arl 的 Fortran/R 源码、
                      wsl_*.sh 编排脚本、era5 体检脚本
- mirror/             上游 footnet_jepa 代码快照与 results/ 实验结果 json

排除范围（约 114 GB）：
- 数据集产物 data/datasets(4.6GB)、data/genghg(34.5GB, 48282 个 .pt)
- 备份子树 data/server_backup_20260830(20.7GB)、reuse_stilt(31GB)
- 气象缓存 met_cache(22.6GB)、downloads/、全部 .npy/.nc/.rds
- Python 环境 py311/、预编译二进制(arw2arl 等)、301MB 的 SFC.GRIB
- code_sync.tar.gz、hrrr_cache/*.nc、prod_*/meta.json 等大块派生物

安全：agent.md（阿里云 AccessKey ID+Secret 明文）、wsl_rc.sh 与
wsl_cdsapi2.sh（CDS API key 明文）已列入 .gitignore，未进入版本历史；
原文件在磁盘上保持不变。核验脚本一律用形态匹配而非密钥明文，
避免脚本自身成为泄漏源。密钥轮换仍为待办，见 PRE_REGISTRATION_v1.json。

行尾：新增 .gitattributes 锁定 LF，避免 Windows core.autocrlf=true
在 checkout 时把 190 个 .sh 转成 CRLF 而在 WSL 下无法执行；
manifests/ 与 receptors_v2/ 下的 CSV 参与 sha256 审计且为混合换行符，
标 -text 按原始字节保存，禁止 git 重写。
MSG
echo "  commit rc=$?"

echo
echo '===== 14. 提交结果 ====='
$G log --stat --oneline -1 | head -5
echo "  ---"
$G log -1 --format='  commit  = %H%n  author  = %an <%ae>%n  date    = %ad%n  subject = %s'
echo "  提交文件数 = $($G ls-tree -r --name-only HEAD | wc -l)"
echo "  .git 体积  = $(du -sm .git | cut -f1) MB"
