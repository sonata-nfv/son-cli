#!/bin/bash

set -xe

virtualenv -p /usr/bin/python3.4 venv-son-cli
source venv-son-cli/bin/activate

# temp workaround for "ImportError: No module named 'numpy'"
pip install numpy

python setup.py egg_info
pip install `cat src/sonata_cli.egg-info/requires.txt`
packages=`pip freeze`
echo "$packages"

# do not convert inside virtualenv in order to obtain the "real" lib paths inside the rpm
deactivate

cd rpm-packages/

while read -r p; do
    echo "> $p"
    IFS='==' read -r -a sp <<< "$p"
    fpm -s python -t rpm --python-bin python3.4 --python-package-name-prefix python34 -v "${sp[2]}" "${sp[0]}"
done <<< "$packages"

fpm -s python -t rpm --python-bin python3.4 --no-python-fix-name --python-package-name-prefix python34 --depends python34-backports.ssl-match-hostname ../setup.py

# remove packages that exist in repository to avoid conflicts
rm -f python34-setuptools* python34-six python34-cffi* python34-chardet* \
      python34-dateutil* python34-decorator* python34-idna* python34-jinja2* python34-jsonschema* \
      python34-markupsafe* python34-numpy* python34-pycparser* python34-pytz* python34-requests-2* \
      python34-scipy* python34-urllib3* #python34-paramiko*


# fix incorrect package file names
rpmrebuild -p -n -d . --change-spec-preamble='sed -e "s/^Name:.*/Name:python34-websocket-client/"' python34-websocket_client*
rm -f python34-websocket_client*
mv noarch/python34-websocket-client* .

rpmrebuild -p -n -d . --change-spec-preamble='sed -e "s/^Name:.*/Name:python34-prometheus-client/"' python34-prometheus_client*
rm -f python34-prometheus_client*
mv noarch/python34-prometheus-client* .

rpmrebuild -p -n -d . --change-spec-preamble='sed -e "s/^Name:.*/Name:python34-backports.ssl-match-hostname/"' python34-backports.ssl_match_hostname*
rm -f python34-backports.ssl_match_hostname*
mv noarch/python34-backports.ssl-match-hostname* .

rm -fd noarch

# rpm -qRp python-sonata-cli-0.9-1.noarch.rpm
# fpm -s python -t rpm --no-python-fix-dependencies setup.py