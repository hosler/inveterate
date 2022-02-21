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

Besides a proxmox node you will also need a machine to run the app (perhaps a vps :)

### Prerequisites

* Postgresql 13
* Redis
* Optional: Nginx or Apache for reverse proxy
```
$ sudo apt install postgresql postgresql-contrib redis-server nginx libpq-dev -y
```
### Installation

Basic installation with Ubuntu Focal Server
1. Set up your environment using conda, virtualenv, or whatever.
In this example i'll use Ubuntu's packaged python and pip. Ubuntu Focal 
users will need to run the following:
```
$ sudo update-alternatives --install /usr/bin/python python /usr/bin/python3 1
update-alternatives: using /usr/bin/python3 to provide /usr/bin/python (python) in auto mode
```
2. Install pip:
```
$ sudo apt install python3-pip -y
```
3. Clone and install requirements
```
$ git clone https://github.com/hosler/inveterate.git
$ cd inveterate
$ pip install --user -r requirements.txt
```
4. Populate the env file
```
$ vim .env
```
At a minimum you will need database and redis info:
```
DEBUG=on # Turn off in production
REDIS_HOST=localhost
DB_HOST=localhost #leave blank to use socket
DB_USER=<username>
DB_PASSWORD=<paassword>
DB=<username>
SECRET_KEY=randomstring
```
5. Setup tables and admin user
```
$ python manage.py makemigrations
$ python manage.py migrate
$ python manage.py createcachetable
$ python manage.py createsuperuser
```

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

Inveterate was designed to run via supervisord and sit behind a reverse proxy.
Let's go ahead and set that up.
```angular2html
$ cd ~/inveterate
$ mkdir logs
$ vim supervisord.conf
```
Here is a basic supervisor config file
```angular2html
[supervisord]
logfile = ~/inveterate/supervisord.log
childlogdir = ~/inveterate/logs
logfile_maxbytes = 50MB
pidfile = ~/inveterate/supervisord.pid
directory=~/inveterate


[inet_http_server]
port=127.0.0.1:9001

[supervisorctl]
serverurl=http://127.0.0.1:9001

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[program:celery_worker]
numprocs=1
process_name=%(program_name)s-%(process_num)s
command=celery -A app worker -l INFO --concurrency=4 -Q celery
autostart=true
autorestart=true
startretries=99999
startsecs=10
stopsignal=TERM
stopwaitsecs=7200
killasgroup=false
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0


[program:celery_beat]
numprocs=1
process_name=%(program_name)s-%(process_num)s
command=celery -A app beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
autostart=true
autorestart=true
startretries=99999
startsecs=10
stopsignal=TERM
stopwaitsecs=7200
killasgroup=false
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0

[program:inveterate]
command=gunicorn -k gevent -b 127.0.0.1:8000 --worker-connections=1000 --timeout 60 --workers 4 app.wsgi
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
```

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