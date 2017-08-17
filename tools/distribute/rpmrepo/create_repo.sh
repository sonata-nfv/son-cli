#!/bin/bash

# disable firewalld (not really a security problem as this will run in a container)
#systemctl stop firewalld
#systemctl mask firewalld

# setup repository
createrepo /var/www/html/repo

# start apache
httpd -k start