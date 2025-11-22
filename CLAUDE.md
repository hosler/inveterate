# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Inveterate is a standalone Django application for VPS hosting providers. It provides a REST API for managing Proxmox virtual machines and containers, handling provisioning, billing integration, and customer lifecycle management.

## Architecture

### Core Components

**Django REST Framework API** (`inveterate/viewsets.py`, `inveterate/urls.py`)
- RESTful API with ViewSets for managing clusters, nodes, services (VMs/LXCs), IP pools, templates, and plans
- Uses Django REST Framework routers for URL routing
- Multi-serializer pattern: different serializers for admin vs client views (e.g., `ServiceSerializer` vs `ServiceSerializerClient`)
- Custom actions on viewsets (e.g., `start`, `stop`, `provision`, `console`) exposed as API endpoints

**Async Task System** (`inveterate/tasks.py`)
- Celery with `celery-singleton` for preventing duplicate task execution
- Background tasks handle VM provisioning, power operations, bandwidth metering, inventory calculation, and IP assignment
- Tasks use `ProxmoxAPI` from `proxmoxer` library to interact with Proxmox nodes
- All Celery tasks use `@shared_task(base=Singleton, lock_expiry=60 * 15)` decorator

**Data Models** (`inveterate/models.py`)
- **Cluster**: Proxmox cluster with connection credentials (host, user, API token)
- **Node**: Individual Proxmox node within a cluster, inherits resource limits from `PlanBase`
- **NodeDisk**: Storage volumes available on nodes
- **Service**: A provisioned VM/LXC with lifecycle status tracking (`pending`, `active`, `destroyed`, `suspended`, `error`, `past_due`)
- **ServicePlan**: Snapshot of plan specifications at time of provisioning (RAM, CPU, disk, bandwidth, IPs)
- **Plan**: Template defining resource allocations for services
- **Template**: OS templates for KVM or LXC
- **IPPool**: IP address ranges (IPv4/IPv6, internal/external) associated with nodes
- **IP**: Individual IP addresses assigned to ServiceNetwork instances
- **ServiceNetwork**: Network interface for a service (has one IP, links to Service)
- **Inventory**: Calculated available capacity per plan on each node

**Provisioning Flow**
1. Service created via API with plan, template, owner
2. `ServicePlan` created as snapshot of `Plan` specifications
3. `assign_ips` task allocates IPs from pools based on node and plan requirements
4. `provision_service` task creates VM/LXC on Proxmox using `proxmoxer`:
   - For KVM: clones template, configures resources, sets cloud-init params
   - For LXC: creates container with specified template and resources
   - Configures networking with assigned IPs
   - Sets up firewall with IP filtering
5. Service status updated to `active` or `error`

**Blesta Integration** (`inveterate/blesta/`)
- Optional billing system integration via REST API client (`blesta/api.py`)
- Handles user creation, package management, service lifecycle, invoicing
- Not required for core Proxmox functionality

### Key Patterns

**Permission System**
- `IsAdminUser` for infrastructure management endpoints
- `IsAuthenticated` for service management (users can only see their own services)
- `ReadOnly`/`ReadOnlyAnonymous` for public plan/inventory browsing

**Service Lifecycle**
- Services track both Django state (Service.status) and Proxmox state (queried via API)
- State transitions managed through Celery tasks to prevent blocking API requests
- `machine_id` format: `1{service.id:06}` (e.g., service ID 123 becomes VM ID 1000123)

**Resource Management**
- `calculate_inventory` task computes available slots for each plan on each node
- Compares node capacity vs. sum of provisioned services
- Inventory prevents overprovisioning by tracking lowest resource bottleneck

## Project Structure

```
inveterate/                        # Project root
├── manage.py                      # Django management script
├── config/                        # Project configuration
│   ├── settings/
│   │   ├── base.py               # Base settings
│   │   ├── dev.py                # Development settings
│   │   └── production.py         # Production settings
│   ├── urls.py                   # Root URL configuration
│   ├── wsgi.py                   # WSGI entry point
│   ├── asgi.py                   # ASGI entry point
│   └── celery.py                 # Celery configuration
├── inveterate/                   # Main Django app
│   ├── models.py                 # Data models
│   ├── serializers.py            # DRF serializers
│   ├── tasks.py                  # Celery tasks
│   ├── viewsets/                 # API viewsets (split into modules)
│   │   ├── base.py
│   │   ├── cluster.py
│   │   ├── node.py
│   │   ├── service.py
│   │   ├── resource.py
│   │   └── dashboard.py
│   ├── urls.py                   # App URL routing
│   ├── admin.py                  # Django admin
│   └── migrations/               # Database migrations
├── requirements.txt              # Python dependencies
├── .env.example                  # Example environment config
└── README.md                     # Project documentation
```

## Development Commands

### Initial Setup

