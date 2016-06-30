#!/bin/bash

# this script is to be run at root of "son-cli" dir

set -xe

# install py2deb tool
sudo apt-get update
sudo apt-get install -y python3-pip dpkg-dev fakeroot
pip3 install py2deb


# package project and dependencies into debs
mkdir -p debs
py2deb -r debs --no-name-prefix=sonata-cli .

export DOCKER_HOST="tcp://registry.sonata-nfv.eu:2375"

docker run debifymod -d -e URI=http://registry.sonata-nfv.eu:8080 \
 -e KEYSERVER=keyserver.ubuntu.com -e APTLY_ARCHITECTURES="i386,amd64" \
 --entrypoint=/bin/bash -p 8080:8080 debifymod

docker restart debifymod

docker cp debs debifymod:/

docker exec debifymod debify.sh
sleep 5
docker exec debifymod aptly serve

export DOCKER_HOST="unix:///var/run/docker.sock"
