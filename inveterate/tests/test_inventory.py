from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

class TestCalculateInventory(TestCase):

    def test_empty_node(self):
        from ..tasks import calculate_inventory
        node = _node()
        disk = _disk(node, size=500)
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024, ipv4_ips=0)
        calculate_inventory()
        inv = Inventory.objects.get(plan=plan, node=node)
        # limiting factor: cores → 32/2=16, ram → 65536/1024=64, size → 500/10=50
        self.assertEqual(inv.quantity, 16)

    def test_node_with_services(self):
        from ..tasks import calculate_inventory
        user = _admin()
        node = _node()
        disk = _disk(node, size=500)
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024, ipv4_ips=0)
        # Create 5 services consuming resources
        for i in range(5):
            sp = _service_plan(storage=disk, size=10, ram=1024, cores=2, bandwidth=1024)
            _service(user, node, sp, hostname=f's{i}.example.com')
        calculate_inventory()
        inv = Inventory.objects.get(plan=plan, node=node)
        # cores is limiting: (32 - 10)/2 = 11
        self.assertEqual(inv.quantity, 11)

    def test_shared_disk_accounting(self):
        from ..tasks import calculate_inventory
        user = _admin()
        cluster = _cluster()
        node1 = _node(cluster=cluster, name='pve1')
        node2 = _node(cluster=cluster, name='pve2')
        # Both nodes share a Ceph disk
        disk1 = _disk(node1, name='ceph-pool', size=100, shared=True)
        disk2 = _disk(node2, name='ceph-pool', size=100, shared=True)
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024, ipv4_ips=0)
        # Service on node1 using shared storage
        sp = _service_plan(storage=disk1, size=10, ram=1024, cores=2, bandwidth=1024)
        _service(user, node1, sp, hostname='s1.example.com')
        calculate_inventory()
        # Node2 shared disk should see the usage from node1
        inv2 = Inventory.objects.get(plan=plan, node=node2)
        # disk slots for node2: (100 - 10) / 10 = 9  (shared sees node1's usage)
        # cores: 32/2 = 16, ram: 65536/1024 = 64 → lowest is 9 (disk)
        self.assertEqual(inv2.quantity, 9)

    def test_local_disk_accounting(self):
        from ..tasks import calculate_inventory
        user = _admin()
        cluster = _cluster()
        node1 = _node(cluster=cluster, name='pve1')
        node2 = _node(cluster=cluster, name='pve2')
        disk1 = _disk(node1, name='local-lvm', size=100, shared=False)
        disk2 = _disk(node2, name='local-lvm', size=100, shared=False)
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024, ipv4_ips=0)
        # Service on node1 only
        sp = _service_plan(storage=disk1, size=10, ram=1024, cores=2, bandwidth=1024)
        _service(user, node1, sp, hostname='s1.example.com')
        calculate_inventory()
        # Node2 local disk should NOT see node1's usage
        inv2 = Inventory.objects.get(plan=plan, node=node2)
        # disk: 100/10=10, cores: 32/2=16, ram: 65536/1024=64 → disk is bottleneck
        self.assertEqual(inv2.quantity, 10)

    def test_zero_plan_field_no_crash(self):
        from ..tasks import calculate_inventory
        node = _node()
        _disk(node, size=500)
        plan = _plan(bandwidth=0)
        calculate_inventory()
        inv = Inventory.objects.get(plan=plan, node=node)
        # bandwidth=0 → ZeroDivisionError handled → inf, not the bottleneck
        self.assertGreaterEqual(inv.quantity, 0)

    def test_node_without_primary_disk(self):
        from ..tasks import calculate_inventory
        node = _node()
        # No disk at all
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024, ipv4_ips=0)
        calculate_inventory()
        inv = Inventory.objects.get(plan=plan, node=node)
        # disk not factored in, cores is bottleneck: 32/2=16
        self.assertEqual(inv.quantity, 16)

    def test_cluster_bandwidth_cap(self):
        from ..tasks import calculate_inventory
        user = _admin()
        cluster = _cluster(bandwidth=5000)  # 5000 GB cluster cap
        node = _node(cluster=cluster)
        disk = _disk(node, size=500)
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024, ipv4_ips=0)
        # Create 3 services consuming 3*1024=3072 GB of bandwidth
        for i in range(3):
            sp = _service_plan(storage=disk, size=10, ram=1024, cores=2, bandwidth=1024)
            _service(user, node, sp, hostname=f's{i}.example.com')
        calculate_inventory()
        inv = Inventory.objects.get(plan=plan, node=node)
        # Per-node: cores=(32-6)/2=13, ram=(65536-3072)/1024=61, disk=(500-30)/10=47 → 13
        # Cluster bw cap: (5000-3072)/1024=1 → caps to 1
        self.assertEqual(inv.quantity, 1)


# ===================================================================
# TestProvisionService
# ===================================================================

