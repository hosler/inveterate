from celery import shared_task
from celery_singleton import Singleton
from proxmoxer.core import ResourceException
from requests.exceptions import ConnectionError

from ..models import Cluster, Service
from ..proxmox import get_proxmox_connection
from ._common import logger


def get_vm(service_id):
    service = Service.objects.get(pk=service_id)
    proxmox = get_proxmox_connection(service.node.cluster)
    node = proxmox.nodes(service.node)
    machine = None
    if service.service_plan.type == "kvm":
        machine = node.qemu(service.machine_id)
    if service.service_plan.type == "lxc":
        machine = node.lxc(service.machine_id)
    return machine, service


def get_service_node(service_id):
    service = Service.objects.get(pk=service_id)
    proxmox = get_proxmox_connection(service.node.cluster)
    node = proxmox.nodes(service.node)
    return node


def get_cluster(cluster_id):
    cluster = Cluster.objects.get(pk=cluster_id)
    proxmox = get_proxmox_connection(cluster)
    return proxmox.cluster


@shared_task(
    name="inveterate.tasks.reset_vm_password",
    base=Singleton,
    lock_expiry=60 * 5,
    autoretry_for=(ConnectionError, ResourceException),
    retry_backoff=5,
    retry_backoff_max=60,
    max_retries=3,
)
def reset_vm_password(service_id, username, password):
    """Reset a user's password inside a KVM guest via QEMU guest agent."""
    machine, service = get_vm(service_id)
    if service.service_plan.type != "kvm":
        raise ValueError("Password reset is only supported for KVM services.")
    proxmox = get_proxmox_connection(service.node.cluster)
    node = proxmox.nodes(service.node)
    node.qemu(service.machine_id).agent("set-user-password").post(
        username=username, password=password, crypted=False
    )
    logger.info("Password reset for user %s on service %s", username, service_id)


@shared_task(
    name="inveterate.tasks.start_vm",
    base=Singleton,
    lock_expiry=60 * 15,
    autoretry_for=(ConnectionError, ResourceException),
    retry_backoff=5,
    retry_backoff_max=60,
    max_retries=3,
)
def start_vm(service_id):
    logger.info("Starting VM for service %s", service_id)
    # operation_in_progress is set True by the dispatching viewset; the finally
    # here guarantees it is cleared even if the power op raises (see models.py).
    Service.objects.filter(pk=service_id).update(operation_in_progress=True)
    try:
        machine, service = get_vm(service_id)
        machine.status.start.post()
    finally:
        Service.objects.filter(pk=service_id).update(operation_in_progress=False, operation_started_at=None)


@shared_task(
    name="inveterate.tasks.stop_vm",
    base=Singleton,
    lock_expiry=60 * 15,
    autoretry_for=(ConnectionError, ResourceException),
    retry_backoff=5,
    retry_backoff_max=60,
    max_retries=3,
)
def stop_vm(service_id):
    logger.info("Stopping VM for service %s", service_id)
    Service.objects.filter(pk=service_id).update(operation_in_progress=True)
    try:
        machine, service = get_vm(service_id)
        machine.status.stop.post()
    finally:
        Service.objects.filter(pk=service_id).update(operation_in_progress=False, operation_started_at=None)


@shared_task(
    name="inveterate.tasks.reset_vm",
    base=Singleton,
    lock_expiry=60 * 15,
    autoretry_for=(ConnectionError, ResourceException),
    retry_backoff=5,
    retry_backoff_max=60,
    max_retries=3,
)
def reset_vm(service_id):
    logger.info("Resetting VM for service %s", service_id)
    Service.objects.filter(pk=service_id).update(operation_in_progress=True)
    try:
        machine, service = get_vm(service_id)
        machine.status.reset.post()
    finally:
        Service.objects.filter(pk=service_id).update(operation_in_progress=False, operation_started_at=None)


@shared_task(
    name="inveterate.tasks.shutdown_vm",
    base=Singleton,
    lock_expiry=60 * 15,
    autoretry_for=(ConnectionError, ResourceException),
    retry_backoff=5,
    retry_backoff_max=60,
    max_retries=3,
)
def shutdown_vm(service_id):
    logger.info("Shutting down VM for service %s", service_id)
    Service.objects.filter(pk=service_id).update(operation_in_progress=True)
    try:
        machine, service = get_vm(service_id)
        machine.status.shutdown.post()
    finally:
        Service.objects.filter(pk=service_id).update(operation_in_progress=False, operation_started_at=None)


@shared_task(
    name="inveterate.tasks.reboot_vm",
    base=Singleton,
    lock_expiry=60 * 15,
    autoretry_for=(ConnectionError, ResourceException),
    retry_backoff=5,
    retry_backoff_max=60,
    max_retries=3,
)
def reboot_vm(service_id):
    logger.info("Rebooting VM for service %s", service_id)
    Service.objects.filter(pk=service_id).update(operation_in_progress=True)
    try:
        machine, service = get_vm(service_id)
        machine.status.reboot.post()
    finally:
        Service.objects.filter(pk=service_id).update(operation_in_progress=False, operation_started_at=None)
