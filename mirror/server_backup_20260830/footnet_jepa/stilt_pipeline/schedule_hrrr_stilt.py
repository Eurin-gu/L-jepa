#!/usr/bin/env python3
"""Build continuous hourly HRRR ARL inputs and produce STILT labels by day.

The scheduler groups receptors by UTC date.  For each date it computes the
smallest hourly meteorology window covering every backward trajectory, selects
one extended HRRR cycle, downloads every consecutive forecast hour, converts
and merges the ARL records, runs STILT, validates the outputs, and applies a
post-success retention policy.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import dataclasses
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterable

if __package__:
    from . import fetch_hrrr_arl_subset as grib
    from . import merge_arl_met as merger
    from . import validate_arl_met as arl
else:
    import fetch_hrrr_arl_subset as grib
    import merge_arl_met as merger
    import validate_arl_met as arl


UTC = dt.timezone.utc
RECEPTOR_FIELDS = ("run_time", "lati", "long", "zagl")
EXTENDED_CYCLE_HOURS = (0, 6, 12, 18)
MODEL_BACKHOURS = (0, 6, 12, 18)


def parse_time(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"receptor time lacks a timezone: {value!r}")
    return parsed.astimezone(UTC)


def floor_hour(value: dt.datetime) -> dt.datetime:
    return value.replace(minute=0, second=0, microsecond=0)


def ceil_hour(value: dt.datetime) -> dt.datetime:
    floored = floor_hour(value)
    return floored if value == floored else floored + dt.timedelta(hours=1)


def choose_cycle(start: dt.datetime, end: dt.datetime) -> dt.datetime:
    cycle_hour = max(hour for hour in EXTENDED_CYCLE_HOURS if hour <= start.hour)
    cycle = start.replace(hour=cycle_hour, minute=0, second=0, microsecond=0)
    horizon = (end - cycle).total_seconds() / 3600
    if horizon > 48:
        raise ValueError(
            f"UTC-day receptor window needs forecast hour {horizon:g}; "
            "HRRR extended cycles stop at f48"
        )
    return cycle


@dataclasses.dataclass(frozen=True)
class HourSource:
    label: str
    cycle: dt.datetime
    forecast_hour: int
    valid_time: dt.datetime

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "cycle_utc": self.cycle.isoformat().replace("+00:00", "Z"),
            "forecast_hour": self.forecast_hour,
            "valid_time_utc": self.valid_time.isoformat().replace("+00:00", "Z"),
        }


@dataclasses.dataclass(frozen=True)
class DayPlan:
    date: str
    rows: tuple[dict[str, str], ...]
    required_start: dt.datetime
    required_end: dt.datetime
    cycle: dt.datetime
    forecast_hours: tuple[int, ...]

    def as_dict(self) -> dict[str, object]:
        receptor_json = json.dumps(
            self.rows, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return {
            "date": self.date,
            "receptors": len(self.rows),
            "required_start": self.required_start.isoformat(),
            "required_end": self.required_end.isoformat(),
            "cycle": self.cycle.isoformat(),
            "forecast_hours": list(self.forecast_hours),
            "hour_count": len(self.forecast_hours),
            "receptor_sha256": hashlib.sha256(receptor_json).hexdigest(),
        }


def plan_day(date: str, rows: Iterable[dict[str, str]], hours: int) -> DayPlan:
    rows = tuple(sorted(rows, key=lambda row: parse_time(row["run_time"])))
    if not rows:
        raise ValueError(f"no receptors for {date}")
    times = [parse_time(row["run_time"]) for row in rows]
    start = floor_hour(min(times) - dt.timedelta(hours=hours))
    end = ceil_hour(max(times))
    cycle = choose_cycle(start, end)
    first = int((start - cycle).total_seconds() // 3600)
    last = int((end - cycle).total_seconds() // 3600)
    if first < 0 or last > 48:
        raise ValueError(f"invalid HRRR forecast-hour window f{first:02d}..f{last:02d}")
    return DayPlan(date, rows, start, end, cycle, tuple(range(first, last + 1)))


def hour_sources(plan: DayPlan, strategy: str) -> tuple[HourSource, ...]:
    if strategy == "single-cycle":
        return tuple(
            HourSource(
                label=f"f{forecast_hour:02d}",
                cycle=plan.cycle,
                forecast_hour=forecast_hour,
                valid_time=plan.cycle + dt.timedelta(hours=forecast_hour),
            )
            for forecast_hour in plan.forecast_hours
        )
    if strategy == "hourly-analysis":
        count = int(
            (plan.required_end - plan.required_start).total_seconds() // 3600
        ) + 1
        return tuple(
            HourSource(
                label=f"a{valid:%Y%m%d%H}_f00",
                cycle=valid,
                forecast_hour=0,
                valid_time=valid,
            )
            for valid in (
                plan.required_start + dt.timedelta(hours=index)
                for index in range(count)
            )
        )
    raise ValueError(f"unknown HRRR meteorology strategy: {strategy}")


def load_plans(paths: list[str], hours: int, dates: set[str] | None) -> list[DayPlan]:
    groups: dict[str, list[dict[str, str]]] = {}
    seen = set()
    for path in paths:
        with open(path, newline="") as handle:
            reader = csv.DictReader(handle)
            missing = set(RECEPTOR_FIELDS).difference(reader.fieldnames or ())
            if missing:
                raise ValueError(f"{path} lacks receptor columns: {sorted(missing)}")
            for line, row in enumerate(reader, 2):
                try:
                    timestamp = parse_time(row["run_time"])
                    float(row["lati"])
                    float(row["long"])
                    float(row["zagl"])
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"invalid receptor at {path}:{line}: {exc}") from exc
                date = timestamp.strftime("%Y%m%d")
                if dates and date not in dates:
                    continue
                normalized = {
                    "run_time": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "lati": row["lati"],
                    "long": row["long"],
                    "zagl": row["zagl"],
                }
                identity = tuple(normalized[field] for field in RECEPTOR_FIELDS)
                if identity in seen:
                    continue
                seen.add(identity)
                groups.setdefault(date, []).append(normalized)
    if dates:
        missing_dates = dates.difference(groups)
        if missing_dates:
            raise ValueError(f"requested dates have no receptors: {sorted(missing_dates)}")
    if not groups:
        raise ValueError("no receptors selected")
    return [plan_day(date, groups[date], hours) for date in sorted(groups)]


def atomic_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_receptors(path: Path, rows: tuple[dict[str, str], ...]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(temporary, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECEPTOR_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def run_logged(command: list[str], cwd: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    displayed = list(command)
    if "--proxy" in displayed:
        proxy_index = displayed.index("--proxy") + 1
        if proxy_index < len(displayed):
            displayed[proxy_index] = "<redacted>"
    with open(log_path, "w") as log:
        log.write("command: " + " ".join(displayed) + "\n")
        log.flush()
        result = subprocess.run(
            command,
            cwd=cwd,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    if result.returncode:
        raise RuntimeError(
            f"command exited {result.returncode}; see {log_path}"
        )


def timestamp_tuple(value: dt.datetime, forecast_hour: int) -> tuple[int, ...]:
    return (
        value.year % 100,
        value.month,
        value.day,
        value.hour,
        forecast_hour,
    )


def validate_single_arl(
    output: Path, config_path: Path, expected: tuple[int, ...]
) -> None:
    config = arl.parse_config(str(config_path))
    times = arl.validate(str(output), config)
    arl.check_stilt_fields(config)
    if times != [expected]:
        raise ValueError(f"ARL timestamp {times} differs from expected {[expected]}")


def hour_conversion_receipt(
    source: HourSource,
    subset: Path,
    output: Path,
    config: Path,
    args,
) -> dict[str, object]:
    def artifact(path: Path) -> dict[str, object]:
        return {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }

    return {
        "schema_version": 1,
        "hour_source": source.as_dict(),
        "source_grib": artifact(subset),
        "hourly_arl": artifact(output),
        "arl_config": artifact(config),
        "converter": artifact(Path(args.converter)),
        "decoder_config": artifact(Path(args.decoder_config)),
    }


def validate_hour_conversion_receipt(
    receipt: dict,
    source: HourSource,
    subset: Path,
    output: Path,
    config: Path,
    args,
) -> None:
    expected = hour_conversion_receipt(
        source, subset, output, config, args)
    if receipt != expected:
        raise ValueError(
            f"hourly ARL conversion receipt mismatch for {source.label}")


def converter_input_path(subset: Path, hour_dir: Path) -> str:
    """Return a short converter path safe for its fixed-width Fortran CLI."""
    return os.path.relpath(subset, start=hour_dir)


def ensure_hour(source: HourSource, work: Path, args) -> tuple[Path, Path, dict]:
    label = source.label
    subset = work / "subsets" / f"{label}.grib2"
    range_cache = work / "subsets" / ".ranges" / label
    hour_dir = work / "hourly_arl" / label
    output = hour_dir / "data.arl"
    config = hour_dir / "arldata.cfg"
    receipt_path = hour_dir / "conversion_receipt.json"
    expected = timestamp_tuple(source.valid_time, source.forecast_hour)

    if subset.exists():
        grib.validate_grib(str(subset))
    elif args.download_mode == "staged":
        raise FileNotFoundError(f"staged subset is missing: {subset}")
    else:
        command = [
            sys.executable,
            str(Path(__file__).with_name("fetch_hrrr_arl_subset.py")),
            "--date", source.cycle.strftime("%Y%m%d"),
            "--hour", str(source.cycle.hour),
            "--forecast-hour", str(source.forecast_hour),
            "--out", str(subset),
            "--jobs", str(args.range_jobs),
            "--timeout", str(args.download_timeout),
            "--retries", str(args.download_retries),
            "--base-url", args.hrrr_base_url,
            "--cache-dir", str(range_cache),
        ]
        if args.proxy:
            command.extend(["--proxy", args.proxy])
        run_logged(command, work, work / "logs" / f"download_{label}.log")
        grib.validate_grib(str(subset))
        if range_cache.is_dir():
            shutil.rmtree(range_cache)

    if output.exists() and config.exists() and receipt_path.exists():
        validate_single_arl(output, config, expected)
        with open(receipt_path, encoding="utf-8") as handle:
            receipt = json.load(handle)
        validate_hour_conversion_receipt(
            receipt, source, subset, output, config, args)
        return output, config, receipt
    if output.exists() or config.exists() or receipt_path.exists():
        raise RuntimeError(
            f"incomplete or unverifiable existing converter output for {label}")

    hour_dir.mkdir(parents=True, exist_ok=True)
    # hrrrv12arl_v2 stores its input argument in a fixed-width Fortran string.
    # Production roots can exceed that limit, so pass a short path relative to
    # the converter working directory instead of the absolute artifact path.
    converter_input = converter_input_path(subset, hour_dir)
    command = [
        args.converter,
        f"-d{args.decoder_config}",
        "-earldata.cfg",
        f"-i{converter_input}",
        "-odata.arl",
        "-gHRRR",
    ]
    run_logged(command, hour_dir, work / "logs" / f"convert_{label}.log")
    validate_single_arl(output, config, expected)
    receipt = hour_conversion_receipt(source, subset, output, config, args)
    atomic_json(receipt_path, receipt)
    return output, config, receipt


def expected_valid_times(plan: DayPlan) -> list[dt.datetime]:
    return [plan.cycle + dt.timedelta(hours=hour) for hour in plan.forecast_hours]


def source_valid_times(sources: tuple[HourSource, ...]) -> list[dt.datetime]:
    return [source.valid_time for source in sources]


def model_feature_forecast_hours(
    plan: DayPlan, backhours: tuple[int, ...] = MODEL_BACKHOURS
) -> tuple[int, ...]:
    """Forecast hours needed by the 4-snapshot FootNet input contract."""
    hours = set()
    available = set(plan.forecast_hours)
    for row in plan.rows:
        receptor_hour = floor_hour(parse_time(row["run_time"]))
        for backhour in backhours:
            valid = receptor_hour - dt.timedelta(hours=backhour)
            forecast_hour = int((valid - plan.cycle).total_seconds() // 3600)
            if forecast_hour not in available:
                raise ValueError(
                    f"model feature f{forecast_hour:02d} is outside the "
                    f"STILT meteorology window for {plan.date}")
            hours.add(forecast_hour)
    return tuple(sorted(hours))


def model_feature_sources(
    plan: DayPlan,
    sources: tuple[HourSource, ...],
    backhours: tuple[int, ...] = MODEL_BACKHOURS,
) -> tuple[HourSource, ...]:
    by_valid = {source.valid_time: source for source in sources}
    required = set()
    for row in plan.rows:
        receptor_hour = floor_hour(parse_time(row["run_time"]))
        for backhour in backhours:
            valid = receptor_hour - dt.timedelta(hours=backhour)
            if valid not in by_valid:
                raise ValueError(
                    f"model feature {valid.isoformat()} is outside the "
                    f"STILT meteorology window for {plan.date}"
                )
            required.add(valid)
    return tuple(by_valid[valid] for valid in sorted(required))


def validate_model_feature(
    metadata: dict, output: Path, source_grib: Path, source: HourSource
) -> None:
    if metadata.get("schema_version") != 1:
        raise ValueError(f"unsupported model feature schema for {output}")
    if metadata.get("cycle_utc") != source.cycle.isoformat().replace("+00:00", "Z"):
        raise ValueError(f"model feature cycle mismatch for {output}")
    if metadata.get("forecast_hour") != source.forecast_hour:
        raise ValueError(f"model feature forecast hour mismatch for {output}")
    if metadata.get("valid_time_utc") != source.valid_time.isoformat().replace("+00:00", "Z"):
        raise ValueError(f"model feature valid time mismatch for {output}")
    if not output.is_file() or metadata.get("sha256") != sha256_file(output):
        raise ValueError(f"model feature hash mismatch for {output}")
    if not source_grib.is_file():
        raise FileNotFoundError(f"model feature source GRIB is missing: {source_grib}")
    source_sha256 = sha256_file(source_grib)
    if metadata.get("source_grib_sha256") != source_sha256:
        raise ValueError(f"model feature source GRIB hash mismatch for {output}")
    recorded_source = metadata.get("source_grib_path")
    if recorded_source and Path(recorded_source).resolve() != source_grib.resolve():
        raise ValueError(f"model feature source GRIB path mismatch for {output}")


def ensure_model_feature(source: HourSource, work: Path) -> dict:
    label = source.label
    subset = work / "subsets" / f"{label}.grib2"
    output = work / "model_features" / f"{label}.npz"
    sidecar = output.with_suffix(output.suffix + ".json")
    if output.exists() and sidecar.exists():
        with open(sidecar, encoding="utf-8") as handle:
            metadata = json.load(handle)
        validate_model_feature(metadata, output, subset, source)
        return metadata
    if output.exists() or sidecar.exists():
        raise RuntimeError(f"incomplete existing model feature for {label}")
    if not subset.is_file():
        raise FileNotFoundError(f"source subset is missing for model feature: {subset}")
    command = [
        sys.executable,
        str(Path(__file__).with_name("extract_hrrr_features.py")),
        "--grib", str(subset),
        "--out", str(output),
        "--cycle", source.cycle.isoformat(),
        "--forecast-hour", str(source.forecast_hour),
    ]
    run_logged(command, work, work / "logs" / f"feature_{label}.log")
    with open(sidecar, encoding="utf-8") as handle:
        metadata = json.load(handle)
    validate_model_feature(metadata, output, subset, source)
    return metadata


def validate_merged(
    sources: tuple[HourSource, ...], output: Path, config_path: Path
) -> list[tuple[int, ...]]:
    config = arl.parse_config(str(config_path))
    arl.check_stilt_fields(config)
    times = arl.validate(str(output), config, min_times=len(sources))
    actual = [arl.valid_time(item) for item in times]
    expected = [item.replace(tzinfo=None) for item in source_valid_times(sources)]
    if actual != expected:
        raise ValueError(
            f"merged ARL coverage {actual[0]}..{actual[-1]} differs from "
            f"required {expected[0]}..{expected[-1]}"
        )
    return times


def check_space(path: Path, needed_bytes: int, reserve_gib: float, stage: str) -> None:
    free = shutil.disk_usage(path).free
    reserve = int(reserve_gib * 1024**3)
    if free < needed_bytes + reserve:
        raise RuntimeError(
            f"insufficient disk for {stage}: free={free / 1024**3:.1f} GiB, "
            f"need={needed_bytes / 1024**3:.1f} GiB plus "
            f"reserve={reserve_gib:.1f} GiB"
        )


def coverage_dates(plan: DayPlan) -> list[str]:
    dates = []
    current = plan.required_start.date()
    while current <= plan.required_end.date():
        dates.append(current.strftime("%Y%m%d"))
        current += dt.timedelta(days=1)
    return dates


def prepare_met_dir(plan: DayPlan, archive: Path, met_dir: Path) -> Path:
    met_dir.mkdir(parents=True, exist_ok=True)
    name = "hrrr." + ".".join(coverage_dates(plan)) + ".hourly.arl"
    link = met_dir / name
    entries = list(met_dir.iterdir())
    if entries and entries != [link]:
        raise RuntimeError(f"isolated met directory contains unexpected paths: {entries}")
    if link.is_symlink():
        if link.resolve() != archive.resolve():
            raise RuntimeError(f"unexpected meteorology symlink target: {link}")
    elif link.exists():
        raise RuntimeError(f"meteorology path is not a symlink: {link}")
    else:
        link.symlink_to(archive.resolve())
    return link


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def safe_remove_tree(path: Path, work: Path) -> None:
    resolved = path.resolve()
    if resolved.parent != work.resolve():
        raise RuntimeError(f"refusing to remove path outside batch directory: {path}")
    if path.exists():
        shutil.rmtree(path)


def apply_retention(retention: str, work: Path, archive: Path, met_link: Path) -> None:
    if retention == "all":
        return
    safe_remove_tree(work / "subsets", work)
    safe_remove_tree(work / "hourly_arl", work)
    if retention == "outputs-only":
        if archive.exists():
            archive.unlink()
        if met_link.is_symlink():
            met_link.unlink()
        try:
            met_link.parent.rmdir()
        except OSError:
            pass


def meteorology_tag(plan: DayPlan, args, archive_sha256: str) -> str:
    """Bind every resumable STILT simulation id to its meteorology bytes."""
    strategy = ("hrrr" if args.meteorology_strategy == "single-cycle"
                else "hrrr-analysis")
    return (
        f"{strategy}-{plan.date}-p{args.numpar}-h{args.hours}-"
        f"m{archive_sha256[:12]}"
    )


def expected_manifest_sim_ids(manifest: Path, tag: str) -> set[str]:
    with open(manifest, newline="") as handle:
        return {
            row["sim_id"]
            for row in csv.DictReader(handle)
            if row.get("sim_id", "").startswith(tag + "_")
        }


def validate_batch_report(validation: dict, expected_sim_ids: set[str]) -> None:
    """Require every planned simulation to pass the full output validation."""
    expected_count = len(expected_sim_ids)
    if validation.get("n_simulations") != expected_count:
        raise RuntimeError(
            f"validator found {validation.get('n_simulations')} simulations; "
            f"expected {expected_count}"
        )
    ok = set(validation.get("ok", []))
    failed = set(validation.get("failed", []))
    if failed or ok != expected_sim_ids:
        missing = sorted(expected_sim_ids.difference(ok))
        unexpected = sorted(ok.difference(expected_sim_ids))
        raise RuntimeError(
            "strict output validation failed: "
            f"passed={len(ok)}/{expected_count}, failed={len(failed)}, "
            f"missing={missing[:5]}, unexpected={unexpected[:5]}"
        )


def process_day(plan: DayPlan, args) -> dict[str, object]:
    work = Path(args.root).resolve() / plan.date
    work.mkdir(parents=True, exist_ok=True)
    sources = hour_sources(plan, args.meteorology_strategy)
    lock_path = work / ".lock"
    with open(lock_path, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"batch is already running for {plan.date}") from exc

        state_path = work / "state.json"
        request = {
            "plan": plan.as_dict(),
            "numpar": args.numpar,
            "hours": args.hours,
            "half_km": args.half_km,
            "res": args.res,
            "retention": args.retention,
            "validation_jobs": args.validation_jobs,
            "model_backhours": list(MODEL_BACKHOURS),
        }
        if args.meteorology_strategy != "single-cycle":
            request["meteorology_strategy"] = args.meteorology_strategy
        if state_path.exists():
            with open(state_path, encoding="utf-8") as handle:
                previous = json.load(handle)
            if previous.get("request") != request:
                raise RuntimeError(
                    f"existing batch state differs for {plan.date}; "
                    "use a different --root"
                )
            if previous.get("status") == "complete":
                print(f"[{plan.date}] already complete", flush=True)
                return previous

        state: dict[str, object] = {
            "status": "running",
            "plan": plan.as_dict(),
            "retention": args.retention,
            "request": request,
            "meteorology_strategy": args.meteorology_strategy,
        }
        atomic_json(state_path, state)
        receptor_csv = work / "receptors.csv"
        write_receptors(receptor_csv, plan.rows)

        estimated_peak = int(
            len(sources)
            * (args.subset_gib_per_hour + 2 * args.arl_gib_per_hour)
            * 1024**3
        )
        check_space(work, estimated_peak, args.min_free_gib, "hourly conversion and merge")

        hourly: dict[str, tuple[Path, Path, dict]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.hour_workers) as pool:
            futures = {
                pool.submit(ensure_hour, source, work, args): source
                for source in sources
            }
            for future in concurrent.futures.as_completed(futures):
                source = futures[future]
                hourly[source.label] = future.result()
                print(
                    f"[{plan.date}] {source.label} ready "
                    f"({len(hourly)}/{len(sources)})",
                    flush=True,
                )
                state["hourly_ready"] = len(hourly)
                state["ready_hour_sources"] = [
                    item.as_dict() for item in sources if item.label in hourly
                ]
                if args.meteorology_strategy == "single-cycle":
                    state["ready_forecast_hours"] = sorted(
                        item.forecast_hour for item in sources
                        if item.label in hourly
                    )
                atomic_json(state_path, state)

        state["hourly_ready"] = len(hourly)
        atomic_json(state_path, state)

        feature_sources = model_feature_sources(plan, sources)
        model_features = [
            ensure_model_feature(source, work) for source in feature_sources
        ]
        state["model_features"] = model_features
        atomic_json(state_path, state)
        source_records = []
        for source in sources:
            subset = work / "subsets" / f"{source.label}.grib2"
            hourly_arl, hourly_config, conversion_receipt = hourly[source.label]
            receipt_path = hourly_arl.parent / "conversion_receipt.json"
            source_records.append({
                **source.as_dict(),
                "path": str(subset),
                "bytes": conversion_receipt["source_grib"]["bytes"],
                "sha256": conversion_receipt["source_grib"]["sha256"],
                "source_url": grib.object_url(
                    source.cycle.strftime("%Y%m%d"),
                    source.cycle.hour,
                    source.forecast_hour,
                    args.hrrr_base_url,
                ),
                "path_availability_after_retention": (
                    "retained" if args.retention == "all"
                    else "deleted_after_validation"
                ),
                "arl_path": str(hourly_arl),
                "arl_bytes": conversion_receipt["hourly_arl"]["bytes"],
                "arl_sha256": conversion_receipt["hourly_arl"]["sha256"],
                "arl_config_path": str(hourly_config),
                "arl_config_sha256": conversion_receipt["arl_config"]["sha256"],
                "conversion_receipt_sha256": sha256_file(receipt_path),
                "arl_path_availability_after_retention": (
                    "retained" if args.retention == "all"
                    else "deleted_after_validation"
                ),
            })
        state["hour_sources"] = source_records
        atomic_json(state_path, state)
        merged_dir = work / "merged"
        archive = merged_dir / (
            f"hrrr.{plan.required_start:%Y%m%d%H}-"
            f"{plan.required_end:%Y%m%d%H}.hourly.arl"
        )
        merged_config = merged_dir / "arldata.cfg"
        merged_dir.mkdir(parents=True, exist_ok=True)
        inputs = [hourly[source.label][:2] for source in sources]
        if archive.exists() and merged_config.exists():
            validate_merged(sources, archive, merged_config)
        elif archive.exists() or merged_config.exists():
            raise RuntimeError("incomplete existing merged archive")
        else:
            merge_bytes = sum(path.stat().st_size for path, _ in inputs)
            check_space(work, merge_bytes, args.min_free_gib, "ARL merge")
            merger.merge(
                [(str(path), str(config)) for path, config in inputs],
                str(archive),
                str(merged_config),
            )
            validate_merged(sources, archive, merged_config)

        archive_fingerprint = {
            "path": str(archive),
            "bytes": archive.stat().st_size,
            "sha256": sha256_file(archive),
            "path_availability_after_retention": (
                "deleted_after_validation"
                if args.retention == "outputs-only" else "retained"
            ),
        }
        state["archive"] = archive_fingerprint
        alignment = (
            "same_cycle_forecast_realization"
            if args.meteorology_strategy == "single-cycle"
            else "same_grib_hourly_analysis_sequence"
        )
        meteorology_manifest = {
            "schema_version": 1,
            "alignment": alignment,
            "meteorology_strategy": args.meteorology_strategy,
            "model_backhours": list(MODEL_BACKHOURS),
            "source_subset_recipe": {
                "pressure_levels_hpa": list(grib.DEFAULT_LEVELS),
                "pressure_fields": sorted(grib.PRESSURE_FIELDS),
                "surface_specs": sorted(grib.SURFACE_SPECS),
                "downloader_sha256": sha256_file(
                    Path(__file__).with_name("fetch_hrrr_arl_subset.py")),
            },
            "conversion_recipe": {
                "converter_path": str(Path(args.converter).resolve()),
                "converter_sha256": sha256_file(Path(args.converter)),
                "decoder_config_path": str(Path(args.decoder_config).resolve()),
                "decoder_config_sha256": sha256_file(Path(args.decoder_config)),
            },
            "required_start_utc": plan.required_start.isoformat().replace(
                "+00:00", "Z"),
            "required_end_utc": plan.required_end.isoformat().replace(
                "+00:00", "Z"),
            "retention_policy": args.retention,
            "artifact_policy": {
                "model_input_features": "retained",
                "source_grib": (
                    "retained" if args.retention == "all"
                    else "deleted_after_validation"
                ),
                "hourly_arl": (
                    "retained" if args.retention == "all"
                    else "deleted_after_validation"
                ),
                "stilt_driver": (
                    "deleted_after_validation"
                    if args.retention == "outputs-only" else "retained"
                ),
            },
            "stilt_driver": archive_fingerprint,
            "hour_sources": source_records,
            "model_input_features": model_features,
        }
        if args.meteorology_strategy == "single-cycle":
            meteorology_manifest["cycle_utc"] = plan.cycle.isoformat().replace(
                "+00:00", "Z")
        meteorology_manifest_path = work / "meteorology_manifest.json"
        atomic_json(meteorology_manifest_path, meteorology_manifest)
        state["meteorology_manifest"] = str(meteorology_manifest_path)
        state["status"] = "meteorology_ready"
        atomic_json(state_path, state)

        met_link = prepare_met_dir(plan, archive, work / "met")
        tag = meteorology_tag(plan, args, archive_fingerprint["sha256"])
        manifest = work / "manifest.csv"
        batch_command = [
            sys.executable,
            str(Path(__file__).with_name("run_batch.py")),
            "--receptors", str(receptor_csv),
            "--stilt-wd", args.stilt_wd,
            "--met", str(met_link.parent),
            "--jobs", str(args.stilt_jobs),
            "--numpar", str(args.numpar),
            "--hours", str(args.hours),
            "--half-km", str(args.half_km),
            "--res", str(args.res),
            "--tag", tag,
            "--timeout", str(args.stilt_timeout),
            "--met-file-tres-hours", "1",
            "--log-dir", str(work / "stilt_logs"),
            "--manifest", str(manifest),
            "--resume",
        ]
        run_logged(batch_command, work, work / "batch.log")

        report = work / "validation.json"
        validate_command = [
            sys.executable,
            str(Path(__file__).with_name("validate_outputs.py")),
            "--stilt-wd", args.stilt_wd,
            "--out-report", str(report),
            "--min-hours", str(max(args.hours - 1, 0)),
            "--max-check", str(len(plan.rows)),
            "--jobs", str(args.validation_jobs),
            "--tag", tag,
        ]
        run_logged(validate_command, work, work / "validate.log")
        with open(report, encoding="utf-8") as handle:
            validation = json.load(handle)
        expected_sim_ids = expected_manifest_sim_ids(manifest, tag)
        if len(expected_sim_ids) != len(plan.rows):
            raise RuntimeError(
                f"manifest has {len(expected_sim_ids)} simulations for {tag}; "
                f"expected {len(plan.rows)}"
            )
        validate_batch_report(validation, expected_sim_ids)

        state.update({
            "status": "complete",
            "tag": tag,
            "manifest": str(manifest),
            "validation": validation,
            "completed_at": dt.datetime.now(UTC).isoformat(),
        })
        apply_retention(args.retention, work, archive, met_link)
        atomic_json(state_path, state)
        print(
            f"[{plan.date}] complete: {len(validation['ok'])}/"
            f"{validation['n_simulations']} passed",
            flush=True,
        )
        return state


def record_failure(plan: DayPlan, args, error: Exception) -> None:
    """Record a terminal attempt failure unless another process owns the day."""
    work = Path(args.root).resolve() / plan.date
    state_path = work / "state.json"
    lock_path = work / ".lock"
    if not state_path.exists():
        return
    with open(lock_path, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        with open(state_path, encoding="utf-8") as handle:
            state = json.load(handle)
        current_plan = state.get("request", {}).get("plan")
        if state.get("status") == "complete" or current_plan != plan.as_dict():
            return
        state.update({
            "status": "failed",
            "error": str(error),
            "failed_at": dt.datetime.now(UTC).isoformat(),
        })
        atomic_json(state_path, state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receptors", nargs="+", required=True)
    parser.add_argument("--dates", nargs="+", help="optional YYYYMMDD subset")
    parser.add_argument("--root", default="/root/autodl-tmp/hrrr_stilt_batches")
    parser.add_argument("--stilt-wd", default="/root/autodl-tmp/stilt")
    parser.add_argument(
        "--converter", default="/root/data2arl/hrrr2arl/hrrrv12arl_v2"
    )
    parser.add_argument(
        "--decoder-config", default="/root/arl_test/full_wrfprs_v1/api2arl.cfg"
    )
    parser.add_argument("--download-mode", choices=("range", "staged"), default="range")
    parser.add_argument(
        "--meteorology-strategy",
        choices=("single-cycle", "hourly-analysis"),
        default="single-cycle",
    )
    parser.add_argument("--hrrr-base-url", default=grib.BASE_URL)
    parser.add_argument("--proxy")
    parser.add_argument("--hour-workers", type=int, default=2)
    parser.add_argument("--range-jobs", type=int, default=4)
    parser.add_argument("--download-timeout", type=int, default=120)
    parser.add_argument("--download-retries", type=int, default=5)
    parser.add_argument("--stilt-jobs", type=int, default=8)
    parser.add_argument("--numpar", type=int, default=1000)
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--half-km", type=float, default=256.0)
    parser.add_argument("--res", type=float, default=0.04)
    parser.add_argument("--stilt-timeout", type=int, default=3600)
    parser.add_argument("--deep-check", type=int, default=20)
    parser.add_argument("--validation-jobs", type=int, default=8)
    parser.add_argument("--min-free-gib", type=float, default=20.0)
    parser.add_argument("--subset-gib-per-hour", type=float, default=0.16)
    parser.add_argument("--arl-gib-per-hour", type=float, default=0.36)
    parser.add_argument(
        "--retention", choices=("all", "merged", "outputs-only"),
        default="outputs-only",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    positive = (
        args.hour_workers,
        args.range_jobs,
        args.download_timeout,
        args.download_retries,
        args.stilt_jobs,
        args.numpar,
        args.hours,
        args.stilt_timeout,
        args.deep_check,
        args.validation_jobs,
    )
    if any(value < 1 for value in positive):
        parser.error("worker, retry, particle, hour, timeout, and check counts must be positive")
    if args.min_free_gib < 0 or args.subset_gib_per_hour <= 0 or args.arl_gib_per_hour <= 0:
        parser.error("disk sizing values must be positive")
    dates = set(args.dates) if args.dates else None
    if dates and any(len(value) != 8 or not value.isdigit() for value in dates):
        parser.error("--dates values must be YYYYMMDD")

    try:
        plans = load_plans(args.receptors, args.hours, dates)
        print(json.dumps([plan.as_dict() for plan in plans], indent=2), flush=True)
        if args.dry_run:
            return
        for required in (args.converter, args.decoder_config, args.stilt_wd):
            if not os.path.exists(required):
                raise FileNotFoundError(required)
        for plan in plans:
            try:
                process_day(plan, args)
            except (OSError, ValueError, RuntimeError) as exc:
                record_failure(plan, args, exc)
                raise
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"[hrrr-stilt-scheduler] FAILED: {exc}") from exc


if __name__ == "__main__":
    main()
