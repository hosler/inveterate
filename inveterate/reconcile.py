from django.utils import timezone

from .models import DriftFinding


def upsert_finding(kind, severity, fingerprint, details):
    """Create or refresh a finding while retaining its incident history."""
    now = timezone.now()
    finding, _ = DriftFinding.objects.update_or_create(
        fingerprint=fingerprint,
        defaults={
            "kind": kind,
            "severity": severity,
            "details": details,
            "last_seen": now,
            "resolved_at": None,
        },
    )
    return finding


def resolve_stale(kinds, seen_fingerprints):
    """Resolve active findings owned by these checks that did not recur."""
    return (
        DriftFinding.objects.filter(kind__in=kinds, resolved_at__isnull=True)
        .exclude(fingerprint__in=seen_fingerprints)
        .update(resolved_at=timezone.now())
    )