**Create database and run migrations:**
```bash
python manage.py migrate
python manage.py createcachetable
python manage.py createsuperuser
```

**Generate encryption key for FERNET_KEY:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Running the Application

**Development (3 terminals required):**
```bash
# Terminal 1: Django dev server
python manage.py runserver

# Terminal 2: Celery worker
celery -A config worker -l INFO

# Terminal 3: Celery beat scheduler
celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

**Production deployment:**
- Gunicorn: `gunicorn -k gevent -b 127.0.0.1:8000 --worker-connections=1000 --timeout 60 --workers 4 config.wsgi:application`
- Celery worker: `celery -A config worker -l INFO --concurrency=4`
- Celery beat: `celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler`
- Use Supervisor for process management (see README.md for complete config)

### Testing

**Run tests:**
```bash
python manage.py test inveterate
```

When creating tests:
- Add test cases to `inveterate/tests.py`
- Mock `ProxmoxAPI` from `proxmoxer` for unit tests
- Use `task.apply()` for synchronous Celery task execution in tests

### Database Migrations

**Create new migration after model changes:**
```bash
python manage.py makemigrations inveterate
```

**Apply migrations:**
```bash
python manage.py migrate
```

## Common Workflows

### Adding a New VM Action

1. Create task in `inveterate/tasks.py` using `@shared_task(base=Singleton)`
2. Add structured logging: `logger.info(f"Action description for service {service_id}")`
3. Use `get_vm(service_id)` helper to retrieve Proxmox machine object
4. Add error handling for ConnectionError, ResourceException, and general exceptions
5. Add custom action to `ServiceViewSet` in `inveterate/viewsets/service.py` using `@action` decorator
6. Call task asynchronously with `.delay()`, return task ID

### Adding a New Resource Model

1. Define model in `inveterate/models.py`, consider inheritance from `PlanBase` for resources
2. Create serializer in `inveterate/serializers.py`
3. Create viewset in appropriate `inveterate/viewsets/*.py` file (usually extends `DynamicPageModelViewSet`)
4. Export viewset in `inveterate/viewsets/__init__.py`
5. Register viewset in `inveterate/urls.py` router
6. Create and run migrations: `python manage.py makemigrations inveterate`
7. Apply migrations: `python manage.py migrate`

### Proxmox API Authentication

All Proxmox connections use API token authentication:
- Token name: `inveterate`
- Token value stored in `Cluster.key` field
- Connection format: `ProxmoxAPI(host, user=user, token_name='inveterate', token_value=key, verify_ssl=False, port=8006)`

## Environment Configuration

**Project uses settings in `config/settings/`:**
- `base.py` - Shared settings
- `dev.py` - Development (default)
- `production.py` - Production (set `DJANGO_SETTINGS_MODULE=config.settings.production`)

**Required environment variables** (see `.env.example`):
- `SECRET_KEY`: Django secret key (generate new for production)
- `FERNET_KEY`: Encryption key for Cluster.key field (use `Fernet.generate_key()`)
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`: PostgreSQL connection
- `REDIS_HOST` or `REDIS_URL`: Redis for Celery broker
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts in production
- Optional: `STRIPE_LIVE_SECRET_KEY`, `STRIPE_TEST_SECRET_KEY` for Stripe integration

**Settings organization:**
- Development: Loads from `config.settings.dev` (default in manage.py)
- Production: Set `DJANGO_SETTINGS_MODULE=config.settings.production`
- Both inherit from `config.settings.base`

## Important Notes

### Security
- **Encrypted credentials**: `Cluster.key` field uses `EncryptedCharField` to encrypt Proxmox API tokens at rest
- **Fernet encryption**: Requires `FERNET_KEY` environment variable (generate with `Fernet.generate_key()`)
- **Console user cleanup**: Temporary Proxmox users (`inveterate{owner_id}@pve`) should be periodically cleaned up using the `cleanup_console_users` task

### Data Integrity
- Service deletion cascades to `ServicePlan` and `ServiceBandwidth` (see `Service.delete()` override in models.py:179)
- IP addresses are assigned atomically using `select_for_update(skip_locked=True)` to prevent race conditions (tasks.py:74)
- VMs are organized in Proxmox pool named `inveterate` for easy identification

### Performance
- Bandwidth metering uses `select_related()` and `bulk_update()` for efficiency (tasks.py:443)
- All Celery tasks use singleton pattern to prevent duplicate execution
- Inventory calculation triggers after each provisioning operation

### Implementation Details
- Console access creates temporary Proxmox users with format `inveterate{owner_id}@pve` (viewsets/service.py:906)
- LXC and KVM (QEMU) have different provisioning paths in `provision_service` task (tasks.py:135-201)
- Storage must be assigned to `ServicePlan.storage` before provisioning (defaults to primary NodeDisk)
- Machine IDs use format `1{service.id:06}` (e.g., service 123 → machine_id 1000123)
