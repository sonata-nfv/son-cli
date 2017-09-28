[![Build Status](https://jenkins.sonata-nfv.eu/buildStatus/icon?job=son-cli)](https://jenkins.sonata-nfv.eu/job/son-cli/)


# son-cli
SONATA SDK command line interface tools

This set of command line tools are meant to aid the SONATA service developers on their tasks. The tools are briefly described as follows.
- `son-workspace` creates, configures and manages development workspaces and projects.
- `son-package` packages a project, containing services and functions, to be instantiated in the SONATA Service Platform. All project components are syntatically validated and external dependencies are retrieved to produce a complete service package.
- `son-validate` can be used to validate the syntax, integrity and topology of SONATA service packages, projects, services and functions. Son-validate can be used through the CLI or as a micro-service running inside a docker container.
- `son-access` enables authenticating users to the Service Platform and integrates features to push and pull resources from the Service Platform Catalogues. It is used to upload the service package to the SDK emulator or the Service Platform Gatekeeper, so the service can be deployed in the respective environment.
- `son-monitor` provides tools to easily monitor/generate metrics for debugging and analyzing service performance.
- `son-profile` supports network service developers to automatically profile their network services and network functions.

## Building
To build the son-cli tools it is recommended the use of a virtual environment to avoid polluting your system and to offer isolation from the installed libraries on the host.

Prerequisites:
- python 3 (3.4 used for most of the development)
- virtualenv
- docker (used by son-monitor)
- docker-compose (used by son-monitor)

### Creating a virtualenv:
1. Install virtualenvwrapper using your distribution repositories or the pip package.
https://virtualenvwrapper.readthedocs.org/en/latest/
1. Create a virtualenv for this project 
`mkvirtualenv -p /usr/bin/python34 sonata`

### Clone and build the project
activate the virtualenv for the project `workon sonata` then clone the project and bootstrap and run buildout. This will download all the dependencies and creante the development environment.
```sh
git clone git@github.com:sonata-nfv/son-cli.git 
cd son-cli
python bootstrap.py
bin/buildout
```

If you are using [pycharm](https://www.jetbrains.com/pycharm/), the IDE has support both for buildout and for virtualenvs,
please read their fine [documentation](https://www.jetbrains.com/help/pycharm/meet-pycharm.html) on the subject before proceeding.

### Generated binaries
The buildout generates the binaries for the tools `son-workspace`, `son-package`, `son-validate`, `son-validate-api`, `son-access`, `son-profile` and `son-monitor`. Information on how to use the tools is detailed in the wiki [documentation](https://github.com/sonata-nfv/son-cli/wiki). 

## Dependencies

The son-cli tools have the following dependencies:
* [pyaml](https://pypi.python.org/pypi/pyaml/) >= 15.8.2 (WTFPL)
* [jsonschema](https://pypi.python.org/pypi/jsonschema) >= 2.5.1 (MIT)
* [validators](https://pypi.python.org/pypi/validators) >= 0.10.3 (BSD)
* [requests](https://pypi.python.org/pypi/requests) >= 2.10 (Apache 2.0)
* [coloredlogs](https://pypi.python.org/pypi/coloredlogs) <= 5.1.1 (MIT)
* [paramiko](https://pypi.python.org/pypi/paramiko/1.16.0) >= 1.6 (LGPL)
* [docker-compose](https://docs.docker.com/compose/) >= 1.6.0 (Apache 2.0)
* [PyJWT](https://pypi.python.org/pypi/PyJWT/1.4.0) >= 1.4.0 (MIT)
* [Flask](http://flask.pocoo.org/) >= 0.11.1 (BSD)
* [Flask-Cors](https://pypi.python.org/pypi/Flask-Cors) (MIT)
* [flask_cache](https://pythonhosted.org/Flask-Cache/) (BSD)
* [numpy](https://pypi.python.org/pypi/numpy)  >= 1.11.3 (BSD)
* [scipy](https://pypi.python.org/pypi/scipy) >= 0.18.1 (BSD)
* [matplotlib](https://matplotlib.org/) >= 2.0.1 (PSF)
* [networkx](https://pypi.python.org/pypi/networkx/) <= 1.11 (BSD)
* [pycrypto](https://pypi.python.org/pypi/pycrypto) (Public Domain)
* [prometheus_client](https://pypi.python.org/pypi/prometheus_client) (Apache 2.0)
* [requests-toolbelt](https://pypi.python.org/pypi/requests-toolbelt) (Apache 2.0)
* [termcolor](https://pypi.python.org/pypi/termcolor) (MIT)
* [tabulate](https://pypi.python.org/pypi/tabulate) (MIT)
* [redis](https://pypi.python.org/pypi/redis) (MIT)
* [docker](https://pypi.python.org/pypi/docker/) (Apache 2.0)
* [watchdog](https://pypi.python.org/pypi/watchdog) (Apache 2.0)

All dependencies can be installed via a provided Ansible script:
```
sudo apt-get install ansible git aptitude
sudo vim /etc/ansible/hosts
Add: localhost ansible_connection=local

cd son-cli/ansible
sudo ansible-playbook install.yml
```

## Contributing

To contribute to son-cli the following sequence of steps should be followed:

1. Fork [this repository](http://github.com/sonata-nfv/son-cli);
2. Work on your proposed changes, preferably through submiting [issues](https://github.com/sonata-nfv/son-cli/issues);
3. Submit a Pull Request to the master branch;
4. Follow/answer related [issues](https://github.com/sonata-nfv/son-cli/issues) (see Feedback-Chanel, below).

## Installation

### Ubuntu Trusty (14.04) and Xenial (16.04)
To install the SONATA CLI toolset in Ubuntu follow these steps:

1. Add the new GPG key
	```sh
	sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 8EC0731023C1F15B
	```
    
2. Add a source entry for your Ubuntu OS.
    For now, supported distributions are supported:
    
- Ubuntu Trusty 14.04 (LTS)
    ```sh
    echo "deb http://repo.sonata-nfv.eu ubuntu-trusty main" | sudo tee -a /etc/apt/sources.list
    ```
    
- Ubuntu Xenial 16.04 (LTS)
    ```sh
    echo "deb http://repo.sonata-nfv.eu ubuntu-xenial main" | sudo tee -a /etc/apt/sources.list
    ```
    
3. Update and install
    ```sh
    sudo apt-get update
    sudo apt-get install sonata-cli
    ```
### CentOS 7
To install the SONATA CLI toolset in CentOS 7 follow these steps:
1. Install EPEL
    ```sh
    yum install epel-release
    ```
2. Create a repository entry file in `/etc/yum.repos.d/sonata.repo` with the following content:
    ```sh
    [sonata-repo]
    name=SONATA Repository
    baseurl=http://rpmrepo.sonata-nfv.eu/repo/
    enabled=1
    gpgcheck=0
    ```
    Note: currently the repository is not GPG signed (future work)
3. Install CLI
    ```sh
    yum install sonata-cli
    ```

### All dists (using setuptools)

The SONATA CLI toolset can also be installed via the Python setup script:
```
cd son-cli
python3 setup.py install
```

Test if its working by invoking:
```sh
$ son-workspace -h
$ son-package -h
$ son-publish -h
$ son-push -h
$ son-monitor -h
```

For usage and detailed description of each tool, please refer to the [wiki documentation](https://github.com/sonata-nfv/son-cli/wiki).

## License
The son-cli is published under Apache 2.0 license. Please see the LICENSE file for more details.

#### Lead Developers
The following lead developers are responsible for this repository and have admin rights. They can, for example, merge pull requests.

* Tiago Batista (https://github.com/tsbatista)
* Wouter Tavernier (https://github.com/wtaverni)
* Luís Conceição (https://github.com/lconceicao)

#### Feedback-Chanel
* You may use the mailing list [sonata-dev@lists.atosresearch.eu](mailto:sonata-dev@lists.atosresearch.eu)
* [GitHub issues](https://github.com/sonata-nfv/son-cli/issues)

