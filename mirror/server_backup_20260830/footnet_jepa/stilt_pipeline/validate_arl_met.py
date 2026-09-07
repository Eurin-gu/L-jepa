#!/usr/bin/env python3
"""Validate an ARL meteorology file and its packing configuration."""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import os
import re


@dataclasses.dataclass(frozen=True)
class Level:
    value: float
    variables: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class ArlConfig:
    nx: int
    ny: int
    levels: tuple[Level, ...]

    @property
    def record_length(self) -> int:
        return 50 + self.nx * self.ny

    @property
    def records_per_time(self) -> int:
        return 1 + sum(len(level.variables) for level in self.levels)

    @property
    def record_labels(self) -> tuple[str, ...]:
        return ("INDX",) + tuple(
            variable
            for level in self.levels
            for variable in level.variables
        )


def parse_config(path: str) -> ArlConfig:
    with open(path, encoding="ascii") as handle:
        text = handle.read()

    def integer(label: str) -> int:
        match = re.search(rf"^{re.escape(label)}:\s+(-?\d+)\s*$", text, re.MULTILINE)
        if not match:
            raise ValueError(f"missing {label!r} in {path}")
        return int(match.group(1))

    nx = integer("Numb X pt")
    ny = integer("Numb Y pt")
    expected_levels = integer("Numb Levels")
    levels = []
    pattern = re.compile(r"^Level\s+\d+:\s+(\S+)\s+(\d+)(.*)$", re.MULTILINE)
    for match in pattern.finditer(text):
        count = int(match.group(2))
        variables = tuple(match.group(3).split())
        if len(variables) != count:
            raise ValueError(
                f"level declares {count} variables but lists {len(variables)}"
            )
        levels.append(Level(float(match.group(1)), variables))
    if len(levels) != expected_levels:
        raise ValueError(
            f"configuration declares {expected_levels} levels but lists {len(levels)}"
        )
    if nx <= 0 or ny <= 0 or not levels:
        raise ValueError("ARL grid dimensions and level count must be positive")
    return ArlConfig(nx, ny, tuple(levels))


def read_header(handle, offset: int) -> tuple[int, int, int, int, int, str]:
    handle.seek(offset)
    raw = handle.read(50)
    if len(raw) != 50:
        raise ValueError(f"short ARL header at byte {offset}")
    try:
        fields = tuple(int(raw[start:start + 2]) for start in range(0, 10, 2))
        label = raw[14:18].decode("ascii")
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid ARL header at byte {offset}") from exc
    return (*fields, label)


def valid_time(timestamp: tuple[int, int, int, int, int]) -> datetime.datetime:
    """Return the valid time encoded directly in an ARL record label."""
    year, month, day, hour, forecast_hour = timestamp
    full_year = 2000 + year if year < 70 else 1900 + year
    if not 0 <= forecast_hour <= 99:
        raise ValueError(f"invalid ARL forecast hour: {forecast_hour}")
    try:
        return datetime.datetime(full_year, month, day, hour)
    except ValueError as exc:
        raise ValueError(f"invalid ARL timestamp: {timestamp}") from exc


def check_time_order(times: list[tuple[int, int, int, int, int]]) -> None:
    interval = None
    for index, (previous, current) in enumerate(zip(times, times[1:]), 1):
        delta = valid_time(current) - valid_time(previous)
        if delta <= datetime.timedelta(0):
            raise ValueError(
                "ARL times are not strictly increasing at time "
                f"{index}: {previous} then {current}"
            )
        if interval is None:
            interval = delta
        elif delta != interval:
            raise ValueError(
                "ARL time interval changes at time "
                f"{index}: expected {interval}, got {delta}"
            )


def validate(
    arl_path: str, config: ArlConfig, min_times: int = 1
) -> list[tuple[int, int, int, int, int]]:
    if min_times < 1:
        raise ValueError("minimum ARL time count must be positive")
    file_size = os.path.getsize(arl_path)
    bytes_per_time = config.record_length * config.records_per_time
    if file_size % bytes_per_time:
        raise ValueError(
            f"ARL size {file_size} is not divisible by {bytes_per_time} bytes/time"
        )
    time_count = file_size // bytes_per_time
    if time_count < min_times:
        raise ValueError(f"ARL contains {time_count} times; need at least {min_times}")

    times = []
    with open(arl_path, "rb") as handle:
        for index in range(time_count):
            time_offset = index * bytes_per_time
            header = read_header(handle, time_offset)
            year, month, day, hour, forecast_hour, label = header
            if label != "INDX":
                raise ValueError(f"time {index} starts with {label!r}, not 'INDX'")
            timestamp = (year, month, day, hour, forecast_hour)
            try:
                valid_time(timestamp)
            except ValueError as exc:
                raise ValueError(
                    f"invalid ARL timestamp at time {index}: {header[:5]}"
                ) from exc
            times.append(timestamp)
            for record_index, expected_label in enumerate(
                config.record_labels[1:], 1
            ):
                field_header = read_header(
                    handle, time_offset + record_index * config.record_length
                )
                if field_header[:5] != timestamp:
                    raise ValueError(
                        f"time {index} record {record_index} has timestamp "
                        f"{field_header[:5]}, expected {timestamp}"
                    )
                if field_header[5] != expected_label:
                    raise ValueError(
                        f"time {index} record {record_index} is "
                        f"{field_header[5]!r}, expected {expected_label!r}"
                    )
    check_time_order(times)
    return times


def check_stilt_fields(config: ArlConfig) -> None:
    required_surface = {"SHGT", "PRSS", "T02M", "U10M", "V10M", "PBLH"}
    missing_surface = required_surface.difference(config.levels[0].variables)
    if missing_surface:
        raise ValueError(f"surface level lacks STILT fields: {sorted(missing_surface)}")
    if len(config.levels) < 2:
        raise ValueError("ARL file is surface-only; STILT requires 3D levels")

    required_upper = {"HGTS", "TEMP", "UWND", "VWND"}
    for level in config.levels[1:]:
        variables = set(level.variables)
        missing = required_upper.difference(variables)
        if missing:
            raise ValueError(
                f"pressure level {level.value:g} lacks fields: {sorted(missing)}"
            )
        if not variables.intersection({"RELH", "SPHU"}):
            raise ValueError(
                f"pressure level {level.value:g} lacks RELH or SPHU"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arl", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--min-times", type=int, default=1)
    parser.add_argument("--allow-incomplete-fields", action="store_true")
    args = parser.parse_args()

    try:
        config = parse_config(args.config)
        times = validate(args.arl, config, args.min_times)
        if not args.allow_incomplete_fields:
            check_stilt_fields(config)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"[arl-check] FAILED: {exc}") from exc
    print(
        f"[arl-check] OK grid={config.nx}x{config.ny} "
        f"levels={len(config.levels)} times={len(times)} "
        f"first={times[0]} last={times[-1]}"
    )


if __name__ == "__main__":
    main()
