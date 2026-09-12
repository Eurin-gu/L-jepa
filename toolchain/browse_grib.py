# -*- coding: utf-8 -*-
"""ERA5 GRIB quick browser (cfgrib + xarray + matplotlib).

Usage (WSL, /root/venvs/cds/bin/python):
    python browse_grib.py <file>                       # list structure
    python browse_grib.py <file> --var t2m [--time 12]  # SFC field plot
    python browse_grib.py <file> --var t --level 850    # PL field at level
"""
import sys, argparse
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import xarray as xr
import numpy as np, warnings
warnings.filterwarnings("ignore")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--var", default=None)
    ap.add_argument("--time", type=int, default=None)
    ap.add_argument("--level", type=float, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    is_sfc = args.file.upper().endswith("_SFC.GRIB")
    ds = None
    if is_sfc or args.var is None:
        # SFC: open all surface fields together (cfgrib handles this file layout)
        try: ds = xr.open_dataset(args.file, engine="cfgrib", backend_kwargs={"filter_by_keys": {"typeOfLevel": "surface"}})
        except Exception: ds = None
    if ds is None:
        # PL or single-var request: filter by shortName
        for lvl in ("isobaricInhPa", "surface", "heightAboveGround"):
            try:
                ds = xr.open_dataset(args.file, engine="cfgrib", backend_kwargs={"filter_by_keys": {"shortName": args.var or "t", "typeOfLevel": lvl}})
                break
            except Exception:
                continue
    if ds is None: sys.exit("cannot open file with cfgrib")
    ds = ds.isel(latitude=slice(None, None, -1))
    print("File:", args.file)
    print("Variables:", list(ds.data_vars))
    print("Time steps:", ds.sizes.get("time", 1), "| grid:", ds.sizes.get("latitude"), "x", ds.sizes.get("longitude"))
    if "isobaricInhPa" in ds.coords: print("Levels:", [float(x) for x in ds.isobaricInhPa.values][:8], "...")
    var = args.var or list(ds.data_vars)[0]
    if var not in ds.data_vars: sys.exit("no %s; have %s" % (var, list(ds.data_vars)))
    field = ds[var]
    if "isobaricInhPa" in field.dims:
        lev = args.level if args.level is not None else float(field.isobaricInhPa.values[len(field.isobaricInhPa)//2])
        field = field.sel(isobaricInhPa=lev); print("(level %.0f hPa)" % lev)
    itime = args.time if args.time is not None else ds.sizes.get("time", 1)//2
    if "time" in field.dims: field = field.isel(time=itime)
    label = var
    if var in ("t2m", "t"): field = field - 273.15; label += " [degC]"
    if var == "sp": field = field/100.0; label += " [hPa]"
    fig, ax = plt.subplots(figsize=(9, 6))
    cf = ax.contourf(field.longitude, field.latitude, field.values, levels=40, cmap="viridis")
    plt.colorbar(cf, ax=ax, label=label)
    if var in ("t2m", "sp", "blh") and "u10" in ds.data_vars and "v10" in ds.data_vars:
        sk = slice(None, None, 3)
        ax.barbs(field.longitude.values[sk], field.latitude.values[sk], ds.u10.isel(time=itime).values[sk,sk], ds.v10.isel(time=itime).values[sk,sk], length=4.5)
    ax.set_title("%s  %s  t=%d" % (var, args.file.split("/")[-1], itime))
    ax.set_xlabel("longitude"); ax.set_ylabel("latitude")
    out = args.out or ("%s_%s.png" % (args.file.split("/")[-1][:-5], var))
    plt.savefig(out, dpi=110, bbox_inches="tight")
    print("Saved:", out)

if __name__ == "__main__":
    main()