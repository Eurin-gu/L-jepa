#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X-STILT 柱足迹垂直加权 —— 严格按 ACOS / O'Dell et al. (2012) Appendix A.

权威定义 (O'Dell et al. 2012, AMT 5, 99-121, Appendix A)
========================================================
预定义气压层 p = p_1..N, 自 space 到 surface, 截断到最后一个层 p_N
**位于地表以下**; 地表由 retrieval surface pressure p_S 定义.

layer i 由 p_i 与 p_{i+1} 界定 (i = 1..N-1).
=> **N 个 level, N-1 个 layer.**

    h'_i = c_i dp_i / sum_j c_j dp_j                       (A4)  layer 权重
    c   = (1 - q) / (g * M_dry)                            (A2)

    h_i = (1-f_1) h'_1                              i=1
        = f_{i-1} h'_{i-1} + (1-f_i) h'_i           i=2..N-2
        = f_{N-2} h'_{N-2} + (1 - f_S f_{N-1}) h'_{N-1}   i=N-1
        = f_S f_{N-1} h'_{N-1}                      i=N        (A5)  level 权重

    ubar_i = (1-f_i) u_i + f_i u_{i+1}                     (A6)
    u_S    = (1-f_S) u_{N-1} + f_S u_N                     (A7)
    f_i = 1/2,  f_S = (p_S - p_{N-1})/(p_N - p_{N-1})      (A8)
    sum_i h_i = 1                                          (守恒检验)

注意 (A5) 中 i=N 分支是 **f_S f_{N-1} h'_{N-1}** (含 f_{N-1}); 漏掉 f_{N-1}
会使 sum h_i = 1 + f_S(1-f_{N-1}) h'_{N-1} != 1.

对 OCO-2 Lite 实测验证 (po 20171023, 2017102312044972)
=====================================================
* 反解 h -> h' (A5 逆):  sum(h') = sum(h) = 1.0000000019
* h' 全部 ~= 1/(N-1) = 0.0526316 (spread 0.876%), 与 19 个近乎等厚层一致
* 正向重建 h' -> h 与文件 pressure_weight:  max|diff| = 0.000e+00
* f_S = 1.000000 => p_S = p_N = 927.183 hPa (表面与第 N 层重合)
* h' 自顶向下严格递减 (0.052866 -> 0.052407), 比值 1.0088, 与
  c=(1-q)/g 随高度增大 (湿度递减) 一致

**因此**: 文件里的 20 个 pressure_weight 是 **20 个 LEVEL 权重**,
而不是 20 个 layer 的层积分权重. 首末权重恰为内部一半, 来源是 A5 的
插值 (h_1 = (1-f_1)h'_1 = h'_1/2), **不是** "首末半厚度层".

X-STILT 柱足迹 (Wu et al. 2018, Eq.4)
====================================
release level 代表的是 O'Dell 的 **LAYER**, 不是 state-vector level:
    XCO2 = sum_i h'_i ubar_i                (i = 1..N-1, ubar = layer 平均)
=>  F_col = sum_i W_i F_i,  W_i = AKbar_i * h'_i,  释放在 z(P_i,layer center)
    P_i,layer center = (p_i + p_{i+1})/2,   AKbar_i = (AK_i + AK_{i+1})/2

默认 scheme="layer": 19 个释放层, 最底层 (po 20171023) 902.784 hPa -> 279.5 m AGL.
(sum_w = 0.87581935, 与 level form 严格相同 —— 两者是同一求积的两种下标写法.)

可选 scheme="level" (20 个 state-vector level) 与 scheme="refined"
(任意释放网格, 把每个 layer 的贡献按气压重叠分配过去).

