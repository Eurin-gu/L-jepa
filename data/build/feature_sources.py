"""Feature readers for the local FootNet assembler.

Each source type implements:
    read_snapshot(snapshot, fields=("U10M","V10M","PBLH","PRSS")) -> dict
returning full 2-D fields (float32, shape (Ny, Nx) in file scan order:
row 0 = southernmost) for one model-input valid time ("snapshot").

The descriptor JSON (per date) selects a source type and its parameters;
all readers are thin wrappers so the descriptor stays declarative.
"""
from __future__ import annotations

import os

import numpy as np

# Field name used by the FootNet schema -> (shortName, typeOfLevel, level).
HRRR_WRFPRS_SELECTORS = {
    "U10M": ("10u", "heightAboveGround", 10),
    "V10M": ("10v", "heightAboveGround", 10),
    "PBLH": ("blh", "surface", 0),
    "PRSS": ("sp", "surface", 0),
}
# ERA5 hourly single-level grib (verified against po_20171023_SFC.GRIB):
# CDS-converted files store all four variables with typeOfLevel="surface".
ERA5_SFC_SELECTORS = {
    "U10M": ("10u", "surface", 0),
    "V10M": ("10v", "surface", 0),
    "PBLH": ("blh", "surface", 0),
    "PRSS": ("sp", "surface", 0),
}


def _iter_messages(path):
    import eccodes

    handle = open(path, "rb")
    try:
        while True:
            msg = eccodes.codes_new_from_file(handle, eccodes.CODES_PRODUCT_GRIB)
            if msg is None:
                break
            yield msg
    finally:
        handle.close()


def _read_values(msg):
    import eccodes

    values = np.asarray(eccodes.codes_get_values(msg), dtype=np.float64)
    nx = int(eccodes.codes_get(msg, "Nx"))
    ny = int(eccodes.codes_get(msg, "Ny"))
    return values.reshape(ny, nx).astype(np.float32)


class HrrrSurfaceGribSource(object):
    """HRRR wrfprs hourly f00 files named <snapshot-as-YYYYMMDDHH>.grib2."""

    def __init__(self, directory, selectors=None, file_prefix="", file_suffix=".grib2"):
        self.directory = directory
        self.selectors = dict(selectors or HRRR_WRFPRS_SELECTORS)
        self.file_prefix = file_prefix
        self.file_suffix = file_suffix

    def snapshot_file(self, snapshot):
        # snapshot "20171111.20z" -> "2017111120.grib2"
        stem = snapshot.replace(".", "").rstrip("zZ")
        return os.path.join(self.directory, self.file_prefix + stem + self.file_suffix)

    def read_snapshot(self, snapshot, fields=None):
        import eccodes

        fields = list(self.selectors) if fields is None else list(fields)
        wanted = {f: self.selectors[f] for f in fields if f in self.selectors}
        if not wanted:
            raise KeyError("no grib selectors for fields " + str(fields))
        path = self.snapshot_file(snapshot)
        if not os.path.isfile(path):
            raise FileNotFoundError("missing feature grib: " + path)
        out = {}
        for msg in _iter_messages(path):
            try:
                short = eccodes.codes_get(msg, "shortName")
                level_type = eccodes.codes_get(msg, "typeOfLevel")
                level = eccodes.codes_get(msg, "level")
            except Exception:
                eccodes.codes_release(msg)
                continue
            for field, (s, t, lev) in wanted.items():
                if (short, level_type, level) == (s, t, lev) and field not in out:
                    out[field] = _read_values(msg)
            eccodes.codes_release(msg)
        missing = [f for f in fields if f not in out]
        if missing:
            raise KeyError("snapshot " + snapshot + " missing grib fields "
                           + str(missing) + " in " + path)
        shapes = {v.shape for v in out.values()}
        if len(shapes) != 1:
            raise ValueError("inconsistent field shapes in " + path + ": " + str(shapes))
        return out

    def describe(self):
        return {"source_type": "hrrr_wrfprs_surface",
                "directory": self.directory,
                "selectors": {k: list(v) for k, v in self.selectors.items()}}


class Era5SfcGribSource(HrrrSurfaceGribSource):
    """ERA5 single-level hourly grib fallback (same GRIB2 code space)."""

    def __init__(self, directory, **kwargs):
        super(Era5SfcGribSource, self).__init__(
            directory, selectors=ERA5_SFC_SELECTORS, **kwargs)


# ---------------------------------------------------------------------------
# npz model-feature source (production a<YYYYMMDDHH>_f00.npz assets)
# ---------------------------------------------------------------------------
NPZ_FIELD_KEYS = ("U10M", "V10M", "PBLH", "PRSS")


