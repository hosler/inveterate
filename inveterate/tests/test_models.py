from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

class TestModels(TestCase):

    def test_service_bw_defaults(self):
        user = _admin()
        node = _node()
        sp = _service_plan()
        svc = _service(user, node, sp)
        self.assertEqual(svc.bw_usage, 0)
        self.assertEqual(svc.bw_banked, 0)
        self.assertEqual(svc.bw_stale, 0)
        self.assertEqual(svc.bw_system_tick, 0)
        self.assertIsNone(svc.bw_renewal_dtm)

    def test_service_delete_cascades_to_service_plan(self):
        user = _admin()
        node = _node()
        sp = _service_plan()
        sp_id = sp.id
        svc = _service(user, node, sp)
        svc.delete()
        self.assertFalse(ServicePlan.objects.filter(pk=sp_id).exists())

    def test_service_plan_name(self):
        sp = _service_plan(name='Custom Plan')
        self.assertEqual(sp.name, 'Custom Plan')

    def test_nodedisk_unique_primary_constraint(self):
        node = _node()
        _disk(node, name='disk1', primary=True)
        with self.assertRaises(IntegrityError):
            _disk(node, name='disk2', primary=True)

    def test_nodedisk_multiple_non_primary(self):
        node = _node()
        _disk(node, name='disk1', primary=False)
        _disk(node, name='disk2', primary=False)
        self.assertEqual(NodeDisk.objects.filter(node=node, primary=False).count(), 2)

    def test_nodedisk_shared_default_false(self):
        node = _node()
        d = _disk(node)
        self.assertFalse(d.shared)


# ===================================================================
# TestServiceSerializer
# ===================================================================

