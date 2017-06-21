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
    && apt-get install -y build-essential libssl-dev libffi-dev python-dev redis-server \
    && apt-get clean \
    && echo 'Done'

# Pre-install this to speed-up the next steps
RUN apt-get remove -y python3-setuptools \
    && wget https://bootstrap.pypa.io/get-pip.py \
    && python3 get-pip.py \
    && pip3 install -U pip \
    # Installing setuptools (now in >v34.0.0 dependencies must be installed in advance)
    && pip3 install wincertstore==0.2 certifi==2016.9.26 six>=1.10.0 packaging>=16.8 appdirs>=1.4.0 \
    && pip3 install setuptools==34.0.2

RUN pip3 install numpy scipy matplotlib

COPY ansible /ansible
COPY ./dist/sonata_cli-*-py3-*.whl /tmp/

RUN cd /ansible \
    # Start the basic Ansible setup
    && ansible-playbook install.yml \
    && echo 'Installing son-cli' \
    # Install the son-cli package from a local wheel
    && pip3 install /tmp/sonata_cli-*-py3-*.whl \
    && echo 'Done, installed son-cli'

# Flag to know if we are running in a docker container or not
ENV SON_CLI_IN_DOCKER 1

# Run validator service
CMD ["son-validate-api"]
