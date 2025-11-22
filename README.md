<div id="top"></div>
<!--
*** Thanks for checking out the Best-README-Template. If you have a suggestion
*** that would make this better, please fork the repo and create a pull request
*** or simply open an issue with the tag "enhancement".
*** Don't forget to give the project a star!
*** Thanks again! Now go create something AMAZING! :D
-->



<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]



<!-- PROJECT LOGO -->
<div>

  <h3 align="center">Inveterate Proxmox API</h3>

  <p align="center">
    Hyper simplified Proxmox API wrapper made for VPS hosting solutions
    <br />
    <a href="https://github.com/hosler/inveterate"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/hosler/inveterate">View Demo</a>
    ·
    <a href="https://github.com/hosler/inveterate/issues">Report Bug</a>
    ·
    <a href="https://github.com/hosler/inveterate/issues">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

There are many options available for managing Proxmox nodes and clusters while running a business. Almost all of them 
are first and foremost billing systems that allow you to install Proxmox support via plugins and modules. This design 
decision makes it very hard to customize the look and feel of your site. I started this project 
with the goal of taking the opposite approach where an easy to use Proxmox integration API is exposed to any app.

Here's why:
* WHMCS and Blesta and their Proxmox plugins are crap
* You should be able to create beautiful vuejs, react, or react sites to support your business
* Billing systems shouldn't manage provisioning. Billing systems should manage billing. 


<p align="right">(<a href="#top">back to top</a>)</p>



### Built With

* [Django](https://www.djangoproject.com/)
* [Celery](https://docs.celeryproject.org/en/stable/)
* [Rest Framework](https://www.django-rest-framework.org/)
* [DJ-Stripe](https://dj-stripe.dev/)


<p align="right">(<a href="#top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

Besides a Proxmox node you will also need a machine to run the app (perhaps a VPS :)

### Prerequisites

* Python 3.8+
* PostgreSQL 13+
* Redis 6+
* Optional: Nginx or Apache for reverse proxy

```bash
sudo apt install postgresql postgresql-contrib redis-server nginx libpq-dev python3-pip python3-venv -y
```

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/hosler/inveterate.git
cd inveterate
```

2. **Create and activate virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
vim .env  # or use your preferred editor
```

Required environment variables:
```bash
# Django
DEBUG=on                          # Turn off in production
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=inveterate
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432

# Redis (for Celery)
REDIS_HOST=localhost

# Encryption (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
FERNET_KEY=your-fernet-key-here
```

5. **Setup database and create admin user**
```bash
python manage.py migrate
python manage.py createcachetable
python manage.py createsuperuser
```

6. **Run development server**
```bash
# Terminal 1: Django dev server
python manage.py runserver

# Terminal 2: Celery worker
celery -A config worker -l INFO

# Terminal 3: Celery beat (for scheduled tasks)
celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Production Deployment

Inveterate is designed to run via Supervisor and sit behind a reverse proxy.

### Production Setup

1. **Set production environment variables**
```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
export DEBUG=off
# Set all other required variables in .env or environment
```

2. **Create logs directory**
```bash
mkdir -p ~/inveterate/logs
```

3. **Collect static files**
```bash
python manage.py collectstatic --noinput
```

4. **Create Supervisor configuration**
```bash
vim supervisord.conf
```

Supervisor config file:
```ini
[supervisord]
logfile = ~/inveterate/logs/supervisord.log
childlogdir = ~/inveterate/logs
logfile_maxbytes = 50MB
pidfile = ~/inveterate/supervisord.pid
directory = ~/inveterate

[inet_http_server]
port = 127.0.0.1:9001

[supervisorctl]
serverurl = http://127.0.0.1:9001

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[program:celery_worker]
command = celery -A config worker -l INFO --concurrency=4
directory = %(here)s
user = %(ENV_USER)s
autostart = true
autorestart = true
startretries = 99999
startsecs = 10
stopsignal = TERM
stopwaitsecs = 7200
stdout_logfile = %(here)s/logs/celery_worker.log
stderr_logfile = %(here)s/logs/celery_worker_error.log

[program:celery_beat]
command = celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
directory = %(here)s
user = %(ENV_USER)s
autostart = true
autorestart = true
startretries = 99999
startsecs = 10
stopsignal = TERM
stopwaitsecs = 7200
stdout_logfile = %(here)s/logs/celery_beat.log
stderr_logfile = %(here)s/logs/celery_beat_error.log

[program:inveterate]
command = gunicorn -k gevent -b 127.0.0.1:8000 --worker-connections=1000 --timeout 60 --workers 4 config.wsgi:application
directory = %(here)s
user = %(ENV_USER)s
autostart = true
autorestart = true
stdout_logfile = %(here)s/logs/gunicorn.log
stderr_logfile = %(here)s/logs/gunicorn_error.log
```

5. **Start services**
```bash
supervisord -c supervisord.conf
supervisorctl -c supervisord.conf status
```

### Scheduled Tasks

Configure these periodic tasks in Django admin (django_celery_beat):

- `inveterate.tasks.meter_bandwidth` - Run every 5-15 minutes to track VM bandwidth
- `inveterate.tasks.calculate_inventory` - Run every hour to update available capacity
- `inveterate.tasks.cleanup_console_users` - Run daily to remove orphaned Proxmox console users

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- ROADMAP -->
## Roadmap

- [x] Stripe Support
- [x] Proxmox Clusters
- [X] Customer Life Cycles
- [ ] Plans and Templates
  - [X] KVM
  - [ ] LXC
- [X] Inventory Management
  - [X] Clusters
  - [X] Nodes
  - [X] IP Pools
- [ ] Health Monitoring
  - [X] VM Stats
  - [ ] Cluster Stats
- [X] VM Controls
  - [X] Start/Stop/Provision
  - [X] Console
- [ ] Domain Management
- [ ] NAT port forwarding
- [ ] Documetation

See the [open issues](https://github.com/hosler/inveterate/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- LICENSE -->
## License

Distributed under the LGPLv3 License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/hosler/inveterate.svg?style=for-the-badge
[contributors-url]: https://github.com/hosler/inveterate/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/hosler/inveterate.svg?style=for-the-badge
[forks-url]: https://github.com/hosler/inveterate/network/members
[stars-shield]: https://img.shields.io/github/stars/hosler/inveterate.svg?style=for-the-badge
[stars-url]: https://github.com/hosler/inveterate/stargazers
[issues-shield]: https://img.shields.io/github/issues/hosler/inveterate.svg?style=for-the-badge
[issues-url]: https://github.com/hosler/inveterate/issues
[license-shield]: https://img.shields.io/github/license/hosler/inveterate.svg?style=for-the-badge
[license-url]: https://github.com/hosler/inveterate/blob/master/LICENSE.txt