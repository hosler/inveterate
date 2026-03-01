# Inveterate

A Django application for VPS hosting providers, providing a REST API for managing Proxmox virtual machines and containers.

## Features

- **VM/LXC Provisioning** — Automated provisioning with cloud-init, cross-node cloning, and resource management
- **App Profiles** — Pre-configured cloud-init templates (e.g., Docker, Nginx) selectable at provisioning time
- **Networking** — IP pool management, NAT port forwarding via Nginx Proxy Manager, domain routing with SSL
- **Console Access** — Browser-based terminal via WebSocket proxy to Proxmox VNC
- **Inventory Management** — Automatic capacity calculation per plan/node (CPU, RAM, disk, IPs, bandwidth)
- **Bandwidth Metering** — Per-service usage tracking with monthly renewal and overage suspension
- **SSH Key Management** — Deploy and update SSH keys on running KVM services via cloud-init
- **Multi-Cluster Support** — Manage multiple Proxmox clusters from a single installation

## Built With

- [Django](https://www.djangoproject.com/) + [Django REST Framework](https://www.django-rest-framework.org/)
- [Celery](https://docs.celeryproject.org/) with [celery-singleton](https://github.com/steinitzu/celery-singleton)
- [proxmoxer](https://github.com/proxmoxer/proxmoxer) for Proxmox VE API interaction
- PostgreSQL + Redis

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 14+
- Redis 6+

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/hosler/inveterate.git
cd inveterate
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**
```bash
cp .env.example .env
```

Required environment variables:
```bash
SECRET_KEY=your-secret-key-here
DB_NAME=inveterate
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
REDIS_HOST=localhost
```

4. **Setup database**
```bash
python manage.py migrate
python manage.py createcachetable
python manage.py createsuperuser
```

5. **Run development server**
```bash
# Terminal 1: Django dev server
python manage.py runserver

# Terminal 2: Celery worker
celery -A config worker -l INFO

# Terminal 3: Celery beat (for scheduled tasks)
celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### As a Reusable Django App

Inveterate is designed to be installed as an editable dependency in a host Django project:

```bash
pip install -e /path/to/inveterate
```

Add to `INSTALLED_APPS` and include the URL configuration:
```python
# settings.py
INSTALLED_APPS = [
    ...
    'inveterate',
]

# urls.py
urlpatterns = [
    path('api/v1/', include('inveterate.urls')),
]
```

## API Endpoints

### Public (anonymous access)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/plans/` | GET | List available plans |
| `/templates/` | GET | List OS templates |
| `/apps/` | GET | List app profiles |
| `/inventory/` | GET | Available capacity per plan/node |

### Customer (authenticated)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/services/` | GET/POST | List or create services |
| `/services/{id}/` | GET | Service detail |
| `/services/{id}/start/` | POST | Start VM |
| `/services/{id}/shutdown/` | POST | Graceful shutdown |
| `/services/{id}/stop/` | POST | Force stop |
| `/services/{id}/reboot/` | POST | Reboot |
| `/services/{id}/cancel/` | POST | Destroy service |
| `/services/{id}/status/` | POST | Live VM status |
| `/services/{id}/ips/` | GET | List assigned IPs |
| `/services/{id}/console/` | GET | Console credentials |
| `/services/{id}/ssh_keys/` | POST | Update SSH keys |
| `/portblocks/` | GET | Port blocks for a service |
| `/portforwards/` | GET/POST/DELETE | CRUD port forward rules |
| `/domainroutes/` | GET/POST/DELETE | CRUD domain routes |
| `/tasks/{task_id}/` | GET | Poll async task status |

### Admin
Full CRUD on all resources: clusters, nodes, node disks, IP pools, IPs, services, plans, templates, app profiles.

## Scheduled Tasks

Configure these periodic tasks via `django-celery-beat`:

| Task | Interval | Description |
|------|----------|-------------|
| `inveterate.tasks.meter_bandwidth` | 5-15 min | Track VM bandwidth usage |
| `inveterate.tasks.calculate_inventory` | 1 hour | Update available capacity |
| `inveterate.tasks.cleanup_console_users` | Daily | Remove orphaned Proxmox console users |
| `inveterate.tasks.cleanup_orphaned_ips` | Daily | Release IPs from destroyed services |

## Production Deployment

Use Gunicorn + Supervisor behind a reverse proxy:

```bash
gunicorn -k gevent -b 127.0.0.1:8000 --worker-connections=1000 --timeout 60 --workers 4 config.wsgi:application
celery -A config worker -l INFO --concurrency=4
celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

See the included `supervisord.conf` example or use systemd units.

## Testing

```bash
python manage.py test inveterate
```

## License

Distributed under the LGPLv3 License. See `LICENSE.txt` for more information.
