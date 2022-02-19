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

This is an example of how to list things you need to use the software and how to install them.
* Postgresql 13
* Redis
* Django
* Optional: Nginx or Apache for reverse proxy

### Installation

TODO

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

TODO

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