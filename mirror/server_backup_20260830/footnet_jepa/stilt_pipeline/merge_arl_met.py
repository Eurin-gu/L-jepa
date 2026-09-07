#!/usr/bin/env python3
"""Validate and merge chronological ARL meteorology archives."""
from __future__ import annotations

import argparse
import os
import shutil
import tempfile

if __package__:
    from . import validate_arl_met as arl
else:
    import validate_arl_met as arl


def config_signature(path: str) -> tuple[str, ...]:
    """Return a whitespace-insensitive signature of the complete ARL config."""
    with open(path, encoding="ascii") as handle:
        return tuple(" ".join(line.split()) for line in handle if line.strip())


def inspect_inputs(
    inputs: list[tuple[str, str]],
) -> tuple[arl.ArlConfig, list[tuple[int, int, int, int, int]]]:
    if not inputs:
        raise ValueError("at least one --input ARL CONFIG pair is required")

    baseline_config = arl.parse_config(inputs[0][1])
    baseline_signature = config_signature(inputs[0][1])
    arl.check_stilt_fields(baseline_config)
    all_times = []

    for index, (arl_path, config_path) in enumerate(inputs):
        config = arl.parse_config(config_path)
        if config != baseline_config or config_signature(config_path) != baseline_signature:
            raise ValueError(
                f"input {index + 1} configuration differs from {inputs[0][1]}: "
                f"{config_path}"
            )
        times = arl.validate(arl_path, config)
        all_times.extend(times)

    arl.check_time_order(all_times)
    return baseline_config, all_times


def _temporary_path(destination: str, prefix: str) -> str:
    directory = os.path.dirname(destination) or "."
    os.makedirs(directory, exist_ok=True)
    descriptor, path = tempfile.mkstemp(prefix=prefix, dir=directory)
    os.close(descriptor)
    return path


def merge(
    inputs: list[tuple[str, str]],
    output_path: str,
    output_config_path: str,
    overwrite: bool = False,
) -> list[tuple[int, int, int, int, int]]:
    output_path = os.path.abspath(output_path)
    output_config_path = os.path.abspath(output_config_path)
    if output_path == output_config_path:
        raise ValueError("ARL output and config output must be different files")

    input_paths = {
        os.path.realpath(path)
        for input_pair in inputs
        for path in input_pair
    }
    if any(
        os.path.realpath(path) in input_paths
        for path in (output_path, output_config_path)
    ):
        raise ValueError("outputs must not overwrite input archives or configurations")
    if not overwrite:
        for path in (output_path, output_config_path):
            if os.path.exists(path):
                raise FileExistsError(f"output already exists: {path}")

    config, times = inspect_inputs(inputs)
    data_temporary = _temporary_path(output_path, ".arl_merge_")
    config_temporary = _temporary_path(output_config_path, ".arl_config_")
    try:
        with open(data_temporary, "wb") as output:
            for input_path, _ in inputs:
                with open(input_path, "rb") as source:
                    shutil.copyfileobj(source, output, length=16 * 1024 * 1024)
            output.flush()
            os.fsync(output.fileno())

        merged_times = arl.validate(data_temporary, config, min_times=len(times))
        if merged_times != times:
            raise ValueError("merged ARL timestamps differ from validated inputs")

        with open(inputs[0][1], "rb") as source, open(config_temporary, "wb") as output:
            shutil.copyfileobj(source, output)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(data_temporary, 0o644)
        os.chmod(config_temporary, 0o644)

        os.replace(config_temporary, output_config_path)
        config_temporary = ""
        os.replace(data_temporary, output_path)
        data_temporary = ""
    finally:
        for temporary in (data_temporary, config_temporary):
            if temporary:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
    return times


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        action="append",
        nargs=2,
        required=True,
        metavar=("ARL", "CONFIG"),
        help="input archive and its arldata.cfg; repeat in chronological order",
    )
    parser.add_argument("--out", required=True, help="merged ARL archive")
    parser.add_argument("--out-config", required=True, help="merged archive config")
    parser.add_argument("--force", action="store_true", help="replace existing outputs")
    args = parser.parse_args()

    try:
        times = merge(args.input, args.out, args.out_config, args.force)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"[arl-merge] FAILED: {exc}") from exc
    size_mb = os.path.getsize(args.out) / 1024**2
    print(
        f"[arl-merge] OK times={len(times)} first={times[0]} last={times[-1]} "
        f"size={size_mb:.1f} MiB output={os.path.abspath(args.out)}"
    )


if __name__ == "__main__":
    main()