P <-> z 映射
============
用受体点/时刻的 **实际 ERA5 剖面** (geopotential), 不用标准大气.
OCO-2 自带 GEOS-5 气象, 其 p_S 与 ERA5 sp 不同
(po 20171023: OCO-2 927.18 hPa vs ERA5 933.59 hPa, 差 6.41 hPa).
zmap="absolute": z = z_ERA5(p)  —— 无额外假设
zmap="sigma"   : p -> (p/p_S,OCO2)*sp_ERA5 —— 令 p_N 落在地面 (因 p_N == p_S)
"""
import os
import glob
import json

import numpy as np

try:
    import eccodes
except Exception:  # pragma: no cover
    eccodes = None

G0 = 9.80665
LITE_DIR = "/mnt/d/co2_data/nasa/oco2_l2_lite_fp_11.2r"
ERA5D_DEFAULT = "/mnt/d/lagrangian-jepa-cn/met_cache/era5d"
RECEPTOR_ROOT = "/mnt/d/lagrangian-jepa-cn/data/receptors_v2"
F_DEFAULT = 0.5

# refined form 默认释放高程 (m AGL). 依据实测 AK*PW 累积:
#   1km 12%, 2km 24%, 3km 34%, 5km 53%, 8km 74%, 12km 90%, 16km 95%
DEFAULT_RELEASE_AGL = [
    100, 200, 350, 500, 700, 900,
    1200, 1500, 1800, 2200, 2700, 3200,
    4000, 5000, 6000, 7000, 8000,
    10000, 12000, 14000, 16000,
]


# --------------------------------------------------------------------------
# OCO-2 Lite
# --------------------------------------------------------------------------
def find_lite_file(date, lite_dir=LITE_DIR):
    """date 'YYYYMMDD' -> Lite 路径 (文件名用 YYMMDD)."""
    hits = glob.glob(os.path.join(lite_dir, "oco2_LtCO2_%s_*.nc4" % date[2:8]))
    return sorted(hits)[0] if hits else None


def load_oco2_sounding(date, sounding_id, lite_dir=LITE_DIR):
    import netCDF4 as nc
    path = find_lite_file(date, lite_dir)
    if path is None:
        raise FileNotFoundError("no Lite file for %s" % date)
    ds = nc.Dataset(path)
    try:
        sv = np.asarray(ds.variables["sounding_id"][:])
        w = np.where(sv == np.uint64(int(sounding_id)))[0]
        if not len(w):
            return None
        i = int(w[0])
        out = dict(
            path=path, index=i,
            P=np.array(ds.variables["pressure_levels"][i], dtype=np.float64),
            AK=np.array(ds.variables["xco2_averaging_kernel"][i], dtype=np.float64),
            PW=np.array(ds.variables["pressure_weight"][i], dtype=np.float64),
            lat=float(ds.variables["latitude"][i]),
            lon=float(ds.variables["longitude"][i]),
            xco2=float(ds.variables["xco2"][i]),
            xco2_apriori=float(ds.variables["xco2_apriori"][i]),
            quality_flag=int(ds.variables["xco2_quality_flag"][i]),
        )
    finally:
        ds.close()
    return out


# --------------------------------------------------------------------------
# O'Dell (2012) Appendix A : h <-> h'
# --------------------------------------------------------------------------
def level_to_layer_weights(h, f=F_DEFAULT):
    """A5 逆运算: 由 N 个 level 权重 h 解出 N-1 个 layer 权重 h' 与 f_S.

    h_1     = (1-f_1) h'_1
    h_i     = f_{i-1} h'_{i-1} + (1-f_i) h'_i        i=2..N-2
    h_{N-1} = f_{N-2} h'_{N-2} + (1 - f_S f_{N-1}) h'_{N-1}
    h_N     = f_S f_{N-1} h'_{N-1}
    """
    h = np.asarray(h, dtype=np.float64)
    N = len(h)
    if N < 3:
        raise ValueError("N 太小")
    hp = np.zeros(N - 1)
    hp[0] = h[0] / (1.0 - f)
    for k in range(1, N - 2):
        hp[k] = (h[k] - f * hp[k - 1]) / (1.0 - f)
    # 由 i=N-1 与 i=N 两式联立
    #   h_N     = f_S f h'_{N-1}                     -> f_S f h'_{N-1} = h_N
    #   h_{N-1} = f h'_{N-2} + h'_{N-1} - h_N
    hp[N - 2] = h[N - 2] - f * hp[N - 3] + h[N - 1]
    fS = h[N - 1] / (f * hp[N - 2])
    return hp, float(fS)


def layer_to_level_weights(hp, fS, f=F_DEFAULT):
    """A5 正运算: 由 N-1 个 layer 权重 h' 重建 N 个 level 权重 h."""
    hp = np.asarray(hp, dtype=np.float64)
    M = len(hp)
    N = M + 1
    h = np.zeros(N)
    h[0] = (1.0 - f) * hp[0]
    for k in range(1, N - 2):
        h[k] = f * hp[k - 1] + (1.0 - f) * hp[k]
    h[N - 2] = f * hp[N - 3] + (1.0 - fS * f) * hp[N - 2]
    h[N - 1] = fS * f * hp[N - 2]
    return h


