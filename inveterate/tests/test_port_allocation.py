from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

class TestPortBlockAllocation(TestCase):

    def test_assign_ips_creates_port_block_for_internal_ip(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        gw = _port_gateway(pools=[pool_int])
        for i in range(5):
            IP.objects.create(pool=pool_int, value=f'192.168.0.{10+i}')

        sp = _service_plan(storage=disk, ipv4_ips=0, ipv6_ips=0, internal_ips=1)
        svc = _service(user, node, sp)

        from ..tasks import assign_ips
        assign_ips(svc.id)

        sn = ServiceNetwork.objects.filter(service=svc).first()
        self.assertIsNotNone(sn)
        self.assertTrue(hasattr(sn, 'port_block'))
        pb = sn.port_block
        self.assertEqual(pb.gateway, gw)
        self.assertEqual(pb.port_start, 10000)
        self.assertEqual(pb.port_end, 10099)

    def test_skips_external_ips(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_ext = _ip_pool(node)
        IP.objects.create(pool=pool_ext, value='10.0.0.10')

        sp = _service_plan(storage=disk, ipv4_ips=1, ipv6_ips=0, internal_ips=0)
        svc = _service(user, node, sp)

        from ..tasks import assign_ips
        assign_ips(svc.id)

        sn = ServiceNetwork.objects.filter(service=svc).first()
        self.assertIsNotNone(sn)
        self.assertFalse(hasattr(sn, 'port_block'))

    def test_idempotent_port_block(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        gw = _port_gateway(pools=[pool_int])
        IP.objects.create(pool=pool_int, value='192.168.0.10')

        sp = _service_plan(storage=disk, ipv4_ips=0, ipv6_ips=0, internal_ips=1)
        svc = _service(user, node, sp)

        from ..tasks import assign_ips
        assign_ips(svc.id)
        first_count = PortBlock.objects.filter(gateway=gw).count()
        assign_ips(svc.id)
        second_count = PortBlock.objects.filter(gateway=gw).count()
        self.assertEqual(first_count, second_count)

    def test_allocates_sequential_blocks(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        gw = _port_gateway(pools=[pool_int])
        for i in range(3):
            IP.objects.create(pool=pool_int, value=f'192.168.0.{10+i}')

        # Service 1
        sp1 = _service_plan(storage=disk, ipv4_ips=0, ipv6_ips=0, internal_ips=1)
        svc1 = _service(user, node, sp1, hostname='s1.example.com')
        from ..tasks import assign_ips
        assign_ips(svc1.id)

        # Service 2
        sp2 = _service_plan(storage=disk, ipv4_ips=0, ipv6_ips=0, internal_ips=1)
        svc2 = _service(user, node, sp2, hostname='s2.example.com')
        assign_ips(svc2.id)

        blocks = list(PortBlock.objects.filter(gateway=gw).order_by('port_start'))
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].port_start, 10000)
        self.assertEqual(blocks[1].port_start, 10100)

    def test_resized_gateway_does_not_allocate_overlapping_block(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        gw = _port_gateway(pools=[pool_int], block_size=100)
        for i in range(2):
            IP.objects.create(pool=pool_int, value=f'192.168.0.{10+i}')

        sp1 = _service_plan(storage=disk, ipv4_ips=0, ipv6_ips=0, internal_ips=1)
        svc1 = _service(user, node, sp1, hostname='s1.example.com')
        from ..tasks import assign_ips
        assign_ips(svc1.id)

        gw.block_size = 30
        gw.save(update_fields=['block_size'])
        sp2 = _service_plan(storage=disk, ipv4_ips=0, ipv6_ips=0, internal_ips=1)
        svc2 = _service(user, node, sp2, hostname='s2.example.com')
        assign_ips(svc2.id)

        blocks = list(PortBlock.objects.filter(gateway=gw).order_by('port_start'))
        self.assertEqual([(block.port_start, block.port_end) for block in blocks], [
            (10000, 10099),
            (10120, 10149),
        ])
        self.assertLess(blocks[0].port_end, blocks[1].port_start)

    def test_handles_full_gateway(self):
        """When the gateway has no available port slots, allocation raises."""
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        # Gateway with space for only 1 block (10000-10099)
        gw = _port_gateway(pools=[pool_int], port_range_start=10000, port_range_end=10099, block_size=100)
        for i in range(2):
            IP.objects.create(pool=pool_int, value=f'192.168.0.{10+i}')

        # Service 1 takes the only block
        sp1 = _service_plan(storage=disk, ipv4_ips=0, ipv6_ips=0, internal_ips=1)
        svc1 = _service(user, node, sp1, hostname='s1.example.com')
        from ..tasks import assign_ips
        assign_ips(svc1.id)
        self.assertEqual(PortBlock.objects.filter(gateway=gw).count(), 1)

        # Service 2 can't get a block — should raise
        sp2 = _service_plan(storage=disk, ipv4_ips=0, ipv6_ips=0, internal_ips=1)
        svc2 = _service(user, node, sp2, hostname='s2.example.com')
        with self.assertRaises(RuntimeError):
            assign_ips(svc2.id)
        # Still only 1 block
        self.assertEqual(PortBlock.objects.filter(gateway=gw).count(), 1)


# ===================================================================
# TestPortBlockDeallocation
# ===================================================================

class TestPortBlockDeallocation(TestCase):

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_cancel_service_cascades_to_port_block(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.tasks.return_value.status.get.return_value = {'status': 'stopped', 'exitstatus': 'OK'}

        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        gw = _port_gateway(pools=[pool_int])
        ip = IP.objects.create(pool=pool_int, value='192.168.0.10')

        tpl = _template(type='kvm', file='100')
        sp = _service_plan(template=tpl, storage=disk, type='kvm')
        svc = _service(user, node, sp, machine_id=1000001)

        sn = ServiceNetwork.objects.create(service=svc)
        ip.owner = sn
        ip.save()
        pb = PortBlock.objects.create(gateway=gw, service_network=sn, port_start=10000, port_end=10099)

        from ..tasks import cancel_service
        cancel_service(svc.id)

        self.assertEqual(PortBlock.objects.filter(pk=pb.pk).count(), 0)


# ===================================================================
# TestPortForwardValidation
# ===================================================================

class TestPortForwardValidation(TestCase):

    def setUp(self):
        self.user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        self.gw = _port_gateway(pools=[pool_int])
        ip = IP.objects.create(pool=pool_int, value='192.168.0.10')
        sp = _service_plan(storage=disk)
        self.svc = _service(self.user, node, sp)
        self.sn = ServiceNetwork.objects.create(service=self.svc)
        ip.owner = self.sn
        ip.save()
        self.pb = PortBlock.objects.create(
            gateway=self.gw, service_network=self.sn, port_start=10000, port_end=10099,
        )

    @patch('inveterate.serializers.sync_port_forward')
    def test_external_port_within_range(self, mock_sync):
        mock_sync.delay.return_value = MagicMock(id='task-1')
        from ..serializers import PortForwardSerializer
        data = {
            'port_block': self.pb.id,
            'external_port': 10050,
            'internal_port': 22,
            'protocol': 'tcp',
        }
        ser = PortForwardSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)

    @patch('inveterate.serializers.sync_port_forward')
    def test_external_port_out_of_range(self, mock_sync):
        from ..serializers import PortForwardSerializer
        data = {
            'port_block': self.pb.id,
            'external_port': 9999,
            'internal_port': 22,
            'protocol': 'tcp',
        }
        ser = PortForwardSerializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn('external_port', ser.errors)

    @patch('inveterate.serializers.sync_port_forward')
    def test_internal_port_out_of_range(self, mock_sync):
        from ..serializers import PortForwardSerializer
        data = {
            'port_block': self.pb.id,
            'external_port': 10001,
            'internal_port': 0,
            'protocol': 'tcp',
        }
        ser = PortForwardSerializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn('internal_port', ser.errors)

    @patch('inveterate.serializers.sync_port_forward')
    def test_unique_constraint(self, mock_sync):
        mock_sync.delay.return_value = MagicMock(id='task-1')
        PortForward.objects.create(
            port_block=self.pb, external_port=10001, internal_port=22, protocol='tcp',
        )
        with self.assertRaises(IntegrityError):
            PortForward.objects.create(
                port_block=self.pb, external_port=10001, internal_port=80, protocol='tcp',
            )


# ===================================================================
# TestPortForwardViewSet
# ===================================================================

class TestPortForwardViewSet(TestCase):

    def setUp(self):
        self.admin = _admin()
        self.user = _user()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        self.gw = _port_gateway(pools=[pool_int])

        # Admin's service + port block
        ip1 = IP.objects.create(pool=pool_int, value='192.168.0.10')
        sp1 = _service_plan(storage=disk)
        self.admin_svc = _service(self.admin, node, sp1, hostname='admin.example.com')
        sn1 = ServiceNetwork.objects.create(service=self.admin_svc)
        ip1.owner = sn1
        ip1.save()
        self.admin_pb = PortBlock.objects.create(
            gateway=self.gw, service_network=sn1, port_start=10000, port_end=10099,
        )

        # User's service + port block
        ip2 = IP.objects.create(pool=pool_int, value='192.168.0.11')
        sp2 = _service_plan(storage=disk)
        self.user_svc = _service(self.user, node, sp2, hostname='user.example.com')
        sn2 = ServiceNetwork.objects.create(service=self.user_svc)
        ip2.owner = sn2
        ip2.save()
        self.user_pb = PortBlock.objects.create(
            gateway=self.gw, service_network=sn2, port_start=10100, port_end=10199,
        )

        self.client = APIClient()

    @patch('inveterate.serializers.sync_port_forward')
    def test_user_creates_forward_on_own_block(self, mock_sync):
        mock_sync.delay.return_value = MagicMock(id='task-1')
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/api/v1/portforwards/', {
            'port_block': self.user_pb.id,
            'external_port': 10100,
            'internal_port': 22,
            'protocol': 'tcp',
        })
        self.assertEqual(resp.status_code, 201)

    def test_user_only_sees_own_forwards(self):
        PortForward.objects.create(
            port_block=self.admin_pb, external_port=10001, internal_port=22, protocol='tcp',
        )
        PortForward.objects.create(
            port_block=self.user_pb, external_port=10100, internal_port=22, protocol='tcp',
        )

        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/v1/portforwards/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 1)
        self.assertEqual(resp.data['results'][0]['external_port'], 10100)

    def test_admin_sees_all_forwards(self):
        PortForward.objects.create(
            port_block=self.admin_pb, external_port=10001, internal_port=22, protocol='tcp',
        )
        PortForward.objects.create(
            port_block=self.user_pb, external_port=10100, internal_port=22, protocol='tcp',
        )

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get('/api/v1/portforwards/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 2)

    @patch('inveterate.serializers.sync_port_forward')
    def test_non_owner_rejected(self, mock_sync):
        """User cannot create forward on admin's port block."""
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/api/v1/portforwards/', {
            'port_block': self.admin_pb.id,
            'external_port': 10050,
            'internal_port': 22,
            'protocol': 'tcp',
        })
        self.assertEqual(resp.status_code, 400)


# ===================================================================
# TestDomainRouteValidation
# ===================================================================

