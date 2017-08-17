FROM    centos:7

## install dependencies
RUN     yum groupinstall -y 'Development Tools' && \
        yum install -y epel-release && \
        yum install -y git python34 python34-pip python34-devel \
        libpng-devel freetype-devel python34-scipy libgfortran atlas-devel \
        libffi-devel openssl-devel  ruby-devel gcc make rpm-build \
        rubygems libcurl-devel rpmrebuild

RUN     gem install --no-ri --no-rdoc fpm

RUN     pip3 install --upgrade pip setuptools \
        && pip3 install virtualenv

COPY    . /son-cli
COPY    tools/distribute/entrypoint-rpm.sh /sbin/entrypoint.sh
RUN     chmod 755 /sbin/entrypoint.sh

RUN     localedef -i en_US -f UTF-8 en_US.UTF-8

## set locale env vars pointing to utf8
ENV     LANG en_US.UTF-8
ENV     LANGUAGE en_US:en
ENV     LC_ALL en_US.UTF-8

WORKDIR /son-cli

ENTRYPOINT ["/sbin/entrypoint.sh"]
