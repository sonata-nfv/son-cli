FROM python:3.5

MAINTAINER Ubiwhere

# install dependencies
RUN     apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 8EC0731023C1F15B \
        && echo "deb http://registry.sonata-nfv.eu:8080 ubuntu-trusty main" | tee -a /etc/apt/sources.list \
        && curl -sL https://deb.nodesource.com/setup_8.x | bin/bash - \
        && apt-get update \
        && apt-get install -y sonata-cli nodejs

# copy source
RUN     mkdir -p /usr/son-validate-gui/ && mkdir -p /root/projects
COPY    . /usr/son-validate-gui/


# build web gui
WORKDIR /usr/son-validate-gui
RUN     npm install request \
        && npm install \
        && npm install -g http-server \
        && npm run build:prod

EXPOSE 8080

WORKDIR /usr/son-validate-gui/dist

COPY  sample/entrypoint.sh /sbin/entrypoint.sh
RUN   chmod 755 /sbin/entrypoint.sh

ENTRYPOINT ["/sbin/entrypoint.sh"]
