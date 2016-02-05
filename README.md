# son-cli
SONATA SDK command line interface tools

This set of command line tools are meant to aid the SONATA service developers on their tasks

## How to develp for this project

Prerequisites:
- python 3 (3.4 used for most of the development)
- virtualenv is recommended to avoid polluting your system instalation

### Creating a virtualenv:
1. Install virtualenvwrapper using your distribution repositories or the pip package.
https://virtualenvwrapper.readthedocs.org/en/latest/
1. Create a virtualenv for this project 
`virtualenv -p /usr/bin/python34 sonata`

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


