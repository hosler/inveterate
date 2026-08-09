# Reconciliation loop — design spec

Status: phase 1 (detect) approved for implementation. Phases 2-3 are design intent, not yet scheduled.

## Problem

Three sources of truth drift apart: the DB (Service/ServiceNetwork/IP/PortBlock/DomainRoute in inveterate, PendingOrder/HostingSubscription in nascent), Stripe subscriptions, and actual Proxmox state. Every operational bug from the 2026-08 audit was an instance of this drift, and each got a point-wise patch. The reconciler turns drift into a detected and reported condition, and later a self-healing one.

## Architecture

Three phases:

1. **Detect (the scope of this spec).** Read-only checkers compare the truths and persist `DriftFinding` rows. They never mutate VMs, Stripe, or NPM.
2. **Repair (later, allowlisted).** Individually-toggled auto-repairs for provably safe classes only: stuck flags, expired-order resurrection, IP release for confirmed-destroyed services. Orphan-VM deletion is never automated.
3. **Converge (later, refactor).** Extract `desired_state(service)` from `provision_service` so that provision, resize, and repair become the same apply-diff function (controller model).

### DriftFinding model (inveterate/models.py)

- `kind` — CharField, one of the check identifiers below
- `severity` — `critical` | `warning`
- `fingerprint` — CharField, unique, dedup key (e.g. `orphan-vm:node1:1000123`)
- `details` — JSONField (human-readable summary plus raw evidence)
- `first_seen`, `last_seen` — DateTimeField
- `resolved_at` — nullable; set automatically when the owning check runs cleanly and the fingerprint no longer fires

Lifecycle: a check run upserts by fingerprint. It refreshes `last_seen` and clears `resolved_at` if the finding had resolved. After the run, untouched findings that belong to the kinds this check owns get `resolved_at=now`. The table therefore doubles as the incident history.

### Checkers

Each checker is a Celery beat task (`@shared_task(base=Singleton, lock_expiry=60*15)`), hourly, staggered. Each is independent; one failing does not block the others.

**`reconcile_proxmox_drift` (inveterate).** One VM enumeration per cluster (the `get_cluster_resources` pattern: `/cluster/resources` type `vm`), then compare against Services:

| kind | condition | severity |
|---|---|---|
| `ghost-service` | Service `active` but its `machine_id` appears on no node | critical |
| `orphan-vm` | VM whose vmid matches `1{d:06}` but no Service row, or Service `destroyed` | critical |
| `config-drift` | VM maxcpu/maxmem/maxdisk differ from ServicePlan cores/ram/size | warning |
| `power-drift` | Service `active` but VM not `running` (skip `suspended` services) | warning |
| `stuck-operation` | `operation_in_progress` true and no matching live task, older than 2× the 15-min lock expiry (use a `operation_started_at` timestamp — add nullable field, set by claim_operation) | warning |
| `stuck-pending` | Service `pending`/`error` > 6h with no operation in flight | warning |

Safety: services with `operation_in_progress` set (and not stuck by the rule above) are skipped entirely. An unreachable cluster/node suspends its checks for the run (no findings emitted for that scope) rather than mass-reporting ghosts.

**`reconcile_db_drift` (inveterate).** Pure DB queries:

| kind | condition | severity |
|---|---|---|
| `stranded-ip` | IP owned by a ServiceNetwork whose Service is `destroyed` | warning |
| `stranded-npm` | PortForward/DomainRoute rows whose service is destroyed | warning |
| `unsynced-domain` | DomainRoute `verified` but never synced to NPM (no npm id) | warning |

**`reconcile_stripe_drift` (nascent, apps/hosting/tasks.py).** One Stripe subscription list (status=active) + local queries:

| kind | condition | severity |
|---|---|---|
| `paying-no-service` | active Stripe subscription with no active Service / HostingSubscription | critical |
| `service-no-billing` | active Service whose subscription is canceled/unpaid/absent | critical |
| `price-drift` | subscription item price ≠ current plan price for the service | warning |
| `zombie-order` | PendingOrder `error`/`expired` whose checkout session has a live subscription | critical |

Stripe checker writes to the same DriftFinding model (imported from inveterate).

### Surfacing

Generalize nascent's `alert_error_services` into `alert_operational_issues`: same cadence and cache-dedup, now also including unresolved `critical` DriftFindings. Known accepted behavior: the 7-day fingerprint dedup means a finding that resolves and re-fires within 7 days does not re-alert. Revisit if flapping findings become common (would need per-incident rows or a refire timestamp). Admin SPA table over `/api/v1/driftfindings/` (admin-only viewset, read-only) can come later.

### Testing

Standard idioms: mock ProxmoxAPI; call tasks directly (never `.apply()`); Stripe listing mocked in nascent tests. Each checker gets: fires-on-drift, resolves-on-clean-rerun, skips-in-flight-operations, suspends-on-unreachable.

## Non-goals (phase 1)

- No repairs, no VM/Stripe/NPM writes.
- No customer-visible surface.
- No desired-state refactor of provision_service (phase 3).