def oco2_layer_bounds(P):
    """19 个 layer 的 20 个边界 = 就是 pressure_levels 本身 (L_i = [p_i, p_{i+1}])."""
    return np.asarray(P, dtype=np.float64)


def oco2_layer_centers(P):
    """19 个 O'Dell layer 的中心气压 (hPa)."""
    P = np.asarray(P, dtype=np.float64)
    return 0.5 * (P[:-1] + P[1:])


def oco2_representative_pressures(P, mode="voronoi"):
    """level i 的 **代表气压** (用于确定释放高度).

    !! 这是 "state-vector level -> STILT release height" 的数值实现选择,
       与 O'Dell 的权重定义是两件独立的事. !!

    mode:
      "voronoi"     20 个控制体 (围绕 level 的 Voronoi 划分):
                    V_i = [mid(p_{i-1},p_i), mid(p_i,p_{i+1})],
                    V_1 = [p_1, mid(p_1,p_2)], V_N = [mid(p_{N-1},p_N), p_S]
                    代表气压 = V_i 的中点.
                    注意: 这不是 O'Dell 的 layer (!), O'Dell 的 layer 以
                    level 为 **边界** L_i=[p_i,p_{i+1}], 而 Voronoi 以 level 为 **中心**.
                    内部两者代表气压相同; 但最底层差别明显:
                    Voronoi 给 914.98 hPa (167.7 m AGL),
                    O'Dell layer 给 902.78 hPa (279.5 m AGL).
      "raw"         直接用 pressure_levels (最底层 927.18 hPa -> 56.6 m AGL)
    """
    P = np.asarray(P, dtype=np.float64)
    if mode == "raw":
        return P.copy()
    if mode == "voronoi":
        b = np.empty(len(P) + 1)
        b[0] = P[0]
        b[1:-1] = 0.5 * (P[:-1] + P[1:])
        b[-1] = P[-1]
        return 0.5 * (b[:-1] + b[1:])
    raise ValueError("center 必须是 voronoi 或 raw")


# --------------------------------------------------------------------------
# ERA5 实际剖面
# --------------------------------------------------------------------------
def _read_msg(g):
    v = eccodes.codes_get_array(g, "values")
    lat = eccodes.codes_get_array(g, "distinctLatitudes")
    lon = eccodes.codes_get_array(g, "distinctLongitudes")
    return v.reshape(len(lat), len(lon)), lat, lon


def _bilin(F, lats, lons, la, lo):
    fi = (lats[0] - la) / (lats[0] - lats[1])
    fj = (lo - lons[0]) / (lons[1] - lons[0])
    i0 = int(np.clip(np.floor(fi), 0, len(lats) - 2))
    j0 = int(np.clip(np.floor(fj), 0, len(lons) - 2))
    di, dj = fi - i0, fj - j0
    return ((1 - di) * ((1 - dj) * F[i0, j0] + dj * F[i0, j0 + 1]) +
            di * ((1 - dj) * F[i0 + 1, j0] + dj * F[i0 + 1, j0 + 1]))


def era5_pz_profile(region, date, hour, lat, lon, era5d=ERA5D_DEFAULT):
    """受体点/时刻的实际 ERA5 气压-位势高度剖面 (hPa 降序 / m ASL 升序)."""
    if eccodes is None:
        raise RuntimeError("eccodes 不可用")
    tgt = int(hour) * 100
    sf = os.path.join(era5d, region, "%s_SFC.GRIB" % date)
    pf = os.path.join(era5d, region, "%s_PL.GRIB" % date)
    for f_ in (sf, pf):
        if not os.path.exists(f_):
            raise FileNotFoundError(f_)
    terrain = sp = None
    zpl = {}
    for path, is_pl in ((sf, False), (pf, True)):
        with open(path, "rb") as fh:
            while True:
                g = eccodes.codes_grib_new_from_file(fh)
                if g is None:
                    break
                try:
                    if int(eccodes.codes_get(g, "dataTime")) != tgt:
                        continue
                    sn = eccodes.codes_get(g, "shortName")
                    if not is_pl:
                        if sn in ("z", "sp"):
                            A, lats, lons = _read_msg(g)
                            if sn == "z":
                                terrain = _bilin(A, lats, lons, lat, lon) / G0
                            else:
                                sp = _bilin(A, lats, lons, lat, lon) / 100.0
                    elif sn == "z":
                        lv = int(eccodes.codes_get(g, "level"))
                        A, lats, lons = _read_msg(g)
                        zpl[lv] = _bilin(A, lats, lons, lat, lon) / G0
                finally:
                    eccodes.codes_release(g)
    if terrain is None or sp is None or not zpl:
        raise RuntimeError("ERA5 剖面不完整 %s %s %02dZ" % (region, date, hour))
    ks = sorted(zpl)
    p = np.array([sp] + [float(k) for k in ks])
    z = np.array([terrain] + [zpl[k] for k in ks])
    o = np.argsort(-p)
    return dict(p=p[o], z=z[o], terrain=float(terrain), sp=float(sp))


