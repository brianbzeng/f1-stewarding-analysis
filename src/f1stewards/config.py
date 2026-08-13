"""Configuration loading with validation."""

from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from f1stewards.models import (
    DocumentClass,
    InternationalSportingCodeIssue,
    PilotEvent,
    RegulatorySource,
    SportingRegulationIssue,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return payload


def load_pilot_events(path: Path | None = None) -> list[PilotEvent]:
    config_path = path or PROJECT_ROOT / "config" / "pilot_events.yml"
    payload = load_yaml(config_path)
    events = payload.get("pilot_events")
    if not isinstance(events, list):
        raise ValueError(f"Missing pilot_events list in {config_path}")
    return [PilotEvent.model_validate(event) for event in events]


def load_full_collection_settings(path: Path | None = None) -> dict[str, Any]:
    config_path = path or PROJECT_ROOT / "config" / "full_collection.yml"
    payload = load_yaml(config_path)
    settings = payload.get("full_collection")
    if not isinstance(settings, dict):
        raise ValueError(f"Missing full_collection mapping in {config_path}")
    seasons = settings.get("completed_seasons")
    if seasons != list(range(2018, 2026)):
        raise ValueError("Full collection must cover completed seasons 2018 through 2025")
    expected = settings.get("expected_event_counts")
    if not isinstance(expected, dict) or {int(year) for year in expected} != set(seasons):
        raise ValueError("Expected event counts must cover every study season")
    return settings


def load_full_corpus_coding_settings(path: Path | None = None) -> dict[str, Any]:
    """Load and validate the frozen machine-suggestion rules for full-corpus coding."""

    config_path = path or PROJECT_ROOT / "config" / "full_corpus_coding.yml"
    payload = load_yaml(config_path)
    settings = payload.get("full_corpus_coding")
    if not isinstance(settings, dict):
        raise ValueError(f"Missing full_corpus_coding mapping in {config_path}")

    required = {
        "schema_version",
        "source_document_class",
        "exclusion_quality_control",
        "primary_sessions",
        "secondary_sessions",
        "primary_incident_patterns",
        "secondary_incident_patterns",
        "excluded_offence_patterns",
    }
    if missing := required - set(settings):
        raise ValueError(f"Full-corpus coding settings are missing: {', '.join(sorted(missing))}")

    expected_primary = {
        "causing_collision",
        "forcing_off_track",
        "gaining_advantage_off_track",
        "unsafe_rejoin",
        "moving_under_braking",
        "multiple_defensive_moves",
    }
    primary_patterns = settings["primary_incident_patterns"]
    if not isinstance(primary_patterns, dict) or set(primary_patterns) != expected_primary:
        raise ValueError("Primary incident patterns must match the frozen protocol families")
    for group_name in (
        "primary_incident_patterns",
        "secondary_incident_patterns",
        "excluded_offence_patterns",
    ):
        group = settings[group_name]
        if not isinstance(group, dict) or not group:
            raise ValueError(f"{group_name} must be a non-empty mapping")
        for family, patterns in group.items():
            if (
                not isinstance(patterns, list)
                or not patterns
                or not all(isinstance(pattern, str) and pattern for pattern in patterns)
            ):
                raise ValueError(f"{group_name}.{family} must contain regex strings")
            for pattern in patterns:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    raise ValueError(
                        f"{group_name}.{family} contains invalid regex {pattern!r}"
                    ) from exc

    primary_sessions = settings["primary_sessions"]
    secondary_sessions = settings["secondary_sessions"]
    if primary_sessions != ["Race", "Sprint"]:
        raise ValueError("Primary sessions must remain Race and Sprint")
    if not isinstance(secondary_sessions, list) or "Qualifying" not in secondary_sessions:
        raise ValueError("Secondary sessions must include Qualifying")
    qa = settings["exclusion_quality_control"]
    if not isinstance(qa, dict):
        raise ValueError("exclusion_quality_control must be a mapping")
    qa_required = {
        "target_fraction",
        "minimum_per_stratum",
        "maximum_per_stratum",
        "hash_salt",
    }
    if missing := qa_required - set(qa):
        raise ValueError(
            f"Exclusion quality-control settings are missing: {', '.join(sorted(missing))}"
        )
    if not 0 < qa["target_fraction"] <= 1:
        raise ValueError("Exclusion QA target_fraction must be in (0, 1]")
    if not 1 <= qa["minimum_per_stratum"] <= qa["maximum_per_stratum"]:
        raise ValueError("Exclusion QA stratum bounds are invalid")
    if not isinstance(qa["hash_salt"], str) or not qa["hash_salt"]:
        raise ValueError("Exclusion QA hash_salt must be non-empty")
    return settings


def load_study_events(path: Path | None = None) -> list[PilotEvent]:
    catalog_path = path or PROJECT_ROOT / "config" / "study_events.csv"
    if not catalog_path.exists():
        raise FileNotFoundError(
            f"Study event catalog not found at {catalog_path}; run build-study-catalog"
        )
    with catalog_path.open(encoding="utf-8-sig", newline="") as stream:
        raw_records = list(csv.DictReader(stream))
    records: list[PilotEvent] = []
    for raw in raw_records:
        record: dict[str, Any] = {
            key: (None if value == "" else value) for key, value in raw.items()
        }
        for key in ("season", "round_number"):
            if record.get(key) is not None:
                record[key] = int(record[key])
        for key in ("has_sprint", "is_pilot"):
            if record.get(key) is not None:
                record[key] = str(record[key]).casefold() == "true"
        records.append(PilotEvent.model_validate(record))
    ids = [event.pilot_id for event in records]
    rounds = [(event.season, event.round_number) for event in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate event id in {catalog_path}")
    if len(rounds) != len(set(rounds)):
        raise ValueError(f"Duplicate season/round in {catalog_path}")
    return records


def load_document_classes(path: Path | None = None) -> dict[str, dict[str, list[str]]]:
    config_path = path or PROJECT_ROOT / "config" / "document_classes.yml"
    payload = load_yaml(config_path)
    classes = payload.get("classes")
    if not isinstance(classes, dict):
        raise ValueError(f"Missing classes mapping in {config_path}")
    return classes


def load_evidence_profiles(path: Path | None = None) -> dict[str, set[DocumentClass]]:
    config_path = path or PROJECT_ROOT / "config" / "evidence_profiles.yml"
    payload = load_yaml(config_path)
    raw_profiles = payload.get("evidence_profiles")
    if not isinstance(raw_profiles, dict) or not raw_profiles:
        raise ValueError(f"Missing evidence_profiles mapping in {config_path}")
    profiles: dict[str, set[DocumentClass]] = {}
    for name, raw_profile in raw_profiles.items():
        if not isinstance(raw_profile, dict):
            raise ValueError(f"Evidence profile {name} must be a mapping")
        raw_classes = raw_profile.get("document_classes")
        if not isinstance(raw_classes, list) or not raw_classes:
            raise ValueError(f"Evidence profile {name} requires document_classes")
        try:
            profiles[str(name)] = {DocumentClass(value) for value in raw_classes}
        except ValueError as exc:
            raise ValueError(f"Evidence profile {name} contains an unknown class") from exc
    return profiles


def load_retrieval_exceptions(path: Path | None = None) -> dict[str, dict[str, str]]:
    config_path = path or PROJECT_ROOT / "config" / "retrieval_exceptions.yml"
    payload = load_yaml(config_path)
    raw_exceptions = payload.get("retrieval_exceptions")
    if not isinstance(raw_exceptions, list):
        raise ValueError(f"Missing retrieval_exceptions list in {config_path}")
    exceptions: dict[str, dict[str, str]] = {}
    for raw in raw_exceptions:
        if not isinstance(raw, dict):
            raise ValueError("Each retrieval exception must be a mapping")
        required = {
            "event_id",
            "document_url",
            "source_availability_status",
            "verified_at",
            "note",
        }
        if missing := required - set(raw):
            raise ValueError(f"Retrieval exception is missing: {', '.join(sorted(missing))}")
        url = str(raw["document_url"])
        if url in exceptions:
            raise ValueError(f"Duplicate retrieval exception URL: {url}")
        if raw["source_availability_status"] != "verified_unavailable":
            raise ValueError("Retrieval exceptions must be verified_unavailable")
        exceptions[url] = {key: str(raw[key]) for key in required - {"document_url"}}
    return exceptions


def load_document_lineage(path: Path | None = None) -> dict[str, dict[str, str]]:
    config_path = path or PROJECT_ROOT / "config" / "document_lineage.yml"
    payload = load_yaml(config_path)
    raw_links = payload.get("lineage_links")
    if not isinstance(raw_links, list):
        raise ValueError(f"Missing lineage_links list in {config_path}")
    links: dict[str, dict[str, str]] = {}
    predecessors: set[str] = set()
    required = {
        "event_id",
        "predecessor_document_id",
        "successor_document_id",
        "verified_at",
        "note",
    }
    for raw in raw_links:
        if not isinstance(raw, dict):
            raise ValueError("Each document-lineage link must be a mapping")
        if missing := required - set(raw):
            raise ValueError(f"Document-lineage link is missing: {', '.join(sorted(missing))}")
        successor = str(raw["successor_document_id"])
        predecessor = str(raw["predecessor_document_id"])
        if successor in links:
            raise ValueError(f"Duplicate lineage successor: {successor}")
        if predecessor in predecessors:
            raise ValueError(f"Duplicate lineage predecessor: {predecessor}")
        if successor == predecessor:
            raise ValueError("A document cannot supersede itself")
        links[successor] = {key: str(raw[key]) for key in required - {"successor_document_id"}}
        predecessors.add(predecessor)
    return links


def load_regulatory_sources(path: Path | None = None) -> list[RegulatorySource]:
    config_path = path or PROJECT_ROOT / "config" / "regulatory_sources.yml"
    payload = load_yaml(config_path)
    sources = payload.get("regulatory_sources")
    if not isinstance(sources, list):
        raise ValueError(f"Missing regulatory_sources list in {config_path}")
    records = [RegulatorySource.model_validate(source) for source in sources]
    source_ids = [record.source_id for record in records]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError(f"Duplicate source_id in {config_path}")
    known_events = {event.pilot_id for event in load_pilot_events()}
    unknown_events = sorted(
        {event_id for record in records for event_id in record.event_ids} - known_events
    )
    if unknown_events:
        raise ValueError(f"Unknown event_ids in {config_path}: {', '.join(unknown_events)}")
    return records


def load_analysis_thresholds(path: Path | None = None) -> dict[str, Any]:
    config_path = path or PROJECT_ROOT / "config" / "analysis_thresholds.yml"
    payload = load_yaml(config_path)
    thresholds = payload.get("analysis_thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError(f"Missing analysis_thresholds mapping in {config_path}")
    required = {
        "pilot_scale",
        "release",
        "consistency",
        "guideline_conformance",
        "nationality",
        "competitive_impact",
        "evidence_explorer",
    }
    missing = required - set(thresholds)
    if missing:
        raise ValueError(f"Missing threshold sections: {', '.join(sorted(missing))}")
    mappable = thresholds["guideline_conformance"].get("minimum_mappable_fraction")
    agreement = thresholds["guideline_conformance"].get("minimum_independent_agreement")
    valid_fractions = all(
        isinstance(value, float | int) and 0 <= value <= 1 for value in [mappable, agreement]
    )
    if not valid_fractions:
        raise ValueError("Guideline threshold fractions must be between zero and one")
    return thresholds


def load_study_v2_settings(path: Path | None = None) -> dict[str, Any]:
    """Load the frozen Study v2 design and enforce its anti-circularity safeguards."""

    config_path = path or PROJECT_ROOT / "config" / "study_v2.yml"
    payload = load_yaml(config_path)
    settings = payload.get("study_v2")
    if not isinstance(settings, dict):
        raise ValueError(f"Missing study_v2 mapping in {config_path}")

    required = {
        "schema_version",
        "protocol_frozen_at",
        "study_seasons",
        "parent_model_review_run",
        "parent_feature_build",
        "estimands",
        "human_review",
        "referral_funnel",
        "incident_timing",
        "close_case_matching",
        "damage_harm",
        "nationality",
        "release",
    }
    if missing := required - set(settings):
        raise ValueError(f"Study v2 settings are missing: {', '.join(sorted(missing))}")
    if settings["schema_version"] != "study_v2_v1":
        raise ValueError("Study v2 schema_version must remain study_v2_v1")
    if settings["study_seasons"] != list(range(2018, 2026)):
        raise ValueError("Study v2 must cover completed seasons 2018 through 2025")

    estimands = settings["estimands"]
    expected_estimands = {
        "conduct_consistency",
        "consequence_burden",
        "sanction_burden",
        "distributive_fairness",
    }
    if not isinstance(estimands, dict) or set(estimands) != expected_estimands:
        raise ValueError("Study v2 estimands must keep the four frozen analytical layers")
    if (
        estimands["conduct_consistency"].get("exclude_post_incident_harm_from_predictors")
        is not True
    ):
        raise ValueError("Conduct models must exclude post-incident harm predictors")
    fairness = estimands["distributive_fairness"]
    if any(
        fairness.get(field) is not True
        for field in (
            "prohibit_composite_fairness_score",
            "require_fault_established",
            "require_reviewed_harm_evidence",
        )
    ):
        raise ValueError("Distributive-fairness safeguards cannot be relaxed")

    review = settings["human_review"]
    if review.get("blind_to_model_final_fields") is not True:
        raise ValueError("Study v2 human review must remain blind to model final fields")
    if review.get("sample_review_does_not_upgrade_entire_corpus") is not True:
        raise ValueError("Sample review cannot upgrade the entire corpus")
    if review.get("disagreement_requires_reconciliation") is not True:
        raise ValueError("Human-review disagreements must require reconciliation")
    if not isinstance(review.get("sample_hash_salt"), str) or not review["sample_hash_salt"]:
        raise ValueError("Study v2 human review requires a deterministic sample salt")

    funnel = settings["referral_funnel"]
    if funnel.get("source_table") != "raw.fastf1_session_race_control_messages":
        raise ValueError("Referral episodes must use the session-keyed Race Control source")
    if any(
        funnel.get(field) is not True
        for field in ("preserve_multi_car_incidents", "unmatched_episodes_must_remain_visible")
    ):
        raise ValueError("Referral funnel must preserve multi-car and unmatched episodes")

    matching = settings["close_case_matching"]
    if matching.get("prohibit_outcome_derived_match_fields") is not True:
        raise ValueError("Close-case matching cannot use outcome-derived fields")
    forbidden_primary_match_fields = {
        "fault_language",
        "outcome_family",
        "penalty_seconds",
        "penalty_points",
        "grid_places",
        "damage",
        "retirement",
        "finish_position",
    }
    if forbidden_primary_match_fields & set(matching.get("distance_fields", [])):
        raise ValueError("Primary close-case distance fields contain post-decision outcomes")
    if matching.get("conditional_sanction_exact_fields") != ["fault_language"]:
        raise ValueError("Fault language is permitted only in the conditional sanction match")
    if int(matching.get("minimum_neighbors", 0)) < 2:
        raise ValueError("Close-case matching requires at least two neighbors")

    harm = settings["damage_harm"]
    if any(
        harm.get(field) is not True
        for field in (
            "timing_patterns_are_screening_only",
            "incident_causality_requires_explicit_source_link",
            "no_damage_inference_from_slow_lap_alone",
        )
    ):
        raise ValueError("Damage/harm evidence safeguards cannot be relaxed")
    if harm.get("minimum_clean_laps_each_side") != 5:
        raise ValueError("Primary persistent-pace window must remain five clean laps per side")
    nationality = settings["nationality"]
    if not 0 < float(nationality.get("minimum_common_support_fraction", 0)) <= 1:
        raise ValueError("Nationality common-support threshold must be in (0, 1]")
    if not 0 < float(nationality.get("maximum_weighted_abs_smd", 0)) <= 0.25:
        raise ValueError("Nationality weighted-balance threshold must be in (0, 0.25]")
    if int(nationality.get("minimum_exposed_effective_sample_size", 0)) < 20:
        raise ValueError("Nationality exposed effective sample size threshold is too small")
    release = settings["release"]
    expected_artifacts = {
        "human_review",
        "referral",
        "incident_clock",
        "incident_context",
        "close_cases",
        "damage",
        "layers",
        "nationality",
        "report_notebook",
        "report_html",
    }
    artifacts = release.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != expected_artifacts:
        raise ValueError("Study v2 release artifacts must name every frozen output")
    if not all(
        isinstance(path, str) and path and not Path(path).is_absolute()
        for path in artifacts.values()
    ):
        raise ValueError("Study v2 release artifact paths must be nonempty and relative")
    return settings


def load_damage_evidence_sources(path: Path | None = None) -> dict[str, Any]:
    """Load and validate the source hierarchy used for damage and harm claims."""

    config_path = path or PROJECT_ROOT / "config" / "damage_evidence_sources.yml"
    payload = load_yaml(config_path)
    settings = payload.get("damage_evidence_sources")
    if not isinstance(settings, dict):
        raise ValueError(f"Missing damage_evidence_sources mapping in {config_path}")
    required = {"schema_version", "frozen_at", "grades", "registries", "adjudication_rules"}
    if missing := required - set(settings):
        raise ValueError(f"Damage source settings are missing: {', '.join(sorted(missing))}")
    if settings["schema_version"] != "damage_sources_v1":
        raise ValueError("Damage source schema_version must remain damage_sources_v1")

    grades = settings["grades"]
    if not isinstance(grades, dict) or set(grades) != {"A1", "A2", "A3", "B1", "C", "D"}:
        raise ValueError("Damage evidence grades must match the frozen hierarchy")
    for grade, rule in grades.items():
        if not isinstance(rule, dict):
            raise ValueError(f"Damage evidence grade {grade} must be a mapping")
        claims = rule.get("allowed_claims")
        if (
            not isinstance(claims, list)
            or not claims
            or not all(isinstance(claim, str) and claim for claim in claims)
        ):
            raise ValueError(f"Damage evidence grade {grade} needs allowed_claims")
        if not isinstance(rule.get("limitations"), str) or not rule["limitations"]:
            raise ValueError(f"Damage evidence grade {grade} needs limitations")

    registries = settings["registries"]
    if not isinstance(registries, list) or not registries:
        raise ValueError("Damage source registry must be a non-empty list")
    source_ids: list[str] = []
    for source in registries:
        if not isinstance(source, dict):
            raise ValueError("Each damage source must be a mapping")
        required_source = {
            "source_id",
            "grade",
            "owner",
            "base_url",
            "evidence_types",
            "retrieval",
            "reliability_note",
        }
        if missing := required_source - set(source):
            raise ValueError(f"Damage source is missing: {', '.join(sorted(missing))}")
        if source["grade"] not in grades:
            raise ValueError(f"Unknown damage evidence grade {source['grade']}")
        if not str(source["base_url"]).startswith("https://"):
            raise ValueError("Damage source base_url must use HTTPS")
        source_ids.append(str(source["source_id"]))
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Damage source_id values must be unique")

    confirmation = settings["adjudication_rules"].get("confirmed_damage")
    if (
        not isinstance(confirmation, dict)
        or confirmation.get("explicit_component_or_damage_statement_required") is not True
    ):
        raise ValueError("Confirmed damage requires an explicit source statement")
    if set(confirmation.get("accepted_grades", [])) - {"A1", "A2", "A3"}:
        raise ValueError("Confirmed damage cannot rely on lower-grade sources")
    no_damage = settings["adjudication_rules"].get("no_confirmed_damage")
    if (
        not isinstance(no_damage, dict)
        or no_damage.get("absence_of_reporting_is_not_evidence") is not True
    ):
        raise ValueError("Silence cannot be treated as evidence of no damage")
    return settings


def load_outcome_model_spec(path: Path | None = None) -> dict[str, Any]:
    """Load the frozen grouped-validation and nationality-overlap specification."""

    config_path = path or PROJECT_ROOT / "config" / "outcome_model_spec.yml"
    payload = load_yaml(config_path)
    spec = payload.get("outcome_model_spec")
    if not isinstance(spec, dict):
        raise ValueError(f"Missing outcome_model_spec mapping in {config_path}")
    required = {
        "schema_version",
        "unit_of_analysis",
        "outcome",
        "release_filter",
        "validation_group",
        "validation_folds",
        "random_seed",
        "consistency_model",
        "nationality_model",
        "safeguards",
    }
    if missing := required - set(spec):
        raise ValueError(f"Outcome model spec is missing: {', '.join(sorted(missing))}")
    if spec["outcome"] != "sanction_outcome":
        raise ValueError("The frozen outcome must remain sanction_outcome")
    if spec["release_filter"] != "reporting_eligible":
        raise ValueError("Outcome modeling must require reporting_eligible rows")
    if spec["validation_group"] != "event_id":
        raise ValueError("Outcome validation must group by event_id")
    if not isinstance(spec["validation_folds"], int) or spec["validation_folds"] < 2:
        raise ValueError("validation_folds must be an integer of at least two")
    consistency = spec["consistency_model"]
    nationality = spec["nationality_model"]
    safeguards = spec["safeguards"]
    if not all(isinstance(section, dict) for section in (consistency, nationality, safeguards)):
        raise ValueError("Model and safeguard sections must be mappings")
    for section_name, section in (
        ("consistency_model", consistency),
        ("nationality_model", nationality),
    ):
        covariate_groups = [
            section.get("categorical_covariates"),
            section.get("numeric_covariates"),
            section.get("binary_covariates"),
        ]
        if not all(
            isinstance(group, list) and all(isinstance(value, str) for value in group)
            for group in covariate_groups
        ):
            raise ValueError(f"{section_name} covariates must be lists of field names")
        flattened = [value for group in covariate_groups for value in group]
        if len(flattened) != len(set(flattened)):
            raise ValueError(f"{section_name} covariates must not overlap")
        forbidden = {
            "outcome_family",
            "penalty_seconds",
            "penalty_points",
            "grid_places",
            "fault_language",
        }
        if forbidden & set(flattened):
            raise ValueError(f"{section_name} contains outcome-derived predictors")
    exposure = nationality.get("primary_exposure")
    nationality_covariates = {
        *nationality["categorical_covariates"],
        *nationality["numeric_covariates"],
        *nationality["binary_covariates"],
    }
    if exposure != "british_accused_driver" or exposure in nationality_covariates:
        raise ValueError("The primary nationality exposure must be separate from covariates")
    clip = nationality.get("propensity_clip")
    if not isinstance(clip, list) or len(clip) != 2 or not 0 < float(clip[0]) < float(clip[1]) < 1:
        raise ValueError("propensity_clip must contain increasing probabilities inside (0, 1)")
    simulation = nationality.get("simulation_power")
    if not isinstance(simulation, dict):
        raise ValueError("nationality_model.simulation_power must be a mapping")
    simulation_required = {
        "baseline_probabilities",
        "target_risk_differences",
        "event_random_intercept_sd",
        "repetitions",
        "alpha",
        "minimum_successful_fit_fraction",
        "target_power",
    }
    if simulation_required - set(simulation):
        raise ValueError("Nationality simulation-power settings are incomplete")
    baselines = simulation["baseline_probabilities"]
    effects = simulation["target_risk_differences"]
    if (
        not isinstance(baselines, list)
        or not baselines
        or not all(0 < float(value) < 1 for value in baselines)
        or not isinstance(effects, list)
        or not effects
        or not all(0 < float(value) < 1 for value in effects)
        or any(float(baseline) + float(effect) >= 1 for baseline in baselines for effect in effects)
    ):
        raise ValueError(
            "Simulation baselines and risk differences must define valid probabilities"
        )
    if (
        not isinstance(simulation["repetitions"], int)
        or simulation["repetitions"] < 100
        or float(simulation["event_random_intercept_sd"]) < 0
        or not 0 < float(simulation["alpha"]) < 1
        or not 0 < float(simulation["minimum_successful_fit_fraction"]) <= 1
        or not 0 < float(simulation["target_power"]) <= 1
    ):
        raise ValueError("Simulation repetitions, random-effect SD, or alpha are invalid")
    required_safeguards = {
        "exclude_penalty_fields_from_predictors",
        "exclude_decision_reason_from_primary_predictors",
        "prohibit_driver_fixed_effect_with_nationality_exposure",
        "prohibit_random_row_splits",
        "context_enrichment_required_before_inference",
        "provisional_labels_allowed_for_effect_estimation",
    }
    if required_safeguards - set(safeguards):
        raise ValueError("Outcome model safeguards are incomplete")
    if any(
        safeguards[name] is not expected
        for name, expected in {
            "exclude_penalty_fields_from_predictors": True,
            "exclude_decision_reason_from_primary_predictors": True,
            "prohibit_driver_fixed_effect_with_nationality_exposure": True,
            "prohibit_random_row_splits": True,
            "context_enrichment_required_before_inference": True,
            "provisional_labels_allowed_for_effect_estimation": False,
        }.items()
    ):
        raise ValueError("Outcome model safeguards cannot be relaxed in the frozen specification")
    return spec


def load_sporting_regulation_issues(
    path: Path | None = None,
) -> list[SportingRegulationIssue]:
    config_path = path or PROJECT_ROOT / "config" / "f1_sporting_regulation_issues.yml"
    payload = load_yaml(config_path)
    issues = payload.get("sporting_regulation_issues")
    if not isinstance(issues, list):
        raise ValueError(f"Missing sporting_regulation_issues list in {config_path}")
    records = [SportingRegulationIssue.model_validate(issue) for issue in issues]
    ids = [record.source_id for record in records]
    keys = [(record.season, record.precedence) for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate source_id in {config_path}")
    if len(keys) != len(set(keys)):
        raise ValueError(f"Duplicate season/precedence in {config_path}")
    covered_seasons = {record.season for record in records}
    if covered_seasons != set(range(2018, 2026)):
        raise ValueError("Sporting regulation catalog must cover every season from 2018 to 2025")
    for season in covered_seasons:
        season_issues = sorted(
            (record for record in records if record.season == season),
            key=lambda record: record.precedence,
        )
        publication_dates = [record.publication_date for record in season_issues]
        if publication_dates != sorted(publication_dates):
            raise ValueError(f"{season} issue precedence must follow publication date")
    return records


def select_sporting_regulation(
    issues: list[SportingRegulationIssue],
    season: int,
    event_date: date,
) -> SportingRegulationIssue:
    candidates = [
        issue for issue in issues if issue.season == season and issue.publication_date <= event_date
    ]
    if not candidates:
        raise ValueError(f"No {season} Sporting Regulation issue available by {event_date}")
    return max(candidates, key=lambda issue: (issue.publication_date, issue.precedence))


def load_international_sporting_code_issues(
    path: Path | None = None,
) -> list[InternationalSportingCodeIssue]:
    config_path = path or PROJECT_ROOT / "config" / "international_sporting_code_issues.yml"
    payload = load_yaml(config_path)
    issues = payload.get("international_sporting_code_issues")
    if not isinstance(issues, list):
        raise ValueError(f"Missing international_sporting_code_issues list in {config_path}")
    records = [InternationalSportingCodeIssue.model_validate(issue) for issue in issues]
    ids = [record.source_id for record in records]
    keys = [(record.season, record.precedence) for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate source_id in {config_path}")
    if len(keys) != len(set(keys)):
        raise ValueError(f"Duplicate season/precedence in {config_path}")
    if {record.season for record in records} != set(range(2018, 2026)):
        raise ValueError("International Sporting Code catalog must cover 2018 through 2025")
    return records


def select_international_sporting_code(
    issues: list[InternationalSportingCodeIssue],
    season: int,
    event_date: date,
) -> InternationalSportingCodeIssue:
    candidates = [
        issue
        for issue in issues
        if issue.season == season and issue.effective_from <= event_date <= issue.effective_through
    ]
    if not candidates:
        raise ValueError(f"No {season} International Sporting Code issue covers {event_date}")
    return max(candidates, key=lambda issue: (issue.effective_from, issue.precedence))
