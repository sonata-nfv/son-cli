[![Build Status](https://jenkins.sonata-nfv.eu/buildStatus/icon?job=son-cli)](https://jenkins.sonata-nfv.eu/job/son-cli/)

Maintainers: [tsbatista](https://github.com/tsbatista) and [wtaverni](https://github.com/wtaverni)

# son-cli
SONATA SDK command line interface tools

This set of command line tools are meant to aid the SONATA service developers on their tasks

## How to install son-cli tools

To install son-cli in a debian-based system run the following:

    $ curl -sSL http://registry.sonata-nfv.eu:8080/go | sudo sh
    $ apt-get install sonata-cli

or if you don't want to pipe `curl` just do it manually:

    $ apt-key adv --keyserver keyserver.ubuntu.com --recv-keys D0DF34A30A4FE3F8
    $ echo "deb http://registry.sonata-nfv.eu:8080 unstable main" >> /etc/apt/sources.list
    $ apt-get update
    $ apt-get install sonata-cli

## How to develop for this project

Prerequisites:
- python 3 (3.4 used for most of the development)
- virtualenv is recommended to avoid polluting your system instalation

### Creating a virtualenv:
1. Install virtualenvwrapper using your distribution repositories or the pip package.
https://virtualenvwrapper.readthedocs.org/en/latest/
1. Create a virtualenv for this project 
`mkvirtualenv -p /usr/bin/python34 sonata`

### working on the project

activate the virtualenv for the project `workon sonata` then clone the project and bootstrap and run buildout. This will download all the dependencies and creante the development environment.
```sh
git clone git@github.com:sonata-nfv/son-cli.git 
cd son-cli
python bootstrap.py
bin/buildout
```

TODO: figure out how to install this system wide (or virtualenv wide) 
but that is low on the priority list

If you are using pycharm, the IDE has support both for buildout and for virtualenvs,
please read their fine documentation on the subject before proceeding


### Generated binaries

The buildout generates the binaries for the tools son-workspace and son-package. Information on how to use the tools is provided in the README file at src/son/workspace and src/son/package, respectively.

