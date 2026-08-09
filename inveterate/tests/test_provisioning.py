from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

class TestProvisionService(TestCase):

    def _setup_service(self, svc_type='lxc'):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        tpl = _template(type=svc_type, file='100' if svc_type == 'kvm' else 'debian.tar.zst')
        sp = _service_plan(template=tpl, storage=disk, type=svc_type, ipv4_ips=0)
        svc = _service(user, node, sp, status='pending')
        return svc

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_lxc_provisioning_uses_storage_name(self, mock_cls, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.return_value.firewall.rules.get.return_value = []
        mock_node.lxc.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_service('lxc')
        from ..tasks import provision_service
        provision_service(svc.id, 'testpass')

        # Check lxc.create was called
        mock_node.lxc.create.assert_called_once()
        call_kwargs = mock_node.lxc.create.call_args[1]
        self.assertEqual(call_kwargs['storage'], 'local-lvm')
        self.assertEqual(call_kwargs['rootfs'], f'local-lvm:{svc.service_plan.size}')

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_lxc_sets_status_active(self, mock_cls, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.return_value.firewall.rules.get.return_value = []
        mock_node.lxc.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_service('lxc')
        from ..tasks import provision_service
        provision_service(svc.id, 'testpass')

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'active')

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_sets_bw_renewal_dtm(self, mock_cls, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.return_value.firewall.rules.get.return_value = []
        mock_node.lxc.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_service('lxc')
        self.assertIsNone(svc.bw_renewal_dtm)
        from ..tasks import provision_service
        provision_service(svc.id, 'testpass')
        svc.refresh_from_db()
        self.assertIsNotNone(svc.bw_renewal_dtm)

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_connection_error_sets_error_status(self, mock_cls, _mock_inv):
        from requests.exceptions import ConnectionError
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        # ConnectionError inside the main try block (lxc.create)
        mock_node.lxc.create.side_effect = ConnectionError("refused")

        svc = self._setup_service('lxc')
        from ..tasks import provision_service
        # Retryable ConnectionErrors now preserve state; exhaust retries to
        # exercise the terminal error path.
        with patch.object(provision_service, 'max_retries', 0):
            with self.assertRaises(ConnectionError):
                provision_service(svc.id, 'testpass')
        svc.refresh_from_db()
        self.assertEqual(svc.status, 'error')

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_resource_exception_sets_error_status(self, mock_cls, _mock_inv):
        from proxmoxer.core import ResourceException
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        # pools.post succeeds (creating inveterate pool)
        mock_proxmox.pools.post.side_effect = ResourceException(500, 'exists', 'already exists')
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        # lxc.create raises ResourceException
        mock_node.lxc.create.side_effect = ResourceException(500, 'fail', 'some error')

        svc = self._setup_service('lxc')
        from ..tasks import provision_service
        with self.assertRaises(ResourceException):
            provision_service(svc.id, 'testpass')
        svc.refresh_from_db()
        self.assertEqual(svc.status, 'error')

    @patch('inveterate.tasks.provisioning.time.sleep')
    @patch('inveterate.tasks._common.subprocess.run')
    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_kvm_provisioning_calls_clone(self, mock_cls, _mock_inv, mock_run, _mock_sleep):
        from proxmoxer.core import ResourceException
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        # Node IP resolution (for the SSH cloud-init snippet write)
        mock_proxmox.cluster.status.get.return_value = [
            {'type': 'node', 'name': 'pve1', 'ip': '192.0.2.10'}
        ]
        mock_run.return_value = MagicMock(returncode=0, stdout=b'', stderr=b'')
        # Template pool lookup
        mock_proxmox.pools.return_value.get.return_value = {'members': []}
        # First status check is the "does the VM already exist?" guard — it must
        # report absent so the clone runs; subsequent checks are the post-clone
        # lock poll, which must report an unlocked VM so the loop exits.
        _checks = {'n': 0}

        def _status(*_a, **_k):
            _checks['n'] += 1
            if _checks['n'] == 1:
                raise ResourceException(500, 'not found', 'no such VM')
            return {'status': 'stopped'}

        mock_node.qemu.return_value.status.current.get.side_effect = _status
        mock_node.qemu.return_value.firewall.rules.get.return_value = []
        mock_node.qemu.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_service('kvm')
        from ..tasks import provision_service
        provision_service(svc.id, 'testpass')

        # clone.post should have been called
        mock_node.qemu.return_value.clone.post.assert_called_once()
        svc.refresh_from_db()
        self.assertEqual(svc.status, 'active')

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_default_storage_fallback(self, mock_cls, _mock_inv):
        """When service_plan.storage is None, provision should grab primary disk and use it."""
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.return_value.firewall.rules.get.return_value = []
        mock_node.lxc.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_service('lxc')
        svc.service_plan.storage = None
        svc.service_plan.save()

        from ..tasks import provision_service
        provision_service(svc.id, 'testpass')
        # Verify lxc.create was called with the primary disk's storage name
        mock_node.lxc.create.assert_called_once()
        call_kwargs = mock_node.lxc.create.call_args[1]
        self.assertEqual(call_kwargs['storage'], 'local-lvm')


# ===================================================================
# TestProvisionServiceIdempotency
# ===================================================================

class TestProvisionServiceIdempotency(TestCase):

    def _setup_service(self, status='pending'):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        tpl = _template()
        sp = _service_plan(template=tpl, storage=disk, ipv4_ips=0)
        return _service(user, node, sp, status=status)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_destroyed_service_skips_provisioning(self, mock_cls):
        """Service with status 'destroyed' should skip provisioning entirely."""
        svc = self._setup_service(status='destroyed')
        from ..tasks import provision_service
        provision_service(svc.id, 'testpass')
        mock_cls.assert_not_called()

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_pending_service_proceeds(self, mock_cls, _mock_inv):
        """Service with status 'pending' should proceed with provisioning."""
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.return_value.firewall.rules.get.return_value = []
        mock_node.lxc.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_service(status='pending')
        from ..tasks import provision_service
        provision_service(svc.id, 'testpass')

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'active')

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_error_service_with_machine_id_skips(self, mock_cls, _mock_inv):
        """Service with status 'error' and existing machine_id should not re-provision
        (it would fail in setup anyway — tests the guard doesn't let it through)."""
        svc = self._setup_service(status='error')
        svc.machine_id = 1000001
        svc.save(update_fields=['machine_id'])
        from ..tasks import provision_service
        # Error status is not in the guard, so Proxmox will be called; this test
        # documents the current behavior: error status proceeds (allows retry).
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.return_value.firewall.rules.get.return_value = []
        mock_node.lxc.return_value.firewall.ipset.return_value.get.return_value = []
        provision_service(svc.id, 'testpass')
        # Should have called Proxmox (provisioning proceeded)
        mock_cls.assert_called_once()


# ===================================================================
# TestAssignIps
# ===================================================================

class TestAssignIps(TestCase):

    def test_service_network_net_ids_are_sequential(self):
        user = _admin()
        node = _node()
        svc = _service(user, node, _service_plan())

        networks = [ServiceNetwork.objects.create(service=svc) for _ in range(3)]

        self.assertEqual([network.net_id for network in networks], [0, 1, 2])

    def test_service_network_integrity_error_is_retried(self):
        user = _admin()
        node = _node()
        disk = _disk(node)
        pool = _ip_pool(node)
        IP.objects.create(pool=pool, value='10.0.0.10')
        svc = _service(user, node, _service_plan(storage=disk, ipv4_ips=1))
        original_create = ServiceNetwork.objects.create
        calls = 0

        def flaky_create(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise IntegrityError('simulated net_id race')
            return original_create(*args, **kwargs)

        from ..tasks import assign_ips
        with patch.object(ServiceNetwork.objects, 'create', side_effect=flaky_create):
            assign_ips(svc.id)

        self.assertEqual(calls, 2)
        self.assertEqual(ServiceNetwork.objects.filter(service=svc).count(), 1)

    def test_assigns_correct_number_of_ips(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_v4 = _ip_pool(node, name='pub-v4', type='ipv4', internal=False)
        pool_v6 = _ip_pool(node, name='pub-v6', type='ipv6', network='2001:db8::', gateway='2001:db8::1', internal=False)
        pool_int = _ip_pool(node, name='internal', type='ipv4', network='192.168.0.0', gateway='192.168.0.1', internal=True)
        # Create IPs in each pool
        for i in range(5):
            IP.objects.create(pool=pool_v4, value=f'10.0.0.{10+i}')
            IP.objects.create(pool=pool_v6, value=f'2001:db8::{10+i}')
            IP.objects.create(pool=pool_int, value=f'192.168.0.{10+i}')

        sp = _service_plan(storage=disk, ipv4_ips=2, ipv6_ips=1, internal_ips=1)
        svc = _service(user, node, sp)

        from ..tasks import assign_ips
        assign_ips(svc.id)

        networks = ServiceNetwork.objects.filter(service=svc)
        self.assertEqual(networks.count(), 4)  # 2 + 1 + 1

        # Check types
        assigned = IP.objects.filter(owner__service=svc)
        v4_count = sum(1 for ip in assigned if ip.pool.type == 'ipv4' and not ip.pool.internal)
        v6_count = sum(1 for ip in assigned if ip.pool.type == 'ipv6')
        int_count = sum(1 for ip in assigned if ip.pool.internal)
        self.assertEqual(v4_count, 2)
        self.assertEqual(v6_count, 1)
        self.assertEqual(int_count, 1)

    def test_idempotent_skip_if_already_assigned(self):
        user = _admin()
        node = _node()
        disk = _disk(node)
        pool = _ip_pool(node)
        IP.objects.create(pool=pool, value='10.0.0.10')
        IP.objects.create(pool=pool, value='10.0.0.11')

        sp = _service_plan(storage=disk, ipv4_ips=1)
        svc = _service(user, node, sp)

        from ..tasks import assign_ips
        assign_ips(svc.id)
        first_count = ServiceNetwork.objects.filter(service=svc).count()
        # Run again
        assign_ips(svc.id)
        second_count = ServiceNetwork.objects.filter(service=svc).count()
        self.assertEqual(first_count, second_count)

    def test_raises_when_pool_exhausted(self):
        """Should raise RuntimeError when matching pools exist but have no free IPs."""
        user = _admin()
        node = _node()
        disk = _disk(node)
        pool = _ip_pool(node)
        # Create only 1 IP but request 2
        IP.objects.create(pool=pool, value='10.0.0.10')

        sp = _service_plan(storage=disk, ipv4_ips=2)
        svc = _service(user, node, sp)

        from ..tasks import assign_ips
        with self.assertRaises(RuntimeError):
            assign_ips(svc.id)

    def test_allocates_port_blocks_for_internal_ips(self):
        """Internal IPs should get port blocks allocated from matching gateways."""
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _ip_pool(node, name='internal', type='ipv4', network='192.168.0.0', gateway='192.168.0.1', internal=True)
        IP.objects.create(pool=pool_int, value='192.168.0.10')

        gw = PortGateway.objects.create(
            name='gw1', host='gw.test', admin_email='a@b.com', admin_password='pw',
            port_range_start=10000, port_range_end=60000, block_size=100,
        )
        gw.pools.add(pool_int)

        sp = _service_plan(storage=disk, ipv4_ips=0, internal_ips=1)
        svc = _service(user, node, sp)

        from ..tasks import assign_ips
        assign_ips(svc.id)

        blocks = PortBlock.objects.filter(gateway=gw, service_network__service=svc)
        self.assertEqual(blocks.count(), 1)
        self.assertEqual(blocks.first().port_start, 10000)
        self.assertEqual(blocks.first().port_end, 10099)


# ===================================================================
# TestMeterBandwidth
# ===================================================================

class TestComposeCloudInit(TestCase):

    def test_merges_packages_runcmd_write_files(self):
        from ..tasks import _compose_cloud_init
        a1 = AppProfile.objects.create(
            name='Docker',
            cloud_init='packages:\n  - curl\nruncmd:\n  - curl -fsSL https://get.docker.com | sh',
        )
        a2 = AppProfile.objects.create(
            name='Minecraft',
            cloud_init=(
                'packages:\n  - openjdk-21-jre-headless\n'
                'write_files:\n  - path: /etc/mc.conf\n    content: hello\n'
                'runcmd:\n  - echo mc'
            ),
        )
        result = _compose_cloud_init(AppProfile.objects.filter(pk__in=[a1.pk, a2.pk]))
        self.assertTrue(result.startswith('#cloud-config\n'))
        import yaml
        doc = yaml.safe_load(result)
        self.assertEqual(doc['packages'], ['curl', 'openjdk-21-jre-headless'])
        self.assertEqual(doc['runcmd'], ['curl -fsSL https://get.docker.com | sh', 'echo mc'])
        self.assertEqual(len(doc['write_files']), 1)
        self.assertEqual(doc['write_files'][0]['path'], '/etc/mc.conf')

    def test_empty_apps_returns_empty_string(self):
        from ..tasks import _compose_cloud_init
        result = _compose_cloud_init(AppProfile.objects.none())
        self.assertEqual(result, '')

    def test_invalid_yaml_skipped(self):
        from ..tasks import _compose_cloud_init
        a1 = AppProfile.objects.create(name='Good', cloud_init='packages:\n  - curl')
        a2 = AppProfile.objects.create(name='Bad', cloud_init='just a string')
        result = _compose_cloud_init(AppProfile.objects.filter(pk__in=[a1.pk, a2.pk]))
        import yaml
        doc = yaml.safe_load(result)
        self.assertEqual(doc['packages'], ['curl'])


# ===================================================================
# TestProvisionServiceApps
# ===================================================================

class TestProvisionServiceApps(TestCase):

    def _setup_kvm_service(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        tpl = _template(type='kvm', file='100')
        sp = _service_plan(template=tpl, storage=disk, type='kvm', ipv4_ips=0)
        svc = _service(user, node, sp, status='pending')
        return svc

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.tasks.provisioning.write_snippet')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_provision_uploads_snippet_when_apps_selected(self, mock_cls, mock_write, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.qemu.return_value.status.current.get.return_value = {'status': 'stopped'}
        mock_node.qemu.return_value.firewall.rules.get.return_value = []
        mock_node.qemu.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_kvm_service()
        app = _app_profile(name='Docker', cloud_init='packages:\n  - curl\nruncmd:\n  - echo docker')
        svc.service_plan.apps.add(app)

        from ..tasks import provision_service
        provision_service(svc.id, 'testpass')
        svc.refresh_from_db()

        # Verify snippet was written via SSH
        mock_write.assert_called_once()
        call_args = mock_write.call_args
        self.assertEqual(call_args[0][1], svc.node.name)
        self.assertIn(f'ci-{svc.machine_id}', call_args[0][2])

        # Verify cicustom was set in vm config
        config_call = mock_node.qemu.return_value.config.post
        config_call.assert_called_once()
        config_kwargs = config_call.call_args[1]
        self.assertIn('cicustom', config_kwargs)
        self.assertIn(f'ci-{svc.machine_id}.yml', config_kwargs['cicustom'])

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.tasks.provisioning.write_snippet')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_provision_writes_base_snippet_when_no_apps(self, mock_cls, mock_write, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.qemu.return_value.status.current.get.return_value = {'status': 'stopped'}
        mock_node.qemu.return_value.firewall.rules.get.return_value = []
        mock_node.qemu.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_kvm_service()

        from ..tasks import provision_service
        provision_service(svc.id, 'testpass')

        # KVM always writes a snippet (qemu-guest-agent + identity fields)
        mock_write.assert_called_once()
        snippet_content = mock_write.call_args[0][3]
        self.assertIn('qemu-guest-agent', snippet_content)
        # No app-specific content beyond the base
        self.assertNotIn('curl', snippet_content)


# ===================================================================
# TestCancelServiceSnippetCleanup
# ===================================================================

