FROM    centos:7

## install dependencies
RUN     yum groupinstall -y 'Development Tools' && \
        yum install -y epel-release && \
        yum install -y httpd createrepo

COPY    packages-centos7/* /var/www/html/repo/centos/7/
COPY    tools/distribute/rpmrepo/create_repo.sh /create_repo.sh
RUN     chmod 755 /create_repo.sh
