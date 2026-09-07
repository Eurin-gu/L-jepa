import os
import tempfile
import unittest

from stilt_pipeline import validate_arl_met as VALIDATE


CONFIG = """\
Numb X pt:             2
Numb Y pt:             3
Numb Levels:           2
Level  0:           .00000  6 SHGT PRSS T02M U10M V10M PBLH
Level  1:           1000.0  5 HGTS TEMP UWND VWND RELH
"""


def header(year=24, month=7, day=5, hour=18, minute=0, label="INDX"):
    prefix = f"{year:02d}{month:2d}{day:2d}{hour:2d}{minute:2d}{0:2d}AA{label}"
    return prefix.encode("ascii").ljust(50, b" ")


def write_time_block(output, config, **timestamp):
    for label in config.record_labels:
        output.write(header(label=label, **timestamp).ljust(config.record_length, b" "))


class ValidateArlTest(unittest.TestCase):
    def test_config_and_binary_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_path = os.path.join(temporary, "arldata.cfg")
            arl_path = os.path.join(temporary, "DATA.ARL")
            with open(config_path, "w", encoding="ascii") as output:
                output.write(CONFIG)
            config = VALIDATE.parse_config(config_path)
            self.assertEqual(config.records_per_time, 12)
            VALIDATE.check_stilt_fields(config)

            with open(arl_path, "wb") as output:
                write_time_block(output, config)
            self.assertEqual(
                VALIDATE.validate(arl_path, config), [(24, 7, 5, 18, 0)]
            )

    def test_rejects_surface_only_and_bad_date(self):
        config = VALIDATE.ArlConfig(
            2, 3, (VALIDATE.Level(0, ("SHGT", "PRSS", "T02M", "U10M", "V10M", "PBLH")),)
        )
        with self.assertRaisesRegex(ValueError, "surface-only"):
            VALIDATE.check_stilt_fields(config)

        with tempfile.TemporaryDirectory() as temporary:
            arl_path = os.path.join(temporary, "bad.ARL")
            with open(arl_path, "wb") as output:
                write_time_block(output, config, month=0)
            with self.assertRaisesRegex(ValueError, "invalid ARL timestamp"):
                VALIDATE.validate(arl_path, config)

    def test_rejects_duplicate_or_out_of_order_times(self):
        config = VALIDATE.ArlConfig(
            2, 3, (VALIDATE.Level(0, ("SHGT", "PRSS", "T02M", "U10M", "V10M", "PBLH")),)
        )
        with tempfile.TemporaryDirectory() as temporary:
            arl_path = os.path.join(temporary, "unordered.ARL")
            with open(arl_path, "wb") as output:
                write_time_block(output, config, hour=18)
                write_time_block(output, config, hour=17)
            with self.assertRaisesRegex(ValueError, "not strictly increasing"):
                VALIDATE.validate(arl_path, config)

    def test_forecast_hour_contributes_to_valid_time(self):
        first = (24, 7, 5, 18, 1)
        second = (24, 7, 5, 19, 0)
        with self.assertRaisesRegex(ValueError, "not strictly increasing"):
            VALIDATE.check_time_order([first, second])

    def test_rejects_wrong_record_label(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_path = os.path.join(temporary, "arldata.cfg")
            arl_path = os.path.join(temporary, "wrong-label.ARL")
            with open(config_path, "w", encoding="ascii") as output:
                output.write(CONFIG)
            config = VALIDATE.parse_config(config_path)
            with open(arl_path, "wb") as output:
                write_time_block(output, config)
            with open(arl_path, "r+b") as output:
                output.seek(config.record_length)
                output.write(header(label="NOPE"))
            with self.assertRaisesRegex(ValueError, "expected 'SHGT'"):
                VALIDATE.validate(arl_path, config)


if __name__ == "__main__":
    unittest.main()
