"""Map FIA local incident clocks to auditable FastF1 lap intervals."""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from f1stewards.config import PROJECT_ROOT
from f1stewards.study_v2_review import DEFAULT_DATABASE, MODEL_WORKSPACE

DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "manual" / "study_v2_incident_clock"


@dataclass(frozen=True)
class ClockLapWindow:
    clock_lower_utc: str
    clock_upper_utc: str
    possible_laps: tuple[int, ...]
    mapping_basis: str


@dataclass(frozen=True)
class IncidentClockBuild:
    run_id: str
    output_dir: Path
    cases: int
    mapped_cases: int
    single_lap_cases: int
    known_validation_cases: int
    known_contained_cases: int


def _fixed_timezone(offset: str) -> timezone:
    match = re.fullmatch(r"([+-])(\d{2}):(\d{2})", str(offset))
    if not match:
        raise ValueError(f"Invalid event timezone offset {offset!r}")
    sign = 1 if match.group(1) == "+" else -1
    return timezone(sign * timedelta(hours=int(match.group(2)), minutes=int(match.group(3))))


def map_local_clock_to_laps(
    laps: pd.DataFrame,
    incident_time_raw: str,
    event_timezone: str,
    *,
    pre_start_tolerance_seconds: int = 300,
) -> ClockLapWindow | None:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", str(incident_time_raw).strip())
    if not match or laps.empty:
        return None
    local_timezone = _fixed_timezone(event_timezone)
    work = laps.sort_values("lap_number").copy()
    work["start"] = pd.to_datetime(
        work["lap_start_timestamp"], utc=True, errors="coerce"
    ).dt.tz_convert(local_timezone)
    work = work.loc[work["start"].notna()].copy()
    if work.empty:
        return None
    session_date = work["start"].min().date()
    lower = datetime(
        session_date.year,
        session_date.month,
        session_date.day,
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3) or 0),
        tzinfo=local_timezone,
    )
    upper = lower + (timedelta(seconds=1) if match.group(3) else timedelta(minutes=1))
    work["end"] = work["start"].shift(-1)
    last_index = work.index[-1]
    fallback_seconds = work.loc[last_index, "lap_time_seconds"]
    if pd.isna(fallback_seconds):
        fallback_seconds = 120
    work.loc[last_index, "end"] = work.loc[last_index, "start"] + timedelta(
        seconds=float(fallback_seconds)
    )
    overlap = work.loc[work["start"].lt(upper) & work["end"].gt(lower)]
    basis = "fia_clock_lap_interval"
    if overlap.empty:
        first = work.iloc[0]
        pre_start = first["start"] - timedelta(seconds=pre_start_tolerance_seconds)
        if pre_start <= lower < first["start"] and int(first["lap_number"]) == 1:
            overlap = work.iloc[[0]]
            basis = "fia_clock_pre_start_first_lap_tolerance"
    possible_laps = tuple(sorted({int(value) for value in overlap["lap_number"]}))
    return ClockLapWindow(
        clock_lower_utc=pd.Timestamp(lower).tz_convert("UTC").isoformat(),
        clock_upper_utc=pd.Timestamp(upper).tz_convert("UTC").isoformat(),
        possible_laps=possible_laps,
        mapping_basis=basis if possible_laps else "fia_clock_unmatched_to_lap_interval",
    )


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    stream = io.StringIO(newline="")
    frame.to_csv(stream, index=False, lineterminator="\n")
    return stream.getvalue().encode("utf-8")


