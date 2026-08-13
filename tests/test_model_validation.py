import numpy as np
import pandas as pd
import pytest

from f1stewards.config import load_outcome_model_spec
from f1stewards.model_validation import (
    nationality_overlap_diagnostics,
    simulate_nationality_power,
    validate_released_outcome_model,
)


def synthetic_population() -> pd.DataFrame:
    rng = np.random.default_rng(20260812)
    rows = []
    families = ["causing_collision", "forcing_off_track", "unsafe_rejoin"]
    for event in range(32):
        for within_event in range(4):
            family = families[(event + within_event) % len(families)]
            season = 2018 + event % 8
            multi_party = within_event == 3
            british_probability = 0.08 + 0.12 * (family == "causing_collision")
            british = bool(rng.random() < british_probability)
            home_race = bool(british and event % 6 == 0)
            linear = (
                -0.4
                + 0.65 * (family == "causing_collision")
                + 0.25 * multi_party
                + 0.1 * (season >= 2022)
            )
            outcome = bool(rng.random() < 1 / (1 + np.exp(-linear)))
            rows.append(
                {
                    "adjudication_instance_id": f"event-{event:02d}-{within_event}",
                    "event_id": f"event-{event:02d}",
                    "season": season,
                    "guideline_regime": (
                        "published_guidance" if season == 2025 else "earlier_regime"
                    ),
                    "incident_family": family,
                    "multi_party": multi_party,
                    "british_accused_driver": british,
                    "home_race_accused": home_race,
                    "sanction_outcome": outcome,
                    "reporting_eligible": True,
                    "feature_label_status": "human_reviewed_final",
                }
            )
    frame = pd.DataFrame(rows)
    assert frame["sanction_outcome"].nunique() == 2
    assert frame["british_accused_driver"].nunique() == 2
    return frame


def test_event_grouped_validation_has_no_fold_leakage() -> None:
    result = validate_released_outcome_model(
        synthetic_population(), load_outcome_model_spec()
    )

    assert len(result.oof_predictions) == 128
    assert result.oof_predictions["adjudication_instance_id"].is_unique
    assert result.fold_audit["event_overlap"].eq(0).all()
    assert result.fold_audit["fold"].nunique() == 5
    assert set(result.metrics["metric"]) >= {
        "model_brier_score",
        "baseline_brier_score",
        "calibration_intercept",
        "calibration_slope",
    }
    assert len(result.leave_one_season_out) == 8
    assert result.reliability["rows"].sum() == 128


def test_outcome_validation_rejects_provisional_population() -> None:
    frame = synthetic_population()
    frame["reporting_eligible"] = False
    frame["feature_label_status"] = "provisional_machine_suggestion"

    with pytest.raises(ValueError, match="No reporting-eligible labels"):
        validate_released_outcome_model(frame, load_outcome_model_spec())


def test_nationality_overlap_is_outcome_free_and_returns_role_support() -> None:
    frame = synthetic_population().drop(columns="sanction_outcome")
    result = nationality_overlap_diagnostics(frame, load_outcome_model_spec())
    summary = result.summary.iloc[0]

    assert summary["rows"] == 128
    assert summary["exposed_rows"] + summary["unexposed_rows"] == 128
    assert 0 <= summary["common_support_fraction"] <= 1
    assert summary["overlap_weight_ess_exposed"] > 0
    assert summary["overlap_weight_ess_unexposed"] > 0
    assert summary["interpretation_status"] == "design_diagnostic_not_effect_estimate"
    assert len(result.row_scores) == 128
    assert result.row_scores["overlap_weight"].between(0, 1).all()
    assert set(result.feature_balance) == {
        "feature",
        "smd_unweighted",
        "smd_overlap_weighted",
    }
    assert set(result.support_cells["dimension"]) == {
        "incident_family",
        "season",
        "multi_party",
        "home_race_accused",
    }


def test_nationality_power_simulation_is_outcome_free_and_scenario_complete() -> None:
    frame = synthetic_population().drop(columns="sanction_outcome")
    result = simulate_nationality_power(
        frame,
        load_outcome_model_spec(),
        repetitions=10,
    )

    assert len(result) == 8
    assert result["repetitions"].eq(10).all()
    assert result["detection_power"].between(0, 1).all()
    assert result["successful_fit_fraction"].between(0, 1).all()
    assert result["simulation_fit_status"].isin({"stable", "unstable"}).all()
    assert result["target_power"].eq(0.8).all()
    assert result["power_target_met"].isin({True, False}).all()
    assert result["event_clusters"].eq(32).all()
    assert result["interpretation_status"].eq(
        "design_simulation_not_effect_estimate"
    ).all()
