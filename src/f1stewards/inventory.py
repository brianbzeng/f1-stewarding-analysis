"""Cross-artifact controls for the full-study evidence inventory."""

from __future__ import annotations

from collections.abc import Collection, Mapping

import pandas as pd

INVENTORY_DISCREPANCY_KEYS = (
    "manifest_duplicate_document_ids",
    "manifest_only_document_ids",
    "warehouse_only_document_ids",
    "catalog_events_without_manifest_documents",
    "catalog_events_without_warehouse_documents",
    "manifest_unknown_event_ids",
    "warehouse_unknown_event_ids",
    "manifest_cross_event_content_hashes",
    "warehouse_cross_event_content_hashes",
    "active_discovery_failures",
    "active_retrieval_failures",
)


def _cross_event_content_hashes(frame: pd.DataFrame, event_column: str) -> int:
    if "content_sha256" not in frame.columns:
        return 0
    hashed = frame.loc[frame["content_sha256"].notna(), ["content_sha256", event_column]].copy()
    if hashed.empty:
        return 0
    event_counts = hashed.groupby("content_sha256")[event_column].nunique()
    return int(event_counts.gt(1).sum())


def reconcile_document_inventory(
    manifest: pd.DataFrame,
    warehouse_documents: pd.DataFrame,
    catalog_event_ids: Collection[str],
    *,
    active_discovery_failures: int = 0,
    active_retrieval_failures: int = 0,
) -> dict[str, int]:
    """Compare the frozen Parquet manifest, DuckDB lineage, and event catalog."""

    manifest_columns = {"document_id", "pilot_id"}
    warehouse_columns = {"document_id", "event_id"}
    if missing := manifest_columns - set(manifest.columns):
        raise ValueError(f"Manifest is missing columns: {', '.join(sorted(missing))}")
    if missing := warehouse_columns - set(warehouse_documents.columns):
        raise ValueError(f"Warehouse inventory is missing columns: {', '.join(sorted(missing))}")

    catalog_ids = set(catalog_event_ids)
    manifest_document_ids = set(manifest["document_id"].astype(str))
    warehouse_document_ids = set(warehouse_documents["document_id"].astype(str))
    manifest_event_ids = set(manifest["pilot_id"].astype(str))
    warehouse_event_ids = set(warehouse_documents["event_id"].astype(str))

    return {
        "manifest_records": len(manifest),
        "warehouse_records": len(warehouse_documents),
        "manifest_events": len(manifest_event_ids),
        "warehouse_events": len(warehouse_event_ids),
        "manifest_duplicate_document_ids": int(manifest["document_id"].duplicated().sum()),
        "manifest_only_document_ids": len(manifest_document_ids - warehouse_document_ids),
        "warehouse_only_document_ids": len(warehouse_document_ids - manifest_document_ids),
        "catalog_events_without_manifest_documents": len(catalog_ids - manifest_event_ids),
        "catalog_events_without_warehouse_documents": len(catalog_ids - warehouse_event_ids),
        "manifest_unknown_event_ids": len(manifest_event_ids - catalog_ids),
        "warehouse_unknown_event_ids": len(warehouse_event_ids - catalog_ids),
        "manifest_cross_event_content_hashes": _cross_event_content_hashes(
            manifest, "pilot_id"
        ),
        "warehouse_cross_event_content_hashes": _cross_event_content_hashes(
            warehouse_documents, "event_id"
        ),
        "active_discovery_failures": active_discovery_failures,
        "active_retrieval_failures": active_retrieval_failures,
    }


def inventory_reconciliation_is_clean(metrics: Mapping[str, int]) -> bool:
    """Return whether all discrepancy metrics are zero."""

    return all(metrics.get(key, 0) == 0 for key in INVENTORY_DISCREPANCY_KEYS)
