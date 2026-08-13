"""Race Control message episodes and conservative links to reviewed adjudications."""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from f1stewards.config import PROJECT_ROOT, load_study_v2_settings
from f1stewards.study_v2_review import DEFAULT_DATABASE, MODEL_WORKSPACE

DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "manual" / "study_v2_referrals"

STATUS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("no_investigation", re.compile(r"\bNO INVESTIGATION (?:NECESSARY|REQUIRED)\b", re.I)),
    ("no_further_action", re.compile(r"\bNO FURTHER ACTION\b", re.I)),
    (
        "post_session_investigation",
        re.compile(r"\b(?:WILL BE |TO BE )?INVESTIGATED AFTER (?:THE )?(?:RACE|SESSION)\b", re.I),
    ),
    (
        "investigation",
        re.compile(r"\b(?:UNDER INVESTIGATION|INVESTIGATED BY THE STEWARDS)\b", re.I),
    ),
    (
        "sanction_announced",
        re.compile(
            r"\b(?:PENALTY|REPRIMAND|WARNING|DRIVE THROUGH|DRIVE-THROUGH|STOP/GO|GRID DROP)\b",
            re.I,
        ),
    ),
    ("noted", re.compile(r"\bNOTED\b", re.I)),
]

FAMILY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("causing_collision", re.compile(r"\b(?:CAUSING A )?COLLISION\b|\bCONTACT\b", re.I)),
    ("forcing_off_track", re.compile(r"FORC(?:ING|ED).*OFF (?:THE )?TRACK", re.I)),
    (
        "gaining_advantage_off_track",
        re.compile(r"LEAVING THE TRACK AND GAINING|GAIN(?:ING|ED) AN ADVANTAGE", re.I),
    ),
    ("unsafe_rejoin", re.compile(r"UNSAFE(?:LY)? REJOIN|REJOIN(?:ED|ING).*UNSAFE", re.I)),
    ("moving_under_braking", re.compile(r"MOV(?:E|ING|ED).*UNDER BRAKING", re.I)),
    ("multiple_defensive_moves", re.compile(r"MORE THAN ONE CHANGE|DEFENSIVE MOVE", re.I)),
    ("unsafe_release", re.compile(r"UNSAFE RELEASE|RELEASED IN AN UNSAFE", re.I)),
    ("impeding", re.compile(r"\bIMPED(?:E|ED|ING)\b", re.I)),
    ("blue_flags", re.compile(r"BLUE FLAG", re.I)),
    ("track_limits", re.compile(r"TRACK LIMIT|LEAVING THE TRACK", re.I)),
]


@dataclass(frozen=True)
class ReferralBuild:
    run_id: str
    output_dir: Path
    parsed_messages: int
    episodes: int
    adjudications: int
    high_confidence_links: int


def parse_status(message: str) -> str | None:
    for status, pattern in STATUS_PATTERNS:
        if pattern.search(message):
            return status
    return None


def extract_car_numbers(message: str) -> tuple[int, ...]:
    numbers = {int(value) for value in re.findall(r"\b(\d{1,2})\s*\([A-Z]{2,4}\)", message)}
    numbers.update(int(value) for value in re.findall(r"\bCAR\s+(\d{1,2})\b", message, re.I))
    return tuple(sorted(numbers))


def extract_location(message: str) -> str:
    turn = re.search(r"\bTURN(?:S)?\s+(\d{1,2}(?:\s*(?:,|AND|-)\s*\d{1,2})*)", message, re.I)
    if turn:
        normalized = re.sub(r"\s+", " ", turn.group(1).upper()).replace(" AND ", "-")
        return f"Turn {normalized}"
    if re.search(r"\b(?:PIT LANE|PIT ENTRY|PIT EXIT)\b", message, re.I):
        return "Pit Lane"
    if re.search(r"\bFIRST (?:CORNER|TURN)\b|\b1ST CORNER\b", message, re.I):
        return "Turn 1"
    return ""


