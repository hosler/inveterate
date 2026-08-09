import re
from datetime import timedelta

from celery import shared_task
from celery_singleton import Singleton
from django.utils import timezone
from requests.exceptions import RequestException

from ..models import Cluster, DomainRoute, DriftFinding, IP, PortForward, Service
from ..proxmox import get_proxmox_connection
from ..reconcile import resolve_stale, upsert_finding
from ._common import logger


PROXMOX_KINDS = {
    "ghost-service", "orphan-vm", "config-drift", "power-drift",
    "stuck-operation", "stuck-pending",
}
DB_KINDS = {"stranded-ip", "stranded-npm", "unsynced-domain"}
INVETERATE_VMID = re.compile(r"^1\d{6}$")


def _emit(seen, kind, severity, fingerprint, details):
    upsert_finding(kind, severity, fingerprint, details)
    seen.add(fingerprint)


@shared_task(base=Singleton, lock_expiry=60 * 15)
def reconcile_proxmox_drift():
    seen = set()
    now = timezone.now()
    operation_cutoff = now - timedelta(minutes=30)
    pending_cutoff = now - timedelta(hours=6)

    for cluster in Cluster.objects.all():
        try:
            resources = get_proxmox_connection(cluster).cluster.resources.get(type="vm")
        except RequestException:
            logger.warning("Skipping reconciliation for unreachable cluster %s", cluster.id)
            # Preserve this scope's active incidents while other clusters reconcile.
            seen.update(DriftFinding.objects.filter(
                kind__in=PROXMOX_KINDS,
                resolved_at__isnull=True,
                details__cluster_id=cluster.id,
            ).values_list("fingerprint", flat=True))
            continue

        vms = {int(vm["vmid"]): vm for vm in resources if vm.get("vmid") is not None}
        services = list(Service.objects.filter(node__cluster=cluster).select_related("service_plan", "node"))
        services_by_vmid = {service.machine_id: service for service in services if service.machine_id is not None}

        for service in services:
            base = {
                "cluster_id": cluster.id,
                "cluster": cluster.name,
                "service_id": service.id,
                "machine_id": service.machine_id,
            }
            if service.operation_in_progress:
                seen.update(DriftFinding.objects.filter(
                    kind__in=PROXMOX_KINDS,
                    resolved_at__isnull=True,
                    details__service_id=service.id,
                ).values_list("fingerprint", flat=True))
                if service.machine_id is not None:
                    seen.update(DriftFinding.objects.filter(
                        kind="orphan-vm",
                        resolved_at__isnull=True,
                        details__cluster_id=cluster.id,
                        details__machine_id=service.machine_id,
                    ).values_list("fingerprint", flat=True))
                if service.operation_started_at and service.operation_started_at < operation_cutoff:
                    _emit(seen, "stuck-operation", "warning", f"stuck-operation:service:{service.id}", {
                        **base, "summary": "Service operation has been in progress for more than 30 minutes",
                        "operation_started_at": service.operation_started_at.isoformat(),
                    })
                continue

            if service.status == "destroyed":
                continue

            vm = vms.get(service.machine_id)
            if service.status == "active" and vm is None:
                _emit(seen, "ghost-service", "critical", f"ghost-service:service:{service.id}", {
                    **base, "summary": "Active service has no VM in Proxmox",
                })
            if vm is not None and service.service_plan is not None:
                expected = {
                    "maxcpu": service.service_plan.cores,
                    "maxmem": service.service_plan.ram * 1024 * 1024,
                }
                actual = {key: int(vm.get(key, 0)) for key in expected}
                maxdisk = vm.get("maxdisk")
                if maxdisk:
                    expected["maxdisk"] = service.service_plan.size * 1024 ** 3
                    actual["maxdisk"] = int(maxdisk)
                drifted = any(
                    abs(actual[key] - value) >= value * 0.01
                    for key, value in expected.items()
                )
                if drifted:
                    _emit(seen, "config-drift", "warning", f"config-drift:service:{service.id}", {
                        **base, "summary": "Proxmox configuration differs from the service plan",
                        "expected": expected, "actual": actual,
                    })
                if service.status == "active" and vm.get("status") != "running":
                    _emit(seen, "power-drift", "warning", f"power-drift:service:{service.id}", {
                        **base, "summary": "Active service VM is not running",
                        "actual_status": vm.get("status"),
                    })
            if service.status in {"pending", "error"} and service.updated < pending_cutoff:
                _emit(seen, "stuck-pending", "warning", f"stuck-pending:service:{service.id}", {
                    **base, "summary": "Pending or errored service has not changed for more than 6 hours",
                    "status": service.status, "updated": service.updated.isoformat(),
                })

        for vmid, vm in vms.items():
            if INVETERATE_VMID.fullmatch(str(vmid)):
                service = services_by_vmid.get(vmid)
                if service is None or service.status == "destroyed":
                    node = vm.get("node", "unknown")
                    _emit(seen, "orphan-vm", "critical", f"orphan-vm:{cluster.id}:{node}:{vmid}", {
                        "cluster_id": cluster.id, "cluster": cluster.name, "node": node,
                        "machine_id": vmid, "service_id": service.id if service else None,
                        "summary": "Inveterate VM has no live service",
                    })

    resolve_stale(PROXMOX_KINDS, seen)


@shared_task(base=Singleton, lock_expiry=60 * 15)
def reconcile_db_drift():
    seen = set()

    for ip in IP.objects.filter(owner__service__status="destroyed").select_related("owner__service"):
        _emit(seen, "stranded-ip", "warning", f"stranded-ip:ip:{ip.id}", {
            "summary": "IP remains assigned to a destroyed service",
            "ip_id": ip.id, "ip": ip.value, "service_id": ip.owner.service_id,
        })

    for forward in PortForward.objects.filter(
        port_block__service_network__service__status="destroyed",
    ).select_related("port_block__service_network__service"):
        service_id = forward.port_block.service_network.service_id
        _emit(seen, "stranded-npm", "warning", f"stranded-npm:port-forward:{forward.id}", {
            "summary": "Port forward remains for a destroyed service",
            "port_forward_id": forward.id, "service_id": service_id,
            "npm_stream_id": forward.npm_stream_id,
        })
    for route in DomainRoute.objects.filter(service__status="destroyed").select_related("service"):
        _emit(seen, "stranded-npm", "warning", f"stranded-npm:domain-route:{route.id}", {
            "summary": "Domain route remains for a destroyed service",
            "domain_route_id": route.id, "service_id": route.service_id,
            "npm_proxy_host_id": route.npm_proxy_host_id,
        })
    for route in DomainRoute.objects.filter(
        verification_status=DomainRoute.VerificationStatus.VERIFIED,
        npm_proxy_host_id__isnull=True,
    ):
        _emit(seen, "unsynced-domain", "warning", f"unsynced-domain:domain-route:{route.id}", {
            "summary": "Verified domain has never been synced to NPM",
            "domain_route_id": route.id, "service_id": route.service_id, "domain": route.domain,
        })

    resolve_stale(DB_KINDS, seen)
