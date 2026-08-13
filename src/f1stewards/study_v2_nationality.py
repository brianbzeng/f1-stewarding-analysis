"""Gated Study v2 nationality diagnostics; no bias effect is released when gates fail."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from f1stewards.config import (
    PROJECT_ROOT,
    load_outcome_model_spec,
    load_study_v2_settings,
)
from f1stewards.model_validation import (
    nationality_overlap_diagnostics,
    simulate_nationality_power,
)
from f1stewards.study_v2_review import DEFAULT_DATABASE

DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "manual" / "study_v2_nationality"


@dataclass(frozen=True)
class NationalityDiagnosticBuild:
    run_id: str
    output_dir: Path
    rows: int
    british_rows: int
    release_gate_passed: bool


def evaluate_nationality_gate(
    *,
    british_rows: int,
    minimum_british_rows: int,
    overlap_status: str,
    target_power: float,
    human_review_complete: bool,
) -> tuple[bool, str]:
    reasons: list[str] = []
    if british_rows < minimum_british_rows:
        reasons.append("minimum_exposed_sample_not_met")
    if overlap_status not in {"adequate", "usable_overlap"}:
        reasons.append("overlap_gate_not_met")
    if target_power < 0.80:
        reasons.append("target_power_not_met")
    if not human_review_complete:
        reasons.append("independent_human_review_incomplete")
    return not reasons, "|".join(reasons) if reasons else "all_prespecified_gates_pass"


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    stream = io.StringIO(newline="")
    frame.to_csv(stream, index=False, lineterminator="\n")
    return stream.getvalue().encode("utf-8")


def build_nationality_diagnostic(
    *,
    database_path: Path = DEFAULT_DATABASE,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> NationalityDiagnosticBuild:
    with duckdb.connect(str(database_path), read_only=True) as connection:
        features = connection.execute(
            "SELECT * FROM analysis.v_latest_adjudication_features "
            "WHERE reporting_eligible ORDER BY event_id, adjudication_instance_id"
        ).fetchdf()
    spec = load_outcome_model_spec()
    settings = load_study_v2_settings()["nationality"]
    descriptive = (
        features.groupby("british_accused_driver", dropna=False)
        .agg(cases=("sanction_outcome", "size"), sanctions=("sanction_outcome", "sum"))
        .reset_index()
    )
    descriptive["group"] = descriptive["british_accused_driver"].map(
        {True: "British accused driver", False: "Other accused driver"}
    )
    descriptive["sanction_rate"] = descriptive["sanctions"] / descriptive["cases"]
    design = features.drop(columns=["sanction_outcome"])
    overlap = nationality_overlap_diagnostics(design, spec)
    power = simulate_nationality_power(design, spec)
    target_difference = float(settings["target_risk_difference"])
    target_rows = power.loc[power["target_risk_difference"].eq(target_difference)]
    target_power = float(target_rows["detection_power"].min())
    british_rows = int(features["british_accused_driver"].fillna(False).sum())
    overlap_summary = overlap.summary.iloc[0]
    overlap_usable = (
        float(overlap_summary["common_support_fraction"])
        >= float(settings["minimum_common_support_fraction"])
        and float(overlap_summary["max_abs_smd_overlap_weighted"])
        <= float(settings["maximum_weighted_abs_smd"])
        and float(overlap_summary["overlap_weight_ess_exposed"])
        >= float(settings["minimum_exposed_effective_sample_size"])
    )
    overlap_status = "usable_overlap" if overlap_usable else "overlap_gate_not_met"
    gate, reason = evaluate_nationality_gate(
        british_rows=british_rows,
        minimum_british_rows=int(settings["minimum_british_accused_cases"]),
        overlap_status=overlap_status,
        target_power=target_power,
        human_review_complete=False,
    )
    gate_frame = pd.DataFrame(
        [
            {
                "rows": len(features),
                "british_accused_rows": british_rows,
                "minimum_british_accused_rows": int(settings["minimum_british_accused_cases"]),
                "target_risk_difference": target_difference,
                "minimum_power_at_target_difference": target_power,
                "overlap_status": overlap_status,
                "minimum_common_support_fraction": settings["minimum_common_support_fraction"],
                "maximum_weighted_abs_smd": settings["maximum_weighted_abs_smd"],
                "minimum_exposed_effective_sample_size": settings[
                    "minimum_exposed_effective_sample_size"
                ],
                "independent_human_review_complete": False,
                "formal_effect_release_gate": gate,
                "gate_reason": reason,
                "interpretation": "descriptive_and_design_diagnostics_only",
            }
        ]
    )
    digest = hashlib.sha256(
        _csv_bytes(descriptive)
        + _csv_bytes(overlap.summary)
        + _csv_bytes(power)
        + _csv_bytes(gate_frame)
    ).hexdigest()[:12]
    run_id = f"nationality-diagnostic-{digest}"
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    descriptive.to_csv(output_dir / "descriptive_rates.csv", index=False)
    overlap.summary.to_csv(output_dir / "overlap_summary.csv", index=False)
    overlap.feature_balance.to_csv(output_dir / "feature_balance.csv", index=False)
    overlap.support_cells.to_csv(output_dir / "support_cells.csv", index=False)
    power.to_csv(output_dir / "simulation_power.csv", index=False)
    gate_frame.to_csv(output_dir / "release_gate.csv", index=False)
    manifest = {
        "schema_version": "study-v2-nationality-diagnostic-v1",
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "rows": len(features),
        "british_accused_rows": british_rows,
        "formal_effect_release_gate": gate,
        "gate_reason": reason,
        "multiplicity_method_if_gate_passes": settings["multiplicity_method"],
        "release_status": "inconclusive_design_gate",
        "guardrail": (
            "The observed outcome is used only for transparent descriptive rates. Overlap and "
            "power diagnostics are outcome-free, and no adjusted nationality effect is fitted or "
            "released while the prespecified gate fails."
        ),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return NationalityDiagnosticBuild(
        run_id=run_id,
        output_dir=output_dir,
        rows=len(features),
        british_rows=british_rows,
        release_gate_passed=gate,
    )
