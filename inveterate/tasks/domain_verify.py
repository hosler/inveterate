"""DNS TXT-challenge verification of a DomainRoute's ownership.

A DomainRoute is only synced to NPM (and therefore only triggers a Let's
Encrypt attempt) once its owning account has proven control of the domain by
publishing the account's verification token at
``_inveterate-verify.<domain>``.
"""
import dns.resolver
from celery import shared_task
from celery_singleton import Singleton
from django.utils import timezone

from ..domain_verification import account_token, verification_record_name
from ..models import DomainRoute
from ._common import logger

# Public resolvers so results don't depend on the app host's resolver (which
# may point at split-horizon / internal DNS that never sees customer records).
_PUBLIC_NAMESERVERS = ["1.1.1.1", "8.8.8.8"]
# Short lifetime: a verify attempt should fail fast rather than block a worker.
_RESOLVE_LIFETIME = 10.0


def _public_resolver():
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = list(_PUBLIC_NAMESERVERS)
    resolver.lifetime = _RESOLVE_LIFETIME
    resolver.timeout = _RESOLVE_LIFETIME
    return resolver


@shared_task(
    name="inveterate.tasks.verify_domain_route",
    base=Singleton,
    unique_on=["domain_route_id"],
    lock_expiry=60 * 15,
    autoretry_for=(dns.resolver.LifetimeTimeout, dns.resolver.NoNameservers),
    retry_backoff=30,
    retry_backoff_max=1800,
    max_retries=10,
)
def verify_domain_route(domain_route_id):
    """Check the TXT challenge for a DomainRoute and gate NPM sync on it.

    * TXT present + matching the owning account's token -> mark ``verified``
      with ``verified_at`` and enqueue ``sync_domain_route`` (the NPM proxy
      host + LE issuance happens NOW, post-verification).
    * TXT absent (NXDOMAIN / NoAnswer) or matching a *different* account's
      token -> mark ``failed`` and do NOT sync.
    * DNS timeout / no-nameservers -> raised for autoretry (covers propagation
      delay); terminal ``failed`` after ``max_retries``.
    """
    from .npm import sync_domain_route

    dr = DomainRoute.objects.select_related("service").get(pk=domain_route_id)
    expected = account_token(dr.service.owner_id)
    name = verification_record_name(dr.domain)

    logger.info("Verifying domain route %s (%s) via TXT %s", dr.id, dr.domain, name)

    resolver = _public_resolver()
    try:
        answers = resolver.resolve(name, "TXT")
        values = [b"".join(r.strings).decode() for r in answers]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        values = []

    if expected in values:
        DomainRoute.objects.filter(pk=dr.pk).update(
            verification_status=DomainRoute.VerificationStatus.VERIFIED,
            verified_at=timezone.now(),
        )
        logger.info("Domain route %s (%s) verified; syncing to NPM", dr.id, dr.domain)
        sync_domain_route.delay(dr.pk)
    else:
        DomainRoute.objects.filter(pk=dr.pk).update(
            verification_status=DomainRoute.VerificationStatus.FAILED,
        )
        logger.info("Domain route %s (%s) verification failed (TXT absent/mismatch)", dr.id, dr.domain)
