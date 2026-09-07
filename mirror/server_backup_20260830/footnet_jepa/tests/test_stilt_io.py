import os
import tempfile
import unittest

import numpy as np

from stilt_io import (_xy_from_table, read_stilt_footprint,
                      stilt_traj_to_xy)


def _write_synthetic_foot(path, lat0, lat1, lon0, lon1, dlat, dlon, value):
    import netCDF4 as nc
    lats = np.arange(lat0, lat1 + dlat / 2, dlat)
    lons = np.arange(lon0, lon1 + dlon / 2, dlon)
    foot = np.full((1, len(lats), len(lons)), value, dtype=np.float32)
    with nc.Dataset(path, "w") as ds:
        ds.createDimension("lon", len(lons))
        ds.createDimension("lat", len(lats))
        ds.createDimension("time", 1)
        ds.createVariable("lon", "f8", ("lon",))[:] = lons
        ds.createVariable("lat", "f8", ("lat",))[:] = lats
        v = ds.createVariable("foot", "f4", ("time", "lat", "lon"))
        v[:] = foot
    return path


class StiltFootprintTests(unittest.TestCase):
    def test_constant_field_resampled_without_renormalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sim_foot.nc")
            # domain spans +-6 deg around receptor: covers the 256 km window
            _write_synthetic_foot(path, 34.0, 46.0, -124.0, -112.0,
                                  0.04, 0.04, value=2.5)
            y, diag = read_stilt_footprint(path, rlat=40.0, rlon=-118.0,
                                           grid=32, spacing_km=4.0)
            self.assertEqual(y.shape, (32, 32))
            self.assertAlmostEqual(diag["coverage"], 1.0, places=5)
            self.assertTrue(np.isfinite(y).all())
            # physical units preserved: constant field stays ~constant
            np.testing.assert_allclose(y, 2.5, rtol=1e-4)

    def test_small_domain_raises_on_low_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tiny_foot.nc")
            _write_synthetic_foot(path, 39.9, 40.1, -118.1, -117.9,
                                  0.01, 0.01, value=1.0)
            with self.assertRaises(ValueError):
                read_stilt_footprint(path, rlat=40.0, rlon=-118.0,
                                     grid=128, spacing_km=4.0)

    def test_time_dimension_is_integrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            import netCDF4 as nc
            path = os.path.join(tmp, "timed_foot.nc")
            lats = np.arange(34.0, 46.0 + 0.02, 0.04)
            lons = np.arange(-124.0, -112.0 + 0.02, 0.04)
            layer = np.full((len(lats), len(lons)), 1.0, dtype=np.float32)
            with nc.Dataset(path, "w") as ds:
                ds.createDimension("lon", len(lons))
                ds.createDimension("lat", len(lats))
                ds.createDimension("time", 3)
                ds.createVariable("lon", "f8", ("lon",))[:] = lons
                ds.createVariable("lat", "f8", ("lat",))[:] = lats
                v = ds.createVariable("foot", "f4", ("time", "lat", "lon"))
                v[:] = np.stack([layer] * 3)          # three identical layers
            y, _ = read_stilt_footprint(path, rlat=40.0, rlon=-118.0,
                                        grid=16, spacing_km=4.0)
            np.testing.assert_allclose(y, 3.0, rtol=1e-4)


class StiltTrajTableTests(unittest.TestCase):
    def test_xy_convention_matches_compute_trajectory_xy(self):
        rlat, rlon, half_km = 34.05, -118.25, 256.0
        hours = np.array([0.0, 1.0, 2.0, 30.0])       # 30 h must be dropped
        longs = np.array([-118.25, -118.75, -119.25, -100.0])
        latis = np.array([34.05, 34.05, 34.05, 10.0])
        xy = _xy_from_table(hours, longs, latis, rlat, rlon, half_km)
        self.assertEqual(xy.shape, (3, 2))
        self.assertAlmostEqual(float(xy[0, 0]), 0.0, places=5)
        self.assertLess(float(xy[-1, 0]), float(xy[0, 0]))   # westward drift
        expected_km = (-0.5 * 111.32 * np.cos(np.radians(rlat)))
        self.assertAlmostEqual(float(xy[1, 0]), expected_km / half_km,
                               places=4)

    def test_traj_reader_rejects_short_trajectory(self):
        import pandas as pd
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            fake = os.path.join(tmp, "t_traj.rds")
            open(fake, "w").close()
            csv = os.path.join(tmp, "dump.csv")
            pd.DataFrame({
                "time": [-30.0],          # one point, 0.5 h back, in window
                "long": [-118.0], "lati": [34.0],
            }).to_csv(csv, index=False)
            with mock.patch("stilt_io._dump_traj_csv", return_value=csv):
                with self.assertRaises(ValueError):
                    stilt_traj_to_xy(fake, 34.0, -118.0, 256.0)


