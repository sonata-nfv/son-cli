#!/bin/bash
# This script creates the debian packages for son-cli and dependencies.
# For now, ubuntu 14.04 and ubuntu 16.04 are supported.
# This script is to be invoked at the root dir of "son-cli"

set -xe

echo "==== Build packages and instantiate debian repository ===="

export DOCKER_HOST="unix:///var/run/docker.sock"

# ====== Build packages for ubuntu 14.04 ======
echo "--> Building packages for Ubuntu 14.04 LTS"

docker build -t ubuntu14.04.build-deb -f tools/distribute/ubuntu14.04.build-deb.Dockerfile .
mkdir -p packages-ubuntu14.04

docker rm -f ubuntu14.04.build-deb || true
docker run -it --name ubuntu14.04.build-deb \
    -v $(pwd)/packages-ubuntu14.04:/son-cli/deb-packages \
    ubuntu14.04.build-deb \
    py2deb -r deb-packages --no-name-prefix=sonata-cli .


# ====== Build packages for ubuntu 16.04 ======




# ====== Build docker image for debian repository and publish it to registry.sonata-nfv.eu ======
#docker build -t  -f tools/dist/debrepo/Dockerfile tools/dist/debrepo

docker build -t registry.sonata-nfv.eu:5000/son-cli-debrepo \
    -f tools/distribute/debrepo/Dockerfile \
    tools/distribute/debrepo

export DOCKER_HOST="unix:///var/run/docker.sock"
echo DOCKER_OPTS=\"--insecure-registry registry.sonata-nfv.eu:5000 -H unix:///var/run/docker.sock -H tcp://0.0.0.0:2375\" | sudo tee /etc/default/docker
sudo service docker restart
docker login -u sonata-nfv -p s0n@t@ registry.sonata-nfv.eu:5000
docker push registry.sonata-nfv.eu:5000/son-cli-debrepo

# ====== Instantiate remote container for debian repository ======
echo "--> Creating debian repository container"

export DOCKER_HOST="tcp://registry.sonata-nfv.eu:2375"

# check if container is running and stop/remove it
CONTAINER="registry.sonata-nfv.eu:5000/son-cli-debrepo"
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

docker run --name=debrepo -dit \
    -e URI=http://registry.sonata-nfv.eu:8080 \
    -e KEYSERVER=keyserver.ubuntu.com \
    -e APTLY_ARCHITECTURES="i386,amd64" \
    --entrypoint=/bin/bash -p 8080:8080 registry.sonata-nfv.eu:5000/son-cli-debrepo


# ====== Copy generated debs to container and create repositories for each distro ======
docker cp packages-ubuntu14.04 registry.sonata-nfv.eu:5000/son-cli-debrepo:/
docker exec registry.sonata-nfv.eu:5000/son-cli-debrepo sh /create_repo.sh ubuntu14.04 main trusty /packages-ubuntu14.04


# ====== Start repository server ======
docker exec -d registry.sonata-nfv.eu:5000/son-cli-debrepo aptly serve


# ====== Print 'add repository' scripts
echo "______________________________________________________________"
docker exec registry.sonata-nfv.eu:5000/son-cli-debrepo cat /go
echo "______________________________________________________________"

export DOCKER_HOST="unix:///var/run/docker.sock"
echo "-->Done."
