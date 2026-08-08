# DomainRoute Ownership Verification (TXT-challenge) — Implementation Spec

## Problem

`DomainRouteSerializer.create()` calls `sync_domain_route.delay()` immediately on
POST, which creates the NPM proxy host and triggers Let's Encrypt for a
**customer-supplied, unverified** domain. Format validation + `INVETERATE_RESERVED_DOMAINS`
(already shipped) block malformed domains and provider-owned hostnames, but nothing
proves the requesting account controls an *arbitrary third-party* domain. Forcing LE
issuance is **not** sufficient: HTTP-01 only proves the domain resolves to the shared
proxy and the proxy answered — it does not bind the domain to a specific tenant, so
domains that already point at the shared IP are contestable (tenant contention,
pre-claim/migration hijack), and it hands attackers the LE rate-limit budget.

**Fix:** gate NPM activation (and therefore the LE attempt) on a DNS TXT challenge
that binds the domain to the **owning account**.

## Core design

- Each account has a **distinct, unguessable, deterministic** verification token derived
  from `SECRET_KEY` — no token storage, no rotation bookkeeping in the common case:

  ```python
  # inveterate/domain_verification.py
  import hashlib, hmac
  from django.conf import settings

  def account_token(owner_id: int) -> str:
      salt = getattr(settings, "INVETERATE_DOMAIN_VERIFICATION_SALT", "")  # bump to rotate all tokens
      mac = hmac.new(
          settings.SECRET_KEY.encode(),
          f"inveterate-domain-verify:v1:{salt}:{owner_id}".encode(),
          hashlib.sha256,
      ).hexdigest()
      return f"inv-verify={mac[:40]}"

  def verification_record_name(domain: str) -> str:
      label = getattr(settings, "INVETERATE_DOMAIN_VERIFICATION_LABEL", "_inveterate-verify")
      return f"{label}.{domain}"
  ```

  Distinct-per-account is the security property that solves tenant contention: publishing
  account A's token proves A, not B. The token need not be secret — the real proof is DNS
  write access — but unguessability stops an attacker pre-poisoning `_inveterate-verify.*`
  on a domain they *do* control and later swapping DNS. Rotation = bump
  `INVETERATE_DOMAIN_VERIFICATION_SALT` (invalidates all published records at once; fine
  for a single-operator colo, documented as a break-glass).

- Customer proves control by publishing:
  `_inveterate-verify.<domain>  TXT  "inv-verify=<hmac>"`

## Model changes (`inveterate/models.py`, `DomainRoute`)

Add:

```python
class VerificationStatus(models.TextChoices):
    PENDING  = "pending",  "Pending verification"
    VERIFIED = "verified", "Verified"
    FAILED   = "failed",   "Verification failed"

verification_status = models.CharField(
    max_length=16, choices=VerificationStatus.choices,
    default=VerificationStatus.PENDING,
)
verified_at = models.DateTimeField(null=True, blank=True)
```

A route is **only synced to NPM when `verification_status == "verified"`**.

### Migration + backfill (critical)

Two-part migration:
1. Schema: add the fields (default `pending`).
2. **Data migration: set every EXISTING DomainRoute to `verified` with
   `verified_at=now`.** Existing production routes are already live and trusted —
   without this backfill they'd all drop to `pending` and get torn down on next sync.
   New rows created after deploy start at `pending`.

## Verification task (`inveterate/tasks/domain_verify.py`, exported in `tasks/__init__.py`)

```python
@shared_task(
    name="inveterate.tasks.verify_domain_route",
    base=Singleton, unique_on=["domain_route_id"],
    autoretry_for=(dns.resolver.LifetimeTimeout, dns.resolver.NoNameservers),
    retry_backoff=30, retry_backoff_max=1800, max_retries=10,
)
def verify_domain_route(domain_route_id):
    dr = DomainRoute.objects.select_related("service__owner").get(pk=domain_route_id)
    expected = account_token(dr.service.owner_id)
    name = verification_record_name(dr.domain)
    try:
        answers = dns.resolver.resolve(name, "TXT")          # public/authoritative lookup
        values = [b"".join(r.strings).decode() for r in answers]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        values = []
    if expected in values:
        DomainRoute.objects.filter(pk=dr.pk).update(
            verification_status="verified", verified_at=timezone.now())
        sync_domain_route.delay(dr.pk)       # NOW the NPM proxy host + LE happen
    else:
        DomainRoute.objects.filter(pk=dr.pk).update(verification_status="failed")
        # retries (autoretry/backoff) cover DNS propagation delay; terminal "failed"
        # after max_retries. User can re-trigger via the /verify action below.
```

