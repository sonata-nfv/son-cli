FROM ubuntu:14.04

RUN apt-get update \
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
    && echo 'Done'

COPY ansible /ansible
COPY ./dist/son-*-py3-*.whl /tmp/

RUN cd /ansible \
    # Start the basic Ansible setup
    && ansible-playbook install.yml \
    && echo 'Installing son-cli' \
    # Install the son-cli package from a local wheel
    && pip3 install /tmp/son-*-py3-*.whl \
    && echo 'Done'

# install son-monitor
RUN cd /son-cli/ansible \
    # Start the basic Ansible setup
    && ansible-playbook install_son-monitor.yml \
    && cd /son-cli \
    && python setup_son-monitor.py develop \
    && echo 'installed son-monitor'