def build_incident_clock_windows(
    *,
    database_path: Path = DEFAULT_DATABASE,
    workspace: Path = MODEL_WORKSPACE,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> IncidentClockBuild:
    adjudications = pd.read_csv(
        workspace / "adjudication_coding_worklist.csv", keep_default_na=False, low_memory=False
    )
    cases = adjudications.loc[
        adjudications["include_primary_final"].astype(str).str.casefold().eq("true")
    ].copy()
    with duckdb.connect(str(database_path), read_only=True) as connection:
        laps = connection.execute(
            """
            SELECT
                event_id,
                session_type,
                driver_number,
                lap_number,
                lap_start_timestamp,
                lap_time_seconds
            FROM raw.fastf1_session_laps
            WHERE session_type IN ('Race', 'Sprint')
            """
        ).fetchdf()
        events = connection.execute(
            "SELECT event_id, event_timezone FROM metadata.events"
        ).fetchdf()
    event_timezones = dict(zip(events["event_id"], events["event_timezone"], strict=True))
    lap_groups = {
        key: group
        for key, group in laps.groupby(["event_id", "session_type", "driver_number"], sort=False)
    }
    records: list[dict[str, Any]] = []
    for _, case in cases.iterrows():
        accused_raw = str(case["accused_driver_number_final"])
        accused = int(accused_raw) if accused_raw.isdigit() else None
        key = (case["event_id"], case["session_type_final"], accused)
        driver_laps = lap_groups.get(key, pd.DataFrame())
        mapped = map_local_clock_to_laps(
            driver_laps,
            str(case["incident_time_raw"]),
            str(event_timezones[case["event_id"]]),
        )
        known_raw = str(case["lap_number_final"])
        known_lap = int(known_raw) if known_raw.isdigit() else None
        possible_laps = mapped.possible_laps if mapped is not None else ()
        records.append(
            {
                "adjudication_instance_id": case["adjudication_instance_id"],
                "adjudication_id": case["adjudication_id_final"],
                "incident_id": case["incident_id_final"],
                "document_id": case["document_id"],
                "event_id": case["event_id"],
                "session_type": case["session_type_final"],
                "accused_driver_number": accused if accused is not None else "",
                "incident_time_raw": case["incident_time_raw"],
                "event_timezone": event_timezones[case["event_id"]],
                "clock_lower_utc": mapped.clock_lower_utc if mapped else "",
                "clock_upper_utc": mapped.clock_upper_utc if mapped else "",
                "possible_accused_laps": "|".join(str(value) for value in possible_laps),
                "possible_lap_count": len(possible_laps),
                "single_lap_candidate": possible_laps[0] if len(possible_laps) == 1 else "",
                "mapping_basis": mapped.mapping_basis if mapped else "clock_or_timing_unavailable",
                "known_model_reviewed_lap": known_lap if known_lap is not None else "",
                "known_lap_within_clock_window": (
                    known_lap in possible_laps if known_lap is not None else ""
                ),
                "clock_mapping_review_status": "algorithmic_pending_human_validation",
            }
        )
    frame = pd.DataFrame(records).sort_values(
        ["event_id", "session_type", "adjudication_instance_id"]
    )
    validation = frame.loc[frame["known_model_reviewed_lap"].astype(str).ne("")]
    digest = hashlib.sha256(_csv_bytes(frame)).hexdigest()[:12]
    run_id = f"incident-clock-{digest}"
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    frame.to_csv(output_dir / "incident_clock_windows.csv", index=False)
    validation.to_csv(output_dir / "known_lap_validation.csv", index=False)
    mapped_count = int(frame["possible_lap_count"].gt(0).sum())
    single_count = int(frame["possible_lap_count"].eq(1).sum())
    contained_count = int(validation["known_lap_within_clock_window"].eq(True).sum())
    manifest = {
        "schema_version": "study-v2-incident-clock-v1",
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "case_count": len(frame),
        "mapped_case_count": mapped_count,
        "single_lap_case_count": single_count,
        "two_lap_window_count": int(frame["possible_lap_count"].eq(2).sum()),
        "unmapped_case_count": int(frame["possible_lap_count"].eq(0).sum()),
        "known_validation_case_count": len(validation),
        "known_validation_contained_count": contained_count,
        "known_validation_containment_rate": contained_count / len(validation),
        "pre_start_tolerance_seconds": 300,
        "human_validation_complete": False,
        "sha256": hashlib.sha256(_csv_bytes(frame)).hexdigest(),
        "limitation": (
            "Minute-only FIA clocks define a one-minute uncertainty window and often overlap two "
            "driver laps. Single-lap mappings remain candidates until source validation."
        ),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return IncidentClockBuild(
        run_id=run_id,
        output_dir=output_dir,
        cases=len(frame),
        mapped_cases=mapped_count,
        single_lap_cases=single_count,
        known_validation_cases=len(validation),
        known_contained_cases=contained_count,
    )
