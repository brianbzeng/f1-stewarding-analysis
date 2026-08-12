import pandas as pd

from f1stewards.inventory import (
    inventory_reconciliation_is_clean,
    reconcile_document_inventory,
)


def test_inventory_reconciliation_accepts_matching_artifacts() -> None:
    manifest = pd.DataFrame(
        {
            "document_id": ["doc-1", "doc-2"],
            "pilot_id": ["2025-aut", "2025-aut"],
        }
    )
    warehouse = pd.DataFrame(
        {
            "document_id": ["doc-1", "doc-2"],
            "event_id": ["2025-aut", "2025-aut"],
        }
    )

    metrics = reconcile_document_inventory(manifest, warehouse, {"2025-aut"})

    assert metrics["manifest_records"] == 2
    assert metrics["warehouse_records"] == 2
    assert inventory_reconciliation_is_clean(metrics)


def test_inventory_reconciliation_reports_cross_artifact_drift() -> None:
    manifest = pd.DataFrame(
        {
            "document_id": ["doc-1", "doc-1", "doc-manifest"],
            "pilot_id": ["2025-aut", "2025-aut", "unknown-event"],
        }
    )
    warehouse = pd.DataFrame(
        {
            "document_id": ["doc-1", "doc-warehouse"],
            "event_id": ["2025-aut", "2024-gbr"],
        }
    )

    metrics = reconcile_document_inventory(
        manifest,
        warehouse,
        {"2025-aut", "2024-gbr", "2023-abu"},
        active_discovery_failures=2,
        active_retrieval_failures=3,
    )

    assert metrics["manifest_duplicate_document_ids"] == 1
    assert metrics["manifest_only_document_ids"] == 1
    assert metrics["warehouse_only_document_ids"] == 1
    assert metrics["catalog_events_without_manifest_documents"] == 2
    assert metrics["catalog_events_without_warehouse_documents"] == 1
    assert metrics["manifest_unknown_event_ids"] == 1
    assert metrics["active_discovery_failures"] == 2
    assert metrics["active_retrieval_failures"] == 3
    assert not inventory_reconciliation_is_clean(metrics)
