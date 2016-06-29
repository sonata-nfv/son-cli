#!/bin/bash

# this script is to be run at root of "son-cli" dir

set -xe

# install py2deb tool
sudo apt-get update
sudo apt-get install -y python3-pip dpkg-dev fakeroot
pip3 install py2deb


# package project and dependencies into debs
mkdir -p sonata-dist-deb
py2deb -r sonata-dist-deb -- .

