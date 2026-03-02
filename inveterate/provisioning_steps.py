"""
Provisioning step constants for progress tracking.

Each step is a (key, label) tuple. The ``status_msg`` field on a Service stores
the current step as ``"provisioning:<key>"``.  Steps that only apply to KVM
provisioning are naturally skipped for LXC services.
"""

from django.utils.translation import gettext_lazy as _

PROVISIONING_STEPS = [
    ("assign_ips", _("Assigning IP addresses")),
    ("clone_vm", _("Cloning VM template")),
    ("move_disks", _("Moving disks to target storage")),
    ("cloud_init", _("Preparing cloud-init configuration")),
    ("configure", _("Applying server configuration")),
    ("network", _("Configuring network interfaces")),
    ("firewall", _("Setting up firewall rules")),
    ("finalize", _("Finalizing provisioning")),
]

STEP_KEYS = [key for key, _ in PROVISIONING_STEPS]


def progress_msg(step_key: str) -> str:
    """Return the ``status_msg`` value for a provisioning step."""
    return f"provisioning:{step_key}"
