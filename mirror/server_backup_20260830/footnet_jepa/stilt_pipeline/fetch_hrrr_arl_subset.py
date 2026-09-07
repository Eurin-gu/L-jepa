#!/usr/bin/env python3
"""Download the HRRR fields needed by the GRIB2-to-ARL converter.

NOAA publishes a byte-offset index beside each HRRR GRIB2 object. This tool
uses HTTP range requests to fetch complete GRIB messages for selected pressure
levels and surface fields, then concatenates them in their original order.
The result remains a valid GRIB2 file but is much smaller than full wrfprs.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import dataclasses
import json
import os
import re
import tempfile
import time
import urllib.request


BASE_URL = "https://noaa-hrrr-bdp-pds.s3.amazonaws.com"
DEFAULT_LEVELS = (
    1000, 975, 950, 925, 900, 850, 800, 750, 700, 650, 600, 550,
    500, 450, 400, 350, 300, 250, 200, 150, 100, 75, 50,
)
PRESSURE_FIELDS = frozenset(
    {"HGT", "TMP", "RH", "DPT", "SPFH", "VVEL", "UGRD", "VGRD"}
)
SURFACE_SPECS = frozenset({
    "MSLMA:mean sea level",
    "PRES:surface",
    "HGT:surface",
    "TMP:2 m above ground",
    "SPFH:2 m above ground",
    "DPT:2 m above ground",
    "RH:2 m above ground",
    "UGRD:10 m above ground",
    "VGRD:10 m above ground",
    "APCP:surface",
    "SHTFL:surface",
    "LHTFL:surface",
    "TCDC:entire atmosphere",
    "DSWRF:surface",
    "ULWRF:surface",
    "HPBL:surface",
})


@dataclasses.dataclass(frozen=True)
class Message:
    number: int
    start: int
    end: int
    description: str


@dataclasses.dataclass(frozen=True)
class ByteRange:
    first_message: int
    last_message: int
    start: int
    end: int


def object_url(
    date: str,
    hour: int,
    forecast_hour: int,
    base_url: str = BASE_URL,
) -> str:
    return (
        f"{base_url.rstrip('/')}/hrrr.{date}/conus/"
        f"hrrr.t{hour:02d}z.wrfprsf{forecast_hour:02d}.grib2"
    )


def read_url(
    url: str, timeout: int, retries: int, proxy: str | None = None
) -> bytes:
    opener = None
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    for attempt in range(retries):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "footnet-hrrr/1"}
            )
            open_request = opener.open if opener else urllib.request.urlopen
            with open_request(request, timeout=timeout) as response:
                return response.read()
        except OSError:
            if attempt + 1 == retries:
                raise
            time.sleep(min(2**attempt, 15))
    raise AssertionError("unreachable")


def parse_index(raw_index: str) -> list[tuple[int, int, str]]:
    entries = []
    for line in raw_index.splitlines():
        match = re.match(r"^(\d+):(\d+):(.*)$", line)
        if match:
            entries.append((int(match.group(1)), int(match.group(2)), match.group(3)))
    if len(entries) < 2:
        raise ValueError("HRRR index contains fewer than two messages")
    return entries


def select_messages(
    entries: list[tuple[int, int, str]],
    levels: frozenset[int],
    total_size: int | None = None,
) -> list[Message]:
    selected = []
    pressure_pattern = re.compile(r":([A-Z0-9]+):(\d+) mb:")
    for index, (number, start, description) in enumerate(entries):
        if index + 1 < len(entries):
            end = entries[index + 1][1] - 1
        elif total_size is not None:
            end = total_size - 1
        else:
            break
        pressure = pressure_pattern.search(f":{description}")
        keep = False
        if pressure:
            field, level = pressure.group(1), int(pressure.group(2))
            keep = field in PRESSURE_FIELDS and level in levels
        if not keep:
            keep = any(f":{spec}:" in f":{description}:" for spec in SURFACE_SPECS)
        if keep:
            selected.append(Message(number, start, end, description))
    if not selected:
        raise ValueError("no required fields matched the HRRR index")
    return selected


def merge_adjacent(messages: list[Message]) -> list[ByteRange]:
    ranges = []
    for message in messages:
        if ranges and message.number == ranges[-1].last_message + 1:
            previous = ranges[-1]
            ranges[-1] = ByteRange(
                previous.first_message, message.number, previous.start, message.end
            )
        else:
            ranges.append(ByteRange(
                message.number, message.number, message.start, message.end
            ))
    return ranges


def download_range(
    url: str,
    byte_range: ByteRange,
    destination: str,
    timeout: int,
    retries: int,
    proxy: str | None = None,
) -> str:
    expected = byte_range.end - byte_range.start + 1
    expected_messages = byte_range.last_message - byte_range.first_message + 1
    if os.path.isfile(destination) and os.path.getsize(destination) == expected:
        try:
            validate_grib(destination, expected_messages)
            return destination
        except ValueError:
            pass
    opener = None
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    for attempt in range(retries):
        temporary = destination + ".part"
        try:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            request = urllib.request.Request(
                url,
                headers={
                    "Range": f"bytes={byte_range.start}-{byte_range.end}",
                    "User-Agent": "footnet-hrrr/1",
                },
            )
            open_request = opener.open if opener else urllib.request.urlopen
            with open_request(request, timeout=timeout) as response:
                if response.status != 206:
                    raise RuntimeError(
                        f"server ignored byte range {byte_range.start}-{byte_range.end}: "
                        f"HTTP {response.status}"
                    )
                with open(temporary, "wb") as output:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        output.write(block)
                    output.flush()
                    os.fsync(output.fileno())
            actual = os.path.getsize(temporary)
            if actual != expected:
                raise IOError(
                    f"short range download for messages {byte_range.first_message}-"
                    f"{byte_range.last_message}: expected {expected}, got {actual}"
                )
            validate_grib(temporary, expected_messages)
            os.replace(temporary, destination)
            return destination
        except (OSError, RuntimeError, ValueError):
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            if attempt + 1 == retries:
                raise
            time.sleep(min(2**attempt, 15))
    raise AssertionError("unreachable")


def validate_grib(path: str, expected_messages: int | None = None) -> int:
    count = 0
    file_size = os.path.getsize(path)
    with open(path, "rb") as handle:
        while True:
            header = handle.read(16)
            if not header:
                break
            if len(header) != 16 or header[:4] != b"GRIB" or header[7] != 2:
                raise ValueError(f"invalid GRIB2 header at message {count + 1}")
            length = int.from_bytes(header[8:16], "big")
            if length < 20:
                raise ValueError(f"invalid GRIB2 length {length} at message {count + 1}")
            handle.seek(length - 16, os.SEEK_CUR)
            if handle.tell() > file_size:
                raise ValueError(f"truncated GRIB2 message {count + 1}")
            count += 1
        if handle.tell() != file_size:
            raise ValueError("GRIB2 parser did not finish at end of file")
    if expected_messages is not None and count != expected_messages:
        raise ValueError(f"expected {expected_messages} GRIB messages, found {count}")
    return count


def extract_messages(
    source_path: str, output_path: str, messages: list[Message]
) -> None:
    """Copy selected complete GRIB messages from a local full object."""
    source_size = os.path.getsize(source_path)
    output_path = os.path.abspath(output_path)
    if os.path.realpath(source_path) == os.path.realpath(output_path):
        raise ValueError("source GRIB and subset output must be different files")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    temporary_output = output_path + ".tmp"
    try:
        with open(source_path, "rb") as source, open(temporary_output, "wb") as output:
            for message in messages:
                if not (0 <= message.start <= message.end < source_size):
                    raise ValueError(
                        f"message {message.number} range lies outside the source GRIB"
                    )
                source.seek(message.start)
                remaining = message.end - message.start + 1
                while remaining:
                    block = source.read(min(1024 * 1024, remaining))
                    if not block:
                        raise ValueError(f"short source GRIB at message {message.number}")
                    output.write(block)
                    remaining -= len(block)
            output.flush()
            os.fsync(output.fileno())
        validate_grib(temporary_output, len(messages))
        os.replace(temporary_output, output_path)
    finally:
        try:
            os.unlink(temporary_output)
        except FileNotFoundError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="cycle date, YYYYMMDD")
    parser.add_argument("--hour", required=True, type=int, help="cycle hour, 0-23")
    parser.add_argument("--forecast-hour", type=int, default=0)
    parser.add_argument("--levels", nargs="+", type=int, default=DEFAULT_LEVELS)
    parser.add_argument("--out", required=True)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--proxy", help="HTTP(S) proxy URL")
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help="HRRR object-store base URL",
    )
    parser.add_argument(
        "--cache-dir",
        help="persistent directory for verified range chunks (enables resume)",
    )
    args = parser.parse_args()

    if not re.fullmatch(r"\d{8}", args.date):
        parser.error("--date must be YYYYMMDD")
    if not 0 <= args.hour <= 23 or not 0 <= args.forecast_hour <= 48:
        parser.error("hour must be 0-23 and forecast hour must be 0-48")
    if args.jobs < 1 or args.timeout < 1 or args.retries < 1:
        parser.error("jobs, timeout, and retries must be positive")

    url = object_url(args.date, args.hour, args.forecast_hour, args.base_url)
    print(f"[hrrr-subset] index {url}.idx", flush=True)
    entries = parse_index(
        read_url(
            url + ".idx", args.timeout, args.retries, args.proxy
        ).decode("ascii")
    )
    messages = select_messages(entries, frozenset(args.levels))
    ranges = merge_adjacent(messages)
    print(
        f"[hrrr-subset] selected {len(messages)} messages in {len(ranges)} ranges",
        flush=True,
    )

    output_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if args.cache_dir:
        cache_path = os.path.abspath(args.cache_dir)
        os.makedirs(cache_path, exist_ok=True)
        cache_context = contextlib.nullcontext(cache_path)
    else:
        cache_context = tempfile.TemporaryDirectory(
            prefix="hrrr_ranges_", dir=os.path.dirname(output_path)
        )
    with cache_context as temporary:
        request_path = os.path.join(temporary, "request.json")
        request = {
            "url": url,
            "levels": sorted(args.levels),
            "ranges": [dataclasses.asdict(item) for item in ranges],
        }
        if os.path.exists(request_path):
            with open(request_path, encoding="utf-8") as handle:
                cached_request = json.load(handle)
            if cached_request != request:
                raise ValueError(
                    f"cache request differs from current HRRR request: {temporary}"
                )
        else:
            request_tmp = request_path + ".tmp"
            with open(request_tmp, "w", encoding="utf-8") as handle:
                json.dump(request, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(request_tmp, request_path)
        chunk_paths = [
            os.path.join(temporary, f"{i:04d}.grib2")
            for i in range(len(ranges))
        ]
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [
                pool.submit(
                    download_range,
                    url,
                    item,
                    path,
                    args.timeout,
                    args.retries,
                    args.proxy,
                )
                for item, path in zip(ranges, chunk_paths)
            ]
            for index, future in enumerate(futures, 1):
                future.result()
                print(f"[hrrr-subset] range {index}/{len(futures)} complete", flush=True)

        temporary_output = output_path + ".tmp"
        with open(temporary_output, "wb") as output:
            for path in chunk_paths:
                with open(path, "rb") as chunk:
                    while True:
                        block = chunk.read(1024 * 1024)
                        if not block:
                            break
                        output.write(block)
        validate_grib(temporary_output, len(messages))
        os.replace(temporary_output, output_path)

    size_mb = os.path.getsize(output_path) / 1024**2
    print(f"[hrrr-subset] wrote {output_path} ({size_mb:.1f} MiB)")


if __name__ == "__main__":
    main()
