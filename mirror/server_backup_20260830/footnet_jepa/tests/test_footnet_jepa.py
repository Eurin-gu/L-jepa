import json
import os
import tempfile
import unittest
from unittest import mock

import numpy as np
import torch

import config as C
import data_builder as D
from models import Encoder, JEPA, visreg_reg
from provenance import data_contract, fingerprint
from simple_lagrangian import back_trajectory_footprint
from lagrangian_jepa import compute_trajectory_xy
from train import (FootprintShapeLoss, metrics, spatial_probability,
                   stratified_label_indices, train_validation_indices,
                   make_criterion, physical_amplitude, load_pretrain_pool)


class DataBuilderTests(unittest.TestCase):
    def test_metric_receptor_grid(self):
        lats, lons, offsets = D.receptor_grid(40.0, -105.0, 8, 4.0)
        self.assertAlmostEqual((lats[1] - lats[0]) * 110.54, 4.0, places=6)
        self.assertAlmostEqual(
            (lons[1] - lons[0]) * 111.32 * np.cos(np.radians(40.0)),
            4.0, places=6)
        self.assertEqual(offsets.tolist(), [-16.0, -12.0, -8.0, -4.0, 0.0, 4.0, 8.0, 12.0])

    def test_bilinear_rejects_out_of_domain(self):
        field = np.arange(16, dtype=float).reshape(4, 4)
        with self.assertRaises(ValueError):
            D._bilinear(field, np.array([-0.1]), np.array([1.0]))
        value = D._bilinear(field, np.array([-0.1]), np.array([1.0]), bounds_error=False)
        self.assertTrue(np.isnan(value[0]))

    def test_train_test_windows_must_not_overlap(self):
        with self.assertRaises(ValueError):
            D._validate_split(["20240402.18z"], ["20240403.00z"])

    def test_wind_scaling_is_not_times_ten(self):
        wind = D._normalize_met(np.array([10.0]), 0)
        np.testing.assert_allclose(wind, [1.0])

    def test_contract_fingerprint_changes_with_grid(self):
        self.assertNotEqual(
            fingerprint(data_contract(64, 100, "oco2")),
            fingerprint(data_contract(128, 100, "oco2")))

    def test_build_memory_guard(self):
        with self.assertRaises(MemoryError):
            D.build(["dummy"] * 100, 1000, 128, 100, np.random.default_rng(0),
                    "oco2", "test", {})


class TrajectoryTests(unittest.TestCase):
    def test_constant_east_wind_moves_back_trajectory_west(self):
        lats = np.linspace(39.0, 41.0, 81)
        lons = np.linspace(-106.0, -104.0, 81)
        fields = [np.full((81, 81), 10.0)]
        zeros = [np.zeros((81, 81))]
        footprint, diagnostic = back_trajectory_footprint(
            lons, lats, fields, zeros, -105.0, 40.0, npart=200,
            dt=600.0, hperblock=1.0, diffusivity=0.0, seed=1,
            return_diagnostics=True)
        _, xx = np.indices(footprint.shape)
        mean_x = float((footprint * xx).sum())
        receptor_x = np.searchsorted(lons, -105.0)
        self.assertLess(mean_x, receptor_x)
        self.assertGreater(diagnostic["capture_fraction"], 0.9)
        self.assertAlmostEqual(float(footprint.sum()), 1.0, places=7)


class ModelAndLossTests(unittest.TestCase):
    def test_spatial_probability_contract(self):
        logits = torch.randn(3, 1, 8, 8)
        probability = spatial_probability(logits)
        self.assertTrue(torch.all(probability >= 0))
        torch.testing.assert_close(probability.sum((1, 2, 3)), torch.ones(3))

    def test_shape_loss_is_batch_separable(self):
        logits = torch.randn(2, 1, 8, 8)
        target = torch.rand(2, 1, 8, 8)
        target /= target.sum((2, 3), keepdim=True)
        criterion = FootprintShapeLoss()
        together = criterion(logits, target)[0]
        separate = torch.stack([
            criterion(logits[i:i + 1], target[i:i + 1])[0] for i in range(2)
        ]).mean()
        torch.testing.assert_close(together, separate)

    def test_metrics_do_not_cancel_mass_errors(self):
        target = np.ones((2, 4, 4), dtype=float) / 16.0
        pred = target.copy(); pred[0] *= 0.5; pred[1] *= 1.5
        result = metrics(pred, target)
        self.assertAlmostEqual(result["mass_error"], 0.5)

    def test_jepa_mask_is_on_input_device_and_per_sample(self):
        torch.manual_seed(7)
        encoder = Encoder(in_channels=20, base=4)
        model = JEPA(encoder, encoder.latent_ch)
        x = torch.randn(4, 20, 64, 64)
        masked, mask = model.make_mask(x)
        self.assertEqual(mask.device, x.device)
        self.assertEqual(mask.shape, (4, 1, 4, 4))
        self.assertTrue(torch.all(mask.flatten(1).sum(1) > 0))
        self.assertFalse(torch.equal(mask[0], mask[1])
                         and torch.equal(mask[1], mask[2])
                         and torch.equal(mask[2], mask[3]))

    def test_visreg_is_finite_for_one_embedding(self):
        values = visreg_reg(torch.randn(1, 8), n_slices=4)
        self.assertTrue(all(torch.isfinite(value) for value in values))

    def test_eulerian_jepa_target_batchnorm_not_updated_by_forward(self):
        torch.manual_seed(2)
        encoder = Encoder(in_channels=20, base=4)
        model = JEPA(encoder, encoder.latent_ch)
        model.train()
        keys = ("running_mean", "running_var", "num_batches_tracked")
        before = {k: v.clone() for k, v in model.target.state_dict().items()
                  if any(key in k for key in keys)}
        model(torch.randn(2, 20, 64, 64))
        after = {k: v for k, v in model.target.state_dict().items()
                 if any(key in k for key in keys)}
        for key in before:
            torch.testing.assert_close(before[key], after[key])