def p_to_z(p_hpa, prof):
    return np.interp(np.asarray(p_hpa, dtype=np.float64), prof["p"][::-1], prof["z"][::-1])


def z_to_p(z_m, prof):
    return np.interp(np.asarray(z_m, dtype=np.float64), prof["z"], prof["p"])


def oco2_p_to_height(p_hpa, prof, p_surf_oco2=None, zmap="absolute"):
    """OCO-2 气压 -> 高度 (m ASL).

    absolute: z = z_ERA5(p)
    sigma   : 令 p_N (= p_S) 落在地面, p -> (p/p_S)*sp_ERA5 再查 ERA5 剖面
    """
    p = np.asarray(p_hpa, dtype=np.float64)
    if zmap == "absolute":
        return p_to_z(p, prof)
    if zmap == "sigma":
        scale = prof["sp"] / float(p_surf_oco2)
        return p_to_z(p * scale, prof)
    raise ValueError("zmap 必须是 absolute 或 sigma")


def ak_at_pressure(P, AK, p_query):
    """AK 作为气压的函数, 在 level 网格上 **线性于气压** 插值 (与 O'Dell A8 假设一致)."""
    P = np.asarray(P, float)
    AK = np.asarray(AK, float)
    return np.interp(np.asarray(p_query, float), P, AK)


# --------------------------------------------------------------------------
# 三种释放方案
# --------------------------------------------------------------------------
def scheme_level(P, h, AK, prof, zmap="absolute", center="voronoi"):
    """[level form] 20 个释放层 = 20 个 retrieval level.

    权重: w_i = AK_i * h_i  —— O'Dell level form, 严格 (XCO2 = sum_i h_i AK_i u_i)
    高度: z_i = z(P_i^rep), P^rep 由 center 决定 (voronoi / raw)

    默认 center="voronoi" => 每层的代表气压取围绕该 level 的控制体中心.
    """
    P = np.asarray(P, float)
    w = np.asarray(AK, float) * np.asarray(h, float)
    Pre = oco2_representative_pressures(P, center)
    z = oco2_p_to_height(Pre, prof, p_surf_oco2=P[-1], zmap=zmap)
    return dict(kind="level", release_p=Pre, release_agl=z - prof["terrain"],
                release_asl=z, w=w, center=center,
                sum_w=float(w.sum()), sum_ref=float(w.sum()))


def scheme_layer(P, h, AK, prof, zmap="absolute", f=F_DEFAULT):
    """[layer form] 19 个释放层 = 19 个 layer 中心.

    h' 由 A5 反解;  c_i = (p_i + p_{i+1})/2;  AK(c_i) = (AK_i + AK_{i+1})/2
    w_i = AK(c_i) * h'_i
    """
    P = np.asarray(P, float)
    hp, fS = level_to_layer_weights(h, f=f)
    c = oco2_layer_centers(P)
    AKc = 0.5 * (np.asarray(AK, float)[:-1] + np.asarray(AK, float)[1:])
    w = AKc * hp
    z = oco2_p_to_height(c, prof, p_surf_oco2=P[-1], zmap=zmap)
    return dict(kind="layer", release_p=c, release_asl=z,
                release_agl=z - prof["terrain"], w=w, hp=hp, fS=fS,
                sum_w=float(w.sum()), sum_ref=float(hp.sum()))


