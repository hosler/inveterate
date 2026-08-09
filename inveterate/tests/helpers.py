from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

import requests.exceptions
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone
from requests.exceptions import ConnectionError
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APIRequestFactory

from ..models import (
    AppProfile, Cluster, Node, NodeDisk, Plan, ServicePlan, Service,
    Template, IPPool, IP, ServiceNetwork, Inventory,
    PortGateway, PortBlock, PortForward, DomainRoute, DispatchedTask,
)
from ..task_ownership import record_task_owner, user_owns_task

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cluster(**kw):
    defaults = dict(name='test-cluster', host='10.0.0.1', user='root@pam', key='tok')
    defaults.update(kw)
    return Cluster.objects.create(**defaults)


def _node(cluster=None, **kw):
    if cluster is None:
        cluster = _cluster()
    defaults = dict(
        name='pve1', cluster=cluster,
        size=500, ram=65536, swap=65536, cores=32, bandwidth=10240,
    )
    defaults.update(kw)
    return Node.objects.create(**defaults)


def _disk(node, **kw):
    defaults = dict(name='local-lvm', size=500, primary=True, shared=False)
    defaults.update(kw)
    return NodeDisk.objects.create(node=node, **defaults)


def _plan(**kw):
    defaults = dict(
        name='VPS-1', size=10, ram=1024, swap=512, cores=2,
        bandwidth=1024, cpu_units=1024, cpu_limit=Decimal('1.00'),
        ipv4_ips=1, ipv6_ips=0, internal_ips=0,
    )
    defaults.update(kw)
    return Plan.objects.create(**defaults)


def _template(**kw):
    defaults = dict(name='debian-12', type='lxc', file='debian-12-standard_12.2-1_amd64.tar.zst')
    defaults.update(kw)
    return Template.objects.create(**defaults)


def _service(owner, node, service_plan, **kw):
    defaults = dict(hostname='test.example.com', status='active')
    defaults.update(kw)
    return Service.objects.create(owner=owner, node=node, service_plan=service_plan, **defaults)


def _service_plan(template=None, storage=None, **kw):
    defaults = dict(
        name='VPS-1', type='lxc', size=10, ram=1024, swap=512, cores=2,
        bandwidth=1024, cpu_units=1024, cpu_limit=Decimal('1.00'),
        ipv4_ips=1, ipv6_ips=0, internal_ips=0,
    )
    defaults.update(kw)
    return ServicePlan.objects.create(template=template, storage=storage, **defaults)


def _ip_pool(node, **kw):
    defaults = dict(
        name='public-v4', type='ipv4', network='10.0.0.0', mask=24,
        gateway='10.0.0.1', dns='8.8.8.8', internal=False,
    )
    defaults.update(kw)
    pool = IPPool.objects.create(**defaults)
    pool.nodes.add(node)
    return pool


def _admin():
    return User.objects.create_superuser('admin', 'admin@test.com', 'pass')


def _user():
    return User.objects.create_user('user1', 'user1@test.com', 'pass')


# ===================================================================
# TestModels
# ===================================================================
def _app_profile(name='Docker', cloud_init='packages:\n  - curl\nruncmd:\n  - echo hello'):
    return AppProfile.objects.create(name=name, cloud_init=cloud_init)

def _port_gateway(pools=None, **kw):
    defaults = dict(
        name='gw1', host='http://gateway:81',
        admin_email='admin@example.com', admin_password='secret',
        port_range_start=10000, port_range_end=10999, block_size=100,
    )
    defaults.update(kw)
    gw = PortGateway.objects.create(**defaults)
    if pools:
        gw.pools.set(pools)
    return gw


def _internal_pool(node, **kw):
    defaults = dict(
        name='internal', type='ipv4', network='192.168.0.0', mask=24,
        gateway='192.168.0.1', dns='8.8.8.8', internal=True,
    )
    defaults.update(kw)
    pool = IPPool.objects.create(**defaults)
    pool.nodes.add(node)
    return pool


# ===================================================================
# TestPortBlockAllocation
# ===================================================================
def _txt_answer(value):
    """Build a fake dnspython TXT rdata whose `.strings` decodes to `value`."""
    ans = MagicMock()
    ans.strings = [value.encode()]
    return ans