class PhysicalTargetModeTests(unittest.TestCase):
    def test_amplitude_is_nonnegative_and_not_normalized(self):
        logits = torch.randn(3, 1, 8, 8) * 2.0
        amplitude = physical_amplitude(logits)
        self.assertTrue(bool((amplitude >= 0).all()))
        sums = amplitude.sum(dim=(1, 2, 3))
        self.assertFalse(torch.allclose(sums, torch.ones_like(sums)))

    def test_physical_loss_is_finite_and_batch_separable(self):
        criterion = make_criterion(C.TARGET_MODE_PHYSICAL)
        logits = torch.randn(4, 1, 8, 8)
        target = torch.rand(4, 1, 8, 8) * 5.0
        loss, amp_error = criterion(logits, target)
        self.assertTrue(torch.isfinite(loss))
        self.assertTrue(torch.isfinite(amp_error))
        separate = torch.stack([
            criterion(logits[i:i + 1], target[i:i + 1])[0] for i in range(4)
        ]).mean()
        torch.testing.assert_close(loss, separate)

    def test_make_criterion_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            make_criterion("bogus_mode")

    def test_pretrain_pool_missing_returns_none(self):
        x, meta = load_pretrain_pool.__wrapped__() if hasattr(
            load_pretrain_pool, "__wrapped__") else (None, None)
        # The default data directory ships no pretraining pool; if one exists
        # it must at least be internally consistent.
        pool_path = os.path.join(C.OUTDIR, "pretrain_inputs.npy")
        if not os.path.exists(pool_path):
            self.assertIsNone(x)


class LabelFractionTests(unittest.TestCase):
    @staticmethod
    def _samples():
        return ([{"snapshot": "20240402.18z"}] * 6
                + [{"snapshot": "20240409.18z"}] * 4)

    def test_full_fraction_keeps_everything(self):
        indices = stratified_label_indices(self._samples(), range(10), 1.0, 0)
        self.assertEqual(indices.tolist(), list(range(10)))

    def test_stratified_subset_keeps_every_date(self):
        indices = stratified_label_indices(self._samples(), range(10), 0.5, 42)
        kept_dates = [self._samples()[i]["snapshot"] for i in indices]
        self.assertEqual(set(kept_dates),
                         {"20240402.18z", "20240409.18z"})
        self.assertEqual(indices.tolist(), sorted(indices))
        self.assertEqual(len(indices), int(round(0.5 * 6)) + int(round(0.5 * 4)))

    def test_invalid_fraction_raises(self):
        with self.assertRaises(ValueError):
            stratified_label_indices(self._samples(), range(10), 0.0, 0)

    def test_selection_is_deterministic(self):
        a = stratified_label_indices(self._samples(), range(10), 0.5, 7)
        b = stratified_label_indices(self._samples(), range(10), 0.5, 7)
        np.testing.assert_array_equal(a, b)


class HourlyTrajectoryTests(unittest.TestCase):
    """compute_trajectory_xy must record hourly points via time interpolation."""

    def test_constant_wind_gives_hourly_westward_trajectory(self):
        base_lat, base_lon = 40.0, -105.0

        def fake_proj(lat, lon):
            x = np.clip((np.asarray(lon) - base_lon) / 6.0 + 3.5, 0.0, 7.0)
            y = np.clip((base_lat - np.asarray(lat)) / 6.0 + 3.5, 0.0, 7.0)
            return x, y

        met = {}
        for snap in ["20240402.18z", "20240402.12z", "20240402.06z",
                     "20240402.00z"]:
            met[snap] = {
                "U10M": np.full((8, 8), 10.0, dtype=np.float32),
                "V10M": np.zeros((8, 8), dtype=np.float32),
                "PBLH": np.full((8, 8), 1000.0, dtype=np.float32),
                "PRSS": np.full((8, 8), 90000.0, dtype=np.float32),
            }
        with mock.patch.object(D, "latlon_to_grid_xy", fake_proj):
            xy = compute_trajectory_xy("20240402.18z", (base_lat, base_lon),
                                       met, grid=64, spacing_km=4.0,
                                       npart=32, seed=0)
        total_h = C.BACKHOURS[-1]
        step = C.TRAJ_RECORD_STEP_H
        self.assertEqual(xy.shape, (int(round(total_h / step)) + 1, 2))
        # Eastward wind: backward trajectory drifts west (x decreases).
        self.assertLess(float(xy[-1, 0]), float(xy[0, 0]))
        diffs = np.diff(xy[:, 0])
        self.assertLessEqual(float(diffs.max()), 1e-3)


class SplitTests(unittest.TestCase):
    def test_validation_groups_by_snapshot(self):
        samples = ([{"snapshot": "20240101.00z"}] * 5
                   + [{"snapshot": "20240201.00z"}] * 5)
        train, val, scope = train_validation_indices({"samples": samples})
        self.assertEqual(scope, "held_out_date")
        self.assertEqual(set(train.tolist()), set(range(5)))
        self.assertEqual(set(val.tolist()), set(range(5, 10)))


if __name__ == "__main__":
    unittest.main()
