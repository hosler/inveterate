"""DNS TXT-challenge domain-ownership verification helpers.

Each account has a distinct, unguessable, deterministic verification token
derived from ``SECRET_KEY`` -- no token storage, no rotation bookkeeping in the
common case. Distinct-per-account is the security property that solves tenant
contention: publishing account A's token proves A, not B. Rotation = bump
``INVETERATE_DOMAIN_VERIFICATION_SALT`` (invalidates all published records at
once; documented as a break-glass for a single-operator colo).
"""
import hashlib
import hmac

from django.conf import settings


def account_token(owner_id) -> str:
    """Return the verification TXT value for ``owner_id``.

    Deterministic and distinct per owner. The token need not be secret -- the
    real proof is DNS write access -- but unguessability stops an attacker
    pre-poisoning ``_inveterate-verify.*`` on a domain they control and later
    swapping DNS. Do NOT weaken this to a global constant; distinctness is the
    security property.
    """
    salt = getattr(settings, "INVETERATE_DOMAIN_VERIFICATION_SALT", "")
    mac = hmac.new(
        settings.SECRET_KEY.encode(),
        f"inveterate-domain-verify:v1:{salt}:{owner_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"inv-verify={mac[:40]}"


def verification_record_name(domain: str) -> str:
    """Return the fully-qualified TXT record name the customer must publish."""
    label = getattr(settings, "INVETERATE_DOMAIN_VERIFICATION_LABEL", "_inveterate-verify")
    return f"{label}.{domain}"
