# DataHub Change Receipt `dcr-d191ab33d00bfdd9`

- Decision: **BLOCK**
- Risk score: **100/100**
- Change: `example-orders-v2`
- Asset: `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.orders,PROD)`
- Evidence mode: `fixture`
- Real DataHub verified: `false`

## Reasons

- drop on `legacy_status` adds 40 risk points.
- rename on `customer_id` adds 25 risk points.
- 2 downstream asset(s) add 10 risk points.
- 1 downstream asset(s) have no owner in the collected context.
- 1 production query signal(s) add 10 risk points.
- 1 manual query signal(s) add 5 risk points.

## Proposed changes

- `drop` `legacy_status`
- `rename` `customer_id` → `buyer_id`

## Downstream evidence

- hop 1: `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.daily_orders,PROD)` (DATASET; owners: urn:li:corpGroup:analytics)
- hop 2: `urn:li:dashboard:(looker,operations_overview)` (DASHBOARD; owners: unowned)

## Privacy-minimized query evidence

- `legacy_status` / `SYSTEM` / `fixture:system-status-filter-001`
- `customer_id` / `MANUAL` / `fixture:manual-customer-join-001`

## Recommended checks

- Notify the listed downstream owners and attach their validation evidence.
- Assign or identify owners for unowned downstream assets.
- Run regression checks for every production query fingerprint.
- Re-run the receipt after mitigations; do not override missing evidence.

## Evidence boundary

Fixture mode validates deterministic behavior only. It is not evidence of a live DataHub connection. A real integration claim requires `real_datahub_verified: true` from a separately recorded smoke test against DataHub Core or Cloud.
