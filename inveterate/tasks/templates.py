import re
import time

from celery import shared_task
from celery_singleton import Singleton
from proxmoxer.core import ResourceException
from requests.exceptions import ConnectionError

from ..models import Cluster, Node, NodeDisk, Template
from ..proxmox import get_proxmox_connection
from ._common import logger


def _wait_for_proxmox_task(node, upid, timeout=600):
    """Poll a Proxmox task UPID until it stops. Raises on failure or timeout."""
    elapsed = 0
    while elapsed < timeout:
        task_status = node.tasks(upid).status.get()
        if task_status["status"] == "stopped":
            if task_status.get("exitstatus", "") != "OK":
                raise RuntimeError(f"Proxmox task {upid} failed: {task_status.get('exitstatus', 'unknown')}")
            return task_status
        time.sleep(5)
        elapsed += 5
    raise TimeoutError(f"Proxmox task {upid} timed out after {timeout}s")


@shared_task(name="inveterate.tasks.sync_templates", base=Singleton, lock_expiry=60 * 15)
def sync_templates():
    """
    Ensure all registered LXC templates are downloaded to every node.
    KVM templates are VM-based (cloned, not downloaded) so they are skipped.
    """
    logger.info("Starting template sync")
    lxc_templates = Template.objects.filter(type="lxc")
    if not lxc_templates.exists():
        logger.info("No LXC templates registered -- nothing to sync")
        return

    downloaded = 0
    already_present = 0
    errors = 0

    for cluster in Cluster.objects.all():
        try:
            proxmox = get_proxmox_connection(cluster, timeout=120)

            for node in Node.objects.filter(cluster=cluster):
                # Get templates already on this node
                try:
                    existing = {
                        item["volid"]
                        for item in proxmox.nodes(node.name).storage("local").content.get()
                        if item.get("content") == "vztmpl"
                    }
                except ResourceException as e:
                    logger.error("Cannot list storage on %s: %s", node.name, e)
                    errors += 1
                    continue

                for template in lxc_templates:
                    volid = f"local:vztmpl/{template.file}"
                    if volid in existing:
                        already_present += 1
                        continue

                    # Check appliance index for this template
                    try:
                        available = proxmox.nodes(node.name).aplinfo.get()
                        match = next((t for t in available if t.get("template") == template.file), None)
                        if not match:
                            logger.warning("Template '%s' not found in appliance index for %s", template.file, node.name)
                            errors += 1
                            continue

                        logger.info("Downloading '%s' to %s", template.file, node.name)
                        proxmox.nodes(node.name).aplinfo.post(storage="local", template=template.file)
                        downloaded += 1
                    except ResourceException as e:
                        logger.error("Failed to download '%s' to %s: %s", template.file, node.name, e)
                        errors += 1

        except ConnectionError as e:
            logger.error("Cannot connect to cluster %s: %s", cluster.name, e)
            errors += 1
        except Exception as e:
            logger.error("Error syncing templates on cluster %s: %s", cluster.name, e, exc_info=True)
            errors += 1

    logger.info("Template sync completed: %s downloaded, %s already present, %s errors", downloaded, already_present, errors)


