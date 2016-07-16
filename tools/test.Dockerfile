FROM ubuntu:14.04

RUN apt-get clean \
    && apt-get update \
    # Install common packages
    && apt-get install -y software-properties-common apt-transport-https ca-certificates wget \
    # Install Ansible and Git
    && apt-add-repository ppa:ansible/ansible \
    && apt-get update \
    && apt-get install -y ansible git \
    # Add the localhost to the Ansible's hosts
    && echo 'localhost ansible_connection=local' >> /etc/ansible/hosts \
    # Pre-install python 3.4 and pip3 to speed-up the next steps
    && apt-get install -y python3.4 python3.pip \
    && apt-get clean \
    && echo 'Done'

WORKDIR /son-cli

COPY . /son-cli

RUN cd /son-cli/ansible \
    # Start the basic Ansible setup
    && ansible-playbook install.yml \
    && cd /son-cli \
    # Removing bin to avoid badly generated binaries
    && rm -rf bin \
    # Bootstrapping the test environment
    && python3.4 bootstrap.py \
    # Generating the test environment
    && bin/buildout \
    && echo 'Done'
