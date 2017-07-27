#!/bin/bash
# This script creates the debian packages for son-cli and dependencies.
# For now, ubuntu 14.04 and ubuntu 16.04 are supported.
# This script is to be invoked at the root dir of "son-cli"

set -xe

echo "==== Build packages and instantiate debian repository ===="

# ====== Build packages for ubuntu 14.04 ======
echo "--> Building packages for Ubuntu 14.04 LTS"

docker build -t ubuntu14.04.build-deb -f tools/distribute/ubuntu14.04.build-deb.Dockerfile .
mkdir -p packages-ubuntu14.04

docker rm -f ubuntu14.04.build-deb || true
docker run -i --name ubuntu14.04.build-deb \
    -v $(pwd)/packages-ubuntu14.04:/son-cli/deb-packages \
    ubuntu14.04.build-deb

# ====== Build packages for ubuntu 16.04 ======
echo "--> Building packages for Ubuntu 16.04 LTS"

docker build -t ubuntu16.04.build-deb -f tools/distribute/ubuntu16.04.build-deb.Dockerfile .
mkdir -p packages-ubuntu16.04

docker rm -f ubuntu16.04.build-deb || true

## run container to build deb packages
## some packages don't support bdist, use debian package instead
docker run -i --name ubuntu16.04.build-deb \
    -v $(pwd)/packages-ubuntu16.04:/son-cli/deb-packages \
    ubuntu16.04.build-deb

# ====== Build docker image for debian repository and publish it to registry.sonata-nfv.eu ======
docker build -t registry.sonata-nfv.eu:5000/son-cli-debrepo \
    -f tools/distribute/debrepo/Dockerfile \
    tools/distribute/debrepo

docker push registry.sonata-nfv.eu:5000/son-cli-debrepo

# ====== Instantiate remote container for debian repository ======
echo "--> Creating debian repository container"

export RESTORE_DOCKER_HOST=$DOCKER_HOST
export DOCKER_HOST="tcp://registry.sonata-nfv.eu:2375"

# check if container is running and stop/remove it
CONTAINER="son-cli-debrepo"
RUNNING=$(docker inspect --format="{{ .State.Running }}" $CONTAINER 2> /dev/null) || true

if [ -z ${RUNNING} ]; then
  echo "'$CONTAINER' does not exist. Do nothing"

elif [ "$RUNNING" == "false" ]; then
  echo "'$CONTAINER' is not running. Just remove it."
  docker rm "$CONTAINER"

else
  echo "$CONTAINER is running. Stop and remove it."
  docker stop "$CONTAINER"
  docker rm "$CONTAINER"
fi

docker run --name=son-cli-debrepo -dit \
    -e URI=http://repo.sonata-nfv.eu \
    -e KEYSERVER=keyserver.ubuntu.com \
    -e APTLY_ARCHITECTURES="i386,amd64" \
    -v /home/sonata/son-cli-dist/.gnupg:/.gnupg \
    --entrypoint=/bin/bash -p 8080:8080 registry.sonata-nfv.eu:5000/son-cli-debrepo

# ====== Copy generated debs to container and create repositories for each distro ======
## ubuntu14.04
docker cp packages-ubuntu14.04 son-cli-debrepo:/
docker exec son-cli-debrepo sh /create_repo.sh ubuntu14.04 main ubuntu-trusty /packages-ubuntu14.04

## ubuntu16.04
docker cp packages-ubuntu16.04 son-cli-debrepo:/
docker exec son-cli-debrepo sh /create_repo.sh ubuntu16.04 main ubuntu-xenial /packages-ubuntu16.04


# ====== Start repository server ======
docker exec -d son-cli-debrepo aptly serve

# ====== Print 'add repository' scripts
echo "______________________________________________________________"
docker exec son-cli-debrepo cat /root/.aptly/public/go
echo "______________________________________________________________"

export DOCKER_HOST=$RESTORE_DOCKER_HOST
echo "-->Done."
