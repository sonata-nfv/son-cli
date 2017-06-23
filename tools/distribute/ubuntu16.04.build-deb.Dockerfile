FROM    ubuntu:16.04

        ## install son-cli package dependencies
        ## (system-wide for avoiding problems with py2deb)
RUN     apt-get update \
        && apt-get install -y software-properties-common apt-transport-https \
        ca-certificates wget libffi-dev libssl-dev tcpdump gfortran \
        libopenblas-dev liblapack-dev python3-dev libyaml-dev curl \
        python3.pip python3-pycparser python3-matplotlib python3-numpy \
        python3-scipy libpng-dev libfreetype6-dev gfortran libatlas-base-dev

        ## install dependencies for py2deb build
RUN     apt-get update \
        && apt-get install -y pkg-config locales dpkg-dev fakeroot

        ## install py2deb package converter
RUN     pip3 install py2deb \
        # generate utf8 locale, otherwise py2deb will result in error!
        && locale-gen en_US.UTF-8 \
        && mkdir -p /son-cli/deb-packages

COPY    . /son-cli
COPY    tools/distribute/entrypoint.sh /sbin/entrypoint.sh
RUN     chmod 755 /sbin/entrypoint.sh

WORKDIR /son-cli

        ## set locale env vars pointing to utf8
ENV     LANG en_US.UTF-8
ENV     LANGUAGE en_US:en
ENV     LC_ALL en_US.UTF-8

ENTRYPOINT ["/sbin/entrypoint.sh"]
