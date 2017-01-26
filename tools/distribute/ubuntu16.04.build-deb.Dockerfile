FROM    ubuntu:16.04

RUN     apt-get update \
        ## install required packages
        && apt-get install -y python3-pip dpkg-dev fakeroot \
        && apt-get install -y python3-dev python3-pycparser \
        && apt-get install -y build-essential libssl-dev libffi-dev \
        ## install py2deb package converter
        && pip3 install --upgrade pip \
        # Installing setuptools (now in >v34.0.0 dependencies must be installed in advance)
        && pip3 install wincertstore==0.2 certifi==2016.9.26 six>=1.10.0 packaging>=16.8 appdirs>=1.4.0 \
        && pip3 install setuptools==34.0.2 \
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
