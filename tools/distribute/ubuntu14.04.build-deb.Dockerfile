FROM    ubuntu:14.04

RUN     apt-get update \
        ## install required packages
        && apt-get install -y python3-pip dpkg-dev fakeroot \
        && apt-get install -y python3-dev python3-pycparser \
        && apt-get install -y build-essential libssl-dev libffi-dev \
        ## install py2deb package converter
        && pip3 install py2deb \
        ## generate utf8 locale, otherwise py2deb will result in error!
        && locale-gen en_US.UTF-8 \
        && mkdir -p /son-cli/deb-packages

COPY    . /son-cli

WORKDIR /son-cli

## set locale env vars pointing to utf8
ENV     LANG en_US.UTF-8
ENV     LANGUAGE en_US:en
ENV     LC_ALL en_US.UTF-8
