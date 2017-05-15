#!/bin/bash
#
# This is the entry point for Jenkins.
# Script has do be called from "son-emu" root directory, like: sudo ./utils/ci/jenkins_entrypoint.sh
export DOCKER_HOST="unix:///var/run/docker.sock"

# don't rely on Debian/Ubuntu Docker engine
apt-get remove docker-engine
# make sure we start from scratch
pip uninstall docker-py
pip uninstall docker

set -e
set -x

# prepare
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -o Dpkg::Options::="--force-confold" --force-yes -y git ansible aptitude
echo "localhost ansible_connection=local" >> /etc/ansible/hosts

# install son-cli dependencies
echo "Installing son-cli dependencies"
ansible-playbook ansible/install.yml

# Installing setuptools (now in >v34.0.0 dependencies must be installed in advance)
pip3 install wincertstore==0.2 certifi==2016.9.26 six>=1.10.0 packaging>=16.8 appdirs>=1.4.0
pip3 install setuptools==34.0.2

echo "Installing son-cli"
# Bootstrapping the test environment
python3.4 bootstrap.py
# Generating the test environment
bin/buildout
python3 setup.py develop