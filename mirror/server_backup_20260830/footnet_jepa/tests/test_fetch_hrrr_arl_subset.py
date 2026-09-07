import os
import tempfile
import unittest

from stilt_pipeline import fetch_hrrr_arl_subset as SUBSET


class HrrrSubsetTest(unittest.TestCase):
    def test_selects_requested_pressure_and_surface_messages(self):
        raw = "\n".join([
            "1:0:d=2024070518:HGT:1000 mb:anl:",
            "2:100:d=2024070518:TMP:1000 mb:anl:",
            "3:200:d=2024070518:UGRD:850 mb:anl:",
            "4:300:d=2024070518:PRES:surface:anl:",
            "5:400:d=2024070518:VGRD:10 m above ground:anl:",
            "6:500:d=2024070518:VIS:surface:anl:",
            "7:600:d=2024070518:END:surface:anl:",
        ])
        entries = SUBSET.parse_index(raw)
        selected = SUBSET.select_messages(entries, frozenset({1000}))
        self.assertEqual([item.number for item in selected], [1, 2, 4, 5])
        self.assertEqual((selected[0].start, selected[0].end), (0, 99))

    def test_merges_only_consecutive_messages(self):
        messages = [
            SUBSET.Message(1, 0, 99, "a"),
            SUBSET.Message(2, 100, 199, "b"),
            SUBSET.Message(4, 300, 399, "d"),
        ]
        ranges = SUBSET.merge_adjacent(messages)
        self.assertEqual(len(ranges), 2)
        self.assertEqual((ranges[0].start, ranges[0].end), (0, 199))
        self.assertEqual((ranges[1].start, ranges[1].end), (300, 399))

    def test_validates_message_count_and_truncation(self):
        def message(payload_size):
            length = 16 + payload_size
            return b"GRIB\x00\x00\x00\x02" + length.to_bytes(8, "big") + b"x" * payload_size

        with tempfile.TemporaryDirectory() as temporary:
            valid = os.path.join(temporary, "valid.grib2")
            with open(valid, "wb") as output:
                output.write(message(4) + message(8))
            SUBSET.validate_grib(valid, 2)
            with self.assertRaisesRegex(ValueError, "expected 1"):
                SUBSET.validate_grib(valid, 1)

            truncated = os.path.join(temporary, "truncated.grib2")
            with open(truncated, "wb") as output:
                output.write(message(8)[:-1])
            with self.assertRaisesRegex(ValueError, "truncated"):
                SUBSET.validate_grib(truncated, 1)

    def test_selects_and_extracts_last_message_from_full_object(self):
        def message(payload):
            length = 16 + len(payload)
            return b"GRIB\x00\x00\x00\x02" + length.to_bytes(8, "big") + payload

        first = message(b"first")
        second = message(b"second")
        entries = [
            (1, 0, "d=2024070518:VIS:surface:anl:"),
            (2, len(first), "d=2024070518:PRES:surface:anl:"),
        ]
        selected = SUBSET.select_messages(
            entries, frozenset({1000}), total_size=len(first) + len(second)
        )
        self.assertEqual([item.number for item in selected], [2])

        with tempfile.TemporaryDirectory() as temporary:
            source = os.path.join(temporary, "full.grib2")
            output = os.path.join(temporary, "subset.grib2")
            with open(source, "wb") as handle:
                handle.write(first + second)
            SUBSET.extract_messages(source, output, selected)
            with open(output, "rb") as handle:
                self.assertEqual(handle.read(), second)


if __name__ == "__main__":
    unittest.main()