if __name__ == "__main__":
    unittest.main()


class BuildStiltTests(unittest.TestCase):
    def test_build_stilt_preserves_physical_units(self):
        import netCDF4 as nc
        import numpy as np
        import os, tempfile
        import config as C
        import data_builder as D

        with tempfile.TemporaryDirectory() as tmp:
            # fake HRRR-lite snapshot covering the receptor window
            hrrr_dir = os.path.join(tmp, "HRRR_lite", "2024")
            os.makedirs(hrrr_dir)
            lats = np.linspace(30.0, 50.0, 81)
            lons = np.linspace(-130.0, -110.0, 81)
            for snap in ("20240705.00z", "20240705.06z",
                         "20240705.12z", "20240705.18z"):
                with nc.Dataset(os.path.join(hrrr_dir,
                                             f"hysplit.{snap}.nc"),
                                "w") as ds:
                    ds.createDimension("y", 81)
                    ds.createDimension("x", 81)
                    for name, val in (("U10M", 5.0), ("V10M", -2.0),
                                      ("PBLH", 800.0), ("PRSS", 101000.0)):
                        v = ds.createVariable(name, "f4", ("y", "x"))
                        v[:] = np.full((81, 81), val, dtype=np.float32)

            # patch projection onto the tiny grid so _assemble_input works
            from unittest import mock

            def fake_proj(lat, lon):
                x = np.clip((np.asarray(lon) + 120.0) / 20.0 * 80.0, 0, 79)
                y = np.clip((50.0 - np.asarray(lat)) / 20.0 * 80.0, 0, 79)
                return x, y

            # fake footprint: constant 3.7 physical units over full domain
            fnc = os.path.join(tmp, "sim_foot.nc")
            with nc.Dataset(fnc, "w") as ds:
                ds.createDimension("lon", 81)
                ds.createDimension("lat", 81)
                ds.createDimension("time", 1)
                ds.createVariable("lon", "f8", ("lon",))[:] = lons
                ds.createVariable("lat", "f8", ("lat",))[:] = lats
                v = ds.createVariable("foot", "f4", ("time", "lat", "lon"))
                v[:] = np.full((1, 81, 81), 3.7, dtype=np.float32)

            manifest = os.path.join(tmp, "receptors_manifest.csv")
            with open(manifest, "w") as fh:
                fh.write("sim_id,run_time,lati,long,zagl,foot_nc,traj_rds\n")
                fh.write(f"s1,2024-07-05T18:00:00Z,40.0,-118.0,5,{fnc},\n")

            outdir = os.path.join(tmp, "out")
            with mock.patch.object(C, "OUTDIR", outdir), \
                 mock.patch.object(C, "HRRR_DIR", hrrr_dir), \
                 mock.patch.object(D, "latlon_to_grid_xy", fake_proj):
                X, Y = D.build_stilt(manifest, grid=32,
                                     out_prefix="unit_stilt")

            self.assertEqual(X.shape[0], 1)
            self.assertTrue(np.isfinite(Y).all())
            self.assertGreater(Y.max(), 3.6)      # ~constant 3.7, NOT sum=1
            meta = __import__("json").load(
                open(os.path.join(outdir, "unit_stilt_meta.json")))
            self.assertEqual(meta["label_source"], "stilt_xstilt")
            self.assertEqual(meta["contract"]["target_mode"],
                             C.TARGET_MODE_PHYSICAL)


if __name__ == "__main__":
    unittest.main()
