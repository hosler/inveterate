"""
Inveterate Celery tasks package.

All public functions and tasks are re-exported here so that existing imports
like ``from inveterate.tasks import provision_service`` continue to work.
"""

from ..provisioning_steps import PROVISIONING_STEPS  # noqa: F401
from .control import (  # noqa: F401
    get_cluster,
    get_service_node,
    get_vm,
    reboot_vm,
    reset_vm,
    reset_vm_password,
    shutdown_vm,
    start_vm,
    stop_vm,
)
from .maintenance import (  # noqa: F401
    calculate_inventory,
    cancel_service,
    cleanup_console_users,
    cleanup_orphaned_ips,
    cleanup_stale_error_services,
    update_service_ssh_keys,
)
from .monitoring import (  # noqa: F401
    get_cluster_resources,
    get_vm_ips,
    get_vm_osinfo,
    get_vm_status,
    meter_bandwidth,
    reinstate_service,
    suspend_service,
)
from .npm import (  # noqa: F401
    delete_npm_proxy_host,
    delete_npm_stream,
    sync_domain_route,
    sync_port_forward,
)
from .provisioning import (  # noqa: F401
    _SSH_KEY_PREFIXES,
    _compose_cloud_init,
    assign_ips,
    provision_service,
)
from .resize import resize_service  # noqa: F401
from .templates import (  # noqa: F401
    import_kvm_template,
    sync_kvm_templates,
    sync_templates,
)

__all__ = [
    # control
    "get_cluster",
    "get_service_node",
    "get_vm",
    "reboot_vm",
    "reset_vm",
    "reset_vm_password",
    "shutdown_vm",
    "start_vm",
    "stop_vm",
    # maintenance
    "calculate_inventory",
    "cancel_service",
    "cleanup_console_users",
    "cleanup_orphaned_ips",
    "cleanup_stale_error_services",
    "update_service_ssh_keys",
    # monitoring
    "get_cluster_resources",
    "get_vm_ips",
    "get_vm_osinfo",
    "get_vm_status",
    "meter_bandwidth",
    "reinstate_service",
    "suspend_service",
    # npm
    "delete_npm_proxy_host",
    "delete_npm_stream",
    "sync_domain_route",
    "sync_port_forward",
    # provisioning
    "_SSH_KEY_PREFIXES",
    "_compose_cloud_init",
    "assign_ips",
    "provision_service",
    "resize_service",
    "PROVISIONING_STEPS",
    # templates
    "import_kvm_template",
    "sync_kvm_templates",
    "sync_templates",
]