- Use `dns.resolver` from **dnspython** (new dependency — add `dnspython` to
  `requirements.txt` / `pyproject.toml`). Configure it to query a public resolver
  (1.1.1.1 / 8.8.8.8) so results don't depend on the app host's resolver, and set a
  short lifetime/timeout.
- `unique_on=["domain_route_id"]` so repeated verify triggers for one route coalesce.

## Serializer changes (`inveterate/serializers.py`, `DomainRouteSerializer`)

1. `create()` / `update()`: **stop calling `sync_domain_route.delay()` directly.**
   - On create: leave `verification_status=pending`, call `verify_domain_route.delay(instance.id)`
     (first attempt — usually fails immediately, that's expected; user then adds the record).
   - On update of an already-`verified` route (e.g. forward_port change): the domain didn't
     change → re-sync directly. If `domain` changed → reset to `pending` + re-verify.
2. Expose read-only helper fields so the client can render instructions without recomputing:
   ```python
   verification_status = serializers.CharField(read_only=True)
   verification_record_name = serializers.SerializerMethodField()
   verification_record_value = serializers.SerializerMethodField()   # account_token(owner)
   ```
   Guard `verification_record_value` so it's only returned to the route's owner/staff.
3. Keep `verification_status`, `verified_at`, `npm_proxy_host_id` in `read_only_fields`.

## Viewset action (`inveterate/viewsets/portforward.py`, `DomainRouteViewSet`)

Add an on-demand re-check the UI calls after the customer says "I've added the record":

```python
@action(methods=["post"], detail=True)
def verify(self, request, pk=None):
    dr = self.get_object()                      # get_queryset already scopes to owner
    task = verify_domain_route.delay(dr.pk)
    record_task_owner(task.id, request.user)    # consistent with the task-IDOR fix
    return Response({"task_id": task.id, "verification_status": dr.verification_status}, status=202)
```

`perform_destroy` is unchanged (NPM proxy host only exists once verified+synced, so the
existing cleanup path already handles both cases — `npm_proxy_host_id` is null for a
never-verified route, so nothing to delete).

## API contract (for nascent-v2 frontend)

- `POST /api/v1/domainroutes/` → `201` with body including
  `verification_status: "pending"`, `verification_record_name: "_inveterate-verify.app.example.com"`,
  `verification_record_value: "inv-verify=<hmac>"`. Route is inert until verified.
- `POST /api/v1/domainroutes/{id}/verify/` → `202 {task_id}`; poll `/api/v1/tasks/{id}/`
  (ownership-checked) then re-GET the route for `verification_status`.
- Frontend (SvelteKit, `frontend/src/lib/components/services/`): show the TXT record
  (name/type/value with copy buttons), a status badge (pending/verified/failed), and a
  "Check now" button hitting the verify action. Domain routes list should visually
  distinguish unverified (inactive) routes.

## Settings (add to nascent-v2 `settings/base.py`)

```python
INVETERATE_DOMAIN_VERIFICATION_LABEL = "_inveterate-verify"   # TXT record prefix
INVETERATE_DOMAIN_VERIFICATION_SALT = ""                      # bump to rotate all tokens
# INVETERATE_RESERVED_DOMAINS already set — reserved-domain + format checks still run
# FIRST; TXT challenge only gates the remaining arbitrary domains.
```

## Tests (`inveterate/tests.py`)

- `account_token` is deterministic per owner, differs across owners, changes when salt bumped.
- `verify_domain_route`: TXT present+matching → status `verified` + `sync_domain_route`
  enqueued; TXT absent → `failed`, sync NOT enqueued; TXT present but matching a *different*
  account's token → `failed` (mock `dns.resolver.resolve`).
- `create()` does NOT enqueue `sync_domain_route` (enqueues `verify_domain_route`); route
  starts `pending`.
- `verify` action returns 202 and is owner-scoped (non-owner 404 via get_queryset).
- Data migration backfills existing rows to `verified`.
- `verification_record_value` not leaked to non-owners.

## Residual risks / notes

- **Post-verification DNS drift:** a domain can change hands after verification; the route
  stays active. Low impact (if it stops pointing at us, NPM simply fails to serve).
  Optional hardening: a periodic `reverify_domain_routes` beat task that re-checks verified
  routes weekly and flips them back to `pending` (disabling NPM) on failure.
- **Wildcard domains** (`*.example.com`): out of scope; concrete FQDN only (already enforced
  by `hostname_pattern`).
- **Order of checks** unchanged: reserved-domain + FQDN format reject first (cheap, no DNS),
  TXT challenge second.
- Belt-and-suspenders with LE: because sync (and thus the LE HTTP-01 attempt) only runs
  post-verification, we no longer expose the LE rate-limit budget to unverified domains.
