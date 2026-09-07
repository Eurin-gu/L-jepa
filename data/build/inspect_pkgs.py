
import sys
print("eccodes import test:")
try:
    import eccodes
    print("eccodes OK", getattr(eccodes,'__version__',''))
except Exception as e:
    print("eccodes FAIL", repr(e))
try:
    import cfgrib
    print("cfgrib OK")
except Exception as e:
    print("cfgrib FAIL", repr(e))
try:
    import xarray
    print("xarray OK", xarray.__version__)
except Exception as e:
    print("xarray FAIL", repr(e))
try:
    import scipy
    print("scipy OK", scipy.__version__)
except Exception as e:
    print("scipy FAIL", repr(e))
