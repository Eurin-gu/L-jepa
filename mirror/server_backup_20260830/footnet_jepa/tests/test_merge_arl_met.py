import os
import tempfile
import unittest

from stilt_pipeline import merge_arl_met as MERGE

from test_validate_arl_met import CONFIG, write_time_block


def write_archive(path, config, hours):
    with open(path, "wb") as output:
        for hour in hours:
            write_time_block(output, config, hour=hour)


class MergeArlTest(unittest.TestCase):
    def test_merges_compatible_archives_atomically(self):
        with tempfile.TemporaryDirectory() as temporary:
            first_config = os.path.join(temporary, "first.cfg")
            second_config = os.path.join(temporary, "second.cfg")
            first_arl = os.path.join(temporary, "first.arl")
            second_arl = os.path.join(temporary, "second.arl")
            output_arl = os.path.join(temporary, "merged", "data.arl")
            output_config = os.path.join(temporary, "merged", "arldata.cfg")
            with open(first_config, "w", encoding="ascii") as output:
                output.write(CONFIG)
            with open(second_config, "w", encoding="ascii") as output:
                output.write(CONFIG.replace("Numb X pt:             2", "Numb X pt: 2"))
            config = MERGE.arl.parse_config(first_config)
            write_archive(first_arl, config, [17])
            write_archive(second_arl, config, [18, 19])

            times = MERGE.merge(
                [(first_arl, first_config), (second_arl, second_config)],
                output_arl,
                output_config,
            )

            self.assertEqual([item[3] for item in times], [17, 18, 19])
            self.assertEqual(
                os.path.getsize(output_arl),
                os.path.getsize(first_arl) + os.path.getsize(second_arl),
            )
            self.assertEqual(MERGE.arl.validate(output_arl, config, 3), times)
            self.assertTrue(os.path.exists(output_config))

    def test_rejects_different_configs_and_nonchronological_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_path = os.path.join(temporary, "arldata.cfg")
            changed_config_path = os.path.join(temporary, "changed.cfg")
            first_arl = os.path.join(temporary, "first.arl")
            second_arl = os.path.join(temporary, "second.arl")
            with open(config_path, "w", encoding="ascii") as output:
                output.write(CONFIG)
            with open(changed_config_path, "w", encoding="ascii") as output:
                output.write(CONFIG.replace("Level  1:", "Level  2:"))
            config = MERGE.arl.parse_config(config_path)
            write_archive(first_arl, config, [18])
            write_archive(second_arl, config, [17])

            with self.assertRaisesRegex(ValueError, "configuration differs"):
                MERGE.inspect_inputs(
                    [(first_arl, config_path), (second_arl, changed_config_path)]
                )
            with self.assertRaisesRegex(ValueError, "not strictly increasing"):
                MERGE.inspect_inputs(
                    [(first_arl, config_path), (second_arl, config_path)]
                )


if __name__ == "__main__":
    unittest.main()
