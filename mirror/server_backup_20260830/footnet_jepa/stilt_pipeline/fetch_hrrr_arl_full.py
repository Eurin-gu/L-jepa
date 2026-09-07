#!/usr/bin/env python3
"""Download full HRRR wrfprs objects, then extract validated ARL inputs locally."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess

if __package__:
    from . import fetch_hrrr_arl_subset as subset
else:
    import fetch_hrrr_arl_subset as subset


def full_name(_date: str, hour: int, forecast_hour: int) -> str:
    return f"hrrr.t{hour:02d}z.wrfprsf{forecast_hour:02d}.grib2"


def run_aria2(
    url: str,
    output_path: str,
    proxy: str | None,
    connections: int,
) -> None:
    aria2 = shutil.which("aria2c")
    if not aria2:
        raise RuntimeError("aria2c is not installed")
    command = [
        aria2,
        "--continue=true",
        f"--max-connection-per-server={connections}",
        f"--split={connections}",
        "--min-split-size=1M",
        "--file-allocation=none",
        "--auto-file-renaming=false",
        "--allow-overwrite=false",
        "--max-tries=10",
        "--retry-wait=5",
        "--console-log-level=warn",
        "--summary-interval=30",
        f"--dir={os.path.dirname(output_path)}",
        f"--out={os.path.basename(output_path)}",
    ]
    if proxy:
        command.append(f"--all-proxy={proxy}")
    command.append(url)
    subprocess.run(command, check=True)
    control_path = output_path + ".aria2"
    if os.path.exists(control_path):
        raise RuntimeError(f"aria2 left an incomplete-download marker: {control_path}")


def validate_or_download(
    url: str,
    output_path: str,
    entries: list[tuple[int, int, str]],
    proxy: str | None,
    connections: int,
) -> None:
    if os.path.isfile(output_path) and not os.path.exists(output_path + ".aria2"):
        try:
            subset.validate_grib(output_path, len(entries))
            print(f"[hrrr-full] reuse validated {output_path}", flush=True)
            return
        except ValueError as exc:
            raise ValueError(
                f"existing file failed validation and has no aria2 resume marker: "
                f"{output_path}"
            ) from exc

    print(f"[hrrr-full] download {url}", flush=True)
    run_aria2(url, output_path, proxy, connections)
    subset.validate_grib(output_path, len(entries))


def process_hour(
    date: str,
    hour: int,
    forecast_hour: int,
    levels: frozenset[int],
    output_dir: str,
    proxy: str | None,
    connections: int,
    timeout: int,
    retries: int,
    remove_full: bool,
) -> str:
    url = subset.object_url(date, hour, forecast_hour)
    entries = subset.parse_index(
        subset.read_url(url + ".idx", timeout, retries, proxy).decode("ascii")
    )
    source_path = os.path.join(output_dir, full_name(date, hour, forecast_hour))
    output_path = source_path.removesuffix(".grib2") + ".subset.grib2"
    validate_or_download(url, source_path, entries, proxy, connections)

    messages = subset.select_messages(
        entries, levels, total_size=os.path.getsize(source_path)
    )
    subset.extract_messages(source_path, output_path, messages)
    print(
        f"[hrrr-full] subset f{forecast_hour:02d}: {len(messages)} messages, "
        f"{os.path.getsize(output_path) / 1024**2:.1f} MiB",
        flush=True,
    )
    if remove_full:
        os.unlink(source_path)
        print(f"[hrrr-full] removed validated full object {source_path}", flush=True)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="cycle date, YYYYMMDD")
    parser.add_argument("--hour", required=True, type=int, help="cycle hour, 0-23")
    parser.add_argument("--forecast-hours", nargs="+", type=int, required=True)
    parser.add_argument("--levels", nargs="+", type=int, default=subset.DEFAULT_LEVELS)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--proxy")
    parser.add_argument("--connections", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--remove-full", action="store_true")
    args = parser.parse_args()

    if not args.date.isdigit() or len(args.date) != 8:
        parser.error("--date must be YYYYMMDD")
    if not 0 <= args.hour <= 23:
        parser.error("--hour must be 0-23")
    if any(not 0 <= item <= 48 for item in args.forecast_hours):
        parser.error("forecast hours must be 0-48")
    if args.connections < 1 or args.timeout < 1 or args.retries < 1:
        parser.error("connections, timeout, and retries must be positive")

    output_dir = os.path.abspath(args.out_dir)
    os.makedirs(output_dir, exist_ok=True)
    outputs = []
    try:
        for forecast_hour in args.forecast_hours:
            outputs.append(process_hour(
                args.date,
                args.hour,
                forecast_hour,
                frozenset(args.levels),
                output_dir,
                args.proxy,
                args.connections,
                args.timeout,
                args.retries,
                args.remove_full,
            ))
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
        raise SystemExit(f"[hrrr-full] FAILED: {exc}") from exc
    print(f"[hrrr-full] OK wrote {len(outputs)} subsets", flush=True)


if __name__ == "__main__":
    main()
