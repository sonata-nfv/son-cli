#!/bin/bash
# This script creates the debian packages for son-cli and dependencies.
# For now, ubuntu 14.04 and ubuntu 16.04 are supported.
# This script is to be invoked at the root dir of "son-cli"

set -xe

echo "==== Build packages and instantiate debian repository ===="

export DOCKER_HOST="tcp://registry.sonata-nfv.eu:2375"

# ====== Build packages for ubuntu 14.04 ======
echo "--> Building packages for Ubuntu 14.04 LTS"

docker build -t ubuntu14.04.build-deb -f tools/distribute/ubuntu14.04.build-deb.Dockerfile .
mkdir -p packages-ubuntu14.04

docker rm -f ubuntu14.04.build-deb || true
docker run -i --name ubuntu14.04.build-deb \
    -v $(pwd)/packages-ubuntu14.04:/son-cli/deb-packages \
    ubuntu14.04.build-deb \
    py2deb -r deb-packages --name-prefix=python3 --no-name-prefix=sonata-cli .

## Patch to FIX conflicting versions of setuptools in Ubuntu 14.04
#docker rm -f tmp_ubuntu16.04 || true
#docker run -i --name tmp_ubuntu16.04 \
#    -v $(pwd)/packages-ubuntu14.04:/son-cli/deb-packages \
#    ubuntu16.04.build-deb \
#    /bin/bash -c "cd /son-cli/deb-packages; rm -f python3-setuptools*.deb; apt-get download python3-setuptools python3-pkg-resources"
## End of patch

# ====== Build packages for ubuntu 16.04 ======
echo "--> Building packages for Ubuntu 16.04 LTS"

docker build -t ubuntu16.04.build-deb -f tools/distribute/ubuntu16.04.build-deb.Dockerfile .
mkdir -p packages-ubuntu16.04

docker rm -f ubuntu16.04.build-deb || true
docker run -i --name ubuntu16.04.build-deb \
    -v $(pwd)/packages-ubuntu16.04:/son-cli/deb-packages \
    ubuntu16.04.build-deb \
    py2deb -r deb-packages --name-prefix=python3 --no-name-prefix=sonata-cli .

# rm -f deb-packages/python3-setuptools*.deb;" # no longer necessary!
# Patch to Fix conflicts in setuptools after packaging

# ====== Build docker image for debian repository and publish it to registry.sonata-nfv.eu ======
#docker build -t  -f tools/dist/debrepo/Dockerfile tools/dist/debrepo

docker build -t registry.sonata-nfv.eu:5000/son-cli-debrepo \
    -f tools/distribute/debrepo/Dockerfile \
    tools/distribute/debrepo

export DOCKER_HOST="tcp://registry.sonata-nfv.eu:2375"
docker login -u sonata-nfv -p s0n@t@ registry.sonata-nfv.eu:5000
docker push registry.sonata-nfv.eu:5000/son-cli-debrepo

# ====== Instantiate remote container for debian repository ======
echo "--> Creating debian repository container"

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
    -e URI=http://registry.sonata-nfv.eu:8080 \
    -e KEYSERVER=keyserver.ubuntu.com \
    -e APTLY_ARCHITECTURES="i386,amd64" \
    -v /home/sonata/son-cli-dist:/.gnupg \
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

export DOCKER_HOST="tcp://registry.sonata-nfv.eu:2375"
echo "-->Done."
