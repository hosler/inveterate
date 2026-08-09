from unittest.mock import MagicMock, patch

from requests.exceptions import ConnectionError

from .helpers import *  # noqa: F401,F403
from .helpers import _admin, _cluster, _disk, _ip_pool, _node, _service, _service_plan
from ..models import DriftFinding
from ..reconcile import upsert_finding
from ..tasks import reconcile_db_drift, reconcile_proxmox_drift


class TestReconcileProxmoxDrift(TestCase):
    def setUp(self):
        self.cluster = _cluster()
        self.node = _node(cluster=self.cluster)
        self.plan = _service_plan(storage=_disk(self.node), type="lxc", cores=2, ram=1024)
        self.service = _service(
            _admin(), self.node, self.plan, status="active", machine_id=1000001,
        )

    @patch("inveterate.proxmox.ProxmoxAPI")
    def test_fires_on_drift(self, proxmox_cls):
        proxmox_cls.return_value.cluster.resources.get.return_value = []

        reconcile_proxmox_drift()

        finding = DriftFinding.objects.get(kind="ghost-service")
        self.assertEqual(finding.severity, "critical")
        self.assertIsNone(finding.resolved_at)

    @patch("inveterate.proxmox.ProxmoxAPI")
    def test_resolves_on_clean_rerun(self, proxmox_cls):
        resources = proxmox_cls.return_value.cluster.resources.get
        resources.return_value = []
        reconcile_proxmox_drift()

        self.service.status = "suspended"
        self.service.save(update_fields=("status",))
        resources.return_value = [{
            "vmid": self.service.machine_id, "node": self.node.name,
            "status": "stopped", "maxcpu": 2, "maxmem": 1024 * 1024 * 1024,
        }]
        reconcile_proxmox_drift()

        self.assertIsNotNone(DriftFinding.objects.get(kind="ghost-service").resolved_at)

    @patch("inveterate.proxmox.ProxmoxAPI")
    def test_skips_in_flight_operations(self, proxmox_cls):
        self.service.operation_in_progress = True
        self.service.operation_started_at = timezone.now()
        self.service.save(update_fields=("operation_in_progress", "operation_started_at"))
        proxmox_cls.return_value.cluster.resources.get.return_value = []

        reconcile_proxmox_drift()

        self.assertFalse(DriftFinding.objects.exists())

    @patch("inveterate.proxmox.ProxmoxAPI")
    def test_unreachable_cluster_emits_and_resolves_nothing_for_scope(self, proxmox_cls):
        finding = upsert_finding(
            "ghost-service", "critical", f"ghost-service:service:{self.service.id}",
            {"cluster_id": self.cluster.id, "service_id": self.service.id},
        )
        previous_last_seen = finding.last_seen
        proxmox_cls.side_effect = ConnectionError("offline")

        reconcile_proxmox_drift()

        finding.refresh_from_db()
        self.assertIsNone(finding.resolved_at)
        self.assertEqual(finding.last_seen, previous_last_seen)
        self.assertEqual(DriftFinding.objects.count(), 1)


class TestReconcileDbDrift(TestCase):
    def setUp(self):
        self.node = _node()
        plan = _service_plan(storage=_disk(self.node), type="lxc")
        self.service = _service(_admin(), self.node, plan, status="destroyed")
        pool = _ip_pool(self.node)
        self.network = ServiceNetwork.objects.create(service=self.service)
        self.ip = IP.objects.create(pool=pool, value="10.0.0.20", owner=self.network)

    def test_fires_on_drift(self):
        reconcile_db_drift()

        finding = DriftFinding.objects.get(kind="stranded-ip")
        self.assertEqual(finding.details["ip_id"], self.ip.id)
        self.assertIsNone(finding.resolved_at)

    def test_resolves_on_clean_rerun(self):
        reconcile_db_drift()
        self.ip.owner = None
        self.ip.save(update_fields=("owner",))

        reconcile_db_drift()

        self.assertIsNotNone(DriftFinding.objects.get(kind="stranded-ip").resolved_at)
