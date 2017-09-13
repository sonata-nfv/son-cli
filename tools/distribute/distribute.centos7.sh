#!/bin/bash

# ====== Build packages for CentOS 7 ======
echo "--> Building packages for CentOS 7"
docker build -t centos7.build-rpm -f tools/distribute/centos7.build-rpm.Dockerfile .
docker rm -f centos7.build-rpm || true
mkdir -p packages-centos7
docker run --name centos7.build-rpm -v $(pwd)/packages-centos7:/son-cli/rpm-packages centos7.build-rpm

# ====== Create repository ======
echo "--> Creating RPM repository"

docker build -t registry.sonata-nfv.eu:5000/son-cli-rpmrepo -f tools/distribute/rpmrepo/Dockerfile .

docker push registry.sonata-nfv.eu:5000/son-cli-rpmrepo

# set docker host to point to where the repo will be deployed
export RESTORE_DOCKER_HOST=$DOCKER_HOST
export DOCKER_HOST="tcp://registry.sonata-nfv.eu:2375"

docker login -u sonata-nfv -p s0n@t@ registry.sonata-nfv.eu:5000

docker pull registry.sonata-nfv.eu:5000/son-cli-rpmrepo

docker rm -f son-cli-rpmrepo || true
docker run -dit --name son-cli-rpmrepo --entrypoint=/bin/bash -p 8081:80 registry.sonata-nfv.eu:5000/son-cli-rpmrepo

docker exec -d son-cli-rpmrepo sh /create_repo.sh

export DOCKER_HOST=$RESTORE_DOCKER_HOST
echo "--> Done."

# [sonata-repo]
# name=SONATA Repository
# baseurl=http://rpmrepo.sonata-nfv.eu/repo/
# enabled=1
# gpgcheck=0