@shared_task(name="inveterate.tasks.import_kvm_template", base=Singleton, lock_expiry=60 * 30)
def import_kvm_template(template_id):
    """Download a cloud image and create a KVM template VM in Proxmox."""
    logger.info("Starting KVM template import for template %s", template_id)
    template = Template.objects.get(pk=template_id)

    if template.type != "kvm":
        template.status = "error"
        template.status_msg = "Only KVM templates can be imported"
        template.save()
        logger.error("Template %s is not KVM type", template_id)
        return

    if not template.source_url:
        template.status = "error"
        template.status_msg = "source_url is required for cloud image import"
        template.save()
        logger.error("Template %s has no source_url", template_id)
        return

    template.status = "importing"
    template.status_msg = ""
    template.save()

    # Pick target node
    target_node = None
    if template.node:
        target_node = template.node
    else:
        target_node = Node.objects.first()
        if not target_node:
            template.status = "error"
            template.status_msg = "No nodes available"
            template.save()
            logger.error("No nodes available for template %s", template_id)
            return
        template.node = target_node
        template.save(update_fields=["node"])

    cluster = target_node.cluster
    try:
        proxmox = get_proxmox_connection(cluster, timeout=600)
        node = proxmox.nodes(target_node.name)

        # Get primary storage for VM disk
        primary_disk = NodeDisk.objects.get(node=target_node, primary=True)
        vm_stor = primary_disk.name

        # Find a dir-type storage for downloading (download-url requires
        # dir/nfs/cifs/cephfs with 'import' content type, not rbd/zfs).
        dl_stor = vm_stor
        for s in node.storage.get():
            if s["type"] in ("dir", "nfs", "cifs", "cephfs") and "import" in s.get("content", ""):
                dl_stor = s["storage"]
                break

        # Extract filename from URL; Proxmox download-url requires a
        # recognised disk extension (.qcow2, .raw, .vmdk, .iso).  Cloud
        # images often use ".img" which is typically QCOW2 -- rename to
        # .qcow2 so Proxmox accepts it.
        filename = template.source_url.rstrip("/").split("/")[-1]
        if filename.endswith(".img"):
            filename = filename[:-4] + ".qcow2"

        # Remove any leftover import file from a previous attempt
        volid = f"{dl_stor}:import/{filename}"
        try:
            node.storage(dl_stor).content.delete(volid)
            logger.info("Removed stale import file %s", volid)
        except ResourceException:
            pass

        # Download image to node storage
        logger.info("Downloading %s to %s:%s", filename, target_node.name, dl_stor)
        upid = node.storage(dl_stor)("download-url").post(
            content="import",
            filename=filename,
            url=template.source_url,
        )
        _wait_for_proxmox_task(node, upid)

        # Reserve VMID
        vmid = proxmox.cluster.nextid.get()
        logger.info("Creating template VM %s on %s", vmid, target_node.name)

        # Create VM with imported disk on primary storage.
        # Sanitise name -- Proxmox requires valid DNS hostname.
        vm_name = re.sub(r"[^a-zA-Z0-9\-]", "-", template.name).strip("-")[:63]
        create_upid = node.qemu.post(
            vmid=vmid,
            name=vm_name,
            scsi0=f"{vm_stor}:0,import-from={dl_stor}:import/{filename}",
            ide2=f"{vm_stor}:cloudinit",
            serial0="socket",
            vga="serial0",
            boot="order=scsi0",
            agent="enabled=1",
            ostype="l26",
            scsihw="virtio-scsi-single",
        )
        _wait_for_proxmox_task(node, create_upid)

        # Convert to template
        logger.info("Converting VM %s to template", vmid)
        node.qemu(vmid).template.post()

        template.file = str(vmid)
        template.status = "ready"
        template.status_msg = ""
        template.save()
        logger.info("KVM template %s imported successfully as VMID %s", template_id, vmid)

    except NodeDisk.DoesNotExist:
        error_msg = f"No primary storage disk configured for node {target_node.name}"
        logger.error("Failed to import template %s: %s", template_id, error_msg)
        template.status = "error"
        template.status_msg = error_msg
        template.save()
        raise
    except ConnectionError as e:
        error_msg = f"Cannot connect to Proxmox cluster at {cluster.host}"
        logger.error("Failed to import template %s: %s - %s", template_id, error_msg, e)
        template.status = "error"
        template.status_msg = error_msg
        template.save()
        raise
    except ResourceException as e:
        error_msg = f"Proxmox API error: {str(e)}"
        logger.error("Failed to import template %s: %s", template_id, error_msg)
        template.status = "error"
        template.status_msg = error_msg
        template.save()
        raise
    except Exception as e:
        error_msg = f"Unexpected error during import: {str(e)}"
        logger.error("Failed to import template %s: %s", template_id, error_msg, exc_info=True)
        template.status = "error"
        template.status_msg = str(e)
        template.save()
        raise


@shared_task(name="inveterate.tasks.sync_kvm_templates", base=Singleton, lock_expiry=60 * 15)
def sync_kvm_templates():
    """
    Periodic task to ensure KVM cloud image templates are available.
    Re-imports missing or failed templates.
    """
    logger.info("Starting KVM template sync")
    kvm_templates = Template.objects.filter(type="kvm").exclude(source_url="")
    if not kvm_templates.exists():
        logger.info("No KVM cloud image templates registered -- nothing to sync")
        return

    checked = 0
    reimported = 0
    errors = 0

    for template in kvm_templates:
        checked += 1

        # Retry pending/error templates
        if template.status in ("pending", "error"):
            logger.info("Retrying import for template %s (%s)", template.id, template.name)
            import_kvm_template.delay(template.id)
            reimported += 1
            continue

        # For ready templates, verify the VM still exists in the cluster
        if template.status == "ready" and template.file and template.node:
            try:
                cluster = template.node.cluster
                proxmox = get_proxmox_connection(cluster)
                vmid = int(template.file)
                found = any(r["vmid"] == vmid for r in proxmox.cluster.resources.get(type="vm"))
                if not found:
                    logger.warning(
                        "Template VM %s missing for template %s (%s), re-importing",
                        vmid, template.id, template.name,
                    )
                    template.file = ""
                    template.status = "pending"
                    template.status_msg = "Template VM missing from cluster"
                    template.save()
                    import_kvm_template.delay(template.id)
                    reimported += 1
            except ConnectionError as e:
                logger.error("Cannot connect to verify template %s: %s", template.id, e)
                errors += 1
            except Exception as e:
                logger.error("Error checking template %s: %s", template.id, e, exc_info=True)
                errors += 1

    logger.info("KVM template sync completed: %s checked, %s re-imported, %s errors", checked, reimported, errors)
