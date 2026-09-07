import os, glob
print("era5 dir:", "/root/era5_grib")
if os.path.isdir("/root/era5_grib"):
    files = sorted(os.listdir("/root/era5_grib"))
    print("files:", len(files))
    for fn in files[:15]: print("  ", fn)
else:
    print("no /root/era5_grib")
