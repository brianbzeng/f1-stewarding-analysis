# ruff: noqa: E501
"""Build the versioned source-review ledger for the 61 manual-scope investigations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from f1stewards.review_explorer import REVIEW_LEDGER_SCHEMA_VERSION, workspace_input_sha256

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = (
    PROJECT_ROOT
    / "data"
    / "manual"
    / "full_corpus_review_rounds"
    / "scope_conflicts"
    / "full-coding-e0192ecbd9e4"
)
OUTPUT = (
    PROJECT_ROOT / "data" / "manual" / "review_ledgers" / "manual_scope_v1.json"
)
EXPECTED_WORKSPACE_SHA256 = (
    "c7d62651b6eb7646b1682e616e32666620cdbc6f8a1d3a451d3da9e4d8ceb7ae"
)
CODER_ID = "codex_source_review_v1"


@dataclass(frozen=True)
class Case:
    family: str
    note: str
    include: bool = True
    session: str = ""
    affected: str = ""
    fault: str = "no_conclusion"
    group: str = ""
    exclusion_reason: str = ""
    outcome: str = ""
    seconds: str = ""
    points: str = ""
    grid: str = ""
    lap: str = ""
    location: str = ""


CASES: dict[str, Case] = {
    "fia-2018-fra-8fdc744f8ecd": Case(
        "unclassified",
        "Car 8 was hit from behind, left the track, and rejoined safely without gaining a position; the source does not allege an unsafe rejoin or another frozen primary offence.",
        include=False,
        exclusion_reason="outside_frozen_primary_secondary_scope",
    ),
    "fia-2018-aut-9c50973f6716": Case(
        "forcing_off_track",
        "Car 55 deliberately crowded Car 31 partly off track after rejoining and received a driving reprimand.",
        affected="31",
    ),
    "fia-2018-gbr-c4ec3bfd58d1": Case(
        "causing_collision",
        "Mirrored Car 20 decision for the Turn 3 collision with Car 8; the preceding incident influenced both cars and no further action was taken.",
        affected="8",
        group="2018-gbr-race-t3-cars8-20",
    ),
    "fia-2018-gbr-dbd297e3a1ec": Case(
        "causing_collision",
        "Mirrored Car 8 decision for the Turn 3 collision with Car 20; the preceding incident influenced both cars and no further action was taken.",
        affected="20",
        group="2018-gbr-race-t3-cars8-20",
    ),
    "fia-2018-ita-46eec3615f40": Case(
        "causing_collision",
        "Mirrored Car 44 decision for the Turn 4 contact with Car 5; neither driver was wholly or predominantly at fault.",
        affected="5",
        group="2018-ita-race-t4-cars5-44",
    ),
    "fia-2018-ita-a3456e32915c": Case(
        "causing_collision",
        "Mirrored Car 5 decision for the Turn 4 contact with Car 44; neither driver was wholly or predominantly at fault.",
        affected="44",
        group="2018-ita-race-t4-cars5-44",
    ),
    "fia-2018-sgp-21e75b934044": Case(
        "causing_collision",
        "Turn 7 collision between Cars 20 and 28; no driver was predominantly at fault.",
        affected="28",
    ),
    "fia-2018-sgp-bcfc0b21409a": Case(
        "causing_collision",
        "First-lap Turn 3 contact between Cars 11 and 31 while three cars were nearly side by side; neither driver was predominantly at fault.",
        affected="31",
        lap="1",
    ),
    "fia-2018-jpn-af0be8505555": Case(
        "gaining_advantage_off_track",
        "Car 14 was forced off but then cut the chicane and gained a significant advantage; five-second penalty and one penalty point.",
        outcome="time_penalty",
        seconds="5",
        points="1",
    ),
    "fia-2019-deu-439337838994": Case(
        "causing_collision",
        "Car 10 made an error attempting to pass Car 23; only Car 10 was disadvantaged and no further action was taken.",
        affected="23",
    ),
    "fia-2019-ita-5d8bd476d009": Case(
        "causing_collision",
        "Car 5 rejoined unsafely and collided with Car 18 in a dangerous incident; ten-second stop-and-go and three penalty points.",
        affected="18",
        outcome="stop_go",
        points="3",
    ),
    "fia-2019-sgp-4f116694a24c": Case(
        "causing_collision",
        "Mirrored Car 7 adjudication for the Turn 1 incident with Car 26; both drivers described it as a racing incident.",
        affected="26",
        fault="racing_incident",
        group="2019-sgp-race-t1-cars7-26",
    ),
    "fia-2019-sgp-ab76599fc615": Case(
        "causing_collision",
        "Mirrored Car 26 adjudication for the Turn 1 incident with Car 7; both drivers described it as a racing incident.",
        affected="7",
        fault="racing_incident",
        group="2019-sgp-race-t1-cars7-26",
    ),
    "fia-2019-sgp-6c9e26d4cab3": Case(
        "causing_collision",
        "Mirrored Car 63 decision for the Turn 8 collision with Car 8; both drivers contributed and neither was predominantly at fault.",
        affected="8",
        fault="shared_fault",
        group="2019-sgp-race-t8-cars8-63",
        location="Turn 8",
    ),
    "fia-2019-sgp-6db2310a0bec": Case(
        "causing_collision",
        "Mirrored Car 8 decision for the Turn 8 collision with Car 63; both drivers contributed and neither was predominantly at fault.",
        affected="63",
        fault="shared_fault",
        group="2019-sgp-race-t8-cars8-63",
        location="Turn 8",
    ),
    "fia-2019-sgp-d456f4419d4f": Case(
        "causing_collision",
        "Mirrored Car 27 decision for the first-lap Turn 5 collision with Car 55; classified as a racing incident.",
        affected="55",
        fault="racing_incident",
        group="2019-sgp-race-l1-t5-cars27-55",
        lap="1",
    ),
    "fia-2019-sgp-e6c461804492": Case(
        "causing_collision",
        "Mirrored Car 55 decision for the first-lap Turn 5 collision with Car 27; classified as a racing incident.",
        affected="27",
        fault="racing_incident",
        group="2019-sgp-race-l1-t5-cars27-55",
        lap="1",
    ),
    "fia-2019-sgp-5c1d1870e601": Case(
        "neutralization_or_flag_procedure",
        "Car 99 disobeyed the Race Director's line instruction near a crane and marshals under double yellow flags; this is an excluded flag/race-direction offence.",
        include=False,
        exclusion_reason="excluded_offence_family:neutralization_or_flag_procedure",
        outcome="time_penalty",
        seconds="10",
    ),
    "fia-2019-jpn-4a022963168d": Case(
        "causing_collision",
        "Car 16 contacted Car 33 and forced it off track on lap 1; Car 16 was predominantly at fault and received five seconds plus two penalty points.",
        affected="33",
        fault="predominantly_to_blame",
        group="2019-jpn-race-l1-t1-2-cars16-33",
        outcome="time_penalty",
        seconds="5",
        points="2",
        lap="1",
        location="Turns 1-2",
    ),
    "fia-2019-jpn-9be40f8bba4d": Case(
        "causing_collision",
        "Mirrored Car 33 no-action adjudication for the lap-1 contact caused by Car 16; the blame language applies to the counterpart, not accused Car 33.",
        affected="16",
        group="2019-jpn-race-l1-t1-2-cars16-33",
        lap="1",
        location="Turns 1-2",
    ),
    "fia-2019-jpn-8f4df880b95b": Case(
        "causing_collision",
        "Mirrored Car 10 decision for the Turn 2 contact with Car 11; both drivers contributed and no driver was wholly at fault.",
        affected="11",
        fault="shared_fault",
        group="2019-jpn-race-t2-cars10-11",
        location="Turn 2",
    ),
    "fia-2019-jpn-ddc6b3eef5b1": Case(
        "causing_collision",
        "Mirrored Car 11 decision for the Turn 2 contact with Car 10; both drivers contributed and no driver was wholly at fault.",
        affected="10",
        fault="shared_fault",
        group="2019-jpn-race-t2-cars10-11",
        location="Turn 2",
    ),
    "fia-2019-mex-9a84e5496c6b": Case(
        "causing_collision",
        "Car 26 hit the rear of Car 27, causing it to spin into the wall; ten-second penalty and two penalty points.",
        affected="27",
        outcome="time_penalty",
        seconds="10",
        points="2",
    ),
    "fia-2019-usa-e8891601d008": Case(
        "causing_collision",
        "First-lap Turn 1 incident between Cars 23 and 55; no driver was wholly or predominantly to blame.",
        affected="55",
        lap="1",
    ),
    "fia-2019-bra-0197a870d5b2": Case(
        "causing_collision",
        "Mirrored Car 16 decision for the Turn 4 collision with Car 5; neither driver was predominantly at fault.",
        affected="5",
        group="2019-bra-race-t4-cars5-16",
    ),
    "fia-2019-bra-38ee05c4fb59": Case(
        "causing_collision",
        "Mirrored Car 5 decision for the Turn 4 collision with Car 16; neither driver was predominantly at fault.",
        affected="16",
        group="2019-bra-race-t4-cars5-16",
    ),
    "fia-2019-bra-b956905dbc4f": Case(
        "causing_collision",
        "Car 3 locked a front wheel and collided with Car 20; Car 3 was predominantly at fault and received five seconds plus two penalty points.",
        affected="20",
        fault="predominantly_to_blame",
        outcome="time_penalty",
        seconds="5",
        points="2",
    ),
    "fia-2019-abu-e94aca06904a": Case(
        "causing_collision",
        "Mirrored Car 88 decision for the Turn 12 incident with Car 99; no driver was wholly or predominantly to blame.",
        affected="99",
        group="2019-abu-race-t12-cars88-99",
    ),
    "fia-2019-abu-eed6b57f5b3f": Case(
        "causing_collision",
        "Mirrored Car 99 decision for the Turn 12 incident with Car 88; no driver was wholly or predominantly to blame.",
        affected="88",
        group="2019-abu-race-t12-cars88-99",
    ),
    "fia-2019-fra-457ded17de98": Case(
        "forcing_off_track",
        "Car 3 rejoined at an angle that forced Car 4 off track and took the position; five-second penalty and two penalty points.",
        affected="4",
        outcome="time_penalty",
        seconds="5",
        points="2",
    ),
    "fia-2020-por-48056c42c597": Case(
        "race_direction_or_slow_driving",
        "Car 11 made one dangerous defensive movement before the braking zone; it was neither reactive nor a multiple move, so it falls outside the frozen primary families.",
        include=False,
        exclusion_reason="excluded_offence_family:race_direction_or_slow_driving",
        outcome="reprimand",
        lap="64",
        location="Main straight",
    ),
    "fia-2020-sty-965461bfbe13": Case(
        "forcing_off_track",
        "Car 18's attempted pass caused both Cars 18 and 3 to leave the track; the stewards classified it as a racing incident.",
        affected="3",
        fault="racing_incident",
    ),
    "fia-2020-gbr-319c8c2d52b9": Case(
        "causing_collision",
        "Car 23 attempted a late pass at Turn 18 and was predominantly at fault for the collision with Car 20; five seconds and two penalty points.",
        affected="20",
        fault="predominantly_to_blame",
        outcome="time_penalty",
        seconds="5",
        points="2",
        location="Turn 18",
    ),
    "fia-2020-ita-5e5acd0fdb41": Case(
        "forcing_off_track",
        "Car 33 was investigated for crowding Car 11 at Turn 2; the source found no deliberate crowding and took no further action.",
        affected="11",
        location="Turn 2",
    ),
    "fia-2021-esp-76f0795efb8a": Case(
        "routine_track_limits",
        "Car 18 could not pass behind the prescribed bollards after being forced off, rejoined safely, and returned any possible advantage; excluded track-rejoin procedure.",
        include=False,
        exclusion_reason="excluded_offence_family:routine_track_limits",
        location="Turns 1-2",
    ),
    "fia-2021-gbr-74d32cf58767": Case(
        "forcing_off_track",
        "Car 7 was forced onto the kerb while alongside Car 11 and spun; no driver was predominantly at fault and no further action was taken.",
        affected="7",
        location="Turn 17",
    ),
    "fia-2022-fra-832a818ac903": Case(
        "causing_collision",
        "Mirrored Car 6 decision for the Turn 2 collision with Car 20; both drivers contributed, both cars were damaged, and both retired.",
        affected="20",
        fault="shared_fault",
        group="2022-fra-race-t2-cars6-20",
        location="Turn 2",
    ),
    "fia-2022-fra-f29d68ccd9b0": Case(
        "causing_collision",
        "Mirrored Car 20 decision for the Turn 2 collision with Car 6; both drivers contributed, both cars were damaged, and both retired.",
        affected="6",
        fault="shared_fault",
        group="2022-fra-race-t2-cars6-20",
        location="Turn 2",
    ),
    "fia-2022-usa-211d82e7968e": Case(
        "routine_track_limits",
        "Car 47 left the track without justification four times; this is a routine track-limits offence, not a lasting-advantage adjudication.",
        include=False,
        exclusion_reason="excluded_offence_family:routine_track_limits",
        outcome="time_penalty",
        seconds="5",
        points="1",
    ),
    "fia-2022-sao-002711fb5ae0": Case(
        "forcing_off_track",
        "Car 18 deliberately drove Car 5 off the road in a dangerous manner; ten-second Sprint penalty and three penalty points.",
        affected="5",
        outcome="time_penalty",
        seconds="10",
        points="3",
    ),
    "fia-2023-aus-0144b2323236": Case(
        "causing_collision",
        "Mirrored Car 31 adjudication for the Turn 2 restart collision with Car 10; both drivers accepted it as a first-lap racing incident.",
        affected="10",
        fault="racing_incident",
        group="2023-aus-race-restart-t2-cars10-31",
        location="Turn 2",
    ),
    "fia-2023-aus-500bb4f284ba": Case(
        "causing_collision",
        "Mirrored Car 10 adjudication for the Turn 2 restart collision with Car 31; both drivers accepted it as a first-lap racing incident.",
        affected="31",
        fault="racing_incident",
        group="2023-aus-race-restart-t2-cars10-31",
        location="Turn 2",
    ),
    "fia-2023-bel-3192ec4d03d6": Case(
        "unclassified",
        "Car 14 moved from right to left after pit exit and caused Car 27 to avoid a collision; it was not a braking-zone or multiple-defence allegation.",
        include=False,
        exclusion_reason="outside_frozen_primary_secondary_scope",
        outcome="warning",
        location="Between Turns 1-2",
    ),
    "fia-2023-qat-002060120e1b": Case(
        "causing_collision",
        "Car 11 side of the three-car Sprint collision with Cars 27 and 31 at Turn 2; no driver was predominantly at fault.",
        affected="27|31",
        fault="racing_incident",
        group="2023-qat-sprint-t2-cars11-27-31",
        location="Turn 2",
    ),
    "fia-2023-qat-8a64aec7daf5": Case(
        "causing_collision",
        "Car 31 side of the three-car Sprint collision with Cars 11 and 27 at Turn 2; no driver was predominantly at fault.",
        affected="11|27",
        fault="racing_incident",
        group="2023-qat-sprint-t2-cars11-27-31",
        location="Turn 2",
    ),
    "fia-2023-qat-9b045d16fdac": Case(
        "causing_collision",
        "Car 27 side of the three-car Sprint collision with Cars 11 and 31 at Turn 2; no driver was predominantly at fault.",
        affected="11|31",
        fault="racing_incident",
        group="2023-qat-sprint-t2-cars11-27-31",
        location="Turn 2",
    ),
    "fia-2024-mia-8181b93a13ff": Case(
        "pit_lane_procedure",
        "Car 31 left its garage without being released and collided with Car 16 on the reconnaissance lap; excluded pre-session pit-lane procedure.",
        include=False,
        session="Reconnaissance",
        affected="16",
        exclusion_reason="excluded_offence_family:pit_lane_procedure",
        outcome="time_penalty",
        seconds="10",
        points="1",
        location="Pit lane",
    ),
    "fia-2024-mia-86547ded7d12": Case(
        "causing_collision",
        "Car 18 side of the four-car, three-contact Sprint chain involving Cars 14, 18, 44, and 4; damage affected Cars 14 and 18 and Car 4 retired.",
        affected="14|4|44",
        group="2024-mia-sprint-l1-t1-cars4-14-18-44",
        lap="1",
        location="Turn 1",
    ),
    "fia-2024-mia-b115633c9ba0": Case(
        "causing_collision",
        "Car 14 side of the four-car, three-contact Sprint chain involving Cars 14, 18, 44, and 4; no driver was predominantly to blame.",
        affected="18|4|44",
        group="2024-mia-sprint-l1-t1-cars4-14-18-44",
        lap="1",
        location="Turn 1",
    ),
    "fia-2024-mia-badde45f9141": Case(
        "causing_collision",
        "Car 44 side of the four-car, three-contact Sprint chain involving Cars 14, 18, 44, and 4; the sudden arrival of Car 44 contributed but no driver was predominantly to blame.",
        affected="14|4|18",
        group="2024-mia-sprint-l1-t1-cars4-14-18-44",
        lap="1",
        location="Turn 1",
    ),
    "fia-2024-can-2d45bb0945a9": Case(
        "causing_collision",
        "Mirrored Car 81 adjudication for slight contact with Car 63 through Turns 13-14; no driver was predominantly at fault.",
        affected="63",
        group="2024-can-race-t13-14-cars63-81",
        location="Turns 13-14",
    ),
    "fia-2024-can-546aad3f9319": Case(
        "causing_collision",
        "Mirrored Car 63 adjudication for slight contact with Car 81 through Turns 13-14; no driver was predominantly at fault.",
        affected="81",
        group="2024-can-race-t13-14-cars63-81",
        location="Turns 13-14",
    ),
    "fia-2024-hun-46b193d4af90": Case(
        "causing_collision",
        "Car 1 locked both fronts and collided with Car 44 at Turn 1; no driver was predominantly to blame. Car 23 was passed before the incident and is not an affected role.",
        affected="44",
    ),
    "fia-2024-usa-1d5ba0527e94": Case(
        "gaining_advantage_off_track",
        "Car 10 left the track and returned ahead of Car 23 after losing the right to the corner; five-second penalty.",
        affected="23",
        outcome="time_penalty",
        seconds="5",
    ),
    "fia-2024-mex-a4340456d96a": Case(
        "forcing_off_track",
        "Car 11's late Turn 4 move caused Car 30 to leave the track to avoid contact; Car 11 later conceded and the stewards called it a racing incident.",
        affected="30",
        fault="racing_incident",
        location="Turns 4-5",
    ),
    "fia-2024-qat-ea0ded916e32": Case(
        "causing_collision",
        "Race incident: Car 30 understeered into Car 77 at Turn 1; FastF1 lap starts place the minute-rounded 19:12 FIA time at the start of lap 5.",
        session="Race",
        affected="77",
        outcome="time_penalty",
        seconds="10",
        points="2",
        lap="5",
        location="Turn 1",
    ),
    "fia-2024-abu-62aed0693198": Case(
        "causing_collision",
        "Race incident: Car 77 hit the rear-left wheel of Car 11 at Turn 6 on lap 1 and was wholly at fault; ten seconds and two penalty points.",
        session="Race",
        affected="11",
        fault="wholly_to_blame",
        outcome="time_penalty",
        seconds="10",
        points="2",
        lap="1",
        location="Turn 6",
    ),
    "fia-2025-chn-c6a27ca62eb2": Case(
        "causing_collision",
        "Car 30 and Car 7 made minor contact at Turn 14 in the Sprint; the source says Car 30 had the right to the corner and took no further action.",
        affected="7",
    ),
    "fia-2025-mco-6f59e264b0c0": Case(
        "causing_collision",
        "Friday Practice 1 collision: Car 18 cut across Car 16, was wholly to blame, and caused confirmed damage; excluded by session while retaining the one-place grid penalty and point.",
        include=False,
        session="Practice 1",
        affected="16",
        exclusion_reason="out_of_scope_session",
        outcome="grid_penalty",
        points="1",
        grid="1",
        location="Turn 6",
    ),
    "fia-2025-esp-f89ab19eeac5": Case(
        "causing_collision",
        "Car 30 made minor contact with Car 87 and forced it onto the Turn 1 escape road; positions were retained and the stewards called it a racing incident.",
        affected="87",
        fault="racing_incident",
    ),
    "fia-2025-bel-91a490dae37f": Case(
        "causing_collision",
        "Qualifying document: the competitor received a pit-lane queue reprimand, while the separate driver-collision allegation ended in no further action because neither driver was predominantly to blame; collisions are outside the secondary impeding-only population.",
        include=False,
        session="Qualifying",
        affected="18",
        exclusion_reason="outside_secondary_offence_scope",
        location="Pit lane",
    ),
}


def _sha16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _single_number(value: object) -> str:
    numbers = [part.strip() for part in _clean(value).split("|") if part.strip()]
    return numbers[0] if len(numbers) == 1 else ""


def _location(value: object) -> str:
    numbers = [int(part) for part in _clean(value).split("|") if part.strip().isdigit()]
    numbers = sorted(set(numbers))
    if not numbers:
        return ""
    if len(numbers) == 1:
        return f"Turn {numbers[0]}"
    if numbers == list(range(numbers[0], numbers[-1] + 1)):
        return f"Turns {numbers[0]}-{numbers[-1]}"
    return "Turns " + ", ".join(str(number) for number in numbers)


def _session_scope(session: str) -> str:
    if session in {"Race", "Sprint"}:
        return "primary"
    if session in {"Qualifying", "Sprint Qualifying", "Sprint Shootout"}:
        return "secondary"
    return "out_of_scope"


def _value(case_value: str, row: pd.Series, source_field: str) -> str:
    return case_value if case_value else _clean(row[source_field])


def build_ledger() -> dict[str, object]:
    digest = workspace_input_sha256(WORKSPACE)
    if digest != EXPECTED_WORKSPACE_SHA256:
        raise ValueError(f"Unexpected source workspace SHA-256: {digest}")

    documents = pd.read_csv(
        WORKSPACE / "document_review_worklist.csv", dtype=str, keep_default_na=False
    ).set_index("document_id", drop=False)
    adjudications = pd.read_csv(
        WORKSPACE / "adjudication_coding_worklist.csv", dtype=str, keep_default_na=False
    ).set_index("document_id", drop=False)
    if set(CASES) - set(documents.index) or set(CASES) - set(adjudications.index):
        raise ValueError("A manual-scope ledger document is absent from the source workspace")
    if len(CASES) != 61:
        raise ValueError(f"Expected 61 manual-scope cases, found {len(CASES)}")

    document_changes: list[dict[str, object]] = []
    adjudication_changes: list[dict[str, object]] = []
    for document_id, case in CASES.items():
        document = documents.loc[document_id]
        adjudication = adjudications.loc[document_id]
        if isinstance(document, pd.DataFrame) or isinstance(adjudication, pd.DataFrame):
            raise ValueError(f"Expected one source row for {document_id}")
        session = case.session or _clean(adjudication["session_type_suggestion"])
        scope = _session_scope(session)
        exclusion_reason = "" if case.include else case.exclusion_reason
        source_note = f"Official FIA source reviewed. {case.note} Pending independent review."
        document_changes.append(
            {
                "row_id": _clean(document["document_review_id"]),
                "fields": {
                    "version_status_final": "effective",
                    "session_scope_final": scope,
                    "offence_family_final": case.family,
                    "eligibility_final": "include" if case.include else "exclude",
                    "exclusion_reason_final": exclusion_reason,
                    "reviewer_id": CODER_ID,
                    "review_status": "single_coded_pending_human",
                    "review_notes": source_note,
                },
            }
        )

        instance_id = _clean(adjudication["adjudication_instance_id"])
        adjudication_id = f"adj-{_sha16(instance_id)}" if case.include else ""
        if case.include and case.group:
            incident_id = f"incident-group-{_sha16('manual-scope-v1|' + case.group)}"
        elif case.include:
            incident_id = f"incident-src-{_sha16(instance_id)}"
        else:
            incident_id = ""
        affected = case.affected or _clean(
            adjudication["affected_driver_numbers_suggestion"]
        )
        lap = case.lap or _single_number(adjudication["lap_numbers_suggestion"])
        location = case.location or _location(adjudication["turn_numbers_suggestion"])
        adjudication_changes.append(
            {
                "row_id": instance_id,
                "fields": {
                    "adjudication_id_final": adjudication_id,
                    "incident_id_final": incident_id,
                    "accused_driver_number_final": _clean(
                        adjudication["driver_number_suggestion"]
                    ),
                    "affected_driver_numbers_final": affected,
                    "session_type_final": session,
                    "lap_number_final": lap,
                    "location_final": location,
                    "incident_family_final": case.family,
                    "outcome_family_final": _value(
                        case.outcome, adjudication, "outcome_family_suggestion"
                    ),
                    "penalty_seconds_final": _value(
                        case.seconds, adjudication, "penalty_seconds_suggestion"
                    ),
                    "penalty_points_final": _value(
                        case.points, adjudication, "penalty_points_suggestion"
                    ),
                    "grid_places_final": _value(
                        case.grid, adjudication, "grid_places_suggestion"
                    ),
                    "fault_language_final": case.fault if case.include else "not_applicable",
                    "include_primary_final": "true" if case.include else "false",
                    "include_secondary_final": "false",
                    "exclusion_reason_final": exclusion_reason,
                    "coder_id": CODER_ID,
                    "review_status": "single_coded_pending_human",
                    "coding_notes": source_note,
                },
            }
        )

    return {
        "schema_version": REVIEW_LEDGER_SCHEMA_VERSION,
        "workspace_id": WORKSPACE.name,
        "source_workspace_sha256": digest,
        "review_basis": (
            "Official FIA source-level coding of all 61 remaining manual-scope investigations, "
            "including mirrored and multi-car incident grouping. These are single-coded "
            "pending-human records, not independent review."
        ),
        "changes": {
            "documents": document_changes,
            "adjudications": adjudication_changes,
        },
    }


def main() -> None:
    ledger = build_ledger()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(CASES)} document/adjudication pairs")


if __name__ == "__main__":
    main()
