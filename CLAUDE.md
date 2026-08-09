# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Inveterate is a standalone Django application (`django-inveterate`) for VPS hosting providers. It provides a REST API for managing Proxmox virtual machines and containers, handling provisioning, networking, and customer lifecycle management. It is designed to be installed as a reusable Django app in a host project.

## Architecture

### Core Components

**Django REST Framework API** (`inveterate/viewsets/`, `inveterate/urls.py`)
- RESTful API with ViewSets split into modules: `base.py`, `cluster.py`, `node.py`, `service.py`, `resource.py`, `dashboard.py`, `portforward.py`, `task.py`
- Uses Django REST Framework routers for URL routing
- Multi-serializer pattern via `MultiSerializerViewSetMixin`: admin users get full serializers, clients get limited ones (e.g., `ServiceSerializer` vs `ServiceSerializerClient`)
- Custom actions on viewsets (e.g., `start`, `stop`, `provision`, `console`, `ssh_keys`) exposed as API endpoints

**Async Task System** (`inveterate/tasks/`)
Tasks are split into modules under a package:
- `_common.py` — Shared logger, constants, SSH-based snippet helpers (`write_snippet`, `delete_snippet`)
- `control.py` — Power operations: start, stop, reboot, reset, shutdown
- `domain_verify.py` — `verify_domain_route` DNS TXT ownership verification
- `maintenance.py` — `calculate_inventory`, `cancel_service`, `cleanup_console_users`, `cleanup_orphaned_ips`, `update_service_ssh_keys`
- `monitoring.py` — `get_vm_status`, `meter_bandwidth`, `suspend_service`, `reinstate_service`
- `npm.py` — Nginx Proxy Manager integration: `sync_port_forward`, `sync_domain_route`, `delete_npm_stream`, `delete_npm_proxy_host`
- `provisioning.py` — `assign_ips`, `provision_service`, `_compose_cloud_init`, `_wait_for_task`, `_wait_for_unlock`
- `resize.py` — `resize_service` plan change executor (stop, apply CPU/RAM/disk, update snapshot, restart; disk shrink refused)
- `templates.py` — `import_kvm_template`, `sync_kvm_templates`, `sync_templates`
- `__init__.py` — Re-exports all public symbols for backward compatibility

All Celery tasks use `@shared_task(base=Singleton, lock_expiry=60 * 15)` via `celery-singleton`.

**Data Models** (`inveterate/models.py`)
- **Cluster**: Proxmox cluster with connection credentials (host, user, API token), bandwidth budget
- **Node**: Individual Proxmox node within a cluster, resource limits inherited from `PlanBase`
- **NodeDisk**: Storage volumes on nodes (`shared` flag for Ceph vs local, `primary` flag for inventory)
- **Service**: A provisioned VM/LXC with lifecycle status tracking and bandwidth metering
- **ServicePlan**: Snapshot of plan specs at provisioning time (M2M with `AppProfile` via `apps`)
- **Plan**: Template defining resource allocations for services
- **Template**: OS templates for KVM or LXC
- **AppProfile**: Cloud-init app profiles with `cloud_init` YAML, min resource requirements
- **IPPool**: IP address ranges (IPv4/IPv6, internal/external) associated with nodes
- **IP**: Individual IP addresses assigned to `ServiceNetwork` instances
- **ServiceNetwork**: Network interface for a service (has one IP, links to Service)
- **PortBlock**: Allocated port range on a `PortGateway` for a service's internal IP
- **PortForward**: Single forward rule within a port block
- **DomainRoute**: Domain-to-service mapping with NPM proxy host integration and `verification_status` (`pending`, `verified`, `failed`)
- **Inventory**: Calculated available capacity per plan on each node
- **DispatchedTask**: Celery task ID-to-owner mapping used to protect task-status lookups

**Console Proxy** (`inveterate/consumers.py`, `inveterate/views.py`)
- WebSocket consumer bridges browser ↔ Proxmox VNC WebSocket
- Console users: `inv-s{service_id}@pve` (per-service, auto-cleaned by maintenance task)
- Views proxy auth and termproxy requests to Proxmox

**NPM Integration** (`inveterate/npm.py`)
- Manages Nginx Proxy Manager streams (port forwards) and proxy hosts (domain routes)
- Async task-based sync for eventual consistency

**Domain Route Verification** (`inveterate/domain_verification.py`, `inveterate/tasks/domain_verify.py`)
- Uses an account-specific DNS TXT challenge at `_inveterate-verify.<domain>`
- Routes remain unsynced to NPM until `verification_status == "verified"`; a successful check enqueues `sync_domain_route`
- Owners can retry with `POST /api/v1/domainroutes/{id}/verify/`

**Task Concurrency and Ownership** (`inveterate/task_ownership.py`)
- `Service.operation_in_progress` serializes mutating provision, resize, power, and cancel operations
- Dispatch mutating service tasks through `ServiceViewSet._guarded_dispatch`: it atomically claims the flag, returns 409 if busy, releases it on dispatch failure, and records task ownership
- Every guarded task must clear `operation_in_progress` in `finally`
- `DispatchedTask` records the requesting owner immediately after `.delay()`; non-staff task-status requests require that ownership record

### Provisioning Flow

1. Service created via API with plan, template, owner, optional apps and SSH keys
2. `ServicePlan` created as snapshot of `Plan` specifications; apps linked via M2M
3. `assign_ips` task allocates IPs from pools, creates `PortBlock` on gateway
4. `provision_service` task creates VM/LXC on Proxmox:
   - **KVM**: Clones template (cross-node via shared storage intermediate + disk move), configures cloud-init with `ciuser` (email prefix), optional `cicustom` snippet for apps/SSH keys
   - **LXC**: Creates container directly from OS template
   - Configures networking with assigned IPs, sets up firewall IP filtering
