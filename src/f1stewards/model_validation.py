"""Event-grouped outcome validation and outcome-free nationality overlap diagnostics."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.special import expit, logit
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler


@dataclass(frozen=True)
class GroupedValidationResult:
    metrics: pd.DataFrame
    fold_audit: pd.DataFrame
    oof_predictions: pd.DataFrame
    reliability: pd.DataFrame
    leave_one_season_out: pd.DataFrame


@dataclass(frozen=True)
class OverlapDiagnosticResult:
    summary: pd.DataFrame
    feature_balance: pd.DataFrame
    support_cells: pd.DataFrame
    row_scores: pd.DataFrame


def _as_float(values: Any) -> np.ndarray:
    return np.asarray(values, dtype=float)


def _model_pipeline(
    categorical: list[str],
    numeric: list[str],
    binary: list[str],
    *,
    inverse_regularization_strength: float,
    random_seed: int,
) -> Pipeline:
    transformers: list[tuple[str, Pipeline, list[str]]] = []
    if categorical:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        (
                            "encode",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                categorical,
            )
        )
    if numeric:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            )
        )
    if binary:
        transformers.append(
            (
                "binary",
                Pipeline(
                    [
                        (
                            "numeric_cast",
                            FunctionTransformer(_as_float, feature_names_out="one-to-one"),
                        ),
                        ("impute", SimpleImputer(strategy="most_frequent")),
                    ]
                ),
                binary,
            )
        )
    if not transformers:
        raise ValueError("At least one prespecified predictor is required")
    return Pipeline(
        [
            (
                "preprocess",
                ColumnTransformer(transformers, remainder="drop"),
            ),
            (
                "model",
                LogisticRegression(
                    l1_ratio=0.0,
                    C=inverse_regularization_strength,
                    solver="lbfgs",
                    max_iter=2000,
                    random_state=random_seed,
                ),
            ),
        ]
    )


def _safe_auc(y_true: np.ndarray, prediction: np.ndarray) -> float:
    return (
        float(roc_auc_score(y_true, prediction))
        if np.unique(y_true).size == 2
        else float("nan")
    )


def _calibration(y_true: np.ndarray, prediction: np.ndarray) -> tuple[float, float]:
    clipped = np.clip(prediction, 1e-6, 1 - 1e-6)
    logit = np.log(clipped / (1 - clipped))
    design = sm.add_constant(logit, has_constant="add")
    try:
        fitted = sm.GLM(y_true, design, family=sm.families.Binomial()).fit()
    except (ValueError, np.linalg.LinAlgError):
        return float("nan"), float("nan")
    return float(fitted.params[0]), float(fitted.params[1])


def _released_population(frame: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    release_filter = spec["release_filter"]
    required = {
        release_filter,
        spec["outcome"],
        spec["validation_group"],
        "adjudication_instance_id",
        "season",
    }
    model = spec["consistency_model"]
    required.update(model["categorical_covariates"])
    required.update(model["numeric_covariates"])
    required.update(model["binary_covariates"])
    if missing := required - set(frame.columns):
        raise ValueError(f"Outcome validation fields are missing: {', '.join(sorted(missing))}")
    release_values = frame[release_filter].fillna(False).astype(bool)
    released = frame.loc[release_values].copy()
    if released.empty:
        raise ValueError(
            "No reporting-eligible labels are available; provisional suggestions cannot be "
            "used for outcome-effect estimation"
        )
    allowed_labels = {"human_reviewed_final", "model_reviewed_final"}
    if "feature_label_status" in released and not released["feature_label_status"].isin(
        allowed_labels
    ).all():
        raise ValueError("Reporting-eligible rows must use a completed, disclosed review label")
    outcome = pd.to_numeric(released[spec["outcome"]], errors="coerce")
    if outcome.isna().any() or not set(outcome.unique()).issubset({0, 1}):
        raise ValueError("Released sanction_outcome must be complete and binary")
    if outcome.nunique() != 2:
        raise ValueError("Released outcome population must contain both classes")
    released[spec["outcome"]] = outcome.astype(int)
    if released[spec["validation_group"]].isna().any():
        raise ValueError("Validation groups cannot be missing")
    return released.reset_index(drop=True)


def _reliability_table(
    y_true: np.ndarray,
    prediction: np.ndarray,
    bins: int,
) -> pd.DataFrame:
    edges = np.linspace(0, 1, bins + 1)
    frame = pd.DataFrame({"observed": y_true, "prediction": prediction})
    frame["probability_bin"] = pd.cut(
        frame["prediction"], edges, include_lowest=True, duplicates="drop"
    )
    return (
        frame.groupby("probability_bin", observed=True)
        .agg(
            rows=("observed", "size"),
            mean_predicted_probability=("prediction", "mean"),
            observed_sanction_rate=("observed", "mean"),
        )
        .reset_index()
        .assign(probability_bin=lambda value: value["probability_bin"].astype(str))
    )


def validate_released_outcome_model(
    frame: pd.DataFrame,
    spec: dict[str, Any],
) -> GroupedValidationResult:
    """Validate an L2 logistic model with strictly event-grouped out-of-fold predictions."""

    released = _released_population(frame, spec)
    model_spec = spec["consistency_model"]
    categorical = model_spec["categorical_covariates"]
    numeric = model_spec["numeric_covariates"]
    binary = model_spec["binary_covariates"]
    predictors = categorical + numeric + binary
    group_column = spec["validation_group"]
    outcome_column = spec["outcome"]
    unique_groups = released[group_column].nunique()
    n_splits = min(int(spec["validation_folds"]), unique_groups)
    if n_splits < 2:
        raise ValueError("At least two event groups are required for grouped validation")

    y = released[outcome_column].to_numpy(dtype=int)
    oof_prediction = np.full(len(released), np.nan)
    baseline_prediction = np.full(len(released), np.nan)
    fold_number = np.full(len(released), -1, dtype=int)
    fold_rows: list[dict[str, Any]] = []
    splitter = GroupKFold(n_splits=n_splits)
    for fold, (train_index, test_index) in enumerate(
        splitter.split(released[predictors], y, groups=released[group_column]), start=1
    ):
        train_y = y[train_index]
        if np.unique(train_y).size != 2:
            raise ValueError(f"Training fold {fold} contains only one outcome class")
        pipeline = _model_pipeline(
            categorical,
            numeric,
            binary,
            inverse_regularization_strength=float(
                model_spec["inverse_regularization_strength"]
            ),
            random_seed=int(spec["random_seed"]),
        )
        pipeline.fit(released.iloc[train_index][predictors], train_y)
        oof_prediction[test_index] = pipeline.predict_proba(
            released.iloc[test_index][predictors]
        )[:, 1]
        baseline_prediction[test_index] = train_y.mean()
        fold_number[test_index] = fold
        train_groups = set(released.iloc[train_index][group_column])
        test_groups = set(released.iloc[test_index][group_column])
        fold_rows.append(
            {
                "fold": fold,
                "train_rows": len(train_index),
                "test_rows": len(test_index),
                "train_events": len(train_groups),
                "test_events": len(test_groups),
                "event_overlap": len(train_groups & test_groups),
                "train_sanction_rate": float(train_y.mean()),
                "test_sanction_rate": float(y[test_index].mean()),
            }
        )
    if np.isnan(oof_prediction).any() or (fold_number < 1).any():
        raise ValueError("Grouped validation failed to produce exactly one prediction per row")

    calibration_intercept, calibration_slope = _calibration(y, oof_prediction)
    model_brier = float(brier_score_loss(y, oof_prediction))
    baseline_brier = float(brier_score_loss(y, baseline_prediction))
    metrics = pd.DataFrame(
        [
            {"metric": "rows", "value": float(len(released))},
            {"metric": "events", "value": float(unique_groups)},
            {"metric": "outcome_prevalence", "value": float(y.mean())},
            {"metric": "model_brier_score", "value": model_brier},
            {"metric": "baseline_brier_score", "value": baseline_brier},
            {
                "metric": "brier_improvement_over_baseline",
                "value": baseline_brier - model_brier,
            },
            {"metric": "model_log_loss", "value": float(log_loss(y, oof_prediction))},
            {"metric": "model_roc_auc", "value": _safe_auc(y, oof_prediction)},
            {"metric": "calibration_intercept", "value": calibration_intercept},
            {"metric": "calibration_slope", "value": calibration_slope},
        ]
    )
    oof = released[
        ["adjudication_instance_id", group_column, "season", outcome_column]
    ].copy()
    oof["fold"] = fold_number
    oof["model_probability"] = oof_prediction
    oof["baseline_probability"] = baseline_prediction

    season_rows: list[dict[str, Any]] = []
    for season in sorted(released["season"].unique()):
        train = released["season"].ne(season)
        test = ~train
        train_y = released.loc[train, outcome_column].to_numpy(dtype=int)
        test_y = released.loc[test, outcome_column].to_numpy(dtype=int)
        if np.unique(train_y).size != 2:
            season_rows.append(
                {
                    "held_out_season": season,
                    "status": "not_estimable_single_class_training",
                    "test_rows": int(test.sum()),
                }
            )
            continue
        pipeline = _model_pipeline(
            categorical,
            numeric,
            binary,
            inverse_regularization_strength=float(
                model_spec["inverse_regularization_strength"]
            ),
            random_seed=int(spec["random_seed"]),
        )
        pipeline.fit(released.loc[train, predictors], train_y)
        probability = pipeline.predict_proba(released.loc[test, predictors])[:, 1]
        season_rows.append(
            {
                "held_out_season": season,
                "status": "estimated",
                "test_rows": int(test.sum()),
                "test_sanction_rate": float(test_y.mean()),
                "brier_score": float(brier_score_loss(test_y, probability)),
                "roc_auc": _safe_auc(test_y, probability),
            }
        )
    return GroupedValidationResult(
        metrics=metrics,
        fold_audit=pd.DataFrame(fold_rows),
        oof_predictions=oof,
        reliability=_reliability_table(
            y, oof_prediction, int(model_spec["calibration_bins"])
        ),
        leave_one_season_out=pd.DataFrame(season_rows),
    )


def _design_matrix(
    frame: pd.DataFrame,
    categorical: list[str],
    numeric: list[str],
    binary: list[str],
    *,
    drop_first: bool = False,
) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    if categorical:
        parts.append(
            pd.get_dummies(
                frame[categorical].fillna("<missing>").astype(str),
                prefix=categorical,
                dtype=float,
                drop_first=drop_first,
            )
        )
    if numeric:
        numeric_frame = frame[numeric].apply(pd.to_numeric, errors="coerce")
        numeric_frame = numeric_frame.fillna(numeric_frame.median())
        parts.append(numeric_frame.astype(float))
    if binary:
        parts.append(frame[binary].fillna(False).astype(bool).astype(float))
    if not parts:
        raise ValueError("Overlap diagnostics require at least one covariate")
    matrix = pd.concat(parts, axis=1)
    if matrix.columns.duplicated().any():
        raise ValueError("Encoded overlap covariate names are not unique")
    return matrix


def _weighted_mean_variance(
    values: np.ndarray,
    weights: np.ndarray,
) -> tuple[float, float]:
    total = weights.sum()
    if total <= 0:
        return float("nan"), float("nan")
    mean = float(np.sum(weights * values) / total)
    variance = float(np.sum(weights * (values - mean) ** 2) / total)
    return mean, variance


def _smd(
    values: np.ndarray,
    exposure: np.ndarray,
    weights: np.ndarray,
) -> float:
    treated = exposure == 1
    control = exposure == 0
    mean_t, variance_t = _weighted_mean_variance(values[treated], weights[treated])
    mean_c, variance_c = _weighted_mean_variance(values[control], weights[control])
    denominator = np.sqrt((variance_t + variance_c) / 2)
    difference = mean_t - mean_c
    if denominator == 0:
        return 0.0 if difference == 0 else float("inf")
    return float(difference / denominator)


def _effective_sample_size(weights: np.ndarray) -> float:
    denominator = np.sum(weights**2)
    return float(np.sum(weights) ** 2 / denominator) if denominator > 0 else 0.0


def nationality_overlap_diagnostics(
    frame: pd.DataFrame,
    spec: dict[str, Any],
) -> OverlapDiagnosticResult:
    """Diagnose British-accused support without reading or modeling sanction outcomes."""

    model_spec = spec["nationality_model"]
    exposure_column = model_spec["primary_exposure"]
    categorical = model_spec["categorical_covariates"]
    numeric = model_spec["numeric_covariates"]
    binary = model_spec["binary_covariates"]
    identifier_columns = ["adjudication_instance_id", "event_id", "season"]
    required = {exposure_column, *identifier_columns, *categorical, *numeric, *binary}
    if missing := required - set(frame.columns):
        raise ValueError(f"Overlap fields are missing: {', '.join(sorted(missing))}")
    analysis = frame.loc[frame[exposure_column].notna()].copy().reset_index(drop=True)
    exposure = analysis[exposure_column].astype(bool).astype(int).to_numpy()
    if np.unique(exposure).size != 2:
        raise ValueError("Nationality overlap requires both exposed and unexposed rows")
    matrix = _design_matrix(analysis, categorical, numeric, binary)
    scaled = StandardScaler().fit_transform(matrix)
    model = LogisticRegression(
        l1_ratio=0.0,
        C=1.0,
        solver="lbfgs",
        max_iter=2000,
        random_state=int(spec["random_seed"]),
    ).fit(scaled, exposure)
    raw_propensity = model.predict_proba(scaled)[:, 1]
    clip_low, clip_high = map(float, model_spec["propensity_clip"])
    propensity = np.clip(raw_propensity, clip_low, clip_high)
    overlap_weights = np.where(exposure == 1, 1 - propensity, propensity)
    treated = exposure == 1
    control = exposure == 0
    lower_support = max(float(propensity[treated].min()), float(propensity[control].min()))
    upper_support = min(float(propensity[treated].max()), float(propensity[control].max()))
    in_common_support = (
        (propensity >= lower_support) & (propensity <= upper_support)
        if lower_support <= upper_support
        else np.zeros(len(propensity), dtype=bool)
    )
    balance_rows = []
    unit_weights = np.ones(len(analysis))
    for column in matrix.columns:
        values = matrix[column].to_numpy(dtype=float)
        balance_rows.append(
            {
                "feature": column,
                "smd_unweighted": _smd(values, exposure, unit_weights),
                "smd_overlap_weighted": _smd(values, exposure, overlap_weights),
            }
        )
    balance = pd.DataFrame(balance_rows)
    max_unweighted = float(balance["smd_unweighted"].abs().max())
    max_weighted = float(balance["smd_overlap_weighted"].abs().max())
    summary = pd.DataFrame(
        [
            {
                "rows": len(analysis),
                "events": analysis["event_id"].nunique(),
                "exposed_rows": int(treated.sum()),
                "unexposed_rows": int(control.sum()),
                "exposure_prevalence": float(exposure.mean()),
                "propensity_auc": _safe_auc(exposure, raw_propensity),
                "propensity_min": float(propensity.min()),
                "propensity_max": float(propensity.max()),
                "common_support_lower": lower_support,
                "common_support_upper": upper_support,
                "common_support_fraction": float(in_common_support.mean()),
                "overlap_weight_ess_exposed": _effective_sample_size(
                    overlap_weights[treated]
                ),
                "overlap_weight_ess_unexposed": _effective_sample_size(
                    overlap_weights[control]
                ),
                "max_abs_smd_unweighted": max_unweighted,
                "max_abs_smd_overlap_weighted": max_weighted,
                "extreme_raw_propensity_rows": int(
                    ((raw_propensity < clip_low) | (raw_propensity > clip_high)).sum()
                ),
                "interpretation_status": "design_diagnostic_not_effect_estimate",
            }
        ]
    )
    row_scores = analysis[identifier_columns + [exposure_column]].copy()
    row_scores["propensity_score_raw"] = raw_propensity
    row_scores["propensity_score_clipped"] = propensity
    row_scores["overlap_weight"] = overlap_weights
    row_scores["in_common_support"] = in_common_support
    support_rows: list[dict[str, Any]] = []
    for dimension in categorical + binary:
        values = analysis[dimension].fillna("<missing>").astype(str)
        for level in sorted(values.unique()):
            selected = values.eq(level).to_numpy()
            exposed_rows = int(exposure[selected].sum())
            total_rows = int(selected.sum())
            support_rows.append(
                {
                    "dimension": dimension,
                    "level": level,
                    "rows": total_rows,
                    "exposed_rows": exposed_rows,
                    "unexposed_rows": total_rows - exposed_rows,
                    "exposure_prevalence": exposed_rows / total_rows,
                    "both_exposure_groups_present": 0 < exposed_rows < total_rows,
                }
            )
    return OverlapDiagnosticResult(
        summary=summary,
        feature_balance=balance.sort_values(
            "smd_overlap_weighted", key=lambda values: values.abs(), ascending=False
        ).reset_index(drop=True),
        support_cells=pd.DataFrame(support_rows),
        row_scores=row_scores,
    )


def simulate_nationality_power(
    frame: pd.DataFrame,
    spec: dict[str, Any],
    *,
    repetitions: int | None = None,
) -> pd.DataFrame:
    """Simulate cluster-robust detection power without reading observed sanction outcomes."""

    model_spec = spec["nationality_model"]
    simulation = model_spec["simulation_power"]
    exposure_column = model_spec["primary_exposure"]
    categorical = model_spec["categorical_covariates"]
    numeric = model_spec["numeric_covariates"]
    binary = model_spec["binary_covariates"]
    required = {exposure_column, "event_id", *categorical, *numeric, *binary}
    if missing := required - set(frame.columns):
        raise ValueError(f"Power-simulation fields are missing: {', '.join(sorted(missing))}")
    analysis = frame.loc[frame[exposure_column].notna()].copy().reset_index(drop=True)
    exposure = analysis[exposure_column].astype(bool).astype(int).to_numpy()
    if np.unique(exposure).size != 2:
        raise ValueError("Power simulation requires both exposed and unexposed rows")
    matrix = _design_matrix(
        analysis,
        categorical,
        numeric,
        binary,
        drop_first=True,
    )
    matrix.insert(0, exposure_column, exposure.astype(float))
    matrix = matrix.loc[:, matrix.nunique(dropna=False).gt(1)]
    if exposure_column not in matrix:
        raise ValueError("Nationality exposure has no variation after design-matrix construction")
    design = sm.add_constant(matrix, has_constant="add")
    event_codes, event_levels = pd.factorize(analysis["event_id"], sort=True)
    if len(event_levels) < 2:
        raise ValueError("Cluster-robust simulation requires at least two events")
    scenario_repetitions = repetitions or int(simulation["repetitions"])
    if scenario_repetitions < 1:
        raise ValueError("Simulation repetitions must be positive")
    alpha = float(simulation["alpha"])
    minimum_successful_fit_fraction = float(
        simulation["minimum_successful_fit_fraction"]
    )
    target_power = float(simulation["target_power"])
    random_effect_sd = float(simulation["event_random_intercept_sd"])
    master_seed = int(spec["random_seed"])
    rows: list[dict[str, Any]] = []
    for baseline_index, baseline in enumerate(simulation["baseline_probabilities"]):
        baseline = float(baseline)
        for effect_index, risk_difference in enumerate(
            simulation["target_risk_differences"]
        ):
            risk_difference = float(risk_difference)
            exposure_log_odds = float(
                logit(baseline + risk_difference) - logit(baseline)
            )
            rng = np.random.default_rng(
                master_seed + baseline_index * 10_000 + effect_index * 1_000
            )
            detected = 0
            successful = 0
            estimates: list[float] = []
            standard_errors: list[float] = []
            for _ in range(scenario_repetitions):
                event_effect = rng.normal(0, random_effect_sd, size=len(event_levels))
                probability = expit(
                    logit(baseline)
                    + exposure_log_odds * exposure
                    + event_effect[event_codes]
                )
                outcome = rng.binomial(1, probability)
                if np.unique(outcome).size != 2:
                    continue
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        fitted = sm.GLM(
                            outcome,
                            design,
                            family=sm.families.Binomial(),
                        ).fit(
                            cov_type="cluster",
                            cov_kwds={"groups": event_codes},
                            disp=0,
                        )
                    estimate = float(fitted.params[exposure_column])
                    standard_error = float(fitted.bse[exposure_column])
                    p_value = float(fitted.pvalues[exposure_column])
                except (ValueError, np.linalg.LinAlgError, KeyError):
                    continue
                if not all(np.isfinite([estimate, standard_error, p_value])):
                    continue
                successful += 1
                estimates.append(estimate)
                standard_errors.append(standard_error)
                detected += int(p_value < alpha and np.sign(estimate) == np.sign(exposure_log_odds))
            power = detected / scenario_repetitions
            successful_fit_fraction = successful / scenario_repetitions
            rows.append(
                {
                    "baseline_probability": baseline,
                    "target_risk_difference": risk_difference,
                    "target_exposure_log_odds": exposure_log_odds,
                    "repetitions": scenario_repetitions,
                    "successful_fits": successful,
                    "successful_fit_fraction": successful_fit_fraction,
                    "simulation_fit_status": (
                        "stable"
                        if successful_fit_fraction >= minimum_successful_fit_fraction
                        else "unstable"
                    ),
                    "detection_power": power,
                    "target_power": target_power,
                    "power_target_met": power >= target_power,
                    "monte_carlo_standard_error": float(
                        np.sqrt(power * (1 - power) / scenario_repetitions)
                    ),
                    "median_estimated_log_odds": (
                        float(np.median(estimates)) if estimates else float("nan")
                    ),
                    "median_cluster_robust_se": (
                        float(np.median(standard_errors))
                        if standard_errors
                        else float("nan")
                    ),
                    "exposed_rows": int(exposure.sum()),
                    "unexposed_rows": int((1 - exposure).sum()),
                    "event_clusters": len(event_levels),
                    "event_random_intercept_sd": random_effect_sd,
                    "interpretation_status": "design_simulation_not_effect_estimate",
                }
            )
    return pd.DataFrame(rows)
