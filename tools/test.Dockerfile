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
    && apt-get install -y python3.4 python3.pip python3-pycparser\
    && apt-get install -y build-essential libssl-dev libffi-dev python-dev \
    && apt-get clean \
    && echo 'Done'

RUN apt-get remove -y python3-setuptools \
    && wget https://bootstrap.pypa.io/get-pip.py \
    && python3 get-pip.py \
    && pip3 install -U pip pytest \
    # Installing setuptools (now in >v34.0.0 dependencies must be installed in advance)
    && pip3 install wincertstore==0.2 certifi==2016.9.26 six>=1.10.0 packaging>=16.8 appdirs>=1.4.0 \
    && pip3 install setuptools==34.0.2

RUN pip3 install numpy scipy matplotlib

WORKDIR /son-cli
ENV PYTHONIOENCODING "UTF-8"
ENV LC_ALL C
ENV VAPI_CACHE_TYPE "simple"

COPY . /son-cli

RUN cd /son-cli/ansible \
    # Start the basic Ansible setup
    && ansible-playbook install.yml

RUN cd /son-cli \
    # Removing bin to avoid badly generated binaries
    && rm -rf bin

# Bootstrapping the test environment
RUN  python3.4 bootstrap.py \
    # Generating the test environment
    && bin/buildout \
    && echo 'Done'
