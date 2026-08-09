from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

class TestMeterBandwidth(TestCase):

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_normal_tick_increase(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_machine = MagicMock()
        mock_proxmox.nodes.return_value.lxc.return_value = mock_machine
        mock_machine.status.current.get.return_value = {
            'uptime': 100, 'netin': 5000, 'netout': 3000,
        }

        user = _admin()
        node = _node()
        disk = _disk(node)
        sp = _service_plan(storage=disk, type='lxc')
        svc = _service(user, node, sp, bw_system_tick=50,
                        bw_renewal_dtm=timezone.now() + timedelta(days=30))

        from ..tasks import meter_bandwidth
        meter_bandwidth()

        svc.refresh_from_db()
        self.assertEqual(svc.bw_usage, 8000)
        self.assertEqual(svc.bw_system_tick, 100)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_vm_restart_banks_correctly(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_machine = MagicMock()
        mock_proxmox.nodes.return_value.lxc.return_value = mock_machine
        mock_machine.status.current.get.return_value = {
            'uptime': 10, 'netin': 100, 'netout': 50,
        }

        user = _admin()
        node = _node()
        disk = _disk(node)
        sp = _service_plan(storage=disk, type='lxc')
        svc = _service(user, node, sp,
                        bw_system_tick=500, bw_usage=10000, bw_stale=2000, bw_banked=0,
                        bw_renewal_dtm=timezone.now() + timedelta(days=30))

        from ..tasks import meter_bandwidth
        meter_bandwidth()

        svc.refresh_from_db()
        # tick < system_tick → restart detected
        # banked += usage - stale = 10000 - 2000 = 8000
        self.assertEqual(svc.bw_banked, 8000)
        # bw_usage reset then set to netin+netout
        self.assertEqual(svc.bw_usage, 150)
        self.assertEqual(svc.bw_stale, 0)
        self.assertEqual(svc.bw_system_tick, 10)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_renewal_resets_bandwidth(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_machine = MagicMock()
        mock_proxmox.nodes.return_value.lxc.return_value = mock_machine
        mock_machine.status.current.get.return_value = {
            'uptime': 100, 'netin': 500, 'netout': 500,
        }

        user = _admin()
        node = _node()
        disk = _disk(node)
        sp = _service_plan(storage=disk, type='lxc')
        svc = _service(user, node, sp,
                        bw_system_tick=50, bw_usage=5000, bw_banked=1000,
                        bw_renewal_dtm=timezone.now() - timedelta(days=1))

        from ..tasks import meter_bandwidth
        meter_bandwidth()

        svc.refresh_from_db()
        # Renewal happened: stale += usage, banked = 0
        self.assertEqual(svc.bw_stale, 5000)
        self.assertEqual(svc.bw_banked, 0)
        # After renewal, normal tick: usage = netin + netout
        self.assertEqual(svc.bw_usage, 1000)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_skip_no_renewal_dtm(self, mock_cls):
        """Services with bw_renewal_dtm=None should be skipped."""
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox

        user = _admin()
        node = _node()
        disk = _disk(node)
        sp = _service_plan(storage=disk, type='lxc')
        svc = _service(user, node, sp, bw_renewal_dtm=None)

        from ..tasks import meter_bandwidth
        meter_bandwidth()

        svc.refresh_from_db()
        # Should remain unchanged
        self.assertEqual(svc.bw_usage, 0)
        self.assertEqual(svc.bw_system_tick, 0)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_two_renewals_then_restart_banks_correctly(self, mock_cls):
        """Two unattended monthly renewals with no reboot in between, then a
        restart, must bank the actual since-last-renewal usage and never go
        negative. With the old ``bw_stale += bw_usage`` accounting the baseline
        accumulated across renewals and bw_banked went negative on restart.
        """
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_machine = MagicMock()
        mock_proxmox.nodes.return_value.lxc.return_value = mock_machine

        user = _admin()
        node = _node()
        disk = _disk(node)
        sp = _service_plan(storage=disk, type='lxc')
        # Seed a live counter already carrying usage from the current period.
        svc = _service(user, node, sp,
                        bw_system_tick=100, bw_usage=5000, bw_stale=0, bw_banked=0,
                        bw_renewal_dtm=timezone.now() - timedelta(days=1))

        from ..tasks import meter_bandwidth

        # Renewal #1: counter is monotonic (no reboot). Baseline should follow
        # the live counter, not accumulate on top of it.
        mock_machine.status.current.get.return_value = {
            'uptime': 200, 'netin': 4000, 'netout': 2000,
        }
        meter_bandwidth()
        svc.refresh_from_db()
        self.assertEqual(svc.bw_stale, 5000)   # = prior bw_usage, not += it
        self.assertEqual(svc.bw_usage, 6000)
        self.assertEqual(svc.bw_banked, 0)

        # Force a second renewal (still no reboot).
        Service.objects.filter(pk=svc.pk).update(bw_renewal_dtm=timezone.now() - timedelta(days=1))
        mock_machine.status.current.get.return_value = {
            'uptime': 300, 'netin': 4500, 'netout': 2500,
        }
        meter_bandwidth()
        svc.refresh_from_db()
        self.assertEqual(svc.bw_stale, 6000)   # tracks the counter at renewal #2
        self.assertEqual(svc.bw_usage, 7000)
        self.assertEqual(svc.bw_banked, 0)
        # Unbanked usage this period stays sane (non-negative).
        self.assertGreaterEqual(svc.bw_usage - svc.bw_stale, 0)

        # Now the VM restarts (uptime drops below the last tick), no renewal.
        mock_machine.status.current.get.return_value = {
            'uptime': 10, 'netin': 30, 'netout': 20,
        }
        meter_bandwidth()
        svc.refresh_from_db()
        # banked = usage - stale = 7000 - 6000 = 1000 (real since-renewal usage),
        # never negative. The old accounting produced a negative bank here.
        self.assertEqual(svc.bw_banked, 1000)
        self.assertGreaterEqual(svc.bw_banked, 0)
        self.assertEqual(svc.bw_stale, 0)
        self.assertEqual(svc.bw_usage, 50)
        self.assertEqual(svc.bw_system_tick, 10)


# ===================================================================
# TestServiceViewSet
# ===================================================================