def scheme_refined(P, h, AK, prof, release_agl=None, zmap="absolute",
                   f=F_DEFAULT, p_top=0.0, p_bottom=None):
    """[refined form] 任意释放高程集合 (低层加密), 权重按 layer 气压重叠分配.

    layer L_i = [p_i, p_{i+1}] 承担 h'_i.  释放层 j 覆盖气压区间
    [pe_{j+1}, pe_j] (pe 自地面到 p_top), 则
        w_j = AK(p_j) * sum_i h'_i * overlap(L_i, layer_j) / dp_i
    若 AK 恒定则 sum_j w_j == sum_i h'_i (守恒).
    """
    P = np.asarray(P, float)
    AK = np.asarray(AK, float)
    hp, fS = level_to_layer_weights(h, f=f)
    # 每个 OCO-2 layer 的层平均 AK 与其 **总** 权重 h'_i * AKbar_i.
    # 关键: AK 必须取该 layer 自身的平均, 不能取释放点处的 AK —— 否则跨越
    # 238 hPa ~ TOA 的顶层释放会用 AK(238 hPa) 代表整层, 造成 ~1.6% 高估.
    AKl = 0.5 * (AK[:-1] + AK[1:])
    Wl = hp * AKl
    ra = np.asarray(release_agl if release_agl is not None else DEFAULT_RELEASE_AGL, float)
    if np.any(np.diff(ra) <= 0):
        raise ValueError("release_agl 必须严格升序")
    zj = ra + prof["terrain"]
    pj = z_to_p(zj, prof)
    N = len(ra)
    pe = np.empty(N + 1)
    pe[0] = float(prof["sp"]) if p_bottom is None else float(p_bottom)
    pe[1:N] = 0.5 * (pj[:-1] + pj[1:])
    pe[N] = float(p_top)
    for k in range(1, N + 1):
        if pe[k] > pe[k - 1]:
            pe[k] = pe[k - 1]
    w = np.zeros(N)
    hpj = np.zeros(N)
    for i in range(len(hp)):
        lo, hi = P[i], P[i + 1]
        dp = hi - lo
        if dp <= 0:
            continue
        for j in range(N):
            a = max(lo, pe[j + 1])
            c = min(hi, pe[j])
            if c > a:
                frac = (c - a) / dp
                w[j] += Wl[i] * frac
                hpj[j] += hp[i] * frac
    return dict(kind="refined", release_p=pj, release_asl=zj, release_agl=ra,
                w=w, hp=hp, hpj=hpj, AKl=AKl, fS=fS, pe=pe,
                sum_w=float(w.sum()), sum_ref=float(Wl.sum()))


SCHEMES = {"level": scheme_level, "layer": scheme_layer, "refined": scheme_refined}


