FROM ubuntu:14.04

ENV DEBIAN_FRONTEND noninteractive

ENV APTLY_ARCHITECTURES "i386,amd64"
ENV APTLY_DISTRIBUTION unstable
ENV APTLY_COMPONENT main
ENV KEYSERVER keyserver.ubuntu.com

ENV GNUPGHOME /.gnupg

# install aptly
RUN echo deb http://repo.aptly.info/ squeeze main >> /etc/apt/sources.list
RUN apt-key adv --keyserver keys.gnupg.net --recv-keys 9E3E53F19C7DE460
RUN apt-get update && \
    apt-get install -y unzip xz-utils aptly && \
    apt-get clean

ADD create_repo.sh /create_repo.sh

RUN unzip -o /gnupg-keys.zip -d /.gnupg
