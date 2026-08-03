"""Synthetic DataHub graph used only by the manual live-smoke workflow."""

from __future__ import annotations

from datahub.sdk.dataset import Dataset
from datahub.sdk.main_client import DataHubClient

PLATFORM = "postgres"
ENVIRONMENT = "PROD"
RAW_DATASET = "change_receipt.raw_orders"
TARGET_DATASET = "change_receipt.orders"
DOWNSTREAM_DATASET = "change_receipt.daily_orders"

TARGET_URN = "urn:li:dataset:(urn:li:dataPlatform:postgres,change_receipt.orders,PROD)"
DOWNSTREAM_URN = "urn:li:dataset:(urn:li:dataPlatform:postgres,change_receipt.daily_orders,PROD)"


def build_demo_datasets() -> tuple[Dataset, Dataset, Dataset]:
    """Build a small lineage graph without contacting a DataHub server."""
    raw = Dataset(
        platform=PLATFORM,
        name=RAW_DATASET,
        env=ENVIRONMENT,
        description="Synthetic source used by the DataHub Change Receipt live smoke.",
        schema=[
            ("order_id", "bigint", "Synthetic order identifier."),
            ("customer_id", "bigint", "Synthetic customer identifier."),
            ("legacy_status", "text", "Synthetic legacy lifecycle value."),
            ("order_total", "decimal", "Synthetic order amount."),
        ],
    )
    target = Dataset(
        platform=PLATFORM,
        name=TARGET_DATASET,
        env=ENVIRONMENT,
        description="Synthetic review target for a proposed schema change.",
        schema=[
            ("order_id", "bigint", "Synthetic order identifier."),
            ("customer_id", "bigint", "Synthetic customer identifier."),
            ("legacy_status", "text", "Synthetic legacy lifecycle value."),
            ("order_total", "decimal", "Synthetic order amount."),
        ],
    )
    target.set_upstreams([str(raw.urn)])

    downstream = Dataset(
        platform=PLATFORM,
        name=DOWNSTREAM_DATASET,
        env=ENVIRONMENT,
        description="Synthetic downstream aggregate used to prove live lineage retrieval.",
        schema=[
            ("order_date", "date", "Synthetic aggregation date."),
            ("order_count", "bigint", "Synthetic order count."),
            ("gross_total", "decimal", "Synthetic gross amount."),
        ],
    )
    downstream.set_upstreams([str(target.urn)])
    return raw, target, downstream


def seed_demo(client: DataHubClient) -> tuple[str, ...]:
    """Upsert only the synthetic graph into an explicitly configured DataHub Core."""
    client.test_connection()
    datasets = build_demo_datasets()
    for dataset in datasets:
        client.entities.upsert(dataset)
    return tuple(str(dataset.urn) for dataset in datasets)


def main() -> int:
    client = DataHubClient.from_env()
    urns = seed_demo(client)
    # Do not print server configuration or authentication material.
    print(f"synthetic_datahub_datasets_seeded={len(urns)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