def column_weights_for_sounding(region, date, sounding_id, scheme="layer",
                                release_agl=None, era5d=ERA5D_DEFAULT,
                                lite_dir=LITE_DIR, zmap="absolute",
                                center="voronoi", z_min_agl=5.0):
    s = load_oco2_sounding(date, sounding_id, lite_dir=lite_dir)
    if s is None:
        raise KeyError("sounding %s not found in %s" % (sounding_id, date))
    hour = int(str(sounding_id)[8:10])
    prof = era5_pz_profile(region, date, hour, s["lat"], s["lon"], era5d=era5d)
    kw = dict(zmap=zmap)
    if scheme == "level":
        kw["center"] = center
    if scheme == "refined":
        kw["release_agl"] = release_agl
    R = SCHEMES[scheme](s["P"], s["PW"], s["AK"], prof, **kw)
    # 有些受体 OCO-2 的 p_S 高于 ERA5 sp, 其最低 level 的代表气压会落到 ERA5 地形
    # 之下 => 负 AGL. 物理上该 level 代表的就是近地面空气, 因此在 ERA5/STILT 大气中
    # 应释放于地面附近, 而不是丢弃 (丢弃会损失约 0.026 权重, 实测 120 个受体中 24 个).
    zmin = float(z_min_agl)
    raw = np.asarray(R["release_agl"], dtype=np.float64)
    R["n_clamped"] = int((raw < zmin).sum())
    R["release_agl_raw"] = raw
    R["release_agl"] = np.maximum(raw, zmin)
    R.update(sounding=s, prof=prof, region=region, date=date,
             sounding_id=str(sounding_id), terrain=prof["terrain"],
             sp_era5=prof["sp"], sp_oco2=float(s["P"][-1]))
    return R


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _cli():
    import argparse
    ap = argparse.ArgumentParser(description="ACOS/X-STILT 柱足迹垂直加权")
    ap.add_argument("--check", action="store_true", help="诊断表")
    ap.add_argument("--verify-acos", action="store_true",
                    help="验证 O'Dell A5 的 h<->h' 往返与守恒")
    ap.add_argument("--emit-table", action="store_true", help="输出 STILT 表 + 权重 JSON")
    ap.add_argument("--region", default="po_valley_italy")
    ap.add_argument("--date", default="20171023")
    ap.add_argument("--sounding-id", default=None)
    ap.add_argument("--scheme", choices=list(SCHEMES), default="layer",
                    help="layer(默认, 19 个 O'Dell layer) / level(20 个 state-vector level) / refined")
    ap.add_argument("--zmap", choices=["absolute", "sigma"], default="absolute")
    ap.add_argument("--center", choices=["voronoi", "raw"], default="voronoi",
                    help="level form 的代表气压: voronoi(控制体中心) 或 raw(pressure_levels)")
    ap.add_argument("--out-dir", default="/tmp/colrun")
    a = ap.parse_args()

    def sid_of(r, d):
        pv = glob.glob(os.path.join(RECEPTOR_ROOT, r, "*%s*.provenance.json" % d))[0]
        return str(json.load(open(pv))["selected_soundings"][0]["sounding_id"])

    if a.verify_acos:
        sid = a.sounding_id or sid_of(a.region, a.date)
        s = load_oco2_sounding(a.date, sid)
        h = s["PW"]
        hp, fS = level_to_layer_weights(h)
        back = layer_to_level_weights(hp, fS)
        print("sounding %s   N=%d levels -> %d layers" % (sid, len(h), len(hp)))
        print("sum(h)   = %.10f" % h.sum())
        print("sum(h')  = %.10f   (1/(N-1)=%.8f)" % (hp.sum(), 1.0 / (len(hp))))
        print("h' spread: min=%.6f max=%.6f  (%.3f%%)"
              % (hp.min(), hp.max(), 100 * (hp.max() / hp.min() - 1)))
        print("round-trip h'->h : max|diff| = %.3e" % np.abs(back - h).max())
        print("f_S = %.6f  -> p_S = %.4f hPa (p_N = %.4f)"
              % (fS, s["P"][-2] + fS * (s["P"][-1] - s["P"][-2]), s["P"][-1]))
        print("h' 单调递减 =", bool(np.all(np.diff(hp) < 0)))
        print()
        print(" idx  p_i(hPa)   h_i        h'_{i-1}   h'_i")
        for k in range(len(h)):
            a_ = "%.6f" % hp[k - 1] if k >= 1 else "   -   "
            b_ = "%.6f" % hp[k] if k < len(hp) else "   -   "
            print(" %3d %9.3f  %.8f   %s  %s" % (k + 1, s["P"][k], h[k], a_, b_))
        return

    if a.emit_table:
        import csv as _csv
        rec_csv = os.path.join(RECEPTOR_ROOT, a.region,
                               "receptors_%s_n120_maximin.csv" % a.date)
        pv = rec_csv + ".provenance.json"
        recs = list(_csv.DictReader(open(rec_csv)))
        prov = json.load(open(pv))["selected_soundings"]
        os.makedirs(a.out_dir, exist_ok=True)
        tpath = os.path.join(a.out_dir, "coltable_%s_%s_%s.csv" % (a.region, a.date, a.scheme))
        wpath = os.path.join(a.out_dir, "colweights_%s_%s_%s.json" % (a.region, a.date, a.scheme))
        weights, nrow, nclamp = [], 0, 0
        with open(tpath, "w", newline="") as fh:
            wtr = _csv.writer(fh)
            wtr.writerow(["run_time", "lati", "long", "zagl"])
            for pr in prov:
                rr = recs[int(pr["csv_row"])]
                try:
                    R = column_weights_for_sounding(a.region, a.date,
                                                    str(pr["sounding_id"]),
                                                    scheme=a.scheme, zmap=a.zmap,
                                                    center=a.center)
                except Exception as e:
                    print("  [skip] %s %s" % (pr["sounding_id"], e))
                    continue
                for j, z in enumerate(R["release_agl"]):
                    if R["w"][j] <= 0:
                        continue
                    wtr.writerow([rr["run_time"], rr["lati"], rr["long"], "%g" % z])
                    nrow += 1
                    if z <= 5.0:
                        nclamp += 1
                weights.append(dict(sounding_id=str(pr["sounding_id"]),
                                    csv_row=int(pr["csv_row"]), run_time=rr["run_time"],
                                    lati=rr["lati"], long=rr["long"],
                                    terrain=R["terrain"], sum_w=R["sum_w"],
                                    release_agl=[float(x) for x in R["release_agl"]],
                                    w=[float(x) for x in R["w"]]))
        json.dump(dict(region=a.region, date=a.date, scheme=a.scheme, zmap=a.zmap,
                       n_receptors=len(weights), n_rows=nrow, weights=weights),
                  open(wpath, "w"), indent=1)
        print("wrote %s (%d rows)" % (tpath, nrow))
        print("wrote %s (%d receptors)" % (wpath, len(weights)))
        print("  clamped-to-ground releases (negative AGL): %d" % nclamp)
        print("  NOTE: 释放高度上限 %.0f m; 高位层(>3km)在 ±256 km 内足迹预期为 0"
              % max(max(x["release_agl"]) for x in weights))
        return

    if not a.check:
        ap.print_help()
        return
    sid = a.sounding_id or sid_of(a.region, a.date)
    R = column_weights_for_sounding(a.region, a.date, sid,
                                    scheme=a.scheme, zmap=a.zmap, center=a.center)
    s, prof = R["sounding"], R["prof"]
    P, AK, h = s["P"], s["AK"], s["PW"]
    print("sounding %s  lat %.4f lon %.4f  scheme=%s zmap=%s%s"
          % (sid, s["lat"], s["lon"], a.scheme, a.zmap,
             (" center=" + a.center) if a.scheme == "level" else ""))
    print("ERA5 terrain %.1f m ASL | sp_era5 %.2f | OCO-2 p_S %.2f hPa (差 %+.2f)"
          % (R["terrain"], R["sp_era5"], R["sp_oco2"], R["sp_oco2"] - R["sp_era5"]))
    print("sum(h)=%.8f   sum(w)=%.8f" % (h.sum(), R["sum_w"]))
    if a.scheme == "level":
        print()
        print(" idx  p_lvl(hPa) p_rep(hPa)  z(m AGL)      AK       h_i       w_i")
        for k in range(len(P)):
            print(" %3d %10.3f %10.3f %10.1f  %7.4f %9.6f %9.6f"
                  % (k + 1, P[k], R["release_p"][k], R["release_agl"][k],
                     AK[k], h[k], R["w"][k]))
    else:
        print()
        if a.scheme == "layer":
            print(" idx  p_ctr(hPa) z(m AGL)     AK(ctr)      h'_i       w_i")
            for k in range(len(R["w"])):
                print(" %3d %10.3f %9.1f  %8.5f %10.6f %10.6f"
                      % (k + 1, R["release_p"][k], R["release_agl"][k],
                         R["w"][k] / R["hp"][k], R["hp"][k], R["w"][k]))
        else:
            print(" idx  p_j(hPa)   z(m AGL)    h'_dist     AKbar_j     w_j")
            ok = R["hpj"] > 0
            for k in range(len(R["w"])):
                akj = R["w"][k] / R["hpj"][k] if R["hpj"][k] > 0 else 0.0
                print(" %3d %9.3f %10.1f  %9.6f  %9.5f %9.6f"
                      % (k + 1, R["release_p"][k], R["release_agl"][k],
                         R["hpj"][k], akj, R["w"][k]))
            print(" (未被任何释放层覆盖的层权重: %.6f)"
                  % (R["sum_ref"] - sum(R["hp"][i] * R["AKl"][i]
                     for i in range(len(R["hp"])))))
    print()
    print("累积权重 (自地面):")
    ze = R["release_agl"]
    order = np.argsort(ze)
    cum = np.cumsum(R["w"][order]) / R["sum_w"]
    for k, j in enumerate(order):
        print("  <= %8.1f m AGL : %6.2f%%" % (ze[j], 100 * cum[k]))


if __name__ == "__main__":
    _cli()
