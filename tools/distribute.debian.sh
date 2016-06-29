#!/bin/bash

# this script is to be run at root of "son-cli" dir

# install py2deb tool
pip3 install py2deb
sudo apt-get install -y dpkg-dev fakeroot

# package project and dependencies into debs
py2deb -r sonata-dist-deb -- .

