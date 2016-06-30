#!/bin/bash

# this script is to be run at root of "son-cli" dir

set -xe

echo ""
echo "==== Build packages and instantiate debian repository ===="
echo ""

# install py2deb tool
echo "-> Preparing environment"
sudo apt-get update
sudo apt-get install -y python3-pip dpkg-dev fakeroot

# Create a dedicated python environment to avoid conflicts between pip packages
sudo pip install virtualenv
rm -rf son-cli-dist/*
virtualenv son-cli-dist
. son-cli-dist/bin/activate

pip3 install py2deb


# package project and dependencies into debs
echo "-> Creating deb packages"
mkdir -p debs
py2deb -r debs --no-name-prefix=sonata-cli .

# deactivate python env -> no longer required
deactivate

echo "-> Running repository container"
# point to remote docker daemon
export DOCKER_HOST="tcp://registry.sonata-nfv.eu:2375"

# check if container is running and stop/remove it
CONTAINER="debifymod"
RUNNING=$(docker inspect --format="{{ .State.Running }}" $CONTAINER 2> /dev/null)

if [ $? -eq 1 ]; then
  echo "'$CONTAINER' does not exist."

elif [ "$RUNNING" == "false" ]; then
  echo "'$CONTAINER' is not running. Just remove it."
  docker rm "$CONTAINER"

else
  echo "$CONTAINER is running. Stop and remove it."
  docker stop "$CONTAINER"
  docker rm "$CONTAINER"
fi


# run server repository container 
docker run --name=debifymod -di -e URI=http://registry.sonata-nfv.eu:8080 \
 -e KEYSERVER=keyserver.ubuntu.com -e APTLY_ARCHITECTURES="i386,amd64" \
 --entrypoint=/bin/bash -p 8080:8080 debifymod

# copy newly generated deb packages to it and create repository
docker cp debs debifymod:/
docker exec -d debifymod sh /debify.sh
sleep 5
docker exec -d debifymod ln -s /repo /root/.aptly/public
docker exec -d debifymod aptly serve

echo "######"
docker exec debifymod cat repo/go
echo "######"
echo "To install SONATA CLI tools run 'apt-get install sonata-cli'"

# restore address to local docker daemon
export DOCKER_HOST="unix:///var/run/docker.sock"

echo "-> Done."
