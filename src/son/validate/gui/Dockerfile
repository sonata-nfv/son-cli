FROM ubuntu:xenial

MAINTAINER Ubiwhere

# install dependencies
RUN	apt-get update && apt-get -y install curl
RUN     apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 8EC0731023C1F15B \
        && echo "deb http://repo.sonata-nfv.eu ubuntu-xenial main" | tee -a /etc/apt/sources.list \
        && curl -sL https://deb.nodesource.com/setup_8.x | bin/bash - \
        && apt-get update \
        && apt-get install -y sonata-cli nodejs

# copy source
RUN     mkdir -p /usr/son-validate-gui/
COPY    . /usr/son-validate-gui/

# build web gui
WORKDIR /usr/son-validate-gui
RUN	apt-get install make
RUN     npm install request \
	&& npm install \
        && npm install -g http-server \
        && npm run build:prod

EXPOSE 8080

WORKDIR /usr/son-validate-gui/dist

COPY entrypoint.sh /sbin/entrypoint.sh
RUN   chmod 755 /sbin/entrypoint.sh

ENTRYPOINT ["/sbin/entrypoint.sh"]