5. Service status updated to `active` or `error`

### Cloud-Init Snippets

When app profiles or SSH keys are specified, a cloud-init snippet is composed and written to the Proxmox node via SSH (the Proxmox upload API does not support the `snippets` content type). The `cicustom user=...` VM config directive completely replaces the auto-generated user-data, so the snippet must include identity fields (`user`, `hostname`, `password`) that would otherwise be auto-generated.

## Project Structure

```
inveterate/                        # Repository root
├── manage.py                      # Django management script (standalone dev)
├── config/                        # Project configuration (standalone dev)
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   ├── production.py
│   │   └── test.py              # SQLite in-memory, eager Celery
│   ├── urls.py
│   ├── wsgi.py, asgi.py
│   └── celery.py
├── inveterate/                    # Reusable Django app
│   ├── models.py                  # Data models
│   ├── serializers.py             # DRF serializers
│   ├── tasks/                     # Celery tasks package
│   │   ├── __init__.py            # Re-exports all tasks
│   │   ├── _common.py             # Shared utilities (logger, SSH snippets)
│   │   ├── control.py             # Power operations
│   │   ├── domain_verify.py       # DNS TXT domain verification
│   │   ├── maintenance.py         # Inventory, cleanup, cancel, SSH key update
│   │   ├── monitoring.py          # Status, bandwidth, suspend/reinstate
│   │   ├── npm.py                 # NPM integration
│   │   ├── provisioning.py        # IP assignment, VM provisioning, cloud-init
│   │   ├── resize.py              # Plan resize executor
│   │   └── templates.py           # Template import/sync
│   ├── viewsets/                   # API viewsets (split into modules)
│   │   ├── base.py, cluster.py, node.py, service.py
│   │   ├── resource.py, dashboard.py, portforward.py, task.py
│   │   └── __init__.py
│   ├── consumers.py               # WebSocket consumer for console proxy
│   ├── views.py                   # Console auth/termproxy proxy views
│   ├── npm.py                     # NPM API client
│   ├── proxmox.py                 # Proxmox connection helper
│   ├── permissions.py             # DRF permission classes
│   ├── urls.py, urls_web.py       # URL routing
│   ├── routing.py                 # WebSocket routing
│   ├── admin.py                   # Django admin
│   ├── tests/                    # Test suite package (grouped by subject)
│   └── migrations/
├── tests/                         # Additional test files
├── requirements.txt
└── pyproject.toml
```

## Development Commands

### Running Tests
```bash
python manage.py test inveterate --settings=config.settings.test
python manage.py test inveterate.tests.test_provisioning.TestComposeCloudInit --settings=config.settings.test  # specific test class
```

The default `manage.py` settings use the development PostgreSQL database; use `config.settings.test` for the self-contained SQLite test suite.

When creating tests:
- Add test cases to the appropriate subject module in `inveterate/tests/`
- Mock `ProxmoxAPI` from `proxmoxer` for unit tests
- Mock `write_snippet`/`delete_snippet` for snippet tests
- Call tasks directly as plain functions (e.g. `cancel_service(svc.id)`) — never `task.apply()`, which runs the celery-singleton tracer and needs a live Redis

### Database Migrations
```bash
python manage.py makemigrations inveterate
python manage.py migrate
```

### Running (Standalone Development)
```bash
# Terminal 1: Django dev server
python manage.py runserver

# Terminal 2: Celery worker
celery -A config worker -l INFO

# Terminal 3: Celery beat scheduler
celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## Common Workflows

### Adding a New VM Action

1. Create task in appropriate `inveterate/tasks/*.py` module using `@shared_task(base=Singleton, lock_expiry=60 * 15)`
2. Add structured logging: `logger.info(f"Action description for service {service_id}")`
3. Use `get_vm(service_id)` helper from `tasks/control.py` to retrieve Proxmox machine object
4. Add error handling for `ConnectionError`, `ResourceException`, and general exceptions
5. Export the task in `tasks/__init__.py`
6. Add custom action to `ServiceViewSet` in `inveterate/viewsets/service.py` using `@action` decorator
7. Dispatch mutating service tasks with `_guarded_dispatch`; otherwise call `.delay()`, immediately `record_task_owner(task.id, request.user)`, and return the task ID

### Proxmox API Authentication

All Proxmox connections use API token authentication:
- Token name: `inveterate`
- Token value stored in `Cluster.key` field
- Connection: `ProxmoxAPI(host, user=user, token_name='inveterate', token_value=key, verify_ssl=False, port=8006)`
- Helper: `get_proxmox_connection(cluster, timeout=30)`

### Important Implementation Details

- **ciuser**: Must be `service.owner.email.split("@")[0]` — never `service.owner` (Django `__str__` is not a valid username)
- **Cross-node clones**: Require shared storage as intermediate; disks must be moved to target local storage via `move_disk` API (async, poll UPID)
- **cancel_service**: Uses `force=1` only for LXC, not KVM. Cleans up cloud-init snippets via SSH, collects NPM cleanup info before deleting ServiceNetwork records
- **Machine IDs**: Format `1{service.id:06}` (e.g., service 123 → machine_id 1000123)
- **IP allocation**: Uses `select_for_update(skip_locked=True)` to prevent race conditions
- **Bandwidth**: `Plan.bandwidth` in GB, `Service.bw_usage` in bytes
