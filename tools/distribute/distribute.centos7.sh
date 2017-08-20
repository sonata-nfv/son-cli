#!/bin/bash

# ====== Build packages for CentOS 7 ======
echo "--> Building packages for CentOS 7"
docker build -t centos7.build-rpm -f tools/distribute/centos7.build-rpm.Dockerfile .
docker rm -f centos7.build-rpm || true
mkdir -p packages-centos7
docker run -it --name centos7.build-rpm -v $(pwd)/packages-centos7:/son-cli/rpm-packages centos7.build-rpm

# ====== Create repository ======
echo "--> Creating RPM repository_"

docker build -t registry.sonata-nfv.eu:5000/son-cli-rpmrepo -f tools/distribute/rpmrepo/Dockerfile .
docker push registry.sonata-nfv.eu:5000/son-cli-rpmrepo

# set docker host to point to where the repo will be deployed
export RESTORE_DOCKER_HOST=$DOCKER_HOST
export DOCKER_HOST="tcp://registry.sonata-nfv.eu:2375"

docker rm -f son-cli-rpmrepo || true
docker run -itd --name son-cli-rpmrepo -p 8081:80 registry.sonata-nfv.eu:5000/son-cli-rpmrepo

docker exec son-cli-rpmrepo sh /create_repo.sh

export DOCKER_HOST=$RESTORE_DOCKER_HOST
echo "--> Done."

# [sonata-repo]
# name=SONATA Repository
# baseurl=http://192.168.2.31/repo/
# enabled=1
# gpgcheck=0