class NpzHrrrSource(object):
    """Full-grid HRRR model features stored as float32 npz.

    Files are named a<snapshot as YYYYMMDDHH>_f00.npz (one per model-input
    valid time), each holding 2-D fields U10M/V10M/PBLH/PRSS on the full
    HRRR Lambert grid (1059, 1799), row 0 = south, matching the
    data_builder latlon_to_grid_xy convention used by assemble.py.
    """

    def __init__(self, directory, file_prefix="a", file_suffix="_f00.npz",
                 field_keys=None):
        self.directory = directory
        self.file_prefix = file_prefix
        self.file_suffix = file_suffix
        self.field_keys = tuple(field_keys or NPZ_FIELD_KEYS)

    def snapshot_file(self, snapshot):
        stem = snapshot.replace(".", "").rstrip("zZ")
        return os.path.join(self.directory,
                            self.file_prefix + stem + self.file_suffix)

    def read_snapshot(self, snapshot, fields=None):
        fields = list(self.field_keys) if fields is None else list(fields)
        path = self.snapshot_file(snapshot)
        if not os.path.isfile(path):
            raise FileNotFoundError("missing model feature npz: " + path)
        with np.load(path) as data:
            missing = [f for f in fields if f not in data]
            if missing:
                raise KeyError("snapshot " + snapshot + " npz " + path
                               + " lacks fields " + str(missing))
            out = {}
            for f in fields:
                arr = np.asarray(data[f], dtype=np.float32)
                if arr.ndim != 2:
                    raise ValueError("non-2D model feature " + f + " in "
                                     + path)
                out[f] = arr.copy()
        shapes = {v.shape for v in out.values()}
        if len(shapes) != 1:
            raise ValueError("inconsistent model feature shapes in " + path
                             + ": " + str(shapes))
        if any(not np.isfinite(v).all() for v in out.values()):
            raise ValueError("non-finite model feature values in " + path)
        return out

    def describe(self):
        return {"source_type": "npz_hrrr",
                "directory": self.directory,
                "file_prefix": self.file_prefix,
                "file_suffix": self.file_suffix,
                "field_keys": list(self.field_keys)}



class Era5SfcDaySource(object):
    """ERA5 single-level daily GRIB with per-hour message selection.

    Files are the CDS daily outputs named <YYYYMMDD>_SFC.GRIB (one file per
    model day, containing hourly records 00..23 for the four schema fields
    stored with typeOfLevel='surface').  A snapshot "20171023.21z" selects
    messages whose valid hour equals 21 from the file 20171023_SFC.GRIB, so a
    single directory may cover both the prev and target model days needed for
    a 24 h backward footprint.
    """

    def __init__(self, directory, selectors=None):
        self.directory = directory
        self.selectors = dict(selectors or ERA5_SFC_SELECTORS)
        self._suffix = "_SFC.GRIB"

    def snapshot_parts(self, snapshot):
        # "20171023.21z" -> (date=20171023, hour=21)
        s = snapshot.replace(".", "").rstrip("zZ")
        if len(s) != 10:
            raise ValueError("bad era5 day snapshot " + snapshot)
        return s[:8], int(s[8:10])

    def day_file(self, date):
        return os.path.join(self.directory, date + self._suffix)

    def snapshot_file(self, snapshot):
        date, _hour = self.snapshot_parts(snapshot)
        return self.day_file(date)


    def read_snapshot(self, snapshot, fields=None):
        import eccodes
        fields = list(self.selectors) if fields is None else list(fields)
        wanted = {f: self.selectors[f] for f in fields if f in self.selectors}
        if not wanted:
            raise KeyError("no era5 selectors for fields " + str(fields))
        date, hour = self.snapshot_parts(snapshot)
        path = self.day_file(date)
        if not os.path.isfile(path):
            raise FileNotFoundError("missing era5 day grib: " + path)
        out = {}
        with open(path, "rb") as handle:
            while True:
                msg = eccodes.codes_new_from_file(
                    handle, eccodes.CODES_PRODUCT_GRIB)
                if msg is None:
                    break
                try:
                    if eccodes.codes_get(msg, "dataTime") != hour * 100:
                        continue
                    short = eccodes.codes_get(msg, "shortName")
                    level_type = eccodes.codes_get(msg, "typeOfLevel")
                    level = eccodes.codes_get(msg, "level")
                    for field, (s, t, lev) in wanted.items():
                        if (short, level_type, level) == (s, t, lev)                                 and field not in out:
                            out[field] = _read_values(msg)
                finally:
                    eccodes.codes_release(msg)
        missing = [f for f in fields if f not in out]
        if missing:
            raise KeyError("snapshot " + snapshot + " missing era5 fields "
                           + str(missing) + " at hour " + str(hour) + " in "
                           + path)
        shapes = {v.shape for v in out.values()}
        if len(shapes) != 1:
            raise ValueError("inconsistent field shapes in " + path + ": "
                             + str(shapes))
        return out

    def describe(self):
        return {"source_type": "era5_sfc_day",
                "directory": self.directory,
                "selectors": {k: list(v) for k, v in self.selectors.items()}}


SOURCE_TYPES = {
    "hrrr_wrfprs_surface": HrrrSurfaceGribSource,
    "era5_sfc_grib": Era5SfcGribSource,
    "era5_sfc_day": Era5SfcDaySource,
    "npz_hrrr": NpzHrrrSource,
}


def make_source(descriptor):
    kind = descriptor["source_type"]
    cls = SOURCE_TYPES[kind]
    kwargs = dict(descriptor.get("params") or {})
    directory = descriptor["directory"]
    if not os.path.isdir(directory):
        raise FileNotFoundError("feature directory not found: " + directory)
    return cls(directory, **kwargs)