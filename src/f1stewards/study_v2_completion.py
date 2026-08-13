"""Requirement-level completion audit for the frozen Study v2 release."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from f1stewards.config import (
    PROJECT_ROOT,
    load_damage_evidence_sources,
    load_study_v2_settings,
    load_yaml,
)
from f1stewards.study_v2_review import validate_review_packet

EXPECTED_RUN_IDS = {
    "human_review": "study-v2-review-7cb1b29b5251",
    "referral": "referrals-5d0559ad2878",
    "incident_clock": "incident-clock-3dc8bb350308",
    "incident_context": "incident-context-a1de9ac2c8ea",
    "close_cases": "close-cases-36f9bc70de82",
    "damage": "damage-screening-66381b550583",
    "layers": "study-v2-layers-a9b8ff776470",
    "nationality": "nationality-diagnostic-2b1b0ffdd961",
}


def _manifest(path: Path) -> dict[str, Any]:
    return json.loads((path / "manifest.json").read_text(encoding="utf-8"))


def _notebook_executed(path: Path) -> tuple[bool, str]:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    code_cells = [cell for cell in notebook["cells"] if cell.get("cell_type") == "code"]
    missing_counts = sum(cell.get("execution_count") is None for cell in code_cells)
    error_outputs = sum(
        output.get("output_type") == "error"
        for cell in code_cells
        for output in cell.get("outputs", [])
    )
    return (
        bool(code_cells) and missing_counts == 0 and error_outputs == 0,
        f"code_cells={len(code_cells)};missing_counts={missing_counts};errors={error_outputs}",
    )


def audit_study_v2_completion(root: Path = PROJECT_ROOT) -> pd.DataFrame:
    """Return one explicit pass/fail control per Study v2 release requirement."""

    settings = load_study_v2_settings(root / "config" / "study_v2.yml")
    artifact_paths = {
        name: root / relative for name, relative in settings["release"]["artifacts"].items()
    }
    controls: list[dict[str, str]] = []

    def record(control: str, passed: bool, observed: object, expected: object) -> None:
        controls.append(
            {
                "control": control,
                "status": "pass" if passed else "fail",
                "observed": str(observed),
                "expected": str(expected),
            }
        )

    record(
        "protocol_frozen",
        settings["schema_version"] == "study_v2_v1"
        and str(settings["protocol_frozen_at"]) == "2026-08-13",
        f"{settings['schema_version']}|{settings['protocol_frozen_at']}",
        "study_v2_v1|2026-08-13",
    )
    record(
        "all_frozen_artifacts_exist",
        all(path.exists() for path in artifact_paths.values()),
        sum(path.exists() for path in artifact_paths.values()),
        len(artifact_paths),
    )
    for name, expected_run_id in EXPECTED_RUN_IDS.items():
        path = artifact_paths[name]
        manifest = _manifest(path)
        observed_run_id = manifest.get("run_id", manifest.get("packet_id"))
        record(
            f"{name}_content_addressed_run",
            path.name == expected_run_id == observed_run_id,
            f"{path.name}|{observed_run_id}",
            expected_run_id,
        )

    source_settings = load_damage_evidence_sources(root / "config" / "damage_evidence_sources.yml")
    source_seed = load_yaml(root / "config" / "damage_evidence_seed.yml")["damage_evidence_seed"][
        "records"
    ]
    record(
        "damage_source_hierarchy_registered",
        len(source_settings["registries"]) >= 10
        and all(
            str(item["base_url"]).startswith("https://") for item in source_settings["registries"]
        ),
        len(source_settings["registries"]),
        ">=10 HTTPS source registries",
    )
    record(
        "damage_seed_awaits_independent_review",
        len(source_seed) == 4
        and all(
            item["model_research_status"].endswith("pending_independent_human")
            for item in source_seed
        ),
        len(source_seed),
        "4 pending model-researched examples",
    )

    review_path = artifact_paths["human_review"]
    review_manifest = _manifest(review_path)
    review_validation = validate_review_packet(review_path)
    record(
        "blind_human_review_packet_valid",
        review_validation["status"] == "pass"
        and review_manifest["blind_to_model_final_fields"] is True
        and review_manifest["reviewer_a_rows"] == 496
        and review_manifest["reviewer_b_rows"] == 158,
        f"A={review_manifest['reviewer_a_rows']};B={review_manifest['reviewer_b_rows']}",
        "A=496;B=158;blank;blind",
    )

    referral = _manifest(artifact_paths["referral"])
    record(
        "race_control_referral_funnel_built",
        referral["episode_count"] == 966
        and referral["high_confidence_link_count"] == 174
        and referral["primary_adjudication_count"] == 346
        and referral["human_validation_complete"] is False,
        (
            f"episodes={referral['episode_count']};links={referral['high_confidence_link_count']};"
            f"cases={referral['primary_adjudication_count']}"
        ),
        "966;174;346;human validation queued",
    )

    clock = _manifest(artifact_paths["incident_clock"])
    context = _manifest(artifact_paths["incident_context"])
    record(
        "incident_clock_validation",
        clock["mapped_case_count"] == 338
        and clock["case_count"] == 346
        and clock["known_validation_case_count"] == 31
        and clock["known_validation_contained_count"] == 31,
        (
            f"mapped={clock['mapped_case_count']}/{clock['case_count']};"
            f"known={clock['known_validation_contained_count']}/"
            f"{clock['known_validation_case_count']}"
        ),
        "338/346 mapped;31/31 known laps contained",
    )
    record(
        "incident_context_enrichment_built",
        context["case_count"] == 346
        and context["new_clock_single_lap_candidates"] == 143
        and context["new_race_control_explicit_lap_candidates"] == 12
        and context["machine_context_fields_are_final"] is False,
        (
            f"cases={context['case_count']};clock={context['new_clock_single_lap_candidates']};"
            f"RC={context['new_race_control_explicit_lap_candidates']}"
        ),
        "346;143;12;pending human context review",
    )

    close = _manifest(artifact_paths["close_cases"])
    forbidden = {
        "fault_language",
        "outcome_family",
        "penalty_seconds",
        "penalty_points",
        "grid_places",
        "damage",
        "retirement",
        "finish_position",
        "sanction_outcome",
    }
    record(
        "outcome_blind_close_case_matching",
        close["case_count"] == 346
        and close["neighbor_edge_count"] == 1655
        and close["pre_review_minimum_support_count"] == 317
        and forbidden <= set(close["outcome_fields_excluded_from_primary_match"])
        and close["human_context_review_complete"] is False,
        (
            f"cases={close['case_count']};edges={close['neighbor_edge_count']};"
            f"supported={close['pre_review_minimum_support_count']}"
        ),
        "346;1655;317;outcome-blind;human review queued",
    )

    damage_path = artifact_paths["damage"]
    damage = _manifest(damage_path)
    harm_screen = pd.read_csv(damage_path / "harm_screening.csv", keep_default_na=False)
    damage_review = pd.read_csv(
        damage_path / "damage_evidence_review_worklist.csv", keep_default_na=False
    )
    record(
        "representative_collision_harm_screen",
        damage["candidate_incident_count"] == 193
        and damage["participant_record_count"] == 411
        and damage["participant_rows_with_incident_lap"] == 240
        and damage["persistent_pace_primary_eligible_rows"] == 52
        and harm_screen["damage_state"].eq("unknown").all(),
        (
            f"incidents={damage['candidate_incident_count']};participants="
            f"{damage['participant_record_count']};laps="
            f"{damage['participant_rows_with_incident_lap']};pace="
            f"{damage['persistent_pace_primary_eligible_rows']}"
        ),
        "193;411;240;52;no timing-only damage inference",
    )
    record(
        "independent_damage_review_queued",
        damage["independent_damage_review_complete"] is False
        and damage_review["independent_review_status"].eq("pending").all(),
        damage_review["independent_review_status"].value_counts().to_dict(),
        "all pending",
    )

    layers_path = artifact_paths["layers"]
    layers = _manifest(layers_path)
    layer_columns = {
        column
        for filename in (
            "conduct_layer.csv",
            "consequence_screening_layer.csv",
            "sanction_layer.csv",
        )
        for column in pd.read_csv(layers_path / filename, nrows=0).columns
    }
    composite_columns = {
        column
        for column in layer_columns
        if "composite" in column.casefold() or "fairness_score" in column.casefold()
    }
    record(
        "conduct_consequence_sanction_layers_separate",
        layers["conduct_rows"] == 346
        and layers["consequence_rows"] == 411
        and layers["sanction_rows"] == 346
        and layers["pace_screen_rows"] == 52
        and layers["pace_screen_estimable_rows"] == 28
        and not composite_columns,
        (
            f"conduct={layers['conduct_rows']};consequence={layers['consequence_rows']};"
            f"sanction={layers['sanction_rows']};pace={layers['pace_screen_estimable_rows']}"
        ),
        "346;411;346;28;no composite score",
    )
    record(
        "proportionality_gate_closed",
        layers["proportionality_release_rows"] == 0 and layers["human_review_complete"] is False,
        layers["proportionality_release_rows"],
        "0 until independent conduct and harm review",
    )

    nationality_path = artifact_paths["nationality"]
    nationality = _manifest(nationality_path)
    nationality_gate = pd.read_csv(nationality_path / "release_gate.csv").iloc[0]
    record(
        "nationality_diagnostic_gated",
        nationality["british_accused_rows"] == 44
        and nationality["formal_effect_release_gate"] is False
        and bool(nationality_gate["formal_effect_release_gate"]) is False
        and "minimum_exposed_sample_not_met" in nationality["gate_reason"]
        and "target_power_not_met" in nationality["gate_reason"],
        f"British={nationality['british_accused_rows']};{nationality['gate_reason']}",
        "44;sample and power gates fail;no adjusted effect",
    )

    sequence = settings["release"]["notebook_sequence"]
    notebook_paths = [
        next((root / "notebooks").glob(f"{number:02d}_*.ipynb")) for number in sequence
    ]
    notebook_results = [_notebook_executed(path) for path in notebook_paths]
    record(
        "notebook_sequence_executed",
        all(result[0] for result in notebook_results),
        "|".join(
            f"{path.name}:{result[1]}"
            for path, result in zip(notebook_paths, notebook_results, strict=True)
        ),
        "07-12 executed with no error outputs",
    )
    html = artifact_paths["report_html"].read_text(encoding="utf-8")
    report_markers = (
        "Study v2 progress report",
        "966 Race Control",
        "240 harm records",
        "37.8% to 53.6%",
        "No full-corpus record meets every gate yet, so the release count is zero.",
    )
    record(
        "integrated_html_report_built",
        all(marker in html for marker in report_markers),
        artifact_paths["report_html"].stat().st_size,
        "nonempty report with all phase markers",
    )

    claims = pd.read_csv(root / "reports" / "claim_ledger.csv", keep_default_na=False)
    expected_claim_status = {
        "claim-15": "study_v2_descriptive",
        "claim-16": "study_v2_validated_candidate_context",
        "claim-17": "withheld_pending_context_review",
        "claim-18": "study_v2_screening_only",
    }
    observed_claim_status = claims.set_index("claim_id")["status"].to_dict()
    record(
        "study_v2_claims_registered",
        all(
            observed_claim_status.get(key) == value for key, value in expected_claim_status.items()
        ),
        {key: observed_claim_status.get(key) for key in expected_claim_status},
        expected_claim_status,
    )

    audit = pd.DataFrame(controls)
    if audit["status"].ne("pass").any():
        failed = ", ".join(audit.loc[audit["status"].ne("pass"), "control"])
        raise ValueError(f"Study v2 completion audit failed: {failed}")
    return audit
