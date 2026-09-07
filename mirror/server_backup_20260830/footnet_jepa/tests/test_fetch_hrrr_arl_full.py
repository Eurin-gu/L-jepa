import os
import tempfile
import unittest
from unittest import mock

from stilt_pipeline import fetch_hrrr_arl_full as FULL


class HrrrFullDownloadTest(unittest.TestCase):
    def test_full_name_includes_cycle_date(self):
        self.assertEqual(
            FULL.full_name("20240704", 18, 3),
            "hrrr.t18z.wrfprsf03.grib2",
        )

    def test_reuses_only_complete_validated_download(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = os.path.join(temporary, "full.grib2")
            with open(output, "wb") as handle:
                handle.write(b"complete")
            entries = [(1, 0, "message")]
            with mock.patch.object(FULL.subset, "validate_grib") as validate, \
                    mock.patch.object(FULL, "run_aria2") as aria2:
                FULL.validate_or_download("url", output, entries, None, 8)
            validate.assert_called_once_with(output, 1)
            aria2.assert_not_called()

            with open(output + ".aria2", "wb"):
                pass
            with mock.patch.object(FULL.subset, "validate_grib") as validate, \
                    mock.patch.object(FULL, "run_aria2") as aria2:
                FULL.validate_or_download("url", output, entries, None, 8)
            aria2.assert_called_once()
            validate.assert_called_once_with(output, 1)

    def test_does_not_overwrite_unmarked_invalid_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = os.path.join(temporary, "full.grib2")
            with open(output, "wb") as handle:
                handle.write(b"invalid")
            with mock.patch.object(
                FULL.subset, "validate_grib", side_effect=ValueError("bad")
            ), mock.patch.object(FULL, "run_aria2") as aria2:
                with self.assertRaisesRegex(ValueError, "no aria2 resume marker"):
                    FULL.validate_or_download("url", output, [(1, 0, "x")], None, 8)
            aria2.assert_not_called()


if __name__ == "__main__":
    unittest.main()