def extract_incident_lap(message: str) -> int | None:
    match = re.search(r"\bLAP\s+(\d{1,3})\b(?=.*\bINCIDENT\b)", message, re.I)
    if match:
        return int(match.group(1))
    if re.search(r"\bFIRST LAP INCIDENT", message, re.I):
        return 1
    return None


def classify_family(message: str) -> str:
    for family, pattern in FAMILY_PATTERNS:
        if pattern.search(message):
            return family
    return "other"


def _normalized_location(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def parse_referral_messages(messages: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for source_index, row in messages.reset_index(drop=True).iterrows():
        message = str(row["message"])
        status = parse_status(message)
        if status is None:
            continue
        cars = extract_car_numbers(message)
        records.append(
            {
                "source_message_index": source_index,
                "event_id": row["event_id"],
                "session_type": row["session_type"],
                "message_timestamp": row["message_timestamp"],
                "message_lap": row.get("lap_number"),
                "message": message,
                "process_status": status,
                "car_numbers": "|".join(str(number) for number in cars),
                "car_count": len(cars),
                "location": extract_location(message),
                "incident_lap_explicit": extract_incident_lap(message),
                "incident_family": classify_family(message),
            }
        )
    return pd.DataFrame(records)


def _car_set(value: str) -> set[int]:
    return {int(part) for part in str(value).split("|") if part and part.isdigit()}


def _episode_candidate_score(message: pd.Series, episode: dict[str, Any]) -> float:
    message_cars = _car_set(message["car_numbers"])
    episode_cars = set(episode["cars"])
    score = 0.0
    if message_cars and episode_cars:
        if message_cars == episode_cars:
            score += 5.0
        elif message_cars <= episode_cars or episode_cars <= message_cars:
            score += 3.0
        elif message_cars & episode_cars:
            score += 1.5
        else:
            return -100.0
    elif message_cars or episode_cars:
        score -= 1.0

    message_location = _normalized_location(message["location"])
    episode_location = _normalized_location(episode["location"])
    if message_location and episode_location:
        if message_location == episode_location:
            score += 3.0
        else:
            score -= 2.0
    if message["incident_family"] != "other" and episode["family"] != "other":
        if message["incident_family"] == episode["family"]:
            score += 2.5
        else:
            score -= 2.0
    message_lap = message["incident_lap_explicit"]
    episode_lap = episode["incident_lap"]
    if pd.notna(message_lap) and episode_lap is not None:
        lap_gap = abs(int(message_lap) - int(episode_lap))
        score += 2.0 if lap_gap <= 1 else -min(3.0, lap_gap / 2)
    return score


def build_referral_episodes(parsed: pd.DataFrame, episode_gap_seconds: int = 900) -> pd.DataFrame:
    episodes: list[dict[str, Any]] = []
    for _, message in parsed.sort_values(
        ["event_id", "session_type", "message_timestamp", "source_message_index"]
    ).iterrows():
        candidates: list[tuple[float, dict[str, Any]]] = []
        for episode in reversed(episodes):
            if (
                episode["event_id"] != message["event_id"]
                or episode["session_type"] != message["session_type"]
            ):
                continue
            gap = (
                pd.Timestamp(message["message_timestamp"]) - episode["last_timestamp"]
            ).total_seconds()
            if gap < 0 or gap > episode_gap_seconds:
                continue
            score = _episode_candidate_score(message, episode) - gap / episode_gap_seconds
            if score >= 3.5:
                candidates.append((score, episode))
        if candidates:
            _, episode = max(candidates, key=lambda item: (item[0], item[1]["episode_order"]))
        else:
            episode = {
                "episode_order": len(episodes) + 1,
                "event_id": message["event_id"],
                "session_type": message["session_type"],
                "first_timestamp": pd.Timestamp(message["message_timestamp"]),
                "last_timestamp": pd.Timestamp(message["message_timestamp"]),
                "cars": set(),
                "location": str(message["location"]),
                "family": str(message["incident_family"]),
                "incident_lap": (
                    int(message["incident_lap_explicit"])
                    if pd.notna(message["incident_lap_explicit"])
                    else None
                ),
                "messages": [],
            }
            episodes.append(episode)
        episode["last_timestamp"] = pd.Timestamp(message["message_timestamp"])
        episode["cars"].update(_car_set(message["car_numbers"]))
        if not episode["location"] and message["location"]:
            episode["location"] = str(message["location"])
        if episode["family"] == "other" and message["incident_family"] != "other":
            episode["family"] = str(message["incident_family"])
        if episode["incident_lap"] is None and pd.notna(message["incident_lap_explicit"]):
            episode["incident_lap"] = int(message["incident_lap_explicit"])
        episode["messages"].append(message.to_dict())

    records: list[dict[str, Any]] = []
    terminal_priority = {
        "sanction_announced": 4,
        "no_further_action": 3,
        "no_investigation": 2,
        "post_session_investigation": 1,
        "investigation": 0,
        "noted": -1,
    }
    for episode in episodes:
        statuses = [str(message["process_status"]) for message in episode["messages"]]
        terminal = max(statuses, key=lambda value: terminal_priority[value])
        digest = hashlib.sha256(
            (
                f"{episode['event_id']}|{episode['session_type']}|"
                f"{'|'.join(str(number) for number in sorted(episode['cars']))}|"
                f"{episode['location']}|{episode['family']}|{episode['first_timestamp'].isoformat()}"
            ).encode()
        ).hexdigest()[:16]
        message_laps = [
            int(message["message_lap"])
            for message in episode["messages"]
            if pd.notna(message["message_lap"])
        ]
        records.append(
            {
                "referral_episode_id": f"referral-{digest}",
                "event_id": episode["event_id"],
                "session_type": episode["session_type"],
                "first_timestamp": episode["first_timestamp"],
                "last_timestamp": episode["last_timestamp"],
                "car_numbers": "|".join(str(number) for number in sorted(episode["cars"])),
                "car_count": len(episode["cars"]),
                "location": episode["location"],
                "incident_family": episode["family"],
                "incident_lap_explicit": episode["incident_lap"],
                "message_lap_min": min(message_laps) if message_laps else None,
                "message_lap_max": max(message_laps) if message_laps else None,
                "process_statuses": "|".join(dict.fromkeys(statuses)),
                "terminal_status": terminal,
                "message_count": len(episode["messages"]),
                "messages_json": json.dumps(
                    [message["message"] for message in episode["messages"]], ensure_ascii=False
                ),
                "episode_review_status": "algorithmic_pending_human_validation",
            }
        )
    return pd.DataFrame(records)


def _adjudication_cases(workspace: Path) -> pd.DataFrame:
    adjudications = pd.read_csv(
        workspace / "adjudication_coding_worklist.csv", keep_default_na=False, low_memory=False
    )
    cases = adjudications.loc[
        adjudications["include_primary_final"].astype(str).str.casefold().eq("true")
    ].copy()
    cases["adjudication_car_numbers"] = cases.apply(
        lambda row: "|".join(
            str(number)
            for number in sorted(
                {
                    *(
                        [int(row["accused_driver_number_final"])]
                        if str(row["accused_driver_number_final"]).isdigit()
                        else []
                    ),
                    *(
                        int(value)
                        for value in str(row["affected_driver_numbers_final"]).split("|")
                        if value.isdigit()
                    ),
                }
            )
        ),
        axis=1,
    )
    return cases[
        [
            "adjudication_instance_id",
            "adjudication_id_final",
            "incident_id_final",
            "document_id",
            "event_id",
            "session_type_final",
            "adjudication_car_numbers",
            "accused_driver_number_final",
            "affected_driver_numbers_final",
            "lap_number_final",
            "location_final",
            "incident_family_final",
            "outcome_family_final",
        ]
    ].rename(
        columns={
            "adjudication_id_final": "adjudication_id",
            "incident_id_final": "incident_id",
            "session_type_final": "session_type",
            "accused_driver_number_final": "accused_driver_number",
            "affected_driver_numbers_final": "affected_driver_numbers",
            "lap_number_final": "lap_number",
            "location_final": "location",
            "incident_family_final": "incident_family",
            "outcome_family_final": "outcome_family",
        }
    )


def _terminal_outcome_match(terminal: str, outcome: str) -> bool:
    if terminal == "sanction_announced":
        return outcome not in {"no_further_action", "racing_incident"}
    if terminal in {"no_further_action", "no_investigation"}:
        return outcome in {"no_further_action", "racing_incident"}
    return False


def _link_score(case: pd.Series, episode: pd.Series) -> tuple[float, list[str]]:
    score = 0.0
    basis: list[str] = []
    case_cars = _car_set(case["adjudication_car_numbers"])
    episode_cars = _car_set(episode["car_numbers"])
    accused = (
        int(case["accused_driver_number"]) if str(case["accused_driver_number"]).isdigit() else None
    )
    affected = _car_set(case["affected_driver_numbers"])
    if case_cars and case_cars == episode_cars:
        score += 8
        basis.append("exact_car_set")
    elif case_cars and case_cars <= episode_cars:
        score += 7
        basis.append("adjudication_car_set_within_episode")
    else:
        if accused is not None and accused in episode_cars:
            score += 3
            basis.append("accused_car")
        if affected & episode_cars:
            score += 3
            basis.append("affected_car_overlap")
    if case["incident_family"] == episode["incident_family"] and case["incident_family"] != "other":
        score += 3
        basis.append("incident_family")
    case_location = _normalized_location(case["location"])
    episode_location = _normalized_location(episode["location"])
    if case_location and case_location == episode_location:
        score += 2
        basis.append("location")
    case_lap = int(case["lap_number"]) if str(case["lap_number"]).isdigit() else None
    episode_lap = episode["incident_lap_explicit"]
    if case_lap is not None and pd.notna(episode_lap):
        gap = abs(case_lap - int(episode_lap))
        if gap <= 1:
            score += 3
            basis.append("explicit_lap")
        elif gap > 3:
            score -= 3
            basis.append("lap_conflict")
    if _terminal_outcome_match(str(episode["terminal_status"]), str(case["outcome_family"])):
        score += 2
        basis.append("terminal_outcome")
    return score, basis


def link_adjudications_to_episodes(cases: pd.DataFrame, episodes: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for _, case in cases.iterrows():
        candidates = episodes.loc[
            episodes["event_id"].eq(case["event_id"])
            & episodes["session_type"].eq(case["session_type"])
        ]
        scored: list[tuple[float, list[str], pd.Series]] = []
        for _, episode in candidates.iterrows():
            score, basis = _link_score(case, episode)
            if score >= 6:
                scored.append((score, basis, episode))
        scored.sort(key=lambda item: (-item[0], str(item[2]["referral_episode_id"])))
        best_score = scored[0][0] if scored else None
        second_score = scored[1][0] if len(scored) > 1 else None
        ambiguous = (
            best_score is not None
            and second_score is not None
            and float(best_score) - float(second_score) < 2
        )
        if not scored:
            link_status = "unmatched"
            episode_id = ""
            basis_json = "[]"
        elif ambiguous:
            link_status = "ambiguous_pending_review"
            episode_id = str(scored[0][2]["referral_episode_id"])
            basis_json = json.dumps(scored[0][1])
        elif float(best_score) >= 13:
            link_status = "high_confidence_algorithmic"
            episode_id = str(scored[0][2]["referral_episode_id"])
            basis_json = json.dumps(scored[0][1])
        else:
            link_status = "candidate_pending_review"
            episode_id = str(scored[0][2]["referral_episode_id"])
            basis_json = json.dumps(scored[0][1])
        records.append(
            {
                **case.to_dict(),
                "referral_episode_id": episode_id,
                "link_score": best_score,
                "runner_up_score": second_score,
                "link_status": link_status,
                "link_basis_json": basis_json,
                "link_review_status": "pending_human_validation",
                "link_reviewer_id": "",
                "link_review_notes": "",
            }
        )
    return pd.DataFrame(records)


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    stream = io.StringIO(newline="")
    frame.to_csv(stream, index=False, lineterminator="\n")
    return stream.getvalue().encode("utf-8")


def build_referral_funnel(
    *,
    database_path: Path = DEFAULT_DATABASE,
    workspace: Path = MODEL_WORKSPACE,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> ReferralBuild:
    settings = load_study_v2_settings()["referral_funnel"]
    with duckdb.connect(str(database_path), read_only=True) as connection:
        messages = connection.execute(
            """
            SELECT
                event_id,
                session_type,
                message_timestamp,
                lap_number,
                category,
                message,
                status,
                flag,
                scope,
                sector,
                racing_number
            FROM raw.fastf1_session_race_control_messages
            WHERE session_type IN ('Race', 'Sprint')
            ORDER BY event_id, session_type, message_timestamp
            """
        ).fetchdf()
    parsed = parse_referral_messages(messages)
    episodes = build_referral_episodes(parsed, int(settings["episode_gap_seconds"]))
    cases = _adjudication_cases(workspace)
    links = link_adjudications_to_episodes(cases, episodes)
    linked_episode_ids = set(links.loc[links["referral_episode_id"].ne(""), "referral_episode_id"])
    episodes["linked_to_primary_adjudication"] = episodes["referral_episode_id"].isin(
        linked_episode_ids
    )

    funnel = pd.DataFrame(
        [
            {"stage": "Race/Sprint Race Control messages", "count": len(messages)},
            {"stage": "Process-state messages parsed", "count": len(parsed)},
            {"stage": "Referral episodes", "count": len(episodes)},
            {
                "stage": "Episodes linked to a primary adjudication",
                "count": int(episodes["linked_to_primary_adjudication"].sum()),
            },
            {"stage": "Primary adjudications", "count": len(cases)},
            {
                "stage": "High-confidence adjudication links",
                "count": int(links["link_status"].eq("high_confidence_algorithmic").sum()),
            },
            {
                "stage": "Adjudication links pending review",
                "count": int(links["link_status"].str.contains("pending_review").sum()),
            },
            {
                "stage": "Unmatched primary adjudications",
                "count": int(links["link_status"].eq("unmatched").sum()),
            },
        ]
    )
    digest = hashlib.sha256(
        _csv_bytes(parsed) + _csv_bytes(episodes) + _csv_bytes(links)
    ).hexdigest()[:12]
    run_id = f"referrals-{digest}"
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    parsed.to_csv(output_dir / "parsed_process_messages.csv", index=False)
    episodes.to_csv(output_dir / "referral_episodes.csv", index=False)
    links.to_csv(output_dir / "adjudication_episode_links.csv", index=False)
    funnel.to_csv(output_dir / "referral_funnel.csv", index=False)
    manifest = {
        "schema_version": "study-v2-referral-funnel-v1",
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "source_table": settings["source_table"],
        "source_scope": "public Formula 1 timing-feed messages accessed through FastF1",
        "parsed_message_count": len(parsed),
        "episode_count": len(episodes),
        "primary_adjudication_count": len(cases),
        "high_confidence_link_count": int(
            links["link_status"].eq("high_confidence_algorithmic").sum()
        ),
        "pending_link_count": int(links["link_status"].str.contains("pending_review").sum()),
        "unmatched_adjudication_count": int(links["link_status"].eq("unmatched").sum()),
        "unmatched_episode_count": int((~episodes["linked_to_primary_adjudication"]).sum()),
        "parsed_messages_sha256": hashlib.sha256(_csv_bytes(parsed)).hexdigest(),
        "episodes_sha256": hashlib.sha256(_csv_bytes(episodes)).hexdigest(),
        "links_sha256": hashlib.sha256(_csv_bytes(links)).hexdigest(),
        "human_validation_complete": False,
        "limitation": (
            "The feed observes public process messages, not every on-track incident or every "
            "internal referral. Algorithmic episodes and links require validation before inference."
        ),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return ReferralBuild(
        run_id=run_id,
        output_dir=output_dir,
        parsed_messages=len(parsed),
        episodes=len(episodes),
        adjudications=len(cases),
        high_confidence_links=manifest["high_confidence_link_count"],
    )
