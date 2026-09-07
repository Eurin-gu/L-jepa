# 标准化 (区域,日期) STILT 批启动模板（2026-09-05）

## 已验证配方（SoCal 2017-11-11 冒烟成功，单受体 45s / p250）
输入：
- 受体表 CSV（6 列区 × 日期，D:\lagrangian-jepa-cn\data\receptors_v2\<region>\receptors_<YYYYMMDD>_n120_maximin.csv）
- met 日文件 /root/met/<YYYYMMDD>（HRRR→hrrrv12arl_v2_modern 逐小时→merge_arl_met 日合并；**cfg 放 /root/met_cfg/，勿放 met 目录**）

## 通用启动（WSL root，per 日期）
```bash
cd /root/work/footnet/stilt_pipeline
/root/venvs/cds/bin/python run_batch.py \
   --receptors /mnt/d/lagrangian-jepa-cn/data/receptors_v2/<REGION>/receptors_<DATE>_n120_maximin.csv \
   --stilt-wd /root/work/stilt --met /root/met --jobs 24 \
   --numpar <P> --hours 24 --half-km 256 --res 0.04 --met-file-tres-hours 1 \
   --tag <TAG> --timeout 3600 \
   --log-dir /root/stilt_out/logs_<DATE> --manifest /root/stilt_out/manifest_<DATE>_p<P>.csv
```
- 训练日期：p250；验证/留出/self-baseline：p1000；TAG 建议 <met>-<region>-<date>-p<P>
- 输出：/root/work/stilt/out/by-id/<sim_id>/{*_foot.nc, *_traj.rds}; manifest CSV 记录 sim_id/run_time/lat/lon/zagl/路径

## 协议注记（v2）
- self-baseline：每区 ≤30 受体同时跑 p250 与 p1000 → noise floor
- 复用：2016-17 正式 SoCal 日期已有 OSS 产物（reuse_stilt 下载中），不重跑
- schema v5 建集：features(npz U10M/V10M/PBLH/PRSS, source-aligned) + foot.nc/traj.rds(stilt_io 重采样) → data_builder

## 故障排查速查
- cfg 误放 met 目录 → HYSPLIT 把 cfg 当数据读，metset.f:141 Bad value → 移走 cfg
- 转换器不认文件 → 用拼接选项 -i<path>（无空格）
- PARTICLE_STILT.DAT 失败 → 看 stilt.log(Fortran error)/MESSAGE(WARNING metini...)